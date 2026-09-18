"""Thin LLM wrapper. All prompts/structured-output calls live here so the graphs
stay LLM-client-agnostic and the deterministic logic (profiling, DQ rules, impact
diffing) never depends on this module.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


def get_llm(model: str = "claude-sonnet-5", temperature: float = 0.0):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model, temperature=temperature)


class CategoryMismatchResult(BaseModel):
    mismatched: bool
    reason: str = ""


def classify_category_mismatch(llm, description: str, category_path: str) -> CategoryMismatchResult:
    structured = llm.with_structured_output(CategoryMismatchResult)
    prompt = (
        f"Product description: {description}\n"
        f"Assigned category path: {category_path}\n"
        "Does the description plausibly belong to this category? "
        "Set mismatched=true only if there is a clear disagreement, and give a short reason."
    )
    return structured.invoke(prompt)


class TranslationSuggestion(BaseModel):
    translated_text: str
    back_translation: str = Field(description="English back-translation of translated_text, for QA")


def suggest_translation(
    llm, source_text: str, target_language: str, source_language: str = "en"
) -> TranslationSuggestion:
    structured = llm.with_structured_output(TranslationSuggestion)
    prompt = (
        f"Translate the following product description from {source_language} to {target_language}, "
        "preserving meaning and tone exactly, suitable for retail product listings.\n\n"
        f"Text: {source_text}\n\n"
        "Also provide an English back-translation of your translated text, for QA purposes."
    )
    return structured.invoke(prompt)


class RewriteSuggestion(BaseModel):
    rewritten_text: str
    rationale: str


def suggest_description_rewrite(llm, source_text: str, instructions: str) -> RewriteSuggestion:
    structured = llm.with_structured_output(RewriteSuggestion)
    prompt = (
        "Improve this retail product description without changing its factual meaning.\n"
        f"Instructions: {instructions}\n\nOriginal: {source_text}"
    )
    return structured.invoke(prompt)


class MeaningPreservationCheck(BaseModel):
    preserved: bool
    similarity_score: float = Field(ge=0.0, le=1.0)
    concerns: str = ""


def check_meaning_preserved(llm, original: str, back_translation: str) -> MeaningPreservationCheck:
    structured = llm.with_structured_output(MeaningPreservationCheck)
    prompt = (
        "Compare these two texts for meaning preservation. The second is a back-translation "
        "of a translation of the first.\n\n"
        f"Original: {original}\n\nBack-translation: {back_translation}\n\n"
        "Score similarity_score from 0 (unrelated) to 1 (identical meaning). "
        "Set preserved=true only if similarity_score >= 0.85."
    )
    return structured.invoke(prompt)
