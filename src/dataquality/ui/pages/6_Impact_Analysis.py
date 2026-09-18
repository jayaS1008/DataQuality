import pandas as pd
import streamlit as st

from dataquality.derivation_rules import list_available
from dataquality.graphs.impact_analysis import build_graph
from dataquality.ui.common import DB_PATH, ensure_db

ensure_db()
st.title("Impact Analysis")
st.caption(
    "Pick the current derivation logic and a candidate, run both across the catalog, and see exactly "
    "which products would change and where. Logic versions live in dataquality/derivation_rules/ - "
    "add a new .py file there (with a compute(record) function) to test your own logic change."
)

available = list_available()
if len(available) < 2:
    st.warning("Need at least 2 logic versions in dataquality/derivation_rules/ to compare.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    current_logic = st.selectbox("Current logic", available, index=0)
with col2:
    candidate_logic = st.selectbox("Candidate logic", available, index=min(1, len(available) - 1))

if st.button("Run impact analysis", type="primary"):
    graph = build_graph()
    result = graph.invoke(
        {"db_path": DB_PATH, "current_logic": current_logic, "candidate_logic": candidate_logic}
    )
    st.session_state["impact_report"] = result["report"]

report = st.session_state.get("impact_report")
if report is None:
    st.info("Click 'Run impact analysis' to compare the two logic versions.")
    st.stop()

c1, c2 = st.columns(2)
c1.metric("Total products evaluated", report.total_products)
c2.metric("Products whose value would change", report.changed_count)

st.subheader("Changes by category")
if report.changed_by_category:
    st.bar_chart(pd.Series(report.changed_by_category, name="changed"))
else:
    st.success("No changes.")

st.subheader("Changes by active status")
if report.changed_by_active_status:
    st.dataframe(pd.Series(report.changed_by_active_status, name="changed").to_frame(), use_container_width=True)

st.subheader("Sample changed products")
if report.sample_changes:
    st.dataframe(pd.DataFrame(report.sample_changes), use_container_width=True)

st.subheader("Narrative")
st.write(report.narrative)
