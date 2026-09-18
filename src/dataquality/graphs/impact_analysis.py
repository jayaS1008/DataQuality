"""Subgraph 4: impact analysis. A PM picks two versions of derivation logic
(current vs candidate, from `dataquality.derivation_rules`), the graph runs
both against every stored product and diffs the results - exact, deterministic,
no LLM involved in the diff itself. Only the closing narrative is LLM-assisted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from dataquality import storage
from dataquality.catalog import ProductRecord
from dataquality.derivation_rules import load_logic


@dataclass
class ImpactReport:
    total_products: int
    changed_count: int
    changed_by_category: dict[str, int]
    changed_by_active_status: dict[str, int]
    sample_changes: list[dict[str, Any]] = field(default_factory=list)
    narrative: str | None = None


class ImpactState(TypedDict, total=False):
    db_path: str
    current_logic: str
    candidate_logic: str
    records: list[ProductRecord]
    diffs: list[dict[str, Any]]
    report: ImpactReport


def load_catalog(state: ImpactState) -> ImpactState:
    records = storage.list_records(state.get("db_path", storage.DEFAULT_DB_PATH))
    return {"records": records}


def compute_diff(state: ImpactState) -> ImpactState:
    current_fn = load_logic(state["current_logic"])
    candidate_fn = load_logic(state["candidate_logic"])

    diffs = []
    for r in state["records"]:
        old_value = current_fn(r)
        new_value = candidate_fn(r)
        diffs.append(
            {
                "unique_key": r.unique_key,
                "category_path": r.category_path or "(uncategorized)",
                "active_status": "active" if r.is_active else "inactive",
                "old_value": old_value,
                "new_value": new_value,
                "changed": old_value != new_value,
            }
        )
    return {"diffs": diffs}


def aggregate_impact(state: ImpactState) -> ImpactState:
    diffs = state["diffs"]
    changed = [d for d in diffs if d["changed"]]

    by_category: Counter[str] = Counter(d["category_path"] for d in changed)
    by_active: Counter[str] = Counter(d["active_status"] for d in changed)

    report = ImpactReport(
        total_products=len(diffs),
        changed_count=len(changed),
        changed_by_category=dict(by_category),
        changed_by_active_status=dict(by_active),
        sample_changes=changed[:20],
    )
    return {"report": report}


def narrate(state: ImpactState) -> ImpactState:
    report = state["report"]
    try:
        from dataquality.llm import get_llm

        llm = get_llm()
    except Exception as exc:  # noqa: BLE001
        report.narrative = f"(LLM narrative skipped: {exc})"
        return {"report": report}

    prompt = (
        "Summarize this impact-analysis result for a retail PM in 3-5 bullet points: "
        "what changing the derivation logic would affect and where the risk concentrates.\n\n"
        f"Total products evaluated: {report.total_products}\n"
        f"Products whose value would change: {report.changed_count}\n"
        f"Changes by category: {report.changed_by_category}\n"
        f"Changes by active status: {report.changed_by_active_status}\n"
    )
    response = llm.invoke(prompt)
    report.narrative = response.content if hasattr(response, "content") else str(response)
    return {"report": report}


def build_graph():
    graph = StateGraph(ImpactState)
    graph.add_node("load_catalog", load_catalog)
    graph.add_node("compute_diff", compute_diff)
    graph.add_node("aggregate_impact", aggregate_impact)
    graph.add_node("narrate", narrate)
    graph.add_edge(START, "load_catalog")
    graph.add_edge("load_catalog", "compute_diff")
    graph.add_edge("compute_diff", "aggregate_impact")
    graph.add_edge("aggregate_impact", "narrate")
    graph.add_edge("narrate", END)
    return graph.compile()
