import io
from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


@dataclass
class LetterMetadata:
    practice_name: str
    practice_address: str
    practice_phone: str
    practice_npi: str
    payer_name: str
    payer_address: str
    date: str
    re_line: str
    subject: str


def generate_appeal_pdf(
    metadata: LetterMetadata,
    body_text: str,
    attachments: list[str],
) -> bytes:
    """Generate a professional appeal letter PDF. Returns raw PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=1.1 * inch,
        rightMargin=1.1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    base = getSampleStyleSheet()
    normal = base["Normal"]
    normal.fontSize = 11
    normal.leading = 15

    heading = ParagraphStyle(
        "Heading",
        parent=normal,
        fontSize=16,
        fontName="Helvetica-Bold",
        spaceAfter=2,
    )
    sub = ParagraphStyle(
        "Sub",
        parent=normal,
        fontSize=10,
        spaceAfter=2,
    )
    bold11 = ParagraphStyle(
        "Bold11",
        parent=normal,
        fontSize=11,
        fontName="Helvetica-Bold",
    )
    bold_underline = ParagraphStyle(
        "BoldUnderline",
        parent=bold11,
        underline=True,
    )
    right_align = ParagraphStyle(
        "RightAlign",
        parent=normal,
        fontSize=11,
        alignment=2,
    )
    small = ParagraphStyle(
        "Small",
        parent=normal,
        fontSize=8,
        textColor=colors.grey,
    )

    story = []

    # Letterhead
    story.append(Paragraph(metadata.practice_name, heading))
    story.append(Paragraph(metadata.practice_address, sub))
    story.append(Paragraph(f"Phone: {metadata.practice_phone} | NPI: {metadata.practice_npi}", sub))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 12))

    # Date (right-aligned)
    story.append(Paragraph(metadata.date, right_align))
    story.append(Spacer(1, 12))

    # Payer address block
    for line in metadata.payer_address.split(","):
        story.append(Paragraph(line.strip(), normal))
    story.append(Spacer(1, 12))

    # RE line
    story.append(Paragraph(metadata.re_line, bold11))
    story.append(Spacer(1, 6))

    # Subject
    story.append(Paragraph(metadata.subject, bold_underline))
    story.append(Spacer(1, 12))

    # Salutation
    story.append(Paragraph("Dear Provider Relations Department,", normal))
    story.append(Spacer(1, 10))

    # Body (preserve paragraph breaks)
    for para in body_text.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para.replace("\n", " "), normal))
            story.append(Spacer(1, 8))

    story.append(Spacer(1, 16))

    # Closing
    story.append(Paragraph("Sincerely,", normal))
    story.append(Spacer(1, 36))
    story.append(Paragraph(metadata.practice_name, normal))
    story.append(Paragraph("Authorized Representative", normal))
    story.append(Spacer(1, 16))

    # Enclosures
    if attachments:
        story.append(Paragraph("Enclosures:", bold11))
        for i, att in enumerate(attachments, 1):
            story.append(Paragraph(f"{i}. {att.replace('_', ' ').title()}", normal))
        story.append(Spacer(1, 16))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "This appeal was prepared with AI assistance and reviewed by an authorized representative.",
        small,
    ))

    doc.build(story)
    return buf.getvalue()
