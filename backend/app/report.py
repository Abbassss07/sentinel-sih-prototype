"""Render a case report from persisted screening and audit evidence."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#172b32")
MUTED = colors.HexColor("#5c6e74")
ACCENT = colors.HexColor("#286472")
LINE = colors.HexColor("#d0d9dc")


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(value or "-")).replace("\n", "<br/>"), style)


def build_report(case: dict, scenario: dict, ledger: dict, audit: list[dict], report_id: str, generated_at: str) -> bytes:
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="SentinelTitle", fontName="Helvetica-Bold", fontSize=18, leading=23, textColor=INK, spaceAfter=5))
    styles.add(ParagraphStyle(name="SentinelSubtitle", fontName="Helvetica", fontSize=9, leading=14, textColor=MUTED))
    styles.add(ParagraphStyle(name="SentinelSection", fontName="Helvetica-Bold", fontSize=10, leading=14, textColor=INK, spaceBefore=17, spaceAfter=7))
    styles.add(ParagraphStyle(name="SentinelBody", fontName="Helvetica", fontSize=9, leading=14, textColor=INK))
    styles.add(ParagraphStyle(name="SentinelLabel", fontName="Helvetica", fontSize=8, leading=12, textColor=MUTED))
    styles.add(ParagraphStyle(name="SentinelNotice", fontName="Helvetica-Bold", fontSize=8, leading=12, textColor=ACCENT, alignment=TA_CENTER))

    def footer(canvas, doc):
        canvas.saveState()
        width, _ = A4
        canvas.setStrokeColor(LINE)
        canvas.line(42, 42, width - 42, 42)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(42, 29, "SENTINEL | SYNTHETIC TEST DATA | PROTOTYPE ONLY")
        canvas.drawRightString(width - 42, 29, f"Page {doc.page}")
        canvas.restoreState()

    document = BaseDocTemplate(
        stream,
        pagesize=A4,
        leftMargin=42,
        rightMargin=42,
        topMargin=42,
        bottomMargin=56,
        title=f"SENTINEL case report {case['id']}",
        author="SENTINEL prototype",
    )
    frame = Frame(42, 56, A4[0] - 84, A4[1] - 98, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    document.addPageTemplates(PageTemplate(id="case", frames=[frame], onPage=footer))
    story = [
        _paragraph("SENTINEL / CASE REPORT", styles["SentinelTitle"]),
        _paragraph("Identity and document screening | Synthetic test environment", styles["SentinelSubtitle"]),
        Spacer(1, 14),
        _paragraph("This report records a demonstration screening. It is not suitable for an operational border or identity decision.", styles["SentinelNotice"]),
    ]

    def section(title, rows):
        heading = _paragraph(title.upper(), styles["SentinelSection"])
        data = [[_paragraph(label, styles["SentinelLabel"]), _paragraph(value, styles["SentinelBody"])] for label, value in rows]
        table = Table(data, colWidths=[135, A4[0] - 84 - 135], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ]))
        story.append(KeepTogether([heading, table]))

    def findings(title, items):
        story.append(_paragraph(title.upper(), styles["SentinelSection"]))
        for item in items:
            story.append(_paragraph(f"- {item}", styles["SentinelBody"]))
            story.append(Spacer(1, 4))

    section("Case and report", [
        ("Case ID", case["id"]),
        ("Report ID", report_id),
        ("Checkpoint", case["checkpoint"]),
        ("Case opened", case["created_at"]),
        ("Report generated", generated_at),
        ("Scenario", scenario["title"]),
    ])
    section("Synthetic document record", [
        ("Credential ID", scenario["credential_id"]),
        ("Holder", scenario["holder_name"]),
        ("Date of birth", scenario["date_of_birth"]),
        ("Issuer", "Republic of Testland (synthetic)"),
    ])
    findings("OCR and MRZ-like findings", scenario["document_checks"])
    findings("Liveness and face checks", [*scenario["liveness_checks"], scenario["face_check"]])
    section("Credential ledger proof", [
        ("Adapter", ledger["adapter"]),
        ("Credential status", ledger["status"]),
        ("Document hash", "MATCH" if ledger["document_hash_match"] else "MISMATCH"),
        ("Transaction ID", ledger["transaction_id"]),
        ("Verification time", ledger["verified_at"]),
    ])
    section("Risk and officer decision", [
        ("Rule-based risk level", scenario["risk_level"]),
        ("Officer action", case["officer_action"]),
        ("Officer note", case["officer_note"] or "No note entered"),
        ("Decision recorded", case["updated_at"]),
    ])
    findings("Reasons", scenario["risk_reasons"])
    findings("Audit trail", [f"{event['created_at']} | {event['event_type']} | {event['description']} | ID {event['id']}" for event in audit])
    story.append(Spacer(1, 12))
    story.append(_paragraph("Method limits: OCR, liveness, and face outcomes in this milestone are seeded synthetic results. The ledger proof comes from a local simulator. No raw document or biometric data is stored on-chain.", styles["SentinelSubtitle"]))
    document.build(story)
    return stream.getvalue()
