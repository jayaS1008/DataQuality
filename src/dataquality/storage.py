"""SQLite persistence: the 3 raw docs per product, plus the AI-suggestion audit log.

This is the system of record - there is no external feed. Products are entered
through the UI (or `upsert_product` directly) as the 3 JSON documents shown in
the source data, keyed by `unique_key`.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

import pandas as pd

from dataquality.catalog import ProductRecord, build_record
from dataquality.schemas import ProductAttributes, ProductMain, ProductSource

DEFAULT_DB_PATH = os.environ.get("DATAQUALITY_DB_PATH", "dataquality.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    unique_key TEXT PRIMARY KEY,
    main_json TEXT NOT NULL,
    source_json TEXT NOT NULL,
    attributes_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unique_key TEXT NOT NULL,
    field TEXT NOT NULL,
    language TEXT,
    old_value TEXT,
    new_value TEXT,
    rationale TEXT,
    thread_id TEXT,
    suggested_by TEXT NOT NULL DEFAULT 'ai',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by TEXT,
    FOREIGN KEY (unique_key) REFERENCES products(unique_key)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_connection(db_path: str = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def upsert_product(
    unique_key: str,
    main_doc: dict[str, Any],
    source_doc: dict[str, Any],
    attributes_doc: dict[str, Any],
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Validate the 3 docs against their schemas and store them."""
    main_doc = {**main_doc, "uniqueKey": unique_key}
    ProductMain.model_validate(main_doc)
    ProductSource.model_validate(source_doc)
    ProductAttributes.model_validate(attributes_doc)

    now = _now()
    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT created_at FROM products WHERE unique_key = ?", (unique_key,)
        ).fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO products (unique_key, main_json, source_json, attributes_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(unique_key) DO UPDATE SET
                main_json = excluded.main_json,
                source_json = excluded.source_json,
                attributes_json = excluded.attributes_json,
                updated_at = excluded.updated_at
            """,
            (
                unique_key,
                json.dumps(main_doc),
                json.dumps(source_doc),
                json.dumps(attributes_doc),
                created_at,
                now,
            ),
        )
        conn.commit()


def delete_product(unique_key: str, db_path: str = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM products WHERE unique_key = ?", (unique_key,))
        conn.execute("DELETE FROM audit_log WHERE unique_key = ?", (unique_key,))
        conn.commit()


def _row_to_record(row: sqlite3.Row) -> ProductRecord:
    main = ProductMain.model_validate(json.loads(row["main_json"]))
    source = ProductSource.model_validate(json.loads(row["source_json"]))
    attributes = ProductAttributes.model_validate(json.loads(row["attributes_json"]))
    return build_record(main, source, attributes)


def get_product(unique_key: str, db_path: str = DEFAULT_DB_PATH) -> ProductRecord | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM products WHERE unique_key = ?", (unique_key,)
        ).fetchone()
        return _row_to_record(row) if row else None


def list_records(db_path: str = DEFAULT_DB_PATH) -> list[ProductRecord]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM products").fetchall()
        return [_row_to_record(r) for r in rows]


def to_dataframe(db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Flat DataFrame of the derived record fields, for profiling/DQ/impact analysis."""
    records = list_records(db_path)
    if not records:
        return pd.DataFrame(
            columns=[
                "unique_key", "item_number", "brand", "is_own_label", "category_path",
                "division_name", "department_name", "section_name", "class_name",
                "subclass_name", "primary_description", "rms_status", "any_country_live",
                "rms_approved", "is_active", "active_status_disagreement", "completeness",
                "orderable", "sellable",
            ]
        )
    rows = [
        {
            "unique_key": r.unique_key,
            "item_number": r.item_number,
            "brand": r.brand,
            "is_own_label": r.is_own_label,
            "category_path": r.category_path,
            "division_name": r.division_name,
            "department_name": r.department_name,
            "section_name": r.section_name,
            "class_name": r.class_name,
            "subclass_name": r.subclass_name,
            "primary_description": r.primary_description,
            "rms_status": r.rms_status,
            "any_country_live": r.any_country_live,
            "rms_approved": r.rms_approved,
            "is_active": r.is_active,
            "active_status_disagreement": r.active_status_disagreement,
            "completeness": r.completeness,
            "orderable": r.orderable,
            "sellable": r.sellable,
        }
        for r in records
    ]
    return pd.DataFrame(rows)


@dataclass
class Suggestion:
    id: int
    unique_key: str
    field: str
    language: str | None
    old_value: str | None
    new_value: str | None
    rationale: str | None
    thread_id: str | None
    status: str
    created_at: str


def add_suggestion(
    unique_key: str,
    field: str,
    new_value: str,
    old_value: str | None = None,
    language: str | None = None,
    rationale: str | None = None,
    thread_id: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO audit_log (unique_key, field, language, old_value, new_value, rationale, thread_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (unique_key, field, language, old_value, new_value, rationale, thread_id, _now()),
        )
        conn.commit()
        return cur.lastrowid


def list_pending_suggestions(db_path: str = DEFAULT_DB_PATH) -> list[Suggestion]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()
        return [
            Suggestion(
                id=r["id"], unique_key=r["unique_key"], field=r["field"],
                language=r["language"], old_value=r["old_value"], new_value=r["new_value"],
                rationale=r["rationale"], thread_id=r["thread_id"], status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


def decide_suggestion(
    suggestion_id: int,
    approve: bool,
    decided_by: str,
    edited_value: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Approve/reject a pending suggestion. If approved, applies it to the product's
    globalDescription (or globalCustFriendlyDesc) values for the given language."""
    status = "approved" if approve else "rejected"
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (suggestion_id,)).fetchone()
        if row is None:
            raise ValueError(f"No suggestion with id {suggestion_id}")
        final_value = edited_value if edited_value is not None else row["new_value"]
        conn.execute(
            """
            UPDATE audit_log SET status = ?, decided_at = ?, decided_by = ?, new_value = ?
            WHERE id = ?
            """,
            (status, _now(), decided_by, final_value, suggestion_id),
        )
        conn.commit()

    if approve:
        _apply_suggestion_to_product(row["unique_key"], row["field"], row["language"], final_value, db_path)


def _apply_suggestion_to_product(
    unique_key: str, field: str, language: str | None, new_value: str, db_path: str
) -> None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT main_json FROM products WHERE unique_key = ?", (unique_key,)).fetchone()
        if row is None:
            return
        main_doc = json.loads(row["main_json"])
        localized = main_doc.setdefault(field, {"values": []})
        values = localized.setdefault("values", [])
        for v in values:
            if v.get("language") == language:
                v["value"] = new_value
                break
        else:
            values.append({"language": language, "value": new_value})
        conn.execute(
            "UPDATE products SET main_json = ?, updated_at = ? WHERE unique_key = ?",
            (json.dumps(main_doc), _now(), unique_key),
        )
        conn.commit()
