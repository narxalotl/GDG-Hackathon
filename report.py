import hashlib
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def get_file_hash(file_path: str) -> str:
    """Calculate the SHA-256 cryptographic hash of an original photo for evidence integrity."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_image_timestamp(image_path: str) -> str:
    """Extract timestamp from image EXIF metadata if available."""
    try:
        img = Image.open(image_path)
        exif_data = img._getexif()
        if exif_data:
            # Tag 36867 corresponds to DateTimeOriginal in EXIF data
            for tag_id, value in exif_data.items():
                if tag_id == 36867:
                    return str(value)
    except Exception:
        pass
    return "Timestamp not found in EXIF"

def build_report(room_name: str, confirmed_items: list[dict], before_path: str, after_path: str, output_path: str) -> str:
    """Write a PDF evidence report and return the file path."""
    doc = SimpleDocTemplate(
        output_path, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styling definitions
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=6,
        textColor=colors.HexColor("#3ec58d")
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor("#26aca5"),
        spaceAfter=12
    )
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=13,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#b48623")
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        textColor=colors.HexColor("#874fc7")
    )
    disclaimer_style = ParagraphStyle(
        'DisclaimerStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor("#812c2c"),
        spaceBefore=4,
        spaceAfter=8
    )

    # Header and Legal Disclaimer Banner
    story.append(Paragraph(f"Security Deposit Evidence Report: {room_name}", title_style))
    story.append(Paragraph("Move-In / Move-Out Photo Evidence Tool | GDG Build with AI x Hacktoberfest 2026", subtitle_style))
    story.append(Paragraph("<b>DISCLAIMER:</b> This tool helps you document conditions. It is not legal advice.", disclaimer_style))
    story.append(Spacer(1, 8))

    # Evidence Integrity & Metadata Table (File hashes & timestamps)
    story.append(Paragraph("Evidence Integrity & Metadata", heading_style))
    before_hash = get_file_hash(before_path)
    after_hash = get_file_hash(after_path)
    before_time = get_image_timestamp(before_path)
    after_time = get_image_timestamp(after_path)

    meta_data = [
        [Paragraph("<b>Image Type</b>", body_style), Paragraph("<b>Timestamp</b>", body_style), Paragraph("<b>SHA-256 File Hash</b>", body_style)],
        [Paragraph("Before (Move-In)", body_style), Paragraph(before_time, body_style), Paragraph(before_hash, body_style)],
        [Paragraph("After (Move-Out)", body_style), Paragraph(after_time, body_style), Paragraph(after_hash, body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[100, 110, 330])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#114208")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Side-by-Side Photos Comparison Section
    story.append(Paragraph("Visual Comparison", heading_style))
    img_before = RLImage(before_path, width=240, height=180)
    img_after = RLImage(after_path, width=240, height=180)
    img_table = Table([[img_before, img_after]], colWidths=[270, 270])
    img_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(img_table)
    story.append(Spacer(1, 10))

    # Tenant-Confirmed Differences Table
    story.append(Paragraph("Tenant-Confirmed Differences", heading_style))
    if confirmed_items:
        item_data = [[Paragraph("<b>Category</b>", body_style), Paragraph("<b>Location</b>", body_style), Paragraph("<b>Description & Details</b>", body_style)]]
        for item in confirmed_items:
            desc_text = f"{item.get('description', '')} (Severity: {item.get('severity', 'minor').capitalize()}, Confidence: {item.get('confidence', 'high').capitalize()})"
            item_data.append([
                Paragraph(item.get('category', 'damage').capitalize(), body_style),
                Paragraph(item.get('location', 'N/A'), body_style),
                Paragraph(desc_text, body_style)
            ])
        item_table = Table(item_data, colWidths=[90, 120, 330])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0a2138")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#c5e243")),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(item_table)
    else:
        story.append(Paragraph("No differences were confirmed for this room.", body_style))
    
    story.append(Spacer(1, 10))

    # Draft Security Deposit Dispute Letter Template (citing Virginia Rules)
    story.append(Paragraph("Draft Security Deposit Dispute Letter Template", heading_style))
    letter_text = (
        "<b>To:</b> Leasing Office / Property Management<br/>"
        "<b>Subject:</b> Security Deposit Return & Itemization Dispute - Virginia Residential Landlord and Tenant Act<br/><br/>"
        "Dear Property Management,<br/><br/>"
        "I am writing regarding the return of my security deposit for the unit at <b>" + room_name + "</b>. "
        "Pursuant to the Virginia Residential Landlord and Tenant Act (VRLTA), I have compiled formal evidence including "
        "timestamped move-in and move-out photographs secured via SHA-256 cryptographic file hashes.<br/><br/>"
        "Based on our joint records and inspection documentation, the items noted above were either pre-existing or disputed. "
        "Please provide a full itemized accounting and refund of the undisputed security deposit funds within the statutory deadlines.<br/><br/>"
        "Sincerely,<br/>"
        "[Tenant Name]"
    )
    story.append(Paragraph(letter_text, body_style))

    # Build PDF document
    doc.build(story)
    return output_path