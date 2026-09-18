"""Top-level intent router.

The Streamlit UI calls each subgraph directly from its own page, so this module
is deliberately thin: it exists for a future free-text entrypoint (e.g. a chat
box) that needs to classify a PM's request into one of the four workflows
before dispatching to the matching subgraph.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Intent = Literal["understand", "enhance", "dq_analysis", "impact_analysis"]

INTENT_DESCRIPTIONS = {
    "understand": "Profile/explore the catalog: counts, categories, active vs inactive.",
    "enhance": "AI-suggested description rewrite or translation, pending human approval.",
    "dq_analysis": "Run the data-quality rule checks and scorecard.",
    "impact_analysis": "Simulate a derivation-logic change and diff its effect across the catalog.",
}


class _Routed(BaseModel):
    intent: Intent


def route_intent(user_message: str) -> Intent:
    from dataquality.llm import get_llm

    llm = get_llm()
    structured = llm.with_structured_output(_Routed)
    options = "\n".join(f"- {k}: {v}" for k, v in INTENT_DESCRIPTIONS.items())
    prompt = f"Classify the PM's request into exactly one workflow:\n{options}\n\nRequest: {user_message}"
    return structured.invoke(prompt).intent
