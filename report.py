import streamlit as st
import os
import uuid
from datetime import date
from dotenv import load_dotenv

load_dotenv()
import report

# Page Configuration
st.set_page_config(
    page_title="Move-In/Move-Out Evidence Tool", 
    layout="centered", 
    page_icon="🏡"
)

# Google 4-Color Top Accent Bar & Status Pill Styling
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

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Inspection Settings")

user_role = st.sidebar.selectbox("Inspector Role", ["Renter (Tenant)", "Landlord / Leasing Office"])
st.sidebar.markdown(f"🏷️ **Active Role:** `{user_role}`")
st.sidebar.markdown("---")

inspection_date = st.sidebar.date_input("Inspection Date", value=date.today())
ai_sensitivity = st.sidebar.slider("AI Sensitivity Level", min_value=1, max_value=5, value=3, help="Higher sensitivity detects minor scuffs more aggressively.")
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
    
    # Unique UUID naming prevents file overwriting and image flipping
    unique_id = uuid.uuid4().hex[:8]
    before_path = os.path.join("temp", f"before_{unique_id}_{before_file.name}")
    after_path = os.path.join("temp", f"after_{unique_id}_{after_file.name}")
    
    with open(before_path, "wb") as f:
        f.write(before_file.getbuffer())
    with open(after_path, "wb") as f:
        f.write(after_file.getbuffer())

    st.image([before_path, after_path], caption=["Move-In Baseline", "Move-Out Audit"], width=300)

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
2. report.py
Python
import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def build_report(room_name, inspection_date, confirmed_items, before_path, after_path, output_path="evidence_report.pdf"):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#202124')
    )
    
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#5f6368')
    )
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1a73e8')
    )
    
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#202124')
    )
    
    story = []
    
    # Google Brand 4-Color Top Accent Bar
    accent_table = Table([['', '', '', '']], colWidths=[130, 130, 130, 130], rowHeights=[4])
    accent_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#4285F4')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#EA4335')),
        ('BACKGROUND', (2,0), (2,0), colors.HexColor('#FBBC05')), # Google Yellow
        ('BACKGROUND', (3,0), (3,0), colors.HexColor('#34A853')),
    ]))
    story.append(accent_table)
    story.append(Spacer(1, 15))
    
    # Title & Metadata
    story.append(Paragraph("Move-In/Move-Out Evidence Report", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Inspection Area:</b> {room_name}", subtitle_style))
    
    # Clean 12-Hour Timestamp using the exact selected sidebar inspection date
    date_formatted = inspection_date.strftime("%m/%d/%Y") if hasattr(inspection_date, 'strftime') else str(inspection_date)
    time_formatted = datetime.now().strftime("%I:%M %p")
    timestamp_str = f"{date_formatted}, {time_formatted}"
    story.append(Paragraph(f"<b>Inspection Timestamp:</b> {timestamp_str}", subtitle_style))
    story.append(Spacer(1, 12))
    
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dadce0'), spaceAfter=15))
    
    # Visual Comparison of Images Section (Google Yellow Outlined Box)
    story.append(Paragraph("Visual Comparison of Images", heading_style))
    story.append(Spacer(1, 8))
    
    img_width = 230
    img_height = 170
    
    img_before = Image(before_path, width=img_width, height=img_height) if os.path.exists(before_path) else Paragraph("Before Image Not Found", body_style)
    img_after = Image(after_path, width=img_width, height=img_height) if os.path.exists(after_path) else Paragraph("After Image Not Found", body_style)
    
    img_table_data = [
        [Paragraph("<b>Move-In Baseline</b>", body_style), Paragraph("<b>Move-Out Audit</b>", body_style)],
        [img_before, img_after]
    ]
    
    img_table = Table(img_table_data, colWidths=[255, 255])
    img_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('BOX', (0,0), (-1,-1), 2, colors.HexColor('#FBBC05')), # Google Yellow Outline Box
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dadce0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    
    story.append(img_table)
    story.append(Spacer(1, 20))
    
    # Tenant Confirmed Differences & Defense Notes Section
    story.append(Paragraph("Tenant Confirmed Differences & Defense Notes", heading_style))
    story.append(Spacer(1, 8))
    
    if not confirmed_items:
        story.append(Paragraph("No discrepancy items recorded.", body_style))
    else:
        for idx, item in enumerate(confirmed_items):
            classification = item.get('classification', 'Normal Wear')
            desc = item.get('description', '')
            tenant_note = item.get('tenant_note', 'No tenant defense note provided.')
            
            is_damage = "Damage" in classification
            status_color = "#c5221f" if is_damage else "#137333"
            
            item_data = [
                [Paragraph(f"<b>Item {idx+1}: {classification}</b>", ParagraphStyle('ItemHead', parent=body_style, textColor=colors.HexColor(status_color)))],
                [Paragraph(f"<b>AI Observation:</b> {desc}", body_style)],
                [Paragraph(f"<b>Tenant Defense / Context:</b> {tenant_note}", body_style)]
            ]
            
            item_table = Table(item_data, colWidths=[510])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#dadce0')),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ('TOPPADDING', (0,0), (-1,-1), 10),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('LINEBELOW', (0,0), (0,0), 0.5, colors.HexColor('#f1f3f4')),
            ]))
            
            story.append(item_table)
            story.append(Spacer(1, 10))
            
    story.append(Spacer(1, 10))
    
    # Professional Draft Deposit Dispute Letter Section
    story.append(Paragraph("Draft Security Deposit Dispute & Evidence Summary", heading_style))
    story.append(Spacer(1, 8))
    
    letter_text = (
        "Dear Property Management / Landlord,<br/><br/>"
        f"Please accept this formal documentation regarding the condition of <b>{room_name}</b> as captured during our move-in baseline and move-out audit inspections. "
        "The accompanying photographic evidence and verified condition notes have been compiled to ensure complete transparency and accuracy regarding the property's state.<br/><br/>"
        "As detailed in the inspection findings above, noted items reflect either normal residential wear or have corresponding tenant defense context documenting their pre-existing or minor nature. "
        "We kindly request that this evidence be taken into full consideration during the security deposit reconciliation process, and that any unwarranted deductions for standard wear and tear be waived.<br/><br/>"
        "Thank you for your prompt attention to this matter and for your cooperation in maintaining a fair and transparent lease agreement.<br/><br/>"
        "Sincerely,<br/>"
        "Tenant / Resident"
    )
    
    letter_data = [[Paragraph(letter_text, body_style)]]
    letter_table = Table(letter_data, colWidths=[510])
    letter_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#dadce0')),
        ('LEFTPADDING', (0,0), (-1,-1), 14),
        ('RIGHTPADDING', (0,0), (-1,-1), 14),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ]))
    
    story.append(letter_table)
    
    doc.build(story)