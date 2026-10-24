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
    
    # Google Brand 4-Color Top Accent Bar (Blue, Red, Google Yellow, Green)
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
    
    # Clean 12-Hour Timestamp using selected inspection date
    date_formatted = inspection_date.strftime("%m/%d/%Y") if hasattr(inspection_date, 'strftime') else str(inspection_date)
    time_formatted = datetime.now().strftime("%I:%M %p")
    timestamp_str = f"{date_formatted}, {time_formatted}"
    story.append(Paragraph(f"<b>Inspection Timestamp:</b> {timestamp_str}", subtitle_style))
    story.append(Spacer(1, 12))
    
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dadce0'), spaceAfter=15))
    
    # Visual Comparison Section ("Visual Comparison of Images") with Google Yellow Box
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