import json
from pathlib import Path

from dataquality.catalog import build_record
from dataquality.rules.dq_rules import run_checks, score_dataset
from dataquality.schemas import ProductAttributes, ProductMain, ProductSource

SAMPLE = json.loads((Path(__file__).resolve().parents[1] / "sample_data" / "sample_product.json").read_text())


def _record_from(main_overrides=None, attributes_overrides=None):
    main_doc = {**SAMPLE["main"], **(main_overrides or {})}
    attributes_doc = attributes_overrides if attributes_overrides is not None else SAMPLE["attributes"]
    main = ProductMain.model_validate(main_doc)
    source = ProductSource.model_validate(SAMPLE["source"])
    attributes = ProductAttributes.model_validate(attributes_doc)
    return build_record(main, source, attributes)


def test_sample_product_flags_low_completeness_and_missing_tariff_code():
    record = _record_from()
    codes = {issue.code for issue in run_checks(record)}
    assert codes == {"low_completeness", "missing_tariff_code"}


def test_missing_description_and_brand_are_flagged():
    record = _record_from(main_overrides={"description": "", "brand": "", "globalDescription": {"values": []}})
    codes = {issue.code for issue in run_checks(record)}
    assert "missing_description" in codes
    assert "missing_brand" in codes


def test_no_countries_flagged():
    record = _record_from(main_overrides={"country": [], "countries": []})
    codes = {issue.code for issue in run_checks(record)}
    assert "no_countries" in codes
    assert "active_status_disagreement" in codes  # rmsStatus Approved but no live country


def test_score_dataset_aggregates_by_category_and_active_status():
    clean = _record_from(
        main_overrides={"completeness": 10},
        attributes_overrides={
            "productAttributes": [
                {
                    "source": "RMS",
                    "common": {
                        "global_identifiers": {"tariff_code": {"name": "tariff code", "value": "12345"}},
                        "status": {
                            "orderable": {"name": "orderable", "value": "yes"},
                            "sellable": {"name": "sellable", "value": "yes"},
                        },
                    },
                }
            ]
        },
    )
    dirty = _record_from()

    scorecard = score_dataset([clean, dirty])
    assert scorecard.total_products == 2
    assert scorecard.products_with_issues == 1
    assert scorecard.clean_ratio == 0.5
    assert scorecard.issue_counts["missing_tariff_code"] == 1
    assert dirty.category_path in scorecard.issues_by_category
    assert "active" in scorecard.issues_by_active_status
