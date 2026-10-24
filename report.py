import hashlib
import io
import os
from xml.sax.saxutils import escape

from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Google Brand Color Palette
GOOGLE_BLUE = colors.HexColor("#4285F4")
GOOGLE_RED = colors.HexColor("#EA4335")
GOOGLE_GREEN = colors.HexColor("#34A853")
GOOGLE_YELLOW = colors.HexColor("#FBBC05")
GOOGLE_DARK = colors.HexColor("#202124")

# NEW: where the verified Virginia rules text lives (checks both folders, since the file
# currently sits in data/data/). Run the app from the project folder.
RULES_PATHS = [
    os.path.join("data", "va_deposit_rules.txt"),
    os.path.join("data", "data", "va_deposit_rules.txt"),
]


def esc(value) -> str:
    """NEW: make text safe for ReportLab Paragraphs (model text can contain & or <)."""
    return escape(str(value))


def load_rules_text() -> str:
    """NEW: return the saved Virginia rules text, or an empty string if the file is missing."""
    for path in RULES_PATHS:
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read().strip()
            if text:
                return text
    return ""


def fit_image(path: str, max_w: int = 240, max_h: int = 180) -> RLImage:
    """NEW: show a photo upright and undistorted, shrunk to fit the box.
    (The original file and its hash are not changed; only the picture in the PDF is resized.)"""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("RGB")   # phone photos are often stored rotated
    img.thumbnail((1200, 1200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    w, h = img.size
    scale = min(max_w / w, max_h / h)
    return RLImage(buf, width=w * scale, height=h * scale)


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
    """Write a PDF evidence report using Google branding and return the file path."""
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

    # Custom Google-Themed Styling Definitions
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=4,
        textColor=GOOGLE_BLUE
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=GOOGLE_GREEN,
        spaceAfter=8
    )
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=13,
        spaceBefore=12,
        spaceAfter=6,
        textColor=GOOGLE_RED
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6,
        textColor=GOOGLE_DARK
    )
    small_style = ParagraphStyle(
        'SmallStyle',
        parent=styles['Normal'],
        fontSize=8.5,
        spaceAfter=4,
        textColor=GOOGLE_DARK
    )
    disclaimer_style = ParagraphStyle(
        'DisclaimerStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor("#C5221F"),  # Dark Google Red for warnings
        spaceBefore=2,
        spaceAfter=8
    )

    # Header and Legal Disclaimer Banner
    story.append(Paragraph(f"Security Deposit Evidence Report: {esc(room_name)}", title_style))
    story.append(Paragraph("Move-In / Move-Out Photo Evidence Tool | GDG Build with AI x Hacktoberfest 2026", subtitle_style))
    story.append(Paragraph("<b>DISCLAIMER:</b> This tool helps you document conditions. It is not legal advice.", disclaimer_style))
    story.append(Spacer(1, 6))

    # Evidence Integrity & Metadata Table (File hashes & timestamps)
    story.append(Paragraph("Evidence Integrity & Metadata", heading_style))
    before_hash = get_file_hash(before_path)
    after_hash = get_file_hash(after_path)
    before_time = get_image_timestamp(before_path)
    after_time = get_image_timestamp(after_path)

    # Table Header text style (white text for contrast on colored headers)
    th_style = ParagraphStyle('TH', parent=styles['Normal'], fontSize=10, textColor=colors.white)

    meta_data = [
        [Paragraph("<b>Image Type</b>", th_style), Paragraph("<b>Timestamp</b>", th_style), Paragraph("<b>SHA-256 File Hash</b>", th_style)],
        [Paragraph("Before (Move-In)", body_style), Paragraph(esc(before_time), body_style), Paragraph(before_hash, body_style)],
        [Paragraph("After (Move-Out)", body_style), Paragraph(esc(after_time), body_style), Paragraph(after_hash, body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[100, 110, 330])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GOOGLE_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC1C6')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)
    story.append(Paragraph(
        "A SHA-256 hash is a fingerprint of the original photo file. If the file is changed in any way, "
        "its hash changes. Photos shown below are resized for the report.", small_style))
    story.append(Spacer(1, 10))

    # Side-by-Side Photos Comparison Section
    story.append(Paragraph("Visual Comparison", heading_style))
    img_before = fit_image(before_path)   # CHANGED: keeps the real proportions and rotation
    img_after = fit_image(after_path)
    img_table = Table([[img_before, img_after]], colWidths=[270, 270])
    img_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(img_table)
    story.append(Spacer(1, 10))

    # Tenant-Confirmed Differences Table
    story.append(Paragraph("Tenant-Confirmed Differences", heading_style))
    model_name = os.environ.get("GEMMA_MODEL", "gemma-4-31b-it")
    story.append(Paragraph(
        f"These differences were suggested by an AI model ({esc(model_name)}) and then reviewed and "
        "confirmed by the tenant. The AI can make mistakes.", small_style))
    if confirmed_items:
        item_data = [[Paragraph("<b>Category</b>", th_style), Paragraph("<b>Location</b>", th_style), Paragraph("<b>Description & Details</b>", th_style)]]
        for item in confirmed_items:
            # CHANGED: missing confidence now shows "Unknown" instead of claiming "High"
            desc_text = (f"{esc(item.get('description', ''))} (Severity: {esc(str(item.get('severity', 'unknown')).capitalize())}, "
                         f"AI confidence: {esc(str(item.get('confidence', 'unknown')).capitalize())})")
            item_data.append([
                Paragraph(esc(str(item.get('category', 'other')).capitalize()), body_style),
                Paragraph(esc(item.get('location', 'N/A')), body_style),
                Paragraph(desc_text, body_style)
            ])
        item_table = Table(item_data, colWidths=[90, 120, 330])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), GOOGLE_GREEN),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC1C6")),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(item_table)
    else:
        story.append(Paragraph("No differences were confirmed for this room.", body_style))

    story.append(Spacer(1, 10))

    # Draft Security Deposit Letter Template
    # CHANGED: neutral wording. The old text called the items "pre-existing or disputed" and mentioned
    # "joint records", which the tool cannot know. The tenant now decides what to say about each item.
    story.append(Paragraph("Draft Security Deposit Letter (edit before sending)", heading_style))
    letter_text = (
        "<b>To:</b> Leasing Office / Property Management<br/>"
        "<b>Subject:</b> Security deposit itemization and return - [Unit address]<br/><br/>"
        "Dear Property Management,<br/><br/>"
        "I am writing about the security deposit for the unit at [Unit address]. I documented the condition of the "
        "<b>" + esc(room_name) + "</b> at move-in and move-out with photographs. The attached report records "
        "a SHA-256 fingerprint (hash) of each original photo file.<br/><br/>"
        "The report lists the differences I reviewed between the two sets of photographs. "
        "<font color='#C5221F'>[Tenant: edit this paragraph. For each item, say whether it is normal wear and tear, "
        "was already there at move-in, or something you accept responsibility for.]</font><br/><br/>"
        "Please send me an itemized written accounting of any deductions from my security deposit and return the "
        "remaining balance within the deadlines required by the Virginia Residential Landlord and Tenant Act "
        "(see the Virginia rules reference in the attached report).<br/><br/>"
        "Sincerely,<br/>"
        "[Tenant Name]"
    )
    story.append(Paragraph(letter_text, body_style))

    # NEW: the verified Virginia rules text that the team saved in data/va_deposit_rules.txt
    story.append(Spacer(1, 10))
    story.append(Paragraph("Virginia Rules Reference", heading_style))
    rules_text = load_rules_text()
    if rules_text:
        story.append(Paragraph(
            "Text copied from the official source by the project team. Check the current statute before relying on it.",
            small_style))
        for block in rules_text.split("\n\n"):
            block = block.strip()
            if block:
                story.append(Paragraph(esc(block).replace("\n", "<br/>"), small_style))
    else:
        story.append(Paragraph(
            "[Rules reference not found. Add the verified text to data/va_deposit_rules.txt.]", small_style))

    # Build PDF document
    doc.build(story)
    return output_path
