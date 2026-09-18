import pandas as pd
import streamlit as st

from dataquality.graphs.understanding import build_graph
from dataquality.ui.common import DB_PATH, ensure_db

ensure_db()
st.title("Understanding the Catalog")
st.caption("Counts, categories, active/inactive, and a best-effort miscategorization flag.")

if st.button("Run profiling", type="primary"):
    graph = build_graph()
    result = graph.invoke({"db_path": DB_PATH})
    st.session_state["profile_report"] = result["report"]

report = st.session_state.get("profile_report")
if report is None:
    st.info("Click 'Run profiling' to analyze the current catalog.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total products", report.total_products)
c2.metric("Active", report.by_active_status.get("active", 0))
c3.metric("Inactive", report.by_active_status.get("inactive", 0))
c4.metric("Missing category", report.missing_category_count)

st.subheader("By category")
if report.by_category:
    st.bar_chart(pd.Series(report.by_category, name="products"))

st.subheader("Missing fields")
st.write(
    {
        "missing_description": report.missing_description_count,
        "missing_brand": report.missing_brand_count,
        "missing_category": report.missing_category_count,
    }
)

st.subheader("Possible miscategorization")
if report.possible_miscategorization is not None:
    if report.possible_miscategorization:
        st.dataframe(pd.DataFrame(report.possible_miscategorization), use_container_width=True)
    else:
        st.success("No mismatches flagged by the LLM.")
else:
    st.info(report.miscategorization_note)

st.subheader("Narrative")
st.write(report.narrative)
