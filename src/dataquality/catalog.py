"""Merges the 3 raw product documents into one analysis-friendly ProductRecord."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from dataquality.schemas import ProductAttributes, ProductMain, ProductSource


class ProductRecord(BaseModel):
    """Flattened, derived view of a product used by every subgraph."""

    unique_key: str
    item_number: str | None
    brand: str | None
    is_own_label: bool

    category_path: str
    division_name: str | None
    department_name: str | None
    section_name: str | None
    class_name: str | None
    subclass_name: str | None

    primary_description: str | None
    descriptions: dict[str, str | None]  # language -> globalDescription text

    rms_status: str | None
    countries: list[dict[str, Any]]
    any_country_live: bool
    rms_approved: bool
    is_active: bool
    active_status_disagreement: bool

    completeness: int | None
    weak_attributes: dict[str, Any]
    orderable: bool | None
    sellable: bool | None

    raw_main: dict[str, Any] = Field(repr=False)
    raw_source: dict[str, Any] = Field(repr=False)
    raw_attributes: dict[str, Any] = Field(repr=False)


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("yes", "true", "1")
    return bool(value)


def build_record(main: ProductMain, source: ProductSource, attributes: ProductAttributes) -> ProductRecord:
    """Combine the 3 docs into a single ProductRecord with derived DQ-relevant fields.

    Active status is a deliberate combination of two signals (per product decision):
    rmsStatus == "Approved" AND at least one country is live (authorised, not
    suspended/deactivated). When the two disagree, `active_status_disagreement`
    is set so it surfaces as its own data-quality issue rather than being silently
    resolved one way or the other.
    """
    rms_approved = (main.rmsStatus or "").strip().lower() == "approved"
    any_country_live = any(c.is_live for c in main.country)
    is_active = rms_approved and any_country_live
    disagreement = rms_approved != any_country_live

    weak_attrs = attributes.flatten()

    hierarchy = main.commercialHierarchy
    descriptions = {v.language: v.value for v in main.globalDescription.values}

    return ProductRecord(
        unique_key=main.uniqueKey,
        item_number=main.itemNumber,
        brand=main.brand,
        is_own_label=main.isOwnLabel,
        category_path=hierarchy.path(),
        division_name=hierarchy.divisionName,
        department_name=hierarchy.departmentName,
        section_name=hierarchy.sectionName,
        class_name=hierarchy.className,
        subclass_name=hierarchy.subclassName,
        primary_description=main.description,
        descriptions=descriptions,
        rms_status=main.rmsStatus,
        countries=[c.model_dump() for c in main.country],
        any_country_live=any_country_live,
        rms_approved=rms_approved,
        is_active=is_active,
        active_status_disagreement=disagreement,
        completeness=main.completeness,
        weak_attributes=weak_attrs,
        orderable=_as_bool(weak_attrs.get("status.orderable")),
        sellable=_as_bool(weak_attrs.get("status.sellable")),
        raw_main=main.model_dump(),
        raw_source=source.model_dump(),
        raw_attributes=attributes.model_dump(),
    )
