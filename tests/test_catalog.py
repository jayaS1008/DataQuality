import json
from pathlib import Path

from dataquality.catalog import build_record
from dataquality.schemas import ProductAttributes, ProductMain, ProductSource

SAMPLE = json.loads((Path(__file__).resolve().parents[1] / "sample_data" / "sample_product.json").read_text())


def _build_sample_record():
    main = ProductMain.model_validate(SAMPLE["main"])
    source = ProductSource.model_validate(SAMPLE["source"])
    attributes = ProductAttributes.model_validate(SAMPLE["attributes"])
    return build_record(main, source, attributes)


def test_category_path_from_commercial_hierarchy():
    record = _build_sample_record()
    assert record.category_path == "Softlines > DS > DS > KIDS DS > KD GirlCloth"


def test_active_status_combines_rms_and_country():
    record = _build_sample_record()
    assert record.rms_approved is True
    assert record.any_country_live is True
    assert record.is_active is True
    assert record.active_status_disagreement is False


def test_active_status_disagreement_when_signals_conflict():
    main_doc = {**SAMPLE["main"], "rmsStatus": "Approved"}
    main_doc["country"] = [{**SAMPLE["main"]["country"][0], "deactivated": True}]
    main = ProductMain.model_validate(main_doc)
    source = ProductSource.model_validate(SAMPLE["source"])
    attributes = ProductAttributes.model_validate(SAMPLE["attributes"])
    record = build_record(main, source, attributes)

    assert record.rms_approved is True
    assert record.any_country_live is False
    assert record.is_active is False
    assert record.active_status_disagreement is True


def test_weak_attributes_flattened():
    record = _build_sample_record()
    assert record.weak_attributes["status.orderable"] == "yes"
    assert record.weak_attributes["global_identifiers.tariff_code"] == ""
    assert record.orderable is True
    assert record.sellable is True
