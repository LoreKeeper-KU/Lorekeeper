# Authored by Faris
"""LoreKeeper UI. Run it with:  streamlit run app.py

The page only calls generation_engine.orchestrator.run_pipeline() and displays the
PipelineResult it returns. It holds no generation, retrieval or verification logic, so it
works unchanged with the current mock pipeline and with the real modules once merged.
"""

import streamlit as st

from generation_engine.models import DemoRequest
from generation_engine.orchestrator import run_pipeline

st.set_page_config(page_title="LoreKeeper", page_icon="🛡️")

DEFAULT_CONCEPT = "Write a scene where Princess Amina defends her castle."

MODES = {
    "basic": "Basic: generate only",
    "rag": "RAG: retrieve canon, then generate",
    "verified": "Verified: generate, check and repair",
}

# Each classification gets its own colour and icon, so none relies on colour alone.
CLASSIFICATIONS = {
    "SUPPORTED": ("✅", "green"),
    "CONTRADICTION": ("❌", "red"),
    "VALID_NEW_ADDITION": ("➕", "blue"),
    "UNCERTAIN": ("❓", "orange"),
}

STATUSES = {
    "verified": ("Verified", "green"),
    "needs_review": ("Needs review", "orange"),
    "unverified": ("Unverified", "gray"),
    "error": ("Error", "red"),
}


def show_scene(scene):
    with st.container(border=True):
        st.markdown(scene.text)
    st.caption(f"Revision {scene.revision}")


def show_claim(assessment):
    icon, colour = CLASSIFICATIONS[assessment.classification.value]
    evidence = ", ".join(f"`{fact_id}`" for fact_id in assessment.evidence_fact_ids)
    with st.container(border=True):
        st.badge(assessment.classification.value, icon=icon, color=colour)
        st.markdown(f"**{assessment.claim}**")
        st.markdown(assessment.reason)
        st.markdown(f"Evidence fact IDs: {evidence or 'none cited'}")


def show_report(number, report):
    # Pass 1 checks the original scene; each later pass checks the scene after one more repair.
    where = "original scene" if number == 1 else f"after repair {number - 1}"
    st.markdown(f"#### Pass {number} ({where})")

    summary = report.summary
    counts = st.columns(4)
    counts[0].metric("Supported", summary.supported)
    counts[1].metric("New additions", summary.valid_new_additions)
    counts[2].metric("Contradictions", summary.contradictions)
    counts[3].metric("Uncertain", summary.uncertain)

    if not report.claims:
        st.caption("No claims were found in this pass.")
    for assessment in report.claims:
        show_claim(assessment)


def show_result(result):
    label, colour = STATUSES.get(result.status, (result.status, "gray"))
    status_column, repairs_column = st.columns(2)
    with status_column:
        st.caption("Pipeline status")
        st.badge(label, color=colour)
    repairs_column.metric("Repair attempts", result.repair_attempts)

    st.subheader("1. Original scene")
    show_scene(result.initial_scene)

    st.subheader("2. Continuity verification")
    if not result.reports:
        st.info("Verification was not run in this mode, so there are no claims to show.")
    for number, report in enumerate(result.reports, start=1):
        show_report(number, report)

    st.subheader("3. Final scene")
    show_scene(result.final_scene)


st.title("🛡️ LoreKeeper")
st.caption("Write a scene, then check it against your world's canon.")

concept = st.text_area("World / story concept", value=DEFAULT_CONCEPT, key="concept")
mode_column, repairs_column = st.columns(2)
mode = mode_column.selectbox(
    "Mode", list(MODES), index=2, format_func=MODES.get, key="mode"
)
max_repairs = repairs_column.slider(
    "Max repair attempts", 0, 5, 3, key="max_repairs", help="Only used in Verified mode."
)

if st.button("Run pipeline", type="primary", key="run"):
    if not concept.strip():
        st.warning("Enter a world or story concept first.")
    else:
        request = DemoRequest(
            prompt=concept.strip(), mode=mode, max_repair_attempts=max_repairs
        )
        st.session_state.pop("result", None)
        st.session_state.pop("error", None)
        with st.spinner("Running the LoreKeeper pipeline..."):
            try:
                st.session_state["result"] = run_pipeline(request)
            except Exception as error:  # show any pipeline failure instead of a stack trace
                st.session_state["error"] = f"{type(error).__name__}: {error}"

if "error" in st.session_state:
    st.error(f"The pipeline could not finish. {st.session_state['error']}")
if "result" in st.session_state:
    st.divider()
    show_result(st.session_state["result"])
