import hashlib
import io
import os
from datetime import datetime
from xml.sax.saxutils import escape
import dmv_laws
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, KeepTogether,
    Image as RLImage, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

VIEW_NORMAL = "Normal wear and tear"
VIEW_PREEXISTING = "Already there at move-in"
VIEW_RESPONSIBLE = "Damage I accept responsibility for"

def esc(value) -> str:
    """Make text safe for ReportLab Paragraphs."""
    return escape(str(value))

def fit_image(path: str, max_w: int = 225, max_h: int = 165) -> RLImage:
    """Show a photo upright and undistorted, shrunk to fit the box."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1200, 1200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    return RLImage(buf, width=w * scale, height=h * scale)

def get_file_hash(file_path: str) -> str:
    """SHA-256 fingerprint of an original photo file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

NOT_FOUND = "Not found in photo metadata"

def get_image_timestamp(image_path: str) -> str:
    """Date and time the photo was taken, read from EXIF metadata."""
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        values = dict(exif)
        values.update(exif.get_ifd(0x8769))
        for tag_id in (36867, 36868, 306):
            raw = values.get(tag_id)
            if raw:
                text = str(raw).strip().replace("\x00", "")
                try:
                    return datetime.strptime(text, "%Y:%m:%d %H:%M:%S").strftime("%m/%d/%Y, %I:%M %p")
                except ValueError:
                    return text
    except Exception:
        pass
    return NOT_FOUND

def view_of(item: dict) -> str:
    return str(item.get("tenant_view", "") or "").strip()

def view_color(view: str) -> str:
    if view in (VIEW_NORMAL, VIEW_PREEXISTING):
        return "#137333"  # green
    if view == VIEW_RESPONSIBLE:
        return "#c5221f"  # red
    return "#5f6368"      # gray

def build_letter(room_name: str, items: list, photo_dates=None, law_info=None) -> str:
    """Draft letter text built from what the TENANT chose, using active law info."""
    if law_info is None:
        law_info = dmv_laws.get_law_details("Virginia")

    dates_sentence = ""
    if photo_dates and NOT_FOUND not in photo_dates:
        dates_sentence = (f" According to the photo files' metadata, the move-in photo was taken on "
                          f"{photo_dates[0].split(',')[0]} and the move-out photo on {photo_dates[1].split(',')[0]}.")
    
    counts = {VIEW_NORMAL: 0, VIEW_PREEXISTING: 0, VIEW_RESPONSIBLE: 0, "": 0}
    for it in items:
        v = view_of(it)
        counts[v if v in counts else ""] += 1
        
    parts = []
    if counts[VIEW_NORMAL]:
        parts.append(f"{counts[VIEW_NORMAL]} item(s) are normal wear and tear")
    if counts[VIEW_PREEXISTING]:
        parts.append(f"{counts[VIEW_PREEXISTING]} item(s) were already present at move-in")
    if counts[VIEW_RESPONSIBLE]:
        parts.append(f"{counts[VIEW_RESPONSIBLE]} item(s) are damage I accept responsibility for")
    if counts[""]:
        parts.append(f"{counts['']} item(s) I have not yet classified")
        
    if parts:
        summary = ("In the attached report I reviewed the differences between my move-in and move-out photographs. "
                   "I have indicated that " + "; ".join(parts) + ". My notes on each item are included in the report.")
    else:
        summary = ("The attached report documents the condition of the area at move-in and move-out. "
                   "No differences were recorded.")
                   
    ask = "I ask that no deductions be made for normal wear and tear." if counts[VIEW_NORMAL] else ""
    
    return (
        "Dear Property Management / Landlord,<br/><br/>"
        f"I am writing about the security deposit for the unit at [Unit Address]. I documented the condition of the "
        f"<b>{esc(room_name)}</b> at move-in and move-out with photographs.{esc(dates_sentence)} The attached report records "
        f"a SHA-256 fingerprint (hash) of each original photo file.<br/><br/>"
        f"{esc(summary)} {esc(ask)}<br/><br/>"
        f"Please send me an itemized written accounting of any deductions from my security deposit and return the "
        f"remaining balance within the deadlines required by the <b>{esc(law_info['statute'])}</b> "
        f"(see the regional rules reference in the attached report).<br/><br/>"
        "Thank you for your attention to this matter.<br/><br/>"
        "Sincerely, <br/>[Tenant Name]<br/><br/>"
        "<font color='#C5221F'>[Edit this draft before sending: add your name and unit address and check that it says "
        "what you mean.]</font>"
    )

def build_report(room_name, confirmed_items, dmv_jurisdiction,
                 before_path, after_path, output_path="evidence_report.pdf",
                 inspection_date=None, inspector_role=None):
    """Write a PDF evidence report and return the file path."""
    is_tenant = inspector_role is None or any(w in inspector_role.lower() for w in ("tenant", "renter"))
    
    # FETCH DYNAMIC JURISDICTION LAW INFO
    law_info = dmv_laws.get_law_details(dmv_jurisdiction)

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
        'ReportTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=colors.HexColor('#202124'))
    subtitle_style = ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'], fontName='Helvetica',
        fontSize=10, leading=14, textColor=colors.HexColor('#5f6368'))
    heading_style = ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#1a73e8'))
    body_style = ParagraphStyle(
        'ReportBody', parent=styles['Normal'], fontName='Helvetica',
        fontSize=10, leading=14, textColor=colors.HexColor('#202124'))
    small_style = ParagraphStyle(
        'ReportSmall', parent=styles['Normal'], fontName='Helvetica',
        fontSize=8.5, leading=11, textColor=colors.HexColor('#5f6368'))
    disclaimer_style = ParagraphStyle(
        'ReportDisclaimer', parent=styles['Normal'], fontName='Helvetica',
        fontSize=9, leading=1.2, textColor=colors.HexColor('#c5221f'))
    th_style = ParagraphStyle(
        'ReportTH', parent=styles['Normal'], fontName='Helvetica-Bold',
        fontSize=10, leading=13, textColor=colors.white)
        
    story = []
    
    # Google Brand 4-Color Top Accent Bar
    accent_table = Table([['', '', '', '']], colWidths=[130, 130, 130, 130], rowHeights=[4])
    accent_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor('#4285F4')),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#EA4335')),
        ('BACKGROUND', (2,0), (2,0), colors.HexColor('#FBBC05')),
        ('BACKGROUND', (3,0), (3,0), colors.HexColor('#34A853')),
    ]))
    story.append(accent_table)
    story.append(Spacer(1, 15))
    
    # Title & Metadata
    story.append(Paragraph("Move-In/Move-Out Evidence Report", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Inspection Area:</b> {esc(room_name)} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Jurisdiction:</b> {esc(law_info['jurisdiction'])}", subtitle_style))
    
    if inspector_role:
        story.append(Paragraph(f"<b>Prepared by:</b> {esc(inspector_role)}", subtitle_style))
        
    before_taken = get_image_timestamp(before_path) if os.path.exists(before_path) else NOT_FOUND
    after_taken = get_image_timestamp(after_path) if os.path.exists(after_path) else NOT_FOUND
    note = " (from photo file metadata)"
    
    story.append(Paragraph(f"<b>Move-in photo taken:</b> {esc(before_taken)}{'' if before_taken == NOT_FOUND else note}", subtitle_style))
    story.append(Paragraph(f"<b>Move-out photo taken:</b> {esc(after_taken)}{'' if after_taken == NOT_FOUND else note}", subtitle_style))
    
    if inspection_date:
        date_text = inspection_date.strftime("%m/%d/%Y") if hasattr(inspection_date, "strftime") else str(inspection_date)
        story.append(Paragraph(f"<b>Inspection date:</b> {esc(date_text)}", subtitle_style))
        
    story.append(Paragraph(f"<b>Report generated:</b> {datetime.now().strftime('%m/%d/%Y, %I:%M %p')}", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>DISCLAIMER:</b> This tool helps you document conditions. It is not legal advice.", disclaimer_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dadce0'), spaceAfter=15))
    
    # Visual Comparison Section
    story.append(Paragraph("Visual Comparison of Images", heading_style))
    story.append(Spacer(1, 8))
    
    img_before = fit_image(before_path) if os.path.exists(before_path) else Paragraph("Before Image Not Found", body_style)
    img_after = fit_image(after_path) if os.path.exists(after_path) else Paragraph("After Image Not Found", body_style)
    
    img_table = Table([
        [Paragraph("<b>Move-In Baseline</b>", body_style), Paragraph("<b>Move-Out Audit</b>", body_style)],
        [img_before, img_after]
    ], colWidths=[255, 255])
    
    img_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('BOX', (0,0), (-1,-1), 2, colors.HexColor('#FBBC05')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dadce0')),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(img_table)
    story.append(Paragraph("Photos are resized for this report. The hashes below belong to the original files.", small_style))
    story.append(Spacer(1, 14))
    
    # Evidence integrity
    story.append(Paragraph("Evidence Integrity", heading_style))
    story.append(Spacer(1, 6))
    meta_rows = [[Paragraph("Photo", th_style), Paragraph("Photo taken (metadata)", th_style), Paragraph("SHA-256 file hash", th_style)]]
    
    for label, path in (("Move-In", before_path), ("Move-Out", after_path)):
        if os.path.exists(path):
            meta_rows.append([
                Paragraph(label, body_style),
                Paragraph(esc(get_image_timestamp(path)), body_style),
                Paragraph(get_file_hash(path), body_style)
            ])
            
    meta_table = Table(meta_rows, colWidths=[70, 120, 320])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4285F4')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dadce0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Paragraph("A SHA-256 hash is a fingerprint of a file. If the file is changed in any way, its hash changes.", small_style))
    story.append(Spacer(1, 16))
    
    # Tenant-confirmed differences and notes
    story.append(Paragraph("Confirmed Differences & Tenant Notes", heading_style))
    story.append(Spacer(1, 6))
    model_name = os.environ.get("GEMMA MODEL", "gemma-4-31b-it")
    story.append(Paragraph(f"These differences were suggested by an AI model ({esc(model_name)}), then reviewed and confirmed by the person who prepared this report. The AI can make mistakes.", small_style))
    story.append(Spacer(1, 8))
    
    if not confirmed_items:
        story.append(Paragraph("No discrepancy items recorded.", body_style))
    else:
        for idx, item in enumerate(confirmed_items):
            view = view_of(item)
            label = view if view else "Not classified by the tenant"
            note = str(item.get('tenant_note', '') or '').strip()
            where = str(item.get('location', '') or '').strip()
            category = str(item.get('category', 'other')).capitalize()
            detail = f"{esc(item.get('description', ''))} (Severity: {esc(str(item.get('severity', 'unknown')).capitalize())}, AI confidence: {esc(str(item.get('confidence', 'unknown')).capitalize())})"
            
            head_style = ParagraphStyle('ItemHead', parent=body_style, textColor=colors.HexColor(view_color(view)))
            item_data = [
                [Paragraph(f"<b>Item {idx+1}: {esc(label)}</b>", head_style)],
                [Paragraph(f"<b>AI observation</b> ({esc(category)}" + (f", {esc(where)}" + ")" if where else ")") + f": {detail}", body_style)],
                [Paragraph(f"<b>Tenant notes:</b> {esc(note) if note else 'No note provided.'}", body_style)],
            ]
            item_table = Table(item_data, colWidths=[510])
            item_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#dadce0')),
                ('LEFTPADDING', (0,0), (-1,-1), 12),
                ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LINEBELOW', (0,0), (0,0), 0.5, colors.HexColor('#f1f3f4')),
            ]))
            story.append(KeepTogether([item_table]))
            story.append(Spacer(1, 10))
            
    story.append(Spacer(1, 8))
    
    # Draft letter
    if is_tenant:
        story.append(Paragraph("Draft Security Deposit Letter (edit before sending)", heading_style))
        story.append(Spacer(1, 8))
        letter_table = Table([[Paragraph(build_letter(room_name, confirmed_items or [], (before_taken, after_taken), law_info), body_style)]], colWidths=[510])
        letter_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#dadce0')),
            ('LEFTPADDING', (0,0), (-1,-1), 14),
            ('RIGHTPADDING', (0,0), (-1,-1), 14),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(letter_table)
        story.append(Spacer(1, 14))
        
    # Regional Rules Reference (Dynamic based on jurisdiction)
    story.append(Paragraph(f"{esc(law_info['jurisdiction'])} Statutory Rules Reference", heading_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<b>Statute:</b> {esc(law_info['statute'])}<br/>"
        f"<b>Mandatory Window:</b> {esc(law_info['return_window'])}<br/>"
        f"<b>Key Compliance Rule:</b> {esc(law_info['key_rule'])}",
        small_style
    ))
    
    doc.build(story)
    return output_path
