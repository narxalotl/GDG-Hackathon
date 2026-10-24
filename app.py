import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables (Gemini API key)
load_dotenv()

# Import team modules
import report

st.set_page_config(page_title="Move-In/Move-Out Evidence Tool", layout="centered", page_icon="🍀")

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

# Sidebar for settings & room name
st.sidebar.header("Inspection Settings")
room_name = st.sidebar.text_input("Room / Area Name", value="Living Room")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Move-In Photo")
    before_file = st.file_uploader("Upload Before Photo", type=["jpg", "jpeg", "png"], key="before")

with col2:
    st.subheader("Move-Out Photo")
    after_file = st.file_uploader("Upload After Photo", type=["jpg", "jpeg", "png"], key="after")

if before_file and after_file:
    os.makedirs("temp", exist_ok=True)
    before_path = os.path.join("temp", before_file.name)
    after_path = os.path.join("temp", after_file.name)
    
    with open(before_path, "wb") as f:
        f.write(before_file.getbuffer())
    with open(after_path, "wb") as f:
        f.write(after_file.getbuffer())

    st.image([before_path, after_path], caption=["Move-In", "Move-Out"], width=300)

    if st.button("Run AI Analysis", type="primary"):
        with st.spinner("Analyzing differences with Google AI..."):
            # Mocked data for testing the UI flow
            mock_diffs = [
                {
                    "category": "damage",
                    "location": "Wall",
                    "description": "Scuff mark and small dent near baseboard",
                    "severity": "minor",
                    "confidence": "high"
                }
            ]
            st.session_state["confirmed_items"] = mock_diffs
            st.success("Analysis complete!")

    if "confirmed_items" in st.session_state and st.session_state["confirmed_items"]:
        st.subheader("Review Confirmed Differences")
        confirmed_items = st.session_state["confirmed_items"]
        
        for idx, item in enumerate(confirmed_items):
            st.write(f"- **{item['category'].capitalize()}** at {item['location']}: {item['description']} *(Severity: {item['severity']})*")

        if st.button("Generate Official PDF Report & Dispute Letter"):
            output_pdf = "evidence_report.pdf"
            report.build_report(
                room_name=room_name,
                confirmed_items=confirmed_items,
                before_path=before_path,
                after_path=after_path,
                output_path=output_pdf
            )
            
            with open(output_pdf, "rb") as pdf_file:
                st.download_button(
                    label="Download Signed Evidence Report (PDF)",
                    data=pdf_file,
                    file_name=f"{room_name.replace(' ', '_')}_Evidence_Report.pdf",
                    mime="application/pdf"
                )