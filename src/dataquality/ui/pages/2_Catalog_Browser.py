import streamlit as st

from dataquality import storage
from dataquality.ui.common import DB_PATH, ensure_db

ensure_db()
st.title("Catalog Browser")

df = storage.to_dataframe(DB_PATH)
if df.empty:
    st.info("No products stored yet - add one on the 'Add / Edit Product' page.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    category_filter = st.multiselect("Filter by category", sorted(df["category_path"].dropna().unique()))
with col2:
    active_filter = st.multiselect("Filter by active status", ["active", "inactive"])

filtered = df.copy()
if category_filter:
    filtered = filtered[filtered["category_path"].isin(category_filter)]
if active_filter:
    filtered = filtered[filtered["is_active"].map(lambda v: "active" if v else "inactive").isin(active_filter)]

st.dataframe(filtered, use_container_width=True)
st.caption(f"{len(filtered)} of {len(df)} products shown")

st.divider()
st.subheader("Inspect a product")
selected = st.selectbox("unique_key", filtered["unique_key"].tolist() if not filtered.empty else [])
if selected:
    record = storage.get_product(selected, DB_PATH)
    left, right = st.columns(2)
    with left:
        st.markdown("**Derived fields**")
        st.json(record.model_dump(exclude={"raw_main", "raw_source", "raw_attributes"}))
    with right:
        st.markdown("**Raw documents**")
        tabs = st.tabs(["main", "source", "attributes"])
        for tab, key in zip(tabs, ["raw_main", "raw_source", "raw_attributes"]):
            with tab:
                st.json(getattr(record, key))
