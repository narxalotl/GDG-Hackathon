import os
import shutil
import tempfile
from datetime import date

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
import report
from pipeline import compare_photos, PipelineError, MODEL   # the real AI function

# Page Configuration & Clean Theme
st.set_page_config(
    page_title="Move-In/Move-Out Evidence Tool",
    layout="centered",
    page_icon="🏡"
)

# Minimal CSS just for the Google top accent bar and status pills
st.markdown("""
    <style>
        .google-bar {
            height: 5px;
            width: 100%;
            background: linear-gradient(90deg, #4285F4 25%, #EA4335 25% 50%, #FBBC05 50% 75%, #34A853 75%);
            margin-bottom: 25px;
            border-radius: 4px;
        }
        .pill-normal {
            background-color: #e6f4ea;
            color: #137333;
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 500;
            font-size: 0.85rem;
            display: inline-block;
        }
        .pill-damage {
            background-color: #fce8e6;
            color: #c5221f;
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 500;
            font-size: 0.85rem;
            display: inline-block;
        }
        .pill-neutral {
            background-color: #f1f3f4;
            color: #3c4043;
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: 500;
            font-size: 0.85rem;
            display: inline-block;
        }
    </style>
    <div class="google-bar"></div>
""", unsafe_allow_html=True)

# App Header
st.title("Move-In/Move-Out Evidence Tool")
st.markdown("GDG Build with AI x Hacktoberfest 2026")

# Honest notices: privacy, the AI only suggests, not legal advice
st.info(
    "Your photos are sent to Google's Gemini API for analysis. The AI only suggests "
    "**possible** differences. You decide which ones are real and how to describe them. "
    "This tool helps you document conditions. It is not legal advice."
)

# Each browser session gets its own private temp folder, so two people using the app at the
# same time (for example judges) can never see or overwrite each other's photos or reports.
if "workdir" not in st.session_state:
    st.session_state["workdir"] = tempfile.mkdtemp(prefix="evidence_")
WORKDIR = st.session_state["workdir"]

# --- SIDEBAR: SETTINGS ---
st.sidebar.header("Inspection Settings")

# 1. Inspector Role Tag
user_role = st.sidebar.selectbox("Inspector Role", ["Renter (Tenant)", "Landlord / Leasing Office"])
st.sidebar.markdown(f"🏷️ **Active Role:** `{user_role}`")

st.sidebar.markdown("---")

# 2. Inspection Date Picker
inspection_date = st.sidebar.date_input(
    "Inspection Date (you enter this)", value=date.today(),
    help="Shown in the report as a date you entered. The report also shows the date each photo was taken, read from the photo files."
)

# 3. AI Sensitivity Slider (this is passed to the model)
ai_sensitivity = st.sidebar.slider(
    "AI Sensitivity Level", min_value=1, max_value=5, value=3,
    help="Higher sensitivity reports smaller scuffs and marks. Lower sensitivity reports only clear problems."
)

st.sidebar.markdown("---")

# Room Selection (Dropdown + Custom "Other")
room_option = st.sidebar.selectbox(
    "Select Room / Area",
    ["Living Room", "Kitchen", "Primary Bedroom", "Bathroom", "Balcony / Patio", "Other (Custom)"]
)

if room_option == "Other (Custom)":
    room_name = st.sidebar.text_input("Enter Custom Room Name", value="Sunroom / Den")
else:
    room_name = room_option

st.sidebar.markdown("---")
st.sidebar.caption(f"AI model: {MODEL}")

# 4. Reset Session Button (also clears this session's photos)
if st.sidebar.button("🔄 Reset Session"):
    shutil.rmtree(st.session_state.get("workdir", ""), ignore_errors=True)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- MAIN UPLOAD SECTION ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("Move-In Photo")
    before_file = st.file_uploader("Upload Before Photo", type=["jpg", "jpeg", "png"], key="before")

with col2:
    st.subheader("Move-Out Photo")
    after_file = st.file_uploader("Upload After Photo", type=["jpg", "jpeg", "png"], key="after")

TENANT_VIEWS = [
    "Not sure yet",
    "Normal wear and tear",
    "Already there at move-in",
    "Damage I accept responsibility for",
]

if before_file and after_file:
    # Save into this session's own folder. Fixed names, so nothing piles up.
    before_ext = os.path.splitext(before_file.name)[1] or ".jpg"
    after_ext = os.path.splitext(after_file.name)[1] or ".jpg"
    before_path = os.path.join(WORKDIR, "before" + before_ext)
    after_path = os.path.join(WORKDIR, "after" + after_ext)

    with open(before_path, "wb") as f:
        f.write(before_file.getbuffer())
    with open(after_path, "wb") as f:
        f.write(after_file.getbuffer())

    # If different photos are chosen, forget the old results
    signature = (before_file.name, before_file.size, after_file.name, after_file.size)
    if st.session_state.get("signature") != signature:
        st.session_state["signature"] = signature
        st.session_state.pop("diffs", None)
        st.session_state.pop("pdf_bytes", None)

    st.image([before_path, after_path], caption=["Move-In", "Move-Out"], width=300)

    # The report uses the dates stored inside the photo files (removing GPS location keeps them).
    taken_before = report.get_image_timestamp(before_path)
    taken_after = report.get_image_timestamp(after_path)
    st.caption(f"Dates found in the photo files: Move-in {taken_before} | Move-out {taken_after}")
    if report.NOT_FOUND in (taken_before, taken_after):
        st.warning("At least one photo has no date stored in its file (some apps and editors remove it). "
                   "The report will say the date was not found. Use the original photo files if you have them.")

    if st.button("Run Analysis", type="primary"):
        with st.spinner(f"Analyzing differences with Gemma 4 (sensitivity {ai_sensitivity})... this can take up to a minute."):
            try:
                st.session_state["diffs"] = compare_photos(before_path, after_path, sensitivity=ai_sensitivity)
                st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
                st.session_state.pop("pdf_bytes", None)
                st.success("Analysis complete!")
            except PipelineError as e:
                st.session_state.pop("diffs", None)
                st.error(str(e))

    diffs = st.session_state.get("diffs")
    if diffs is not None:
        st.markdown("---")
        st.subheader("Review Possible Differences & Add Your Notes")

        confirmed_items = []
        if not diffs:
            st.success("The AI did not find meaningful differences between these photos.")
        else:
            st.caption("Check the box for each difference that is real. Only checked items go in the report.")
            run_id = st.session_state.get("run_id", 0)

            for idx, item in enumerate(diffs):
                k = f"{run_id}_{idx}"
                st.markdown(f"**Item {idx + 1}: {item.get('category', 'other').capitalize()}** "
                            f"in *{room_name}* ({item.get('location', '')})")
                st.write(f"AI finding: {item.get('description', '')}")
                st.caption(f"Severity: {item.get('severity', 'unknown')}  |  AI confidence: {item.get('confidence', 'unknown')}")

                include = st.checkbox("This difference is real. Include it in the report.", key=f"include_{k}")

                # The tenant (not the AI) decides how to classify each item.
                view = st.selectbox("Your view of this item", TENANT_VIEWS, key=f"view_{k}")
                if view in ("Normal wear and tear", "Already there at move-in"):
                    st.markdown(f'<span class="pill-normal">🟢 {view}</span>', unsafe_allow_html=True)
                elif view == "Not sure yet":
                    st.markdown(f'<span class="pill-neutral">⚪ {view}</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="pill-damage">🔴 {view}</span>', unsafe_allow_html=True)

                st.markdown("")
                tenant_note = st.text_input(
                    f"Add your note or context for item {idx + 1} (optional):",
                    key=f"note_{k}",
                    placeholder="e.g., This scuff was already present on move-in day."
                )
                st.markdown("---")

                if include:
                    confirmed_items.append(dict(
                        item,
                        tenant_view="" if view == "Not sure yet" else view,
                        tenant_note=tenant_note,
                    ))

        if confirmed_items:
            if st.button("Generate PDF Report & Draft Letter", type="primary"):
                output_pdf = os.path.join(WORKDIR, "evidence_report.pdf")
                try:
                    report.build_report(
                        room_name=room_name,
                        confirmed_items=confirmed_items,
                        before_path=before_path,
                        after_path=after_path,
                        output_path=output_pdf,
                        inspection_date=str(inspection_date),
                        inspector_role=user_role,
                    )
                    with open(output_pdf, "rb") as pdf_file:
                        st.session_state["pdf_bytes"] = pdf_file.read()
                except Exception as e:   # show a readable message instead of crashing
                    st.error(f"Could not build the report: {e}")
        elif diffs:
            st.info("Check at least one difference above to generate a report.")

        # The download button sits outside the Generate button so it stays visible after a rerun.
        if st.session_state.get("pdf_bytes"):
            st.download_button(
                label="Download Evidence Report (PDF)",
                data=st.session_state["pdf_bytes"],
                file_name=f"{room_name.replace(' ', '_').replace('/', '-')}_Evidence_Report.pdf",
                mime="application/pdf"
            )
