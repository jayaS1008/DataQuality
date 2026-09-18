"""Deterministic data-quality rules. No LLM involved - these numbers must be exact
and reproducible, since PMs act on them directly.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from dataquality.catalog import ProductRecord

# `completeness` in the source data is a small integer with no documented max seen
# in the sample; until a real scale is confirmed, anything below this is flagged
# as low so the check isn't silently a no-op.
LOW_COMPLETENESS_THRESHOLD = 5


@dataclass(frozen=True)
class DQIssue:
    code: str
    severity: str  # "critical" | "warning"
    message: str


RuleFn = "Callable[[ProductRecord], DQIssue | None]"


def _missing_description(r: ProductRecord) -> DQIssue | None:
    if not (r.primary_description or "").strip():
        return DQIssue("missing_description", "critical", "No primary description")
    return None


def _missing_category(r: ProductRecord) -> DQIssue | None:
    fields = [r.division_name, r.department_name, r.section_name, r.class_name, r.subclass_name]
    if any(not f for f in fields):
        return DQIssue("missing_category", "critical", "Commercial hierarchy incomplete")
    return None


def _missing_brand(r: ProductRecord) -> DQIssue | None:
    if not (r.brand or "").strip():
        return DQIssue("missing_brand", "warning", "No brand set")
    return None


def _no_countries(r: ProductRecord) -> DQIssue | None:
    if not r.countries:
        return DQIssue("no_countries", "critical", "No country listings at all")
    return None


def _active_status_disagreement(r: ProductRecord) -> DQIssue | None:
    if r.active_status_disagreement:
        return DQIssue(
            "active_status_disagreement",
            "warning",
            f"rmsStatus approved={r.rms_approved} but any_country_live={r.any_country_live}",
        )
    return None


def _low_completeness(r: ProductRecord) -> DQIssue | None:
    if r.completeness is None:
        return DQIssue("missing_completeness", "warning", "No completeness score")
    if r.completeness < LOW_COMPLETENESS_THRESHOLD:
        return DQIssue("low_completeness", "warning", f"completeness={r.completeness}")
    return None


def _missing_tariff_code(r: ProductRecord) -> DQIssue | None:
    tariff = r.weak_attributes.get("global_identifiers.tariff_code")
    is_empty = not tariff.strip() if isinstance(tariff, str) else not tariff
    if is_empty:
        return DQIssue("missing_tariff_code", "warning", "global_identifiers.tariff_code is empty")
    return None


def _orderable_sellable_mismatch(r: ProductRecord) -> DQIssue | None:
    if r.orderable is not None and r.sellable is not None and r.orderable != r.sellable:
        return DQIssue(
            "orderable_sellable_mismatch",
            "warning",
            f"orderable={r.orderable} sellable={r.sellable}",
        )
    return None


RULES: list = [
    _missing_description,
    _missing_category,
    _missing_brand,
    _no_countries,
    _active_status_disagreement,
    _low_completeness,
    _missing_tariff_code,
    _orderable_sellable_mismatch,
]


def run_checks(record: ProductRecord) -> list[DQIssue]:
    return [issue for rule in RULES for issue in [rule(record)] if issue is not None]


@dataclass
class DQScorecard:
    total_products: int
    products_with_issues: int
    clean_ratio: float
    issue_counts: dict[str, int]
    issues_by_category: dict[str, dict[str, int]]
    issues_by_active_status: dict[str, dict[str, int]]


def score_dataset(records: list[ProductRecord]) -> DQScorecard:
    issue_counts: Counter[str] = Counter()
    issues_by_category: dict[str, Counter[str]] = {}
    issues_by_active_status: dict[str, Counter[str]] = {}
    products_with_issues = 0

    for r in records:
        issues = run_checks(r)
        if issues:
            products_with_issues += 1
        active_key = "active" if r.is_active else "inactive"
        for issue in issues:
            issue_counts[issue.code] += 1
            issues_by_category.setdefault(r.category_path or "(uncategorized)", Counter())[issue.code] += 1
            issues_by_active_status.setdefault(active_key, Counter())[issue.code] += 1

    total = len(records)
    clean_ratio = (total - products_with_issues) / total if total else 1.0

    return DQScorecard(
        total_products=total,
        products_with_issues=products_with_issues,
        clean_ratio=clean_ratio,
        issue_counts=dict(issue_counts),
        issues_by_category={k: dict(v) for k, v in issues_by_category.items()},
        issues_by_active_status={k: dict(v) for k, v in issues_by_active_status.items()},
    )
