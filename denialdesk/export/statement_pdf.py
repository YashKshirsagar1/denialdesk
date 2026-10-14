"""Generate a monthly recovery statement PDF."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

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


def generate_statement_pdf(statement, practice) -> bytes:
    """Return PDF bytes for a monthly recovery statement and save to disk."""
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

    heading = ParagraphStyle("Heading", parent=normal, fontSize=18, fontName="Helvetica-Bold", spaceAfter=4)
    sub = ParagraphStyle("Sub", parent=normal, fontSize=10, textColor=colors.grey, spaceAfter=2)
    bold11 = ParagraphStyle("Bold11", parent=normal, fontSize=11, fontName="Helvetica-Bold")
    small = ParagraphStyle("Small", parent=normal, fontSize=8, textColor=colors.grey)

    story = []

    # Header
    story.append(Paragraph("DenialDesk", heading))
    story.append(Paragraph("Recovery Statement", sub))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 10))

    # Practice + period
    story.append(Paragraph(f"Practice: {practice.name}", bold11))
    if practice.address:
        story.append(Paragraph(practice.address, normal))
    story.append(Paragraph(
        f"Period: {statement.period_start} to {statement.period_end}",
        normal,
    ))
    story.append(Paragraph(f"Generated: {statement.generated_at.strftime('%Y-%m-%d')}", normal))
    story.append(Spacer(1, 16))

    # Line items table
    line_items = json.loads(statement.line_items or "[]")
    table_data = [["Case ID", "Patient Ref", "Denial Date", "Recovered", "Rate", "Fee", "Aged?"]]
    for item in line_items:
        table_data.append([
            str(item["case_id"]),
            item.get("patient_ref") or "—",
            item.get("denial_date") or "—",
            f"${item['amount_recovered']:,.2f}",
            f"{item['rate']*100:.0f}%",
            f"${item['fee']:,.2f}",
            "Yes" if item["aged"] else "No",
        ])

    if len(table_data) > 1:
        tbl = Table(table_data, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#343a40")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No verified outcomes in this period.", normal))

    story.append(Spacer(1, 16))

    # Totals
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"Total Recovered: ${float(statement.total_recovered):,.2f}", bold11))
    story.append(Paragraph(f"Total Fee Due:   ${float(statement.fee_amount):,.2f}", bold11))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Payment terms: Net 30 days from statement date.", normal))
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "DenialDesk charges a contingency fee on recovered amounts only. "
        "No fee is charged for denied or declined claims.",
        small,
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()

    # Save to disk (prod: replace with S3 upload)
    out_dir = Path("data/statements")
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / f"{statement.id}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    statement.pdf_path = str(pdf_path)

    return pdf_bytes
