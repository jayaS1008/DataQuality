"""Subgraph 3: data quality analysis. Runs the deterministic rule checks, scores
the dataset, and (if an LLM is configured) turns the scorecard into a short
prioritized narrative for a PM.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from dataquality import storage
from dataquality.catalog import ProductRecord
from dataquality.rules.dq_rules import DQScorecard, score_dataset


class DQState(TypedDict, total=False):
    db_path: str
    records: list[ProductRecord]
    scorecard: DQScorecard
    narrative: str | None


def load_catalog(state: DQState) -> DQState:
    records = storage.list_records(state.get("db_path", storage.DEFAULT_DB_PATH))
    return {"records": records}


def run_rule_checks(state: DQState) -> DQState:
    scorecard = score_dataset(state["records"])
    return {"scorecard": scorecard}


def explain(state: DQState) -> DQState:
    scorecard = state["scorecard"]
    try:
        from dataquality.llm import get_llm
    except Exception as exc:  # noqa: BLE001
        return {"narrative": f"(LLM narrative skipped: {exc})"}

    try:
        llm = get_llm()
    except Exception as exc:  # noqa: BLE001
        return {"narrative": f"(LLM narrative skipped: {exc})"}

    prompt = (
        "You are summarizing a product data-quality scorecard for a retail PM. "
        "Be concise (5 bullet points max), lead with the highest-impact issues, "
        "and reference category/active-status breakdowns where relevant.\n\n"
        f"Total products: {scorecard.total_products}\n"
        f"Products with at least one issue: {scorecard.products_with_issues}\n"
        f"Clean ratio: {scorecard.clean_ratio:.2%}\n"
        f"Issue counts: {scorecard.issue_counts}\n"
        f"Issues by category: {scorecard.issues_by_category}\n"
        f"Issues by active status: {scorecard.issues_by_active_status}\n"
    )
    response = llm.invoke(prompt)
    return {"narrative": response.content if hasattr(response, "content") else str(response)}


def build_graph():
    graph = StateGraph(DQState)
    graph.add_node("load_catalog", load_catalog)
    graph.add_node("run_rule_checks", run_rule_checks)
    graph.add_node("explain", explain)
    graph.add_edge(START, "load_catalog")
    graph.add_edge("load_catalog", "run_rule_checks")
    graph.add_edge("run_rule_checks", "explain")
    graph.add_edge("explain", END)
    return graph.compile()
