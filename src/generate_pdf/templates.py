"""ReportLab layout for the monthly attestation PDF.

Single entry point: render_pdf(run, findings, narrative) -> bytes. Layout:
  1. Cover page with run_id / cadence / trace_id / manifest hash.
  2. Summary table (counts by rule + by severity).
  3. Findings tables grouped by severity (CRITICAL → LOW).
  4. Narrative section: executive summary + theme clusters.
  5. ISM control map appendix.
"""
from __future__ import annotations
import io
from typing import Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def _styles() -> dict[str, ParagraphStyle]:
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="Tag", fontName="Helvetica", fontSize=8, textColor=colors.grey))
    return s


def _cover(run: dict, styles) -> list[Any]:
    items: list[Any] = [
        Paragraph("Access Review Attestation", styles["Title"]),
        Spacer(1, 0.5 * cm),
        Paragraph(f"Run: {run.get('run_id', '')}", styles["Heading2"]),
        Paragraph(f"Cadence: {run.get('cadence', '')}", styles["BodyText"]),
        Paragraph(f"Started: {run.get('started_at', '')}", styles["BodyText"]),
        Paragraph(f"Trace: {run.get('trace_id', '')}", styles["BodyText"]),
        Paragraph(f"Manifest SHA-256: {run.get('manifest_sha256', '')}", styles["Tag"]),
        Spacer(1, 0.5 * cm),
        Paragraph(f"Rows scanned: {run.get('rows_scanned', 0)}", styles["BodyText"]),
        Paragraph(f"Findings: {run.get('findings_count', 0)}", styles["BodyText"]),
    ]
    return items


def _summary_table(findings: list[dict]) -> Table:
    by_rule: dict[str, int] = {}
    by_sev: dict[str, int] = {s: 0 for s in SEVERITIES}
    for f in findings:
        by_rule[f["rule_id"]] = by_rule.get(f["rule_id"], 0) + 1
        by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
    data: list[list[str]] = [["Rule", "Count"]]
    for rid in sorted(by_rule):
        data.append([rid, str(by_rule[rid])])
    for sev in SEVERITIES:
        data.append([sev, str(by_sev[sev])])
    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    return table


def _findings_section(findings: list[dict], styles) -> list[Any]:
    items: list[Any] = [Spacer(1, 0.5 * cm), Paragraph("Findings", styles["Heading2"])]
    for sev in SEVERITIES:
        sub = [f for f in findings if f["severity"] == sev]
        if not sub:
            continue
        items.append(Paragraph(f"{sev} ({len(sub)})", styles["Heading3"]))
        rows: list[list[str]] = [["Finding ID", "Rule", "Principal", "Databases", "ISM"]]
        for f in sub:
            rows.append([
                f["finding_id"],
                f["rule_id"],
                f.get("principal", ""),
                ", ".join(f.get("databases", [])),
                ", ".join(f.get("ism_controls", [])),
            ])
        t = Table(rows, hAlign="LEFT", colWidths=[5 * cm, 1.5 * cm, 3 * cm, 5 * cm, 3 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        items.append(t)
    return items


def _narrative_section(narrative: dict, styles) -> list[Any]:
    items: list[Any] = [PageBreak(), Paragraph("Narrative", styles["Heading2"])]
    items.append(Paragraph(narrative.get("executive_summary", ""), styles["BodyText"]))
    for theme in narrative.get("theme_clusters", []):
        items.append(Paragraph(theme.get("theme", ""), styles["Heading3"]))
        items.append(Paragraph(theme.get("summary", ""), styles["BodyText"]))
    return items


def _ism_appendix(findings: list[dict], styles) -> list[Any]:
    items: list[Any] = [PageBreak(), Paragraph("ISM Control Map", styles["Heading2"])]
    by_control: dict[str, set[str]] = {}
    for f in findings:
        for c in f.get("ism_controls", []):
            by_control.setdefault(c, set()).add(f["finding_id"])
    rows: list[list[str]] = [["Control", "Findings"]]
    for c in sorted(by_control):
        rows.append([c, ", ".join(sorted(by_control[c]))])
    if len(rows) > 1:
        t = Table(rows, hAlign="LEFT", colWidths=[3 * cm, 14 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        items.append(t)
    else:
        items.append(Paragraph("No findings cite ISM controls in this run.", styles["BodyText"]))
    return items


def render_pdf(run: dict, findings: list[dict], narrative: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Attestation {run.get('run_id', '')}",
    )
    styles = _styles()
    story: list[Any] = []
    story.extend(_cover(run, styles))
    story.append(Spacer(1, 0.5 * cm))
    story.append(_summary_table(findings))
    story.extend(_findings_section(findings, styles))
    story.extend(_narrative_section(narrative, styles))
    story.extend(_ism_appendix(findings, styles))
    doc.build(story)
    return buf.getvalue()
