import json
import os
import shutil
import tempfile
import submissions
from datetime import date
import streamlit as st
from dotenv import load_dotenv
import report
from pipeline import compare_photos, PipelineError, MODEL, have_server_key

load_dotenv()

BASE = os.path.dirname(os.path.abspath(__file__))
DEMO_JSON = os.path.join(BASE, "demo", "demo.json")

# How many live AI analyses one browser session may run on the app's shared key.
MAX_LIVE_RUNS = int(os.environ.get("MAX_LIVE_RUNS", "8"))

# Page Configuration & Clean Theme
st.set_page_config(
    page_title="Move-In/Move-Out Evidence Tool",
    layout="wide",
    page_icon="🏡"
)

# Secrets check[cite: 5]
try:
    if not os.environ.get("GEMINI_API_KEY") and "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = str(st.secrets["GEMINI_API_KEY"])
except Exception:
    pass

# Modern SaaS CSS styling with Google top bar and cards[cite: 6, 7]
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .google-bar {
        height: 5px;
        width: 100%;
        background: linear-gradient(90deg, #4285F4 25%, #EA4335 25% 50%, #FBBC05 50% 75%, #34A853 75%);
        margin-bottom: 25px;
        border-radius: 4px;
    }
    .web-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        padding: 25px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    }
    .pill-normal {
        background-color: rgba(19, 115, 51, 0.15);
        color: #34a853;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 500;
        font-size: 0.85rem;
        border: 1px solid rgba(52, 168, 83, 0.3);
        display: inline-block;
    }
    .pill-damage {
        background-color: rgba(197, 34, 31, 0.15);
        color: #ea4335;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 500;
        font-size: 0.85rem;
        border: 1px solid rgba(234, 67, 53, 0.3);
        display: inline-block;
    }
    .pill-neutral {
        background-color: rgba(241, 243, 244, 0.15);
        color: #bdc1c6;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 500;
        font-size: 0.85rem;
        border: 1px solid rgba(189, 193, 198, 0.3);
        display: inline-block;
    }
</style>
<div class="google-bar"></div>
""", unsafe_allow_html=True)

# Single, Clean Header Card with House Emoji[cite: 7]
with st.container():
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.title("🏡 Move-In/Move-Out Evidence Tool")
    st.markdown("GDG Build with AI x Hacktoberfest 2026")
    st.info(
        "Your photos are sent to Google's Gemini API for analysis. The AI only suggests "
        "**possible** differences. You decide which ones are real and how to describe them.\n\n"
        "This tool helps you document conditions. It is not legal advice."
    )
    st.markdown('</div>', unsafe_allow_html=True)

def load_demo():
    try:
        with open(DEMO_JSON, encoding="utf-8") as f:
            data = json.load(f)
        before = os.path.join(BASE, "demo", data["before"])
        after = os.path.join(BASE, "demo", data["after"])
        if os.path.exists(before) and os.path.exists(after):
            return before, after, data["items"]
    except Exception:
        pass
    return None

demo = load_demo()

if "workdir" not in st.session_state:
    st.session_state["workdir"] = tempfile.mkdtemp(prefix="evidence_")
WORKDIR = st.session_state["workdir"]

# Initialize batch session state for multi-issue adding
if "batched_issues" not in st.session_state:
    st.session_state.batched_issues = []

# ==========================================
# SIDEBAR: MODERN SAAS NAVIGATION & SETTINGS
# ==========================================
st.sidebar.markdown("### 🧭 Portal Navigation")
user_role = st.sidebar.radio(
    "Select Portal",
    ["Renters", "Leasing Office"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Active Portal:** <span style='color: #4285F4; font-weight: bold;'>{user_role}</span>", unsafe_allow_html=True)
st.sidebar.markdown(f"**System Status:** <span style='color: #34a853; font-weight: bold;'>🟢 Online</span>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Tenant Details for Baseline & Submissions
tenant_name = st.sidebar.text_input("Tenant Name", "Jane Doe")
unit_number = st.sidebar.text_input("Apartment / Unit Number", "Unit 4B")

st.sidebar.header("Inspection Settings")
inspection_date = st.sidebar.date_input(
    "Inspection Date (you enter this)", value=date.today(),
    help="Shown in the report as a date you entered. The report also shows the date each photo was taken, read from the photo files."
)
dmv_jurisdiction = st.sidebar.selectbox(
    "DMV Jurisdiction",
    [
        "Maryland Security Deposit Law",
        "District of Columbia (DC Tenant Bill of Rights)",
        "Virginia (VRLTA)"
    ]
)
ai_sensitivity = st.sidebar.slider(
    "AI Sensitivity Level", min_value=1, max_value=5, value=3,
    help="Higher sensitivity reports smaller scuffs and marks. Lower sensitivity reports only clear problems.")

st.sidebar.markdown("---")

# Workflow Mode Selector for Renters
if user_role == "Renters":
    workflow_mode = st.sidebar.selectbox(
        "Renter Workflow Mode",
        [
            "3. Quick One-Time Compare (Standard)",
            "1. Record Move-In Baseline (Day 1)",
            "2. Move-Out Audit (Match Saved Baseline)"
        ]
    )
    st.sidebar.markdown("---")

room_option = st.sidebar.selectbox(
    "Select Room / Area",
    ["Living Room", "Kitchen", "Primary Bedroom", "Bathroom", "Balcony / Patio", "Other (Custom)"]
)
if room_option == "Other (Custom)":
    room_name = st.sidebar.text_input("Enter Custom Room Name", value="Sunroom / Den")
else:
    room_name = room_option

st.sidebar.markdown("---")
with st.sidebar.expander("AI access (optional)"):
    user_key = st.text_input(
        "Your own Gemini API key", type="password", key="user_key",
        help="A free key from Google AI Studio. It is used only to analyze your photos and is kept only for this browser session. This app does not save it."
    )
    user_key = (user_key or "").strip()
    if user_key:
        st.sidebar.caption("AI access: your own key")
    elif have_server_key():
        st.sidebar.caption(f"AI access: the app's shared key ({MAX_LIVE_RUNS} analyses per session)")
    else:
        st.sidebar.caption("AI access: no key set. Load the saved example, or paste your own key above.")
    st.sidebar.caption(f"AI model: {MODEL}")

if st.sidebar.button("Reset Session"):
    shutil.rmtree(st.session_state.get("workdir", ""), ignore_errors=True)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ==========================================
# CHECK WHO IS LOGGED IN
# ==========================================
if user_role == "Leasing Office":
    # LEASING OFFICE DASHBOARD VIEW[cite: 10]
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.subheader("🏢 Leasing Office Inspection Dashboard")
    st.write("Review incoming tenant inspection submissions and evidence records.")
    all_subs = submissions.get_all_submissions() if hasattr(submissions, "get_all_submissions") else []
    if not all_subs:
        st.info("No tenant inspection reports have been submitted yet.")
    else:
        table_data = []
        for s in all_subs:
            table_data.append({
                "Tenant Name": s.get("name", "N/A"),
                "Unit / Apt": s.get("unit", "N/A"),
                "Room / Area": s.get("room", "N/A"),
                "Jurisdiction": s.get("jurisdiction", "N/A")
            })
        st.dataframe(table_data, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# RENTERS (TENANT) VIEW
# ==========================================
else:
    # SaaS Metrics Header Cards[cite: 11]
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="web-card" style="text-align: center; padding: 15px;"><p style="color: #8b949e; font-size: 0.8rem; margin:0;">ACTIVE JURISDICTION</p><h4 style="color: #4285F4; margin:5px 0 0;">{dmv_jurisdiction.split()[0]}</h4></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="web-card" style="text-align: center; padding: 15px;"><p style="color: #8b949e; font-size: 0.8rem; margin:0;">SELECTED ROOM</p><h4 style="color: #34a853; margin:5px 0 0;">{room_name}</h4></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="web-card" style="text-align: center; padding: 15px;"><p style="color: #8b949e; font-size: 0.8rem; margin:0;">AI ENGINE</p><h4 style="color: #FBBC05; margin:5px 0 0;">{MODEL}</h4></div>', unsafe_allow_html=True)

    # ----------------------------------------------------
    # MODE 1: RECORD MOVE-IN BASELINE (DAY 1)
    # ----------------------------------------------------
    if workflow_mode.startswith("1."):
        st.markdown('<div class="web-card">', unsafe_allow_html=True)
        st.subheader(f"📥 Record Move-In Baseline: {room_name}")
        st.info("Take and save baseline condition photos on day one so you have a verified reference for your move-out inspection months later.")
        
        baseline_file = st.file_uploader(f"Upload Move-In Photo for {room_name}", type=["jpg", "jpeg", "png"], key="baseline_file")
        
        if st.button("💾 Save Move-In Baseline", type="primary"):
            if baseline_file:
                os.makedirs("uploads", exist_ok=True)
                b_path = os.path.join(WORKDIR, f"baseline_{unit_number}_{room_name}.jpg".replace(" ", "_"))
                with open(b_path, "wb") as f:
                    f.write(baseline_file.getbuffer())
                
                submissions.save_move_in_baseline(tenant_name, unit_number, room_name, b_path, str(inspection_date), dmv_jurisdiction)
                st.success(f"Successfully saved move-in baseline for {room_name} in {unit_number}!")
            else:
                st.warning("Please upload a photo before saving.")
        st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------------------
    # MODE 2: MOVE-OUT AUDIT (MATCH SAVED BASELINE)
    # ----------------------------------------------------
    elif workflow_mode.startswith("2."):
        st.markdown('<div class="web-card">', unsafe_allow_html=True)
        st.subheader(f"📤 Move-Out Audit (Paired with Saved Baseline): {room_name}")
        
        baselines = submissions.get_move_in_baselines(unit_number) if hasattr(submissions, "get_move_in_baselines") else []
        
        if not baselines:
            st.warning(f"No saved move-in baselines found for {unit_number}. Please switch mode to '1. Record Move-In Baseline' first!")
        else:
            baseline_options = {f"{b['room']} (Saved on {b['date']})": b for b in baselines}
            selected_baseline_label = st.selectbox("Select Saved Move-In Baseline", list(baseline_options.keys()))
            chosen_baseline = baseline_options[selected_baseline_label]
            
            st.image(chosen_baseline["photo_path"], width=300, caption=f"Move-In Baseline: {chosen_baseline['room']}")
            
            after_file = st.file_uploader("Upload Move-Out Audit Photo", type=["jpg", "jpeg", "png"], key="audit_after")
            
            st.info(
                "💡 **Tip for Best AI Accuracy:** Try to take your Move-Out photo from the "
                "**same angle and lighting** as your Move-In photo. Consistent framing helps "
                "the AI accurately distinguish real damage from shadows or perspective shifts!"
            )
            
            if after_file:
                after_path = os.path.join(WORKDIR, "audit_after.jpg")
                with open(after_path, "wb") as f:
                    f.write(after_file.getbuffer())
                
                # Set paths for analysis flow
                before_path = chosen_baseline["photo_path"]
                mode = "upload"
            else:
                before_path, after_path = None, None
        st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------------------
    # MODE 3: QUICK ONE-TIME COMPARE (STANDARD)
    # ----------------------------------------------------
    else:
        # Main Upload Section[cite: 11]
        st.markdown('<div class="web-card">', unsafe_allow_html=True)
        st.subheader("📸 Upload Audit Photos")
        st.info(
            "💡 **Tip for Best AI Accuracy:** Try to take your Move-Out photo from the "
            "**same angle and lighting** as your Move-In photo. Consistent framing helps "
            "the AI accurately distinguish real damage from shadows or perspective shifts!"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            before_file = st.file_uploader("Upload Before Photo", type=["jpg", "jpeg", "png"], key="before")
        with col2:
            after_file = st.file_uploader("Upload After Photo", type=["jpg", "jpeg", "png"], key="after")
        st.markdown('</div>', unsafe_allow_html=True)

        mode, before_path, after_path, signature, demo_items = None, None, None, None, None

        if 'before_file' in locals() and before_file and after_file:
            mode = "upload"
            st.session_state.pop("use_demo", None)
            before_ext = os.path.splitext(before_file.name)[1] or ".jpg"
            after_ext = os.path.splitext(after_file.name)[1] or ".jpg"
            before_path = os.path.join(WORKDIR, "before" + before_ext)
            after_path = os.path.join(WORKDIR, "after" + after_ext)
            with open(before_path, "wb") as f:
                f.write(before_file.getbuffer())
            with open(after_path, "wb") as f:
                f.write(after_file.getbuffer())
            signature = ("upload", before_file.name, before_file.size, after_file.name, after_file.size)
        elif st.session_state.get("use_demo") and demo:
            mode = "demo"
            before_path, after_path, demo_items = demo
            signature = ("demo",)
        elif demo and workflow_mode.startswith("3."):
            st.markdown('<div class="web-card">', unsafe_allow_html=True)
            st.write("No photos handy, or no API key? Try the saved example. It needs no key and makes no AI call.")
            if st.button("Load the saved example"):
                st.session_state["use_demo"] = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # ----------------------------------------------------
    # ANALYSIS & REVIEW WORKFLOW
    # ----------------------------------------------------
    if workflow_mode.startswith("2.") and 'after_file' in locals() and after_file:
        mode = "upload"
        signature = ("baseline_match", chosen_baseline["photo_path"], after_file.name)

    if 'signature' in locals() and signature and st.session_state.get("signature") != signature:
        st.session_state["signature"] = signature
        st.session_state.pop("diffs", None)
        st.session_state.pop("pdf_bytes", None)

    if mode == "demo":
        st.session_state["diffs"] = demo_items
        st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1

    if 'before_path' in locals() and before_path and 'after_path' in locals() and after_path and os.path.exists(before_path) and os.path.exists(after_path):
        st.markdown('<div class="web-card">', unsafe_allow_html=True)
        st.subheader("🔍 Visual Comparison")
        st.image([before_path, after_path], caption=["Move-In / Baseline", "Move-Out"], width=300)
        
        taken_before = report.get_image_timestamp(before_path)
        taken_after = report.get_image_timestamp(after_path)
        st.caption(f"Dates found in the photo files: Move-in ({taken_before}) | Move-Out ({taken_after})")
        
        # Safely check for missing timestamps without crashing if report.NOT_FOUND is missing
        not_found_val = getattr(report, "NOT_FOUND", "Not found")
        if taken_before in (not_found_val, None, "Not found") or taken_after in (not_found_val, None, "Not found"):
            st.warning(
                "At least one photo has no date stored in its file (some apps and editors remove it). "
                "The report will say the date was not found. Use the original photo files if you have them."
            )
        if mode == "demo":
            st.info("You are looking at a saved example result. No AI call was made. Upload your own photos to run the AI.")