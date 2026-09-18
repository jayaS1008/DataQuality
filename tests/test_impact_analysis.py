from dataquality import storage
from dataquality.derivation_rules import list_available, load_logic
from dataquality.graphs.impact_analysis import build_graph


def _minimal_main(unique_key, countries, rms_status="Approved"):
    return {
        "uniqueKey": unique_key,
        "rmsStatus": rms_status,
        "country": countries,
        "commercialHierarchy": {"divisionName": "Softlines"},
    }


def test_list_available_finds_both_versions():
    versions = list_available()
    assert "active_status_v1_any_country" in versions
    assert "active_status_v2_all_countries" in versions


def test_v1_vs_v2_diff_on_partially_live_product(tmp_path):
    db_path = str(tmp_path / "test.db")
    storage.init_db(db_path)

    # Fully live: agrees under both v1 (any) and v2 (all).
    storage.upsert_product(
        "fully-live",
        _minimal_main("fully-live", [{"code": "CZ", "authorised": True, "suspended": False, "deactivated": False}]),
        {},
        {},
        db_path,
    )
    # Partially live: v1 says active (at least one live country), v2 says inactive (not all live).
    storage.upsert_product(
        "partially-live",
        _minimal_main(
            "partially-live",
            [
                {"code": "CZ", "authorised": True, "suspended": False, "deactivated": False},
                {"code": "SK", "authorised": True, "suspended": False, "deactivated": True},
            ],
        ),
        {},
        {},
        db_path,
    )

    graph = build_graph()
    result = graph.invoke(
        {
            "db_path": db_path,
            "current_logic": "active_status_v1_any_country",
            "candidate_logic": "active_status_v2_all_countries",
        }
    )
    report = result["report"]

    assert report.total_products == 2
    assert report.changed_count == 1
    changed_keys = {d["unique_key"] for d in result["diffs"] if d["changed"]}
    assert changed_keys == {"partially-live"}


def test_logic_functions_directly():
    v1 = load_logic("active_status_v1_any_country")
    v2 = load_logic("active_status_v2_all_countries")

    from dataquality.catalog import build_record
    from dataquality.schemas import ProductAttributes, ProductMain, ProductSource

    main = ProductMain.model_validate(
        _minimal_main(
            "x",
            [
                {"code": "CZ", "authorised": True, "suspended": False, "deactivated": False},
                {"code": "SK", "authorised": True, "suspended": False, "deactivated": True},
            ],
        )
    )
    record = build_record(main, ProductSource.model_validate({}), ProductAttributes.model_validate({}))
    assert v1(record) is True
    assert v2(record) is False
