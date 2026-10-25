# app.py
import json
import os
import shutil
import tempfile
import submissions
from datetime import date
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
import report
from pipeline import compare_photos, PipelineError, MODEL, have_server_key

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

# Secrets check
try:
    if not os.environ.get("GEMINI_API_KEY") and "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = str(st.secrets["GEMINI_API_KEY"])
except Exception:
    pass

# Modern SaaS CSS styling with Google top bar and cards
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

# Top Navigation Bar with Portal Role Selector
nav_col1, nav_col2, nav_col3 = st.columns([3, 4, 2])
with nav_col1:
    st.markdown("### 🏡 Move-In/Move-Out Evidence Tool")
    st.markdown("<p style='color: #8b949e; font-size: 0.85rem; margin-top: -15px;'>GDG Build with AI x Hacktoberfest 2026</p>", unsafe_allow_html=True)

with nav_col3:
    user_role = st.selectbox(
        "Portal Access", 
        ["Renter (Tenant)", "Landlord / Leasing Office"],
        label_visibility="collapsed"
    )
    st.markdown(f"<p style='text-align: right; font-size: 0.75rem; color: #8b949e; margin-top: -5px;'>Active Portal: <span style='color: #4285F4; font-weight: bold;'>{user_role}</span></p>", unsafe_allow_html=True)

st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)

# App Header Card
with st.container():
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.title("Move-In/Move-Out Evidence Tool")
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

# --- SIDEBAR: SETTINGS ---
st.sidebar.header("Inspection Settings")

st.sidebar.markdown(f"**Active Role:** {user_role}")
st.sidebar.markdown("---")

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
    help="Higher sensitivity reports smaller scuffs and marks. Lower sensitivity reports only clear problems."
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
    st.text_input(
        "Your own Gemini API key", type="password", key="user_key",
        help="A free key from Google AI Studio. It is used only to analyze your photos and is kept only for this browser session. This app does not save it."
    )

user_key = (st.session_state.get("user_key") or "").strip()
if user_key:
    st.sidebar.caption("AI access: your own key")
elif have_server_key():
    st.sidebar.caption(f"AI access: the app's shared key ({MAX_LIVE_RUNS} analyses per session)")
else:
    st.sidebar.caption("AI access: no key set. Load the saved example, or paste your own key above.")

st.sidebar.caption(f"AI model: {MODEL}")

if st.sidebar.button("🔄 Reset Session"):
    shutil.rmtree(st.session_state.get("workdir", ""), ignore_errors=True)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- MAIN UPLOAD SECTION ---
st.markdown('<div class="web-card">', unsafe_allow_html=True)
st.subheader("📸 Upload Audit Photos")
col1, col2 = st.columns(2)
with col1:
    before_file = st.file_uploader("Upload Before Photo", type=["jpg", "jpeg", "png"], key="before")
with col2:
    after_file = st.file_uploader("Upload After Photo", type=["jpg", "jpeg", "png"], key="after")
st.markdown('</div>', unsafe_allow_html=True)

TENANT_VIEWS = [
    "Not sure yet",
    "Normal wear and tear",
    "Already there at move-in",
    "Damage I accept responsibility for",
]

mode, before_path, after_path, signature, demo_items = None, None, None, None, None

if before_file and after_file:
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
elif demo:
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.write("No photos handy, or no API key? Try the saved example. It needs no key and makes no AI call.")
    if st.button("Load the saved example"):
        st.session_state["use_demo"] = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

if st.session_state.get("signature") != signature:
    st.session_state["signature"] = signature
    st.session_state.pop("diffs", None)
    st.session_state.pop("pdf_bytes", None)

if mode == "demo":
    st.session_state["diffs"] = demo_items
    st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1

if before_path and after_path and os.path.exists(before_path) and os.path.exists(after_path):
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.subheader("🔍 Visual Comparison")
    st.image([before_path, after_path], caption=["Move-In", "Move-Out"], width=300)

    taken_before = report.get_image_timestamp(before_path)
    taken_after = report.get_image_timestamp(after_path)
    st.caption(f"Dates found in the photo files: Move-in ({taken_before}) | Move-out ({taken_after})")
    
    if report.NOT_FOUND in (taken_before, taken_after):
        st.warning(
            "At least one photo has no date stored in its file (some apps and editors remove it). "
            "The report will say the date was not found. Use the original photo files if you have them."
        )

    if mode == "demo":
        st.info("You are looking at a saved example result. No AI call was made. Upload your own photos to run the AI.")
        if st.button("Close the saved example"):
            for k in ("use_demo", "signature", "diffs", "pdf_bytes"):
                st.session_state.pop(k, None)
            st.rerun()
    else:
        if st.button("Run Analysis", type="primary", use_container_width=True):
            if not user_key and not have_server_key():
                st.warning(
                    "No AI key is available here. Paste your own free Gemini API key in the sidebar "
                    "(under AI access), or load the saved example."
                )
            elif not user_key and st.session_state.get("live_runs", 0) >= MAX_LIVE_RUNS:
                st.warning(
                    f"This session has used its {MAX_LIVE_RUNS} analyses on the app's shared key. "
                    "Paste your own free Gemini API key in the sidebar to keep going."
                )
            else:
                with st.spinner(f"Analyzing differences with Gemma 4 (sensitivity {ai_sensitivity})... this can take up to a minute."):
                    try:
                        st.session_state["diffs"] = compare_photos(
                            before_path, after_path,
                            sensitivity=ai_sensitivity, api_key=user_key or None
                        )
                        st.session_state["run_id"] = st.session_state.get("run_id", 0) + 1
                        st.session_state.pop("pdf_bytes", None)
                        if not user_key:
                            st.session_state["live_runs"] = st.session_state.get("live_runs", 0) + 1
                        st.success("Analysis complete!")
                    except PipelineError as e:
                        st.session_state.pop("diffs", None)
                        st.error(str(e))
                        st.caption(
                            "If the AI is busy or out of quota, you can paste your own free Gemini API key "
                            "in the sidebar, or load the saved example."
                        )
    st.markdown('</div>', unsafe_allow_html=True)

diffs = st.session_state.get("diffs")
if diffs is not None:
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.subheader("✍️ Review Possible Differences & Add Your Notes")
    confirmed_items = []
    if not diffs:
        st.success("The AI did not find meaningful differences between these photos.")
    else:
        st.caption("Check the box for each difference that is real. Only checked items go in the report.")
        run_id = st.session_state.get("run_id", 0)
        for idx, item in enumerate(diffs):
            k = f"{run_id}_{idx}"
            st.markdown(f"**Item {idx+1}: {item.get('category', 'other').capitalize()}** in {room_name} ({item.get('location', '')})")
            st.write(f"AI finding: {item.get('description', '')}")
            st.caption(f"Severity: {item.get('severity', 'unknown')} | AI confidence: {item.get('confidence', 'unknown')}")
            
            include = st.checkbox("This difference is real. Include it in the report.", key=f"include_{k}")
            
            view = st.selectbox("Your view of this item", TENANT_VIEWS, key=f"view_{k}")
            if view in ("Normal wear and tear", "Already there at move-in"):
                st.markdown(f'<span class="pill-normal">{view}</span>', unsafe_allow_html=True)
            elif view == "Not sure yet":
                st.markdown(f'<span class="pill-neutral">{view}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="pill-damage">{view}</span>', unsafe_allow_html=True)
            
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
            with st.expander("Share these findings with the leasing office (optional)"):
                share_name = st.text_input("Your name", key="share_name")
                share_unit = st.text_input("Apartment / unit", key="share_unit")
                share_ok = st.checkbox(
                    "I agree to share these photos and the items I confirmed with the leasing office.",
                    key="share_ok"
                )
                if st.button("Send to leasing office"):
                    if not (share_name.strip() and share_unit.strip()):
                        st.warning("Please enter your name and unit.")
                    elif not share_ok:
                        st.warning("Please check the box to confirm you agree to share.")
                    else:
                        submissions.save_submission(
                            name=share_name,
                            unit=share_unit,
                            room=room_name,
                            jurisdiction=dmv_jurisdiction,
                            before_path=before_path,
                            after_path=after_path,
                            items=confirmed_items,
                        )
                        st.success("Sent. The leasing office can now see this room's photos and confirmed items.")

        if st.button("Generate Official PDF Report & Dispute Letter", type="primary", use_container_width=True):
            output_pdf = "evidence_report.pdf"
            current_date = inspection_date if 'inspection_date' in locals() else date.today()
            items_to_report = confirmed_items if 'confirmed_items' in locals() else []
            
            report.build_report(
                room_name=room_name,
                inspection_date=current_date,
                dmv_jurisdiction=dmv_jurisdiction,
                confirmed_items=items_to_report,
                before_path=before_path,
                after_path=after_path,
                output_path=output_pdf,
                inspector_role=user_role
            )
            
            with open(output_pdf, "rb") as pdf_file:
                st.download_button(
                    label="📥 Download Signed Evidence Report (PDF)",
                    data=pdf_file,
                    file_name=f"{room_name.replace(' ', '_')}_Evidence_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
    st.markdown('</div>', unsafe_allow_html=True)