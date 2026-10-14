import io
from dataclasses import dataclass, field

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
class CallPacketData:
    payer_name: str
    payer_phone: str
    phone_tree: str
    claim_number: str
    patient_ref: str
    dos: str
    cpt: str
    billed_amt: float
    denial_reason: str
    the_ask: str
    talking_points: list[str]
    escalation_trigger: str
    reference_numbers: list[str] = field(default_factory=list)
    prepared_date: str = ""


def generate_call_packet_pdf(data: CallPacketData) -> bytes:
    """Generate a structured call packet PDF. Returns raw PDF bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    base = getSampleStyleSheet()
    normal = base["Normal"]
    normal.fontSize = 11
    normal.leading = 15

    title_style = ParagraphStyle(
        "Title",
        parent=normal,
        fontSize=20,
        fontName="Helvetica-Bold",
        alignment=1,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=normal,
        fontSize=11,
        alignment=1,
        textColor=colors.grey,
        spaceAfter=12,
    )
    section_head = ParagraphStyle(
        "SectionHead",
        parent=normal,
        fontSize=12,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=4,
    )
    bold11 = ParagraphStyle(
        "Bold11",
        parent=normal,
        fontSize=11,
        fontName="Helvetica-Bold",
    )
    small_footer = ParagraphStyle(
        "SmallFooter",
        parent=normal,
        fontSize=8,
        textColor=colors.grey,
        alignment=1,
    )

    story = []

    # Header
    story.append(Paragraph("PAYER CALL PACKET", title_style))
    story.append(Paragraph(f"Prepared: {data.prepared_date}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a56db")))
    story.append(Spacer(1, 10))

    # Payer info box (light blue background via table)
    payer_table_data = [
        [Paragraph("<b>Payer</b>", normal), Paragraph(data.payer_name, normal)],
        [Paragraph("<b>Phone</b>", normal), Paragraph(data.payer_phone, normal)],
        [Paragraph("<b>Phone Tree</b>", normal), Paragraph(data.phone_tree, normal)],
    ]
    payer_table = Table(payer_table_data, colWidths=[1.4 * inch, 5.1 * inch])
    payer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8f4fd")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b3d4f0")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(payer_table)
    story.append(Spacer(1, 14))

    # Claim summary table
    story.append(Paragraph("Claim Summary", section_head))
    summary_data = [
        ["Claim #", data.claim_number, "Patient", data.patient_ref],
        ["Date of Service", data.dos, "CPT Code", data.cpt],
        ["Amount Billed", f"${data.billed_amt:,.2f}", "Denial Reason", data.denial_reason],
    ]
    summary_table = Table(summary_data, colWidths=[1.4 * inch, 2 * inch, 1.4 * inch, 2 * inch])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f4f6")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f3f4f6")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # The Ask (bold box)
    ask_data = [[
        Paragraph(f"<b>WHAT TO REQUEST:</b><br/>{data.the_ask}", normal)
    ]]
    ask_table = Table(ask_data, colWidths=[6.5 * inch])
    ask_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdf4")),
        ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#16a34a")),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(ask_table)
    story.append(Spacer(1, 14))

    # Talking points
    story.append(Paragraph("Talking Points", section_head))
    for i, point in enumerate(data.talking_points, 1):
        story.append(Paragraph(f"{i}. {point}", normal))
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 8))

    # Escalation trigger (yellow warning box)
    escalation_data = [[
        Paragraph(f"<b>ESCALATE IF:</b><br/>{data.escalation_trigger}", normal)
    ]]
    escalation_table = Table(escalation_data, colWidths=[6.5 * inch])
    escalation_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fefce8")),
        ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#ca8a04")),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(escalation_table)
    story.append(Spacer(1, 14))

    # Reference numbers
    if data.reference_numbers:
        story.append(Paragraph("Have these ready:", bold11))
        for ref in data.reference_numbers:
            story.append(Paragraph(f"• {ref}", normal))
        story.append(Spacer(1, 12))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Keep this document confidential. Do not leave with payer.",
        small_footer,
    ))

    doc.build(story)
    return buf.getvalue()
