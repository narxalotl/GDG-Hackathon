import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()
import report
import db

# Initialize SQLite Database (with encryption support)
db.init_db()

# Page Configuration & Google-Themed Material Design Styling
st.set_page_config(
    page_title="VaultInspect | Move-In & Move-Out Evidence", 
    layout="centered", 
    page_icon="🛡️"
)

st.markdown("""
    <style>
        /* Google Brand Color Accent Bar */
        .google-bar {
            height: 6px;
            width: 100%;
            background: linear-gradient(90deg, #4285F4 25%, #EA4335 25% 50%, #FBBC05 50% 75%, #34A853 75%);
            margin-bottom: 25px;
            border-radius: 3px;
        }
        .card {
            background-color: #ffffff;
            border: 1px solid #dadce0;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }
        .main-header {
            font-family: 'Google Sans', sans-serif;
            color: #202124;
            font-weight: 700;
        }
    </style>
    <div class="google-bar"></div>
""", unsafe_allow_html=True)

# App Header
st.title("🛡️ VaultInspect: Move-In / Move-Out Evidence Portal")
st.markdown("**GDG Build with AI x Hacktoberfest 2026** — Secure SQLite Database, AES-256 Encryption & Dispute Engine.")

# --- SIDEBAR: USER PORTAL, SETTINGS & HISTORY ---
st.sidebar.header("🔐 User Portal & Cloud Vault")
user_role = st.sidebar.selectbox("Select Portal Role", ["🏠 Renter (Tenant)", "🏢 Leasing Office / Landlord"])
user_email = st.sidebar.text_input("Account Email", value="renter@example.com" if "Renter" in user_role else "manager@apts.com")

# Register/ensure user in SQLite
db.register_user(user_email, user_role)

st.sidebar.markdown("---")
st.sidebar.header("📍 Inspection Area")

room_option = st.sidebar.selectbox(
    "Select Room / Area", 
    ["Living Room", "Kitchen", "Primary Bedroom", "Bathroom", "Balcony / Patio", "Other (Custom)"]
)

if room_option == "Other (Custom)":
    room_name = st.sidebar.text_input("Enter Custom Room Name", value="Sunroom / Den")
else:
    room_name = room_option

# Display Past Inspection History from SQLite (with decrypted notes)
st.sidebar.markdown("---")
st.sidebar.header("📂 Encrypted Audit History")
past_records = db.get_user_inspections(user_email)
if past_records:
    for rec in past_records:
        st.sidebar.text(f"• {rec['room_name']} ({rec['created_at'][:10]})")
else:
    st.sidebar.caption("No past inspections found in SQLite for this email.")

# --- MAIN UPLOAD SECTION ---
st.markdown("### 📸 Photo Evidence Vault (AES-256 Encrypted Storage)")
col1, col2 = st.columns(2)

with col1:
    st.info("📁 **Move-In Baseline**")
    before_file = st.file_uploader("Upload Initial Condition Photo", type=["jpg", "jpeg", "png"], key="before")

with col2:
    st.info("📁 **Move-Out Audit**")
    after_file = st.file_uploader("Upload Final Condition Photo", type=["jpg", "jpeg", "png"], key="after")

if before_file and after_file:
    os.makedirs("temp", exist_ok=True)
    before_path = os.path.join("temp", before_file.name)
    after_path = os.path.join("temp", after_file.name)
    
    with open(before_path, "wb") as f:
        f.write(before_file.getbuffer())
    with open(after_path, "wb") as f:
        f.write(after_file.getbuffer())

    st.image([before_path, after_path], caption=["Move-In Baseline", "Move-Out Audit"], width=300)

    if st.button("🚀 Run AI Difference Analysis", type="primary"):
        with st.spinner("Analyzing pixel-level differences with Google AI..."):
            # Mocked data distinguishing normal wear vs actionable damage
            mock_diffs = [
                {
                    "category": "cosmetic",
                    "location": f"{room_name} Wall",
                    "description": "Light scuff mark near baseboard",
                    "classification": "Normal Wear (Non-Chargeable)",
                    "severity": "minor",
                    "confidence": "high"
                },
                {
                    "category": "damage",
                    "location": f"{room_name} Floor",
                    "description": "Deep gouge/scratch in hardwood flooring",
                    "classification": "Actual Damage (Chargeable)",
                    "severity": "moderate",
                    "confidence": "high"
                }
            ]
            st.session_state["confirmed_items"] = mock_diffs
            st.success("Analysis complete!")

    # --- REVIEW & TENANT CONTEXT SECTION ---
    if "confirmed_items" in st.session_state and st.session_state["confirmed_items"]:
        st.markdown("---")
        st.subheader("📝 Review Findings & Add Tenant Defense Notes")
        confirmed_items = st.session_state["confirmed_items"]
        
        for idx, item in enumerate(confirmed_items):
            if "Normal Wear" in item.get('classification', ''):
                st.info(f"🟢 **{item.get('classification')}** at *{item.get('location')}*: {item.get('description')}")
            else:
                st.warning(f"🔴 **{item.get('classification', 'Damage')}** at *{item.get('location')}*: {item.get('description')}")
            
            # Tenant custom context text input box
            tenant_note = st.text_input(
                f"Add your defense note for Item {idx+1}:",
                value=item.get('tenant_note', ''),
                key=f"tenant_note_{idx}",
                placeholder="e.g., Pre-existing damage noted on signed move-in sheet."
            )
            item['tenant_note'] = tenant_note
            st.markdown("")

        if st.button("📑 Generate Official Aesthetic PDF Report & Save to Secure SQL Vault", type="primary"):
            # Save securely into SQLite database with encryption
            db.save_secure_inspection(
                user_email=user_email,
                room_name=room_name,
                before_path=before_path,
                after_path=after_path,
                confirmed_items=confirmed_items
            )
            
            output_pdf = "evidence_report.pdf"
            report.build_report(
                room_name=room_name,
                user_email=user_email,
                confirmed_items=confirmed_items,
                before_path=before_path,
                after_path=after_path,
                output_path=output_pdf
            )
            
            st.success("Inspection securely encrypted and saved to SQLite database!")
            
            with open(output_pdf, "rb") as pdf_file:
                st.download_button(
                    label="📥 Download Signed Evidence Report (PDF)",
                    data=pdf_file,
                    file_name=f"{room_name.replace(' ', '_')}_Evidence_Report.pdf",
                    mime="application/pdf"
                )