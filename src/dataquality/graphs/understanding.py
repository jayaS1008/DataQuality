"""Subgraph 1: "understand the data" - counts, categories, active/inactive,
missing fields, and a best-effort miscategorization flag.

Core profiling is pure Python (no LLM needed). Miscategorization detection uses
the LLM when configured and skips cleanly with a note otherwise, so the rest of
the report is always available.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from dataquality import storage
from dataquality.catalog import ProductRecord


@dataclass
class ProfileReport:
    total_products: int
    by_category: dict[str, int]
    by_active_status: dict[str, int]
    missing_category_count: int
    missing_brand_count: int
    missing_description_count: int
    possible_miscategorization: list[dict] | None = None
    miscategorization_note: str | None = None
    narrative: str | None = None


class UnderstandingState(TypedDict, total=False):
    db_path: str
    records: list[ProductRecord]
    report: ProfileReport


def load_catalog(state: UnderstandingState) -> UnderstandingState:
    records = storage.list_records(state.get("db_path", storage.DEFAULT_DB_PATH))
    return {"records": records}


def profile_dataset(state: UnderstandingState) -> UnderstandingState:
    records = state["records"]
    by_category = Counter(r.category_path or "(uncategorized)" for r in records)
    by_active = Counter("active" if r.is_active else "inactive" for r in records)
    missing_category = sum(
        1
        for r in records
        if any(
            not f
            for f in (r.division_name, r.department_name, r.section_name, r.class_name, r.subclass_name)
        )
    )
    missing_brand = sum(1 for r in records if not (r.brand or "").strip())
    missing_description = sum(1 for r in records if not (r.primary_description or "").strip())

    report = ProfileReport(
        total_products=len(records),
        by_category=dict(by_category),
        by_active_status=dict(by_active),
        missing_category_count=missing_category,
        missing_brand_count=missing_brand,
        missing_description_count=missing_description,
    )
    return {"report": report}


def flag_miscategorization(state: UnderstandingState) -> UnderstandingState:
    report = state["report"]
    records = state["records"]
    try:
        from dataquality.llm import get_llm

        llm = get_llm()
    except Exception as exc:  # noqa: BLE001 - any config/env issue just disables this step
        report.miscategorization_note = f"Skipped (LLM not available): {exc}"
        return {"report": report}

    from dataquality.llm import classify_category_mismatch

    flagged = []
    for r in records:
        if not r.primary_description or not r.category_path:
            continue
        result = classify_category_mismatch(llm, r.primary_description, r.category_path)
        if result.mismatched:
            flagged.append({"unique_key": r.unique_key, "reason": result.reason})
    report.possible_miscategorization = flagged
    return {"report": report}


def narrate(state: UnderstandingState) -> UnderstandingState:
    report = state["report"]
    lines = [
        f"{report.total_products} products total.",
        f"Category breakdown: {report.by_category}",
        f"Active/inactive: {report.by_active_status}",
        f"Missing category info: {report.missing_category_count}",
        f"Missing brand: {report.missing_brand_count}",
        f"Missing description: {report.missing_description_count}",
    ]
    if report.possible_miscategorization is not None:
        lines.append(f"Possible miscategorization flagged: {len(report.possible_miscategorization)}")
    elif report.miscategorization_note:
        lines.append(report.miscategorization_note)
    report.narrative = "\n".join(lines)
    return {"report": report}


def build_graph():
    graph = StateGraph(UnderstandingState)
    graph.add_node("load_catalog", load_catalog)
    graph.add_node("profile_dataset", profile_dataset)
    graph.add_node("flag_miscategorization", flag_miscategorization)
    graph.add_node("narrate", narrate)
    graph.add_edge(START, "load_catalog")
    graph.add_edge("load_catalog", "profile_dataset")
    graph.add_edge("profile_dataset", "flag_miscategorization")
    graph.add_edge("flag_miscategorization", "narrate")
    graph.add_edge("narrate", END)
    return graph.compile()
