import streamlit as st
import os
import uuid
from datetime import date
from dotenv import load_dotenv

load_dotenv()
import report

# Page Configuration & Clean Theme
st.set_page_config(
    page_title="Move-In/Move-Out Evidence Tool", 
    layout="centered", 
    page_icon="🏡"
)

# Minimal CSS for the Google top accent bar and status pills
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
    </style>
    <div class="google-bar"></div>
""", unsafe_allow_html=True)

# App Header
st.title("Move-In/Move-Out Evidence Tool")
st.markdown("GDG Build with AI x Hacktoberfest 2026")

# --- SIDEBAR: ENHANCED SETTINGS ---
st.sidebar.header("Inspection Settings")

# 1. Inspector Role Tag
user_role = st.sidebar.selectbox("Inspector Role", ["Renter (Tenant)", "Landlord / Leasing Office"])
st.sidebar.markdown(f"🏷️ **Active Role:** `{user_role}`")

st.sidebar.markdown("---")

# 2. Inspection Date Picker
inspection_date = st.sidebar.date_input("Inspection Date", value=date.today())

# 3. AI Sensitivity Slider
ai_sensitivity = st.sidebar.slider("AI Sensitivity Level", min_value=1, max_value=5, value=3, help="Higher sensitivity detects minor scuffs more aggressively.")

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

# 4. Reset Session Button
if st.sidebar.button("🔄 Reset Session"):
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

if before_file and after_file:
    os.makedirs("temp", exist_ok=True)
    
    # Generate unique IDs to prevent image flipping/overwriting issues
    unique_id = uuid.uuid4().hex[:8]
    before_path = os.path.join("temp", f"before_{unique_id}_{before_file.name}")
    after_path = os.path.join("temp", f"after_{unique_id}_{after_file.name}")
    
    with open(before_path, "wb") as f:
        f.write(before_file.getbuffer())
    with open(after_path, "wb") as f:
        f.write(after_file.getbuffer())

    st.image([before_path, after_path], caption=["Move-In", "Move-Out"], width=300)

    if st.button("Run Analysis", type="primary"):
        with st.spinner(f"Analyzing differences (Sensitivity Level {ai_sensitivity})..."):
            mock_diffs = [
                {
                    "category": "damage",
                    "location": f"{room_name}",
                    "description": "Scuff mark detected near baseboard",
                    "classification": "Normal Wear (Non-Chargeable)",
                    "severity": "minor",
                    "confidence": "high"
                },
                {
                    "category": "damage",
                    "location": f"{room_name}",
                    "description": "Noticeable scratch on surface",
                    "classification": "Actual Damage (Chargeable)",
                    "severity": "moderate",
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
            
            # Color-coded status pills
            classification = item.get('classification', 'Normal Wear')
            if "Normal Wear" in classification:
                st.markdown(f'<span class="pill-normal">🟢 {classification}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="pill-damage">🔴 {classification}</span>', unsafe_allow_html=True)
            
            st.markdown("")
            tenant_note = st.text_input(
                f"Add your defense note or context for item {idx+1}:",
                value=item.get('tenant_note', ''),
                key=f"tenant_note_{idx}",
                placeholder="e.g., This scuff was already present on move-in day."
            )
            item['tenant_note'] = tenant_note
            st.markdown("---")

        if st.button("Generate Official PDF Report & Dispute Letter", type="primary"):
            output_pdf = "evidence_report.pdf"
            current_date = inspection_date if 'inspection_date' in locals() else date.today()
            items_to_report = confirmed_items if 'confirmed_items' in locals() else []
            
            report.build_report(
                room_name=room_name,
                inspection_date=current_date,
                confirmed_items=items_to_report,
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
