"""Subgraph 2: AI-suggested description enhancement/translation with a human
approval gate.

The graph runs generation + a self-check up to `wait_for_human`, where it calls
LangGraph's `interrupt()` and pauses. A SqliteSaver checkpointer persists that
paused state under a `thread_id`, so a reviewer (via the Streamlit review queue)
can approve/edit/reject minutes or days later by resuming the same thread -
the process doesn't need to stay running in between.
"""

from __future__ import annotations

import uuid
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from dataquality import storage


class EnhancementState(TypedDict, total=False):
    db_path: str
    thread_id: str
    unique_key: str
    task: str  # "translate" | "rewrite"
    field: str  # "globalDescription" | "globalCustFriendlyDesc"
    source_language: str
    target_language: str | None  # required for task="translate"
    instructions: str | None  # required for task="rewrite"

    source_text: str
    old_value: str | None
    suggested_text: str
    rationale: str
    self_check_note: str
    suggestion_id: int

    # populated on resume, via Command(resume=...)
    decision: str  # "approve" | "reject"
    edited_value: str | None
    decided_by: str


def load_source_text(state: EnhancementState) -> EnhancementState:
    db_path = state.get("db_path", storage.DEFAULT_DB_PATH)
    record = storage.get_product(state["unique_key"], db_path)
    if record is None:
        raise ValueError(f"No product with unique_key={state['unique_key']!r}")

    source_language = state.get("source_language", "en")
    source_text = record.descriptions.get(source_language) or record.primary_description or ""

    if state["task"] == "translate":
        old_value = record.descriptions.get(state.get("target_language") or "")
    else:
        old_value = record.descriptions.get(source_language)

    return {"source_text": source_text, "old_value": old_value}


def generate_suggestion(state: EnhancementState) -> EnhancementState:
    from dataquality.llm import get_llm, suggest_description_rewrite, suggest_translation

    llm = get_llm()
    if state["task"] == "translate":
        result = suggest_translation(
            llm, state["source_text"], state["target_language"], state.get("source_language", "en")
        )
        return {
            "suggested_text": result.translated_text,
            "rationale": f"back-translation: {result.back_translation}",
        }
    result = suggest_description_rewrite(llm, state["source_text"], state.get("instructions") or "")
    return {"suggested_text": result.rewritten_text, "rationale": result.rationale}


def self_check(state: EnhancementState) -> EnhancementState:
    if state["task"] != "translate":
        return {"self_check_note": "n/a for rewrite task"}

    from dataquality.llm import check_meaning_preserved, get_llm

    back_translation = state["rationale"].removeprefix("back-translation: ")
    llm = get_llm()
    check = check_meaning_preserved(llm, state["source_text"], back_translation)
    note = f"similarity={check.similarity_score:.2f} preserved={check.preserved}"
    if check.concerns:
        note += f" concerns={check.concerns}"
    return {"self_check_note": note}


def persist_pending(state: EnhancementState) -> EnhancementState:
    field = state.get("field", "globalDescription")
    language = state.get("target_language") if state["task"] == "translate" else state.get("source_language", "en")
    suggestion_id = storage.add_suggestion(
        unique_key=state["unique_key"],
        field=field,
        new_value=state["suggested_text"],
        old_value=state.get("old_value"),
        language=language,
        rationale=f"{state.get('rationale', '')} | self-check: {state.get('self_check_note', '')}",
        thread_id=state.get("thread_id"),
        db_path=state.get("db_path", storage.DEFAULT_DB_PATH),
    )
    return {"suggestion_id": suggestion_id}


def wait_for_human(state: EnhancementState) -> EnhancementState:
    decision = interrupt(
        {
            "suggestion_id": state["suggestion_id"],
            "unique_key": state["unique_key"],
            "field": state.get("field"),
            "old_value": state.get("old_value"),
            "suggested_text": state["suggested_text"],
            "rationale": state.get("rationale"),
            "self_check_note": state.get("self_check_note"),
        }
    )
    return decision


def apply_decision(state: EnhancementState) -> EnhancementState:
    storage.decide_suggestion(
        suggestion_id=state["suggestion_id"],
        approve=state.get("decision") == "approve",
        decided_by=state.get("decided_by", "unknown"),
        edited_value=state.get("edited_value"),
        db_path=state.get("db_path", storage.DEFAULT_DB_PATH),
    )
    return {}


def build_graph(checkpointer=None):
    graph = StateGraph(EnhancementState)
    graph.add_node("load_source_text", load_source_text)
    graph.add_node("generate_suggestion", generate_suggestion)
    graph.add_node("self_check", self_check)
    graph.add_node("persist_pending", persist_pending)
    graph.add_node("wait_for_human", wait_for_human)
    graph.add_node("apply_decision", apply_decision)
    graph.add_edge(START, "load_source_text")
    graph.add_edge("load_source_text", "generate_suggestion")
    graph.add_edge("generate_suggestion", "self_check")
    graph.add_edge("self_check", "persist_pending")
    graph.add_edge("persist_pending", "wait_for_human")
    graph.add_edge("wait_for_human", "apply_decision")
    graph.add_edge("apply_decision", END)
    return graph.compile(checkpointer=checkpointer)


def _checkpoint_path(db_path: str) -> str:
    return f"{db_path}.checkpoints.sqlite"


def start_enhancement(
    unique_key: str,
    task: str,
    field: str = "globalDescription",
    source_language: str = "en",
    target_language: str | None = None,
    instructions: str | None = None,
    db_path: str = storage.DEFAULT_DB_PATH,
) -> str:
    """Run the graph up to the human-review interrupt. Returns the thread_id
    needed to resume it later (surfaced alongside the pending suggestion row)."""
    thread_id = f"enh-{uuid.uuid4().hex[:12]}"
    with SqliteSaver.from_conn_string(_checkpoint_path(db_path)) as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        graph.invoke(
            {
                "unique_key": unique_key,
                "task": task,
                "field": field,
                "source_language": source_language,
                "target_language": target_language,
                "instructions": instructions,
                "db_path": db_path,
                "thread_id": thread_id,
            },
            config={"configurable": {"thread_id": thread_id}},
        )
    return thread_id


def resume_enhancement(
    thread_id: str,
    decision: str,
    decided_by: str,
    edited_value: str | None = None,
    db_path: str = storage.DEFAULT_DB_PATH,
) -> None:
    """Resume a paused enhancement thread with a human decision."""
    with SqliteSaver.from_conn_string(_checkpoint_path(db_path)) as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        graph.invoke(
            Command(resume={"decision": decision, "decided_by": decided_by, "edited_value": edited_value}),
            config={"configurable": {"thread_id": thread_id}},
        )
