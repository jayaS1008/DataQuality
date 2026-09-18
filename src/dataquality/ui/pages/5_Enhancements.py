import streamlit as st

from dataquality import storage
from dataquality.graphs.enhancement import resume_enhancement, start_enhancement
from dataquality.ui.common import DB_PATH, ensure_db

ensure_db()
st.title("Enhancements")
st.caption("AI suggests a translation or rewrite; nothing is applied until a human approves it here.")

records = storage.list_records(DB_PATH)
if not records:
    st.info("No products stored yet - add one on the 'Add / Edit Product' page.")
    st.stop()

st.subheader("Request a suggestion")
by_key = {r.unique_key: r for r in records}
selected_key = st.selectbox("Product", list(by_key))
record = by_key[selected_key]
st.caption(f"Descriptions currently stored for: {list(record.descriptions.keys()) or '(none)'}")

task = st.radio("Task", ["translate", "rewrite"], horizontal=True)

if task == "translate":
    source_language = st.text_input("Source language code", value=next(iter(record.descriptions), "en"))
    target_language = st.text_input("Target language (e.g. Welsh, Scottish Gaelic, Hungarian)", value="Welsh")
    instructions = None
else:
    source_language = st.text_input("Language of text to rewrite", value=next(iter(record.descriptions), "en"))
    target_language = None
    instructions = st.text_area("Rewrite instructions", value="Make it clearer and more customer-friendly.")

if st.button("Generate suggestion (calls AI)", type="primary"):
    try:
        thread_id = start_enhancement(
            unique_key=selected_key,
            task=task,
            source_language=source_language,
            target_language=target_language,
            instructions=instructions,
            db_path=DB_PATH,
        )
        st.success(f"Suggestion generated (thread {thread_id}). See the review queue below.")
    except RuntimeError as exc:
        st.error(f"Could not generate a suggestion: {exc}")

st.divider()
st.subheader("Review queue")
pending = storage.list_pending_suggestions(DB_PATH)
if not pending:
    st.info("No pending suggestions.")
else:
    reviewer = st.text_input("Reviewing as", value="PM")
    for s in pending:
        with st.expander(f"#{s.id} - {s.unique_key} - {s.field} [{s.language}]"):
            st.markdown(f"**Old value:** {s.old_value or '(none)'}")
            edited = st.text_area("Suggested value (editable before approval)", value=s.new_value, key=f"val_{s.id}")
            st.caption(s.rationale or "")
            c1, c2 = st.columns(2)
            if c1.button("Approve", key=f"approve_{s.id}"):
                resume_enhancement(s.thread_id, "approve", reviewer, edited_value=edited, db_path=DB_PATH)
                st.rerun()
            if c2.button("Reject", key=f"reject_{s.id}"):
                resume_enhancement(s.thread_id, "reject", reviewer, db_path=DB_PATH)
                st.rerun()
