import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables (Gemini API key)
load_dotenv()

# Import team modules
import report
from pipeline import compare_photos, PipelineError, MODEL   # CHANGED: the real AI function

st.set_page_config(page_title="Move-In/Move-Out Evidence Tool", layout="centered", page_icon="🏡")

# Inject Custom Google-Themed CSS Styling
st.markdown("""
    <style>
        /* Google Color Accent Bar at the Top */
        .google-bar {
            height: 6px;
            width: 100%;
            background: linear-gradient(90deg, #4285F4 25%, #EA4335 25% 50%, #FBBC05 50% 75%, #34A853 75%);
            margin-bottom: 20px;
            border-radius: 3px;
        }
        .main-title {
            color: #202124;
            font-weight: 700;
        }
    </style>
    <div class="google-bar"></div>
""", unsafe_allow_html=True)

st.title("Move-In / Move-Out Photo Evidence Tool")
st.markdown("**GDG Build with AI x Hacktoberfest 2026** — Protect your security deposit with AI-powered analysis and cryptographic evidence reports.")

# NEW: honest notices (privacy + the AI suggests, you decide + not legal advice)
st.info(
    "Your photos are sent to Google's Gemini API for analysis. The AI only suggests "
    "**possible** differences, and you decide which ones are real. This tool helps you "
    "document conditions. It is not legal advice."
)

# Sidebar for settings & room name
st.sidebar.header("Inspection Settings")

room_option = st.sidebar.selectbox(
    "Select Room / Area", 
    ["Living Room", "Kitchen", "Primary Bedroom", "Bathroom", "Balcony / Patio", "Other (Custom)"]
)
if room_option == "Other (Custom)":
    room_name = st.sidebar.text_input("Enter Custom Room Name", value="Sunroom / Den")
else:
    room_name = room_option

st.sidebar.caption(f"AI model: {MODEL}")   # NEW: shows the model name (needed for the Gemma 4 track)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Move-In Photo")
    before_file = st.file_uploader("Upload Before Photo", type=["jpg", "jpeg", "png"], key="before")

with col2:
    st.subheader("Move-Out Photo")
    after_file = st.file_uploader("Upload After Photo", type=["jpg", "jpeg", "png"], key="after")

if before_file and after_file:
    os.makedirs("temp", exist_ok=True)
    # CHANGED: prefix the names so two uploads with the same file name cannot overwrite each other
    before_path = os.path.join("temp", "before_" + before_file.name)
    after_path = os.path.join("temp", "after_" + after_file.name)

    with open(before_path, "wb") as f:
        f.write(before_file.getbuffer())
    with open(after_path, "wb") as f:
        f.write(after_file.getbuffer())

    # NEW: if the user picks different photos, forget the old results
    signature = (before_file.name, before_file.size, after_file.name, after_file.size)
    if st.session_state.get("signature") != signature:
        st.session_state["signature"] = signature
        st.session_state.pop("diffs", None)
        st.session_state.pop("pdf_bytes", None)

    st.image([before_path, after_path], caption=["Move-In", "Move-Out"], width=300)

    if st.button("Run AI Analysis", type="primary"):
        with st.spinner("Analyzing differences with Gemma 4... this can take up to a minute."):
            # CHANGED: the real model call replaces the mocked data
            try:
                st.session_state["diffs"] = compare_photos(before_path, after_path)
                st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
                st.session_state.pop("pdf_bytes", None)
                st.success("Analysis complete!")
            except PipelineError as e:
                st.session_state.pop("diffs", None)
                st.error(str(e))
    if st.button("Generate Official PDF Report & Dispute Letter", type="primary"):
            output_pdf = "evidence_report.pdf"
            report.build_report(
                room_name=room_name,
                inspection_date=inspection_date, # <--- Pass the sidebar date here
                confirmed_items=confirmed_items,
                before_path=before_path,
                after_path=after_path,
                output_path=output_pdf

    diffs = st.session_state.get("diffs")
    if diffs is not None:
        st.subheader("Review Possible Differences")

        # CHANGED: the tenant confirms each item. Only checked items go in the report.
        confirmed_items = []
        if not diffs:
            st.success("The AI did not find meaningful differences between these photos.")
        else:
            st.caption("Check the boxes for the differences that are real. Only checked items go in the report.")
            run_id = st.session_state.get("run_id", 0)
            for idx, item in enumerate(diffs):
                label = (f"**{item['category'].capitalize()}** at {item['location']}: {item['description']} "
                         f"*(Severity: {item['severity']}, AI confidence: {item['confidence']})*")
                if st.checkbox(label, key=f"confirm_{run_id}_{idx}"):
                    confirmed_items.append(item)

        if confirmed_items:
            if st.button("Generate Official PDF Report & Dispute Letter"):
                output_pdf = "evidence_report.pdf"
                try:
                    report.build_report(
                        room_name=room_name,
                        confirmed_items=confirmed_items,
                        before_path=before_path,
                        after_path=after_path,
                        output_path=output_pdf
                    )
                    with open(output_pdf, "rb") as pdf_file:
                        st.session_state["pdf_bytes"] = pdf_file.read()
                except Exception as e:   # show a readable message instead of crashing
                    st.error(f"Could not build the report: {e}")
        elif diffs:
            st.info("Check at least one difference above to generate a report.")

        # CHANGED: download button lives outside the generate button so it does not vanish on rerun
        if st.session_state.get("pdf_bytes"):
            st.download_button(
                label="Download Evidence Report (PDF)",
                data=st.session_state["pdf_bytes"],
                file_name=f"{room_name.replace(' ', '_')}_Evidence_Report.pdf",
                mime="application/pdf"
            )
