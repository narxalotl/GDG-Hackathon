"""Leasing Office page.

Streamlit shows any file in the pages/ folder in the sidebar menu of app.py.
The leasing office signs in, clicks a renter, and sees what that renter shared:
the photos, when they were uploaded, and the issues the renter confirmed.
"""
import hmac
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
import report
import submissions

st.set_page_config(page_title="Leasing Office | Evidence Tool", layout="wide", page_icon="🏢")


def get_office_password():
    pw = os.environ.get("LEASING_PASSWORD")
    if not pw:
        try:
            pw = st.secrets["LEASING_PASSWORD"]
        except Exception:
            pw = None
    return str(pw) if pw else None


def fmt_dt(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%b %d, %Y, %I:%M %p")
    except Exception:
        return str(iso)


st.title("Leasing Office")

# --- Sign-in (shared password; locked if none is configured) ---
password = get_office_password()
sample = submissions.demo_data()

if not st.session_state.get("office_ok") and not st.session_state.get("office_demo"):
    # Anyone can look at made-up sample data. Real renter submissions stay behind the password.
    if sample:
        st.info("**Judges and visitors:** you can preview this page with sample data. No password is needed, "
                "and no real renter's information is shown.")
        if st.button("Preview with sample data", type="primary"):
            st.session_state["office_demo"] = True
            st.rerun()
        st.markdown("---")
        st.subheader("Leasing office sign-in")
        st.caption("Real submissions from renters need the leasing office password.")
    if not password:
        st.error("Real submissions are locked because no password is set. Set LEASING_PASSWORD in the .env file "
                 "(or in the hosting platform's secrets) and restart the app.")
        st.stop()
    with st.form("office_login"):
        entered = st.text_input("Leasing office password", type="password")
        if st.form_submit_button("Sign in"):
            if hmac.compare_digest(entered.encode(), password.encode()):
                st.session_state["office_ok"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()

if st.sidebar.button("Sign out" if st.session_state.get("office_ok") else "Exit sample preview"):
    for k in ("office_ok", "office_demo", "selected_renter"):
        st.session_state.pop(k, None)
    st.rerun()

demo_mode = bool(st.session_state.get("office_demo")) and not st.session_state.get("office_ok")
if demo_mode:
    st.warning("**SAMPLE DATA.** This is an example built from the app's saved example. "
               "It is not a real renter's submission.")

st.info("You only see items the renter chose to share and confirmed as real. "
        "These are the renter's own findings and notes, not a ruling on who is responsible. "
        "This tool is not legal advice.")

renters = [sample[0]] if demo_mode else submissions.list_renters()
if not renters:
    st.write("No renter has shared anything yet. Submissions appear here after a renter "
             "confirms items and chooses **Send to leasing office** in the main app.")
    st.stop()

left, right = st.columns([1, 3])

# --- Left: renter accounts ---
with left:
    st.subheader("Renters")
    query = st.text_input("Search by name or unit", placeholder="e.g. Smith or 4B").strip().lower()
    shown = [r for r in renters if query in f"{r['name']} {r['unit']}".lower()]
    if not shown:
        st.caption("No renters match that search.")

    ids = [r["id"] for r in renters]
    if st.session_state.get("selected_renter") not in ids:
        st.session_state["selected_renter"] = ids[0]

    for r in shown:
        is_selected = r["id"] == st.session_state["selected_renter"]
        if st.button(f"{r['name']} (Unit {r['unit']})", key=f"renter_{r['id']}",
                     type="primary" if is_selected else "secondary", use_container_width=True):
            st.session_state["selected_renter"] = r["id"]
            st.rerun()
        st.caption(f"{r['count']} upload(s) | last: {fmt_dt(r['last_upload'])}")

# --- Right: the selected renter's uploads ---
with right:
    renter = next(r for r in renters if r["id"] == st.session_state["selected_renter"])
    subs = [sample[1]] if demo_mode else submissions.list_submissions(renter["id"])
    total_issues = sum(len(s.get("items", [])) for s in subs)

    st.subheader(f"{renter['name']}, Unit {renter['unit']}")
    st.caption(f"{len(subs)} upload(s) | {total_issues} confirmed issue(s) in total")

    for sub in subs:
        with st.container(border=True):
            items = sub.get("items", [])
            st.markdown(f"### {sub.get('room', 'Room')}")
            st.write(f"**Uploaded:** {fmt_dt(sub.get('uploaded_at', ''))}")
            st.caption(f"Jurisdiction selected by renter: {sub.get('jurisdiction', 'not given')}")

            taken_before = report.get_image_timestamp(sub["before_path"])
            taken_after = report.get_image_timestamp(sub["after_path"])
            c1, c2 = st.columns(2)
            with c1:
                st.image(sub["before_path"], use_container_width=True,
                         caption=f"Move-in photo. Taken: {taken_before}")
                st.caption(f"SHA-256: {sub.get('before_sha256', '')[:16]}...")
            with c2:
                st.image(sub["after_path"], use_container_width=True,
                         caption=f"Move-out photo. Taken: {taken_after}")
                st.caption(f"SHA-256: {sub.get('after_sha256', '')[:16]}...")

            st.markdown(f"**Issues the renter confirmed ({len(items)})**")
            if not items:
                st.write("None.")
            for i, item in enumerate(items, start=1):
                st.markdown(f"**{i}. {str(item.get('category', 'other')).capitalize()}**, "
                            f"{item.get('severity', 'unknown')} severity")
                st.text(f"Where: {item.get('location', '')}")
                st.text(f"What the AI saw: {item.get('description', '')}")
                st.caption(f"AI confidence: {item.get('confidence', 'unknown')}")
                if item.get("tenant_view"):
                    st.text(f"Renter's view: {item['tenant_view']}")
                if item.get("tenant_note"):
                    st.text(f"Renter's note: {item['tenant_note']}")
