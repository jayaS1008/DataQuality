"""Pydantic models for the three raw product documents.

Doc 1 (ProductMain)       -> final/resolved attributes, one record per product.
Doc 2 (ProductSource)     -> provenance: same fields, tagged by originating source system.
Doc 3 (ProductAttributes) -> "weak"/long-tail attributes, grouped and named.

These mirror the real Tesco-style payloads as given, not a redesign of them.
Unknown/extra fields (e.g. per-country flags like CZFlag, HUFlag) are preserved
via `extra="allow"` rather than enumerated, since the set of countries varies.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LocalizedValue(BaseModel):
    model_config = ConfigDict(extra="allow")

    language: str
    value: Any = None


class LocalizedField(BaseModel):
    """Wrapper shape used for globalDescription, globalBrand, globalQtyContents, etc."""

    model_config = ConfigDict(extra="allow")

    values: list[LocalizedValue] = Field(default_factory=list)

    def text(self, language: str | None = None) -> str | None:
        """Return the value for a language, or the first available value."""
        for v in self.values:
            if language is None or v.language == language:
                return v.value
        return None

    def languages(self) -> list[str]:
        return [v.language for v in self.values]


class DescriptionLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    lineNo: int
    description: str = ""


class CountryStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str
    custFriendlyDesc: str | None = None
    authorised: bool = False
    suspended: bool = False
    deactivated: bool = False
    epw: bool = False
    status: str | None = None

    @property
    def is_live(self) -> bool:
        return self.authorised and not self.suspended and not self.deactivated


class CommercialHierarchy(BaseModel):
    model_config = ConfigDict(extra="allow")

    divisionCode: str | None = None
    divisionNumber: int | None = None
    divisionName: str | None = None
    departmentCode: str | None = None
    departmentNumber: int | None = None
    departmentName: str | None = None
    sectionCode: str | None = None
    sectionNumber: int | None = None
    sectionName: str | None = None
    classCode: str | None = None
    classNumber: int | None = None
    className: str | None = None
    subclassCode: str | None = None
    subclassNumber: int | None = None
    subclassName: str | None = None
    source: str | None = None  # present in doc 2's commercialHierarchyInfo entries

    def path(self) -> str:
        parts = [self.divisionName, self.departmentName, self.sectionName, self.className, self.subclassName]
        return " > ".join(p for p in parts if p)


class ProductCharacteristics(BaseModel):
    model_config = ConfigDict(extra="allow")

    isFood: bool = False
    isDrink: bool = False
    storageType: str | None = None


class ProductMain(BaseModel):
    """Doc 1: main/resolved product document."""

    model_config = ConfigDict(extra="allow")

    uniqueKey: str
    gtin: str | None = None
    printedGtin: str | None = None
    gtinType: str | None = None
    tpnb: str | None = None
    tpnc: str | None = None
    tpna: str | None = None
    globalDescription: LocalizedField = Field(default_factory=LocalizedField)
    globalCustFriendlyDesc: LocalizedField = Field(default_factory=LocalizedField)
    tpnaGlobalDescription: LocalizedField = Field(default_factory=LocalizedField)
    createdDate: str | None = None
    itemNumber: str | None = None
    description: str | None = None
    brand: str | None = None
    isOwnLabel: bool = False
    country: list[CountryStatus] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    tillDescription: str | None = None
    selDescription: list[DescriptionLine] = Field(default_factory=list)
    baseDescription: list[DescriptionLine] = Field(default_factory=list)
    commercialHierarchy: CommercialHierarchy = Field(default_factory=CommercialHierarchy)
    rmsStatus: str | None = None
    drainedIndicator: bool = False
    productCharacteristics: ProductCharacteristics = Field(default_factory=ProductCharacteristics)
    lastModifiedTime: str | None = None
    completeness: int | None = None
    globalBrand: LocalizedField = Field(default_factory=LocalizedField)
    globalQtyContents: LocalizedField = Field(default_factory=LocalizedField)
    updatedNumber: int | None = None


class SourceInfoEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str | None = None


class ProductSource(BaseModel):
    """Doc 2: per-field provenance across source systems (RMS, etc.)."""

    model_config = ConfigDict(extra="allow")

    brandInfo: list[dict[str, Any]] = Field(default_factory=list)
    commercialHierarchyInfo: list[dict[str, Any]] = Field(default_factory=list)
    qtyContentsInfo: list[dict[str, Any]] = Field(default_factory=list)
    globalBrandInfo: list[dict[str, Any]] = Field(default_factory=list)
    globalQtyContentsInfo: list[dict[str, Any]] = Field(default_factory=list)
    globalDescriptionInfo: list[dict[str, Any]] = Field(default_factory=list)
    gtinTypeInfo: list[dict[str, Any]] = Field(default_factory=list)


class AttributeValue(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    value: Any = None


class AttributeSourceBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str | None = None
    common: dict[str, dict[str, AttributeValue]] = Field(default_factory=dict)


class ProductAttributes(BaseModel):
    """Doc 3: weak/long-tail attributes, grouped by domain (merchandising_details, status, ...)."""

    model_config = ConfigDict(extra="allow")

    productAttributes: list[AttributeSourceBlock] = Field(default_factory=list)
    extnUpdatedNumber: int | None = None
    lastModifiedTime: str | None = None

    def flatten(self) -> dict[str, Any]:
        """Flatten all groups/attributes into a single {group.attr: value} dict."""
        flat: dict[str, Any] = {}
        for block in self.productAttributes:
            for group_name, attrs in block.common.items():
                for attr_key, attr in attrs.items():
                    flat[f"{group_name}.{attr_key}"] = attr.value
        return flat
