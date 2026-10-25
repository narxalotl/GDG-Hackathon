import hmac
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
MAX_LIVE_RUNS = int(os.environ.get("MAX_LIVE_RUNS", "10"))

st.set_page_config(
    page_title="Move-In/Move-Out Evidence Tool",
    layout="wide",
    page_icon="🏡"
)

try:
    if not os.environ.get("GEMINI_API_KEY") and "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = str(st.secrets["GEMINI_API_KEY"])
except Exception:
    pass

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

# Header Card
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
    return None, None, None

demo_before, demo_after, demo_items = load_demo()
demo_ok = bool(demo_before and demo_after and demo_items is not None)
fake_mode = os.environ.get("USE_FAKE") == "1"   # test mode: pipeline.py returns example data, no key needed


class DemoFile:
    """Stands in for an uploaded file, so the saved example uses the same code as real uploads."""
    def __init__(self, path):
        self.name = os.path.basename(path)
        self._path = path

    def getbuffer(self):
        with open(self._path, "rb") as f:
            return f.read()


def get_office_password():
    """The leasing office password comes from LEASING_PASSWORD (.env or hosting secrets). Never hard-code it."""
    pw = os.environ.get("LEASING_PASSWORD")
    if not pw:
        try:
            pw = st.secrets["LEASING_PASSWORD"]
        except Exception:
            pw = None
    return str(pw) if pw else None


if "workdir" not in st.session_state:
    st.session_state["workdir"] = tempfile.mkdtemp(prefix="evidence")
WORKDIR = st.session_state["workdir"]

if "leasing_logged_in" not in st.session_state:
    st.session_state["leasing_logged_in"] = False

# Sidebar Navigation & Settings
st.sidebar.markdown("### 🧭 Portal Navigation")
st.sidebar.radio(
    "Navigation",
    ["Renters Portal"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")

# Secure Password-Protected Leasing Office Login in Sidebar
with st.sidebar.expander("🔐 Leasing Office Login"):
    lo_password = st.text_input("Password", type="password", key="leasing_password_input")
    if st.button("Unlock Dashboard", key="unlock_lo_btn"):
        office_pw = get_office_password()
        if not office_pw:
            st.error("The leasing office view is locked because no LEASING_PASSWORD is set.")
        elif hmac.compare_digest(lo_password.encode(), office_pw.encode()):
            st.session_state["leasing_logged_in"] = True
            st.success("Unlocked!")
            st.rerun()
        else:
            st.error("Incorrect password.")

if st.session_state["leasing_logged_in"]:
    if st.sidebar.button("🔒 Lock Leasing Office View", key="lock_lo_btn"):
        st.session_state["leasing_logged_in"] = False
        st.rerun()

st.sidebar.markdown(f"**System Status:** <span style='color: #34a853; font-weight: bold;'>🟢 Online</span>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# If Leasing Office view is active, show Admin Dashboard
if st.session_state["leasing_logged_in"]:
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.subheader("🏢 Leasing Office Inspection Dashboard")
    st.write("Review incoming tenant inspection submissions and evidence records.")
    
    all_subs = []
    try:
        for renter in submissions.list_renters():
            r_name = renter.get("name", "N/A")
            r_unit = renter.get("unit", "N/A")
            for s in submissions.list_submissions(renter.get("id")):
                s["tenant_name"] = r_name
                s["tenant_unit"] = r_unit
                all_subs.append(s)
    except Exception:
        pass

    if not all_subs:
        st.info("No tenant inspection reports have been submitted yet.")
    else:
        table_data = []
        for s in all_subs:
            table_data.append({
                "Tenant Name": s.get("tenant_name", "N/A"),
                "Unit / Apt": s.get("tenant_unit", "N/A"),
                "Room / Area": s.get("room", "N/A"),
                "Jurisdiction": s.get("jurisdiction", "N/A"),
                "Uploaded At": s.get("uploaded_at", "N/A")
            })
        st.dataframe(table_data, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

else:
    # Renters Portal Inputs
    tenant_name = st.sidebar.text_input("Tenant Name", "Jane Doe")
    unit_number = st.sidebar.text_input("Apartment / Unit Number", "Unit 4B")

    st.sidebar.header("Inspection Settings")
    inspection_date = st.sidebar.date_input(
        "Inspection Date", value=date.today(),
        help="Shown in report as entered date."
    )
    dmv_jurisdiction = st.sidebar.selectbox(
        "DMV Jurisdiction",
        [
            "Virginia (VRLTA)",
            "Maryland Security Deposit Law",
            "District of Columbia (DC Tenant Bill of Rights)"
        ]
    )
    ai_sensitivity = st.sidebar.slider(
        "AI Sensitivity Level", min_value=1, max_value=5, value=3,
        help="Higher sensitivity reports smaller scuffs."
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
            help="A free key from Google AI Studio."
        )
        user_key = (user_key or "").strip()
        if fake_mode:
            st.sidebar.caption("AI access: TEST MODE (fake example data, no AI call)")
        elif user_key:
            st.sidebar.caption("AI access: your own key")
        elif have_server_key():
            st.sidebar.caption(f"AI access: the app's shared key ({MAX_LIVE_RUNS} analyses per session)")
        else:
            st.sidebar.caption("AI access: no key set. Load the saved example, or paste your own key above.")
    
    st.sidebar.caption(f"AI model: {MODEL}")

    if st.sidebar.button("Reset Session"):
        shutil.rmtree(st.session_state.get("workdir", ""), ignore_errors=True)
        for key in list(st.session_state.keys()):
            if key != "leasing_logged_in":
                del st.session_state[key]
        st.rerun()

    # Summary Metrics Row
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="web-card" style="text-align: center; padding: 15px;"><p style="color: #ea4335; font-size: 0.8rem; margin:0;">ACTIVE JURISDICTION</p><h4 style="color: #4285F4; margin:5px 0 0;">{dmv_jurisdiction.split()[0]}</h4></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="web-card" style="text-align: center; padding: 15px;"><p style="color: #ea4335; font-size: 0.8rem; margin:0;">SELECTED ROOM</p><h4 style="color: #34A853; margin:5px 0 0;">{room_name}</h4></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="web-card" style="text-align: center; padding: 15px;"><p style="color: #ea4335; font-size: 0.8rem; margin:0;">AI ENGINE</p><h4 style="color: #FBBC05; margin:5px 0 0;">{MODEL}</h4></div>', unsafe_allow_html=True)

    # Multi-Issue Upload Section
    st.markdown('<div class="web-card">', unsafe_allow_html=True)
    st.subheader("📷 Upload Audit Photos")
    st.info(
        "💡 **Tip for Best AI Accuracy:** Try to take your Move-Out photo from the "
        "**same angle and lighting** as your Move-In photo. Consistent framing helps "
        "the AI accurately distinguish real damage from shadows or perspective shifts!\n\n"
        "📌 **Note:** You can add a maximum of **5 pairs of issues** (Move-In + Move-Out pairs, 10 pictures total max)."
    )

    if "num_issue_pairs" not in st.session_state:
        st.session_state.num_issue_pairs = 1

    batched_uploaded_files = []

    for i in range(st.session_state.num_issue_pairs):
        if st.session_state.num_issue_pairs > 1:
            st.markdown(f"**Issue Pair {i + 1} of {st.session_state.num_issue_pairs}**")
        
        col1, col2 = st.columns(2)
        with col1:
            b_file = st.file_uploader(f"Upload Move-In (Before) Photo #{i + 1}", type=["jpg", "jpeg", "png"], key=f"unique_before_key_{i}")
        with col2:
            a_file = st.file_uploader(f"Upload Move-Out (After) Photo #{i + 1}", type=["jpg", "jpeg", "png"], key=f"unique_after_key_{i}")
        
        if b_file or a_file:
            batched_uploaded_files.append({"index": i, "before": b_file, "after": a_file})
        
        if i < st.session_state.num_issue_pairs - 1:
            st.markdown("---")

    if st.session_state.num_issue_pairs < 5:
        if st.button("➕ Add another issue", key="unique_global_add_issue_btn"):
            st.session_state.num_issue_pairs += 1
            st.rerun()
    else:
        st.caption("Maximum limit of 5 issue pairs (10 photos total) reached.")

    st.markdown('</div>', unsafe_allow_html=True)

    # The saved example behaves like one uploaded pair (no key, no AI call)
    if batched_uploaded_files:
        # real photos were uploaded: leave the saved example
        if st.session_state.pop("demo_loaded", None):
            st.session_state["diffs_dict"] = {}
        st.session_state.pop("use_demo", None)
    elif st.session_state.get("use_demo") and demo_ok:
        batched_uploaded_files = [{"index": 0, "before": DemoFile(demo_before), "after": DemoFile(demo_after)}]
        if not st.session_state.get("demo_loaded"):
            st.session_state["diffs_dict"] = {0: demo_items}
            st.session_state["demo_loaded"] = True
        st.info("You are looking at a saved example result. No AI call was made. "
                "Upload your own photos to run the AI.")
        if st.button("Close the saved example", key="close_demo_btn"):
            for k in ("use_demo", "demo_loaded", "diffs_dict", "pair_sigs", "pair_ver", "pdf_bytes"):
                st.session_state.pop(k, None)
            st.rerun()

    # Process all uploaded issue pairs independently
    if batched_uploaded_files:
        if "diffs_dict" not in st.session_state:
            st.session_state["diffs_dict"] = {}
        pair_sigs = st.session_state.setdefault("pair_sigs", {})
        pair_ver = st.session_state.setdefault("pair_ver", {})
        pair_paths = {}
        all_confirmed_items = []

        for item in batched_uploaded_files:
            i = item["index"]
            b_file = item["before"]
            a_file = item["after"]
            
            st.markdown('<div class="web-card">', unsafe_allow_html=True)
            st.subheader(f"Visual Comparison & Analysis — Issue Pair #{i + 1}")
            
            b_name = b_file.name if b_file else f"dummy_before_{i}.jpg"
            a_name = a_file.name if a_file else f"dummy_after_{i}.jpg"
            
            before_ext = os.path.splitext(b_name)[1] or ".jpg"
            after_ext = os.path.splitext(a_name)[1] or ".jpg"

            before_path = os.path.join(WORKDIR, f"before_{i}" + before_ext)
            after_path = os.path.join(WORKDIR, f"after_{i}" + after_ext)
            pair_paths[i] = (before_path, after_path)

            # New photos in this slot: forget the old analysis so it can't be shown for the wrong photos
            sig = (getattr(b_file, "name", None), getattr(b_file, "size", None),
                   getattr(a_file, "name", None), getattr(a_file, "size", None))
            if i in pair_sigs and pair_sigs[i] != sig:
                st.session_state["diffs_dict"].pop(i, None)
                pair_ver[i] = pair_ver.get(i, 0) + 1
                st.session_state.pop("pdf_bytes", None)
            pair_sigs[i] = sig

            if b_file:
                with open(before_path, "wb") as f:
                    f.write(b_file.getbuffer())

            if a_file:
                with open(after_path, "wb") as f:
                    f.write(a_file.getbuffer())

            paths_to_show = []
            captions = []
            if b_file and os.path.exists(before_path):
                paths_to_show.append(before_path)
                captions.append(f"Move-In #{i + 1}")
            if a_file and os.path.exists(after_path):
                paths_to_show.append(after_path)
                captions.append(f"Move-Out #{i + 1}")

            if paths_to_show:
                st.image(paths_to_show, caption=captions, width=300)

                taken_before = report.get_image_timestamp(before_path) if b_file else "N/A"
                taken_after = report.get_image_timestamp(after_path) if a_file else "N/A"
                st.caption(f"Dates found in photo files: Move-in ({taken_before}) | Move-Out ({taken_after})")

            if st.button(f"🔍 Run Analysis for Issue #{i + 1}", type="primary", key=f"run_analysis_btn_{i}"):
                if not (b_file and a_file):
                    st.warning("Please upload both the move-in and the move-out photo first.")
                elif not (fake_mode or user_key or have_server_key()):
                    st.warning("No AI key is available here. Paste your own free Gemini API key in the sidebar "
                               "(under AI access), or load the saved example.")
                elif not (fake_mode or user_key) and st.session_state.get("live_runs", 0) >= MAX_LIVE_RUNS:
                    st.warning(f"This session has used its {MAX_LIVE_RUNS} analyses on the app's shared key. "
                               "Paste your own free Gemini API key in the sidebar to keep going.")
                else:
                    with st.spinner(f"Analyzing Issue #{i + 1} with {MODEL}... this can take up to a minute."):
                        try:
                            diffs = compare_photos(
                                before_path, after_path,
                                sensitivity=ai_sensitivity,
                                api_key=user_key or None
                            )
                            st.session_state["diffs_dict"][i] = diffs
                            pair_ver[i] = pair_ver.get(i, 0) + 1
                            st.session_state.pop("pdf_bytes", None)
                            if not (fake_mode or user_key):
                                st.session_state["live_runs"] = st.session_state.get("live_runs", 0) + 1
                            st.success(f"Analysis complete for Issue #{i + 1}!")
                        except PipelineError as e:
                            st.error(str(e))
                            st.caption("If the AI is busy or out of quota, you can paste your own free Gemini API "
                                       "key in the sidebar, or load the saved example.")

            diffs = st.session_state["diffs_dict"].get(i)
            if diffs is not None:
                st.markdown("---")
                st.subheader(f"📝 Review Findings for Issue #{i + 1}")
                if not diffs:
                    st.success("The AI did not find meaningful differences for this pair.")
                else:
                    TENANT_VIEWS = [
                        "Not sure yet",
                        "Normal wear and tear",
                        "Already there at move-in",
                        "Damage I accept responsibility for"
                    ]
                    for idx, diff_item in enumerate(diffs):
                        k = f"issue_{i}_{pair_ver.get(i, 0)}_{idx}"
                        st.markdown(f"**Item {idx + 1}: {diff_item.get('category', 'other').capitalize()}** in {room_name} ({diff_item.get('location', '')})")
                        st.write(f"AI finding: {diff_item.get('description', '')}")
                        st.caption(f"Severity: {diff_item.get('severity', 'unknown')} | Confidence: {diff_item.get('confidence', 'unknown')}")

                        include = st.checkbox("This difference is real. Include it in the report.", key=f"include_{k}")
                        view = st.selectbox("Your view of this item", TENANT_VIEWS, key=f"view_{k}")

                        if view in ("Normal wear and tear", "Already there at move-in"):
                            st.markdown(f'<span class="pill-normal">{view}</span>', unsafe_allow_html=True)
                        elif view == "Not sure yet":
                            st.markdown(f'<span class="pill-neutral">{view}</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="pill-damage">{view}</span>', unsafe_allow_html=True)

                        tenant_note = st.text_input(
                            f"Add your note for Issue #{i + 1}, Item {idx + 1} (optional):",
                            key=f"note_{k}",
                            placeholder="e.g., Scuff present at move-in."
                        )

                        if include:
                            all_confirmed_items.append(dict(
                                diff_item,
                                view=view,
                                tenant_view="" if view == "Not sure yet" else view,
                                tenant_note=tenant_note,
                                issue_group=f"Issue #{i + 1}"
                            ))
            st.markdown('</div>', unsafe_allow_html=True)

        complete = [it["index"] for it in batched_uploaded_files if it["before"] and it["after"]]
        first_paths = pair_paths[complete[0]] if complete else None

        # Global actions for all processed issue pairs
        if all_confirmed_items:
            st.markdown('<div class="web-card">', unsafe_allow_html=True)
            st.subheader("📤 Finalize & Submit Report")
            
            with st.expander("Share these findings with the leasing office (optional)"):
                share_name = st.text_input("Your name", key="share_name", value=tenant_name)
                share_unit = st.text_input("Apartment / unit", key="share_unit", value=unit_number)
                share_ok = st.checkbox(
                    "I agree to share these photos and confirmed items with the leasing office.",
                    key="share_ok"
                )
                if st.button("Send to leasing office", key="send_lo_multi"):
                    if not (share_name.strip() and share_unit.strip()):
                        st.warning("Please enter your name and unit.")
                    elif not share_ok:
                        st.warning("Please check the box to confirm you agree to share.")
                    elif first_paths is None:
                        st.warning("Upload at least one complete pair (move-in and move-out photo) first.")
                    else:
                        submissions.save_submission(
                            share_name,
                            share_unit,
                            room_name,
                            dmv_jurisdiction,
                            first_paths[0],
                            first_paths[1],
                            all_confirmed_items
                        )
                        st.success("Sent successfully to the leasing office!")

            if st.button("Generate PDF Report & Draft Letter", type="primary", use_container_width=True, key="generate_pdf_btn_multi"):
                if first_paths is None:
                    st.warning("Upload at least one complete pair (move-in and move-out photo) first.")
                else:
                    output_pdf = os.path.join(WORKDIR, "evidence_report.pdf")   # private to this visitor
                    try:
                        report.build_report(
                            room_name=room_name,
                            inspection_date=inspection_date,
                            dmv_jurisdiction=dmv_jurisdiction,
                            confirmed_items=all_confirmed_items,
                            before_path=first_paths[0],
                            after_path=first_paths[1],
                            output_path=output_pdf,
                            inspector_role="Renters"
                        )
                        with open(output_pdf, "rb") as pdf_file:
                            st.session_state["pdf_bytes"] = pdf_file.read()
                    except Exception as e:
                        st.error(f"Could not build the report: {e}")
            if st.session_state.get("pdf_bytes"):
                st.download_button(
                    label="📥 Download Evidence Report (PDF)",
                    data=st.session_state["pdf_bytes"],
                    file_name=f"{room_name.replace(' ', '_').replace('/', '-')}_Evidence_Report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="download_pdf_btn_multi"
                )
            st.markdown('</div>', unsafe_allow_html=True)

    elif demo_ok:
        st.markdown('<div class="web-card">', unsafe_allow_html=True)
        st.write("No photos handy, or no API key? Try the saved example. It needs no key and makes no AI call.")
        if st.button("Load the saved example", key="load_demo_btn_unique"):
            st.session_state["use_demo"] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)