import os

import streamlit as st

from dataquality.ui.common import DB_PATH, ensure_db

st.set_page_config(page_title="Product Data Quality Copilot", page_icon="🧭", layout="wide")
ensure_db()

st.title("Product Data Quality Copilot")
st.caption("LangGraph-based catalog understanding, AI-assisted enhancement, DQ analysis, and impact analysis.")

st.markdown(
    f"""
Use the pages in the sidebar:

1. **Add / Edit Product** - enter a product's 3 documents (main, source, weak attributes).
2. **Catalog Browser** - see everything currently stored.
3. **Understanding** - counts, categories, active/inactive, possible miscategorization.
4. **Data Quality** - deterministic rule checks + scorecard.
5. **Enhancements** - request AI translation/rewrite suggestions and approve/reject them.
6. **Impact Analysis** - simulate a derivation-logic change and see who it affects.

Storage: `{DB_PATH}` (SQLite - no external data source; this app is the system of record).
"""
)

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.warning(
        "ANTHROPIC_API_KEY is not set. Catalog browsing, DQ analysis, and impact-analysis diffing all still "
        "work (they're deterministic), but AI-assisted steps (enhancement suggestions, miscategorization "
        "flagging, narratives) will be skipped until it's configured."
    )
