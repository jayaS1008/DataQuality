import json
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from dataquality import storage
from dataquality.ui.common import DB_PATH, ensure_db

ensure_db()
st.title("Add / Edit Product")

SAMPLE_PATH = Path(__file__).resolve().parents[3].parent / "sample_data" / "sample_product.json"

records = storage.list_records(DB_PATH)
existing_keys = [r.unique_key for r in records]

choice = st.selectbox("Load existing product (or start a new one)", ["New product"] + existing_keys)

default_unique_key = ""
default_main, default_source, default_attributes = "{}", "{}", "{}"

if choice != "New product":
    with storage.get_connection(DB_PATH) as conn:
        row = conn.execute("SELECT * FROM products WHERE unique_key = ?", (choice,)).fetchone()
    default_unique_key = choice
    default_main = json.dumps(json.loads(row["main_json"]), indent=2)
    default_source = json.dumps(json.loads(row["source_json"]), indent=2)
    default_attributes = json.dumps(json.loads(row["attributes_json"]), indent=2)

if st.button("Fill with sample data (Tesco example)") and SAMPLE_PATH.exists():
    sample = json.loads(SAMPLE_PATH.read_text())
    default_unique_key = sample["unique_key"]
    default_main = json.dumps(sample["main"], indent=2)
    default_source = json.dumps(sample["source"], indent=2)
    default_attributes = json.dumps(sample["attributes"], indent=2)

unique_key = st.text_input("unique_key (joins the 3 documents)", value=default_unique_key)

col1, col2, col3 = st.columns(3)
with col1:
    main_text = st.text_area("Doc 1: main (final attributes)", value=default_main, height=400)
with col2:
    source_text = st.text_area("Doc 2: source (provenance)", value=default_source, height=400)
with col3:
    attributes_text = st.text_area("Doc 3: weak attributes", value=default_attributes, height=400)

save_col, delete_col = st.columns(2)

with save_col:
    if st.button("Save product", type="primary"):
        if not unique_key.strip():
            st.error("unique_key is required.")
        else:
            try:
                main_doc = json.loads(main_text)
                source_doc = json.loads(source_text)
                attributes_doc = json.loads(attributes_text)
                storage.upsert_product(unique_key.strip(), main_doc, source_doc, attributes_doc, DB_PATH)
                st.success(f"Saved {unique_key}")
                st.rerun()
            except json.JSONDecodeError as exc:
                st.error(f"Invalid JSON: {exc}")
            except ValidationError as exc:
                st.error(f"Schema validation failed: {exc}")

with delete_col:
    if choice != "New product" and st.button("Delete this product"):
        storage.delete_product(choice, DB_PATH)
        st.success(f"Deleted {choice}")
        st.rerun()
