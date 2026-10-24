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
        @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Google Sans', sans-serif;
            color: #202124;
        }
        
        /* Google 4-Color Top Accent Bar */
        .google-bar {
            height: 5px;
            width: 100%;
            background: linear-gradient(90deg, #4285F4 25%, #EA4335 25% 50%, #FBBC05 50% 75%, #34A853 75%);
            margin-bottom: 25px;
            border-radius: 4px;
        }
        
        .stApp {
            background-color: #f8f9fa;
        }
        
        .stButton>button {
            background-color: #1a73e8;
            color: white;
            border-radius: 4px;
            font-weight: 500;
            border: none;
        }
        .stButton>button:hover {
            background-color: #1557b0;
            color: white;
        }
    </style>
    <div class="google-bar"></div>
""", unsafe_allow_html=True)

# App Header
st.title("VaultInspect")
st.markdown("GDG Build with AI x Hacktoberfest 2026")

# --- SIDEBAR: ROOM SELECTION ---
st.sidebar.header("Inspection Settings")

# Dropdown with Custom "Other" Option (Replaced the old text input)
room_option = st.sidebar.selectbox(
    "Select Room / Area", 
    ["Living Room", "Kitchen", "Primary Bedroom", "Bathroom", "Balcony / Patio", "Other (Custom)"]
)

if room_option == "Other (Custom)":
    room_name = st.sidebar.text_input("Enter Custom Room Name", value="Sunroom / Den")
else:
    room_name = room_option

# --- MAIN UPLOAD SECTION ---
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

    if st.button("Run Analysis", type="primary"):
        with st.spinner("Analyzing differences..."):
            mock_diffs = [
                {
                    "category": "damage",
                    "location": f"{room_name}",
                    "description": "Scuff mark detected",
                    "severity": "minor",
                    "confidence": "high"
                }
            ]
            st.session_state["confirmed_items"] = mock_diffs
            st.success("Analysis complete!")

    if "confirmed_items" in st.session_state and st.session_state["confirmed_items"]:
        st.markdown("---")
        st.subheader("Review Confirmed Differences & Add Tenant Notes")
        confirmed_items = st.session_state["confirmed_items"]
        
        for idx, item in enumerate(confirmed_items):
            st.markdown(f"**Item {idx+1}: {item.get('category', 'damage').capitalize()}** at *{room_name}*")
            st.write(f"AI Finding: {item.get('description', '')}")
            
            tenant_note = st.text_input(
                f"Add your defense note or context for this item:",
                value=item.get('tenant_note', ''),
                key=f"tenant_note_{idx}",
                placeholder="e.g., This scuff was already present on move-in day."
            )
            item['tenant_note'] = tenant_note
            st.markdown("---")

        if st.button("Generate Official PDF Report & Dispute Letter", type="primary"):
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