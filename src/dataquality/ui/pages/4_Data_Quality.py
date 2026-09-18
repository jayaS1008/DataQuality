import pandas as pd
import streamlit as st

from dataquality.graphs.dq_analysis import build_graph
from dataquality.ui.common import DB_PATH, ensure_db

ensure_db()
st.title("Data Quality Analysis")
st.caption("Deterministic rule checks - reproducible numbers a PM can act on.")

if st.button("Run DQ analysis", type="primary"):
    graph = build_graph()
    result = graph.invoke({"db_path": DB_PATH})
    st.session_state["dq_scorecard"] = result["scorecard"]
    st.session_state["dq_narrative"] = result["narrative"]

scorecard = st.session_state.get("dq_scorecard")
if scorecard is None:
    st.info("Click 'Run DQ analysis' to score the current catalog.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Total products", scorecard.total_products)
c2.metric("Products with issues", scorecard.products_with_issues)
c3.metric("Clean ratio", f"{scorecard.clean_ratio:.1%}")

st.subheader("Issues by type")
if scorecard.issue_counts:
    st.bar_chart(pd.Series(scorecard.issue_counts, name="count"))
else:
    st.success("No issues found.")

st.subheader("Issues by category")
if scorecard.issues_by_category:
    st.dataframe(pd.DataFrame(scorecard.issues_by_category).fillna(0).astype(int).T, use_container_width=True)

st.subheader("Issues by active status")
if scorecard.issues_by_active_status:
    st.dataframe(pd.DataFrame(scorecard.issues_by_active_status).fillna(0).astype(int).T, use_container_width=True)

st.subheader("Narrative")
st.write(st.session_state.get("dq_narrative"))
