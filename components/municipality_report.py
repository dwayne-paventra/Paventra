"""Executive reporting for any configured public agency."""

from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pilot.municipality_config import MunicipalityConfig


def municipality_report_title(config: MunicipalityConfig) -> str:
    """Return the agency-specific title used in the PDF."""

    return f"{config.short_name} Transportation Investment Scenario"


def municipality_report_filename(config: MunicipalityConfig) -> str:
    """Return a safe agency-specific download filename."""

    return f"{config.slug}_transportation_investment_scenario.pdf"


def build_municipality_report(
    config: MunicipalityConfig,
    roads,
    results: dict,
) -> bytes:
    """Create an executive PDF in memory for the selected pilot scenario."""

    stream = BytesIO()
    doc = SimpleDocTemplate(
        stream,
        pagesize=letter,
        rightMargin=42,
        leftMargin=42,
        topMargin=42,
        bottomMargin=42,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "MunicipalityTitle",
        parent=styles["Title"],
        textColor=colors.HexColor("#005EA2"),
        fontSize=20,
        leading=24,
    )
    heading = ParagraphStyle(
        "MunicipalityHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#0B3C5D"),
        spaceBefore=12,
    )
    body = styles["BodyText"]
    data_version = (
        str(roads["data_updated_at"].max())
        if "data_updated_at" in roads.columns
        else "Illustrative demo dataset"
    )
    story = [Paragraph(f"Paventra | {config.pilot_name}", heading)]
    story.append(Paragraph(municipality_report_title(config), title))
    story.append(Paragraph(
        f"Illustrative executive briefing | Report date {date.today().isoformat()} | "
        f"Data version {data_version} | Paventra Pilot v1.1",
        body,
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Executive summary", heading))
    story.append(Paragraph(
        f"The <b>{results['scenario_name']}</b> scenario considers an illustrative budget of "
        f"<b>${results['scenario']['budget']:,.0f}</b>. It recommends {len(results['roads'])} projects, "
        f"representing ${results['spent']:,.0f} in investment and an illustrative "
        f"{results['risk_reduction_percent']:.0f}% reduction in portfolio risk.",
        body,
    ))
    story.append(Paragraph("Network condition", heading))
    metrics = [
        ["Average PCI", f"{roads['PCI'].mean():.0f}"],
        ["High-risk segments", str(int((roads["Risk Level"] == "High").sum()))],
        ["Lane miles treatable", f"{results['selected_lane_miles']:.1f}"],
        ["Portfolio risk", f"{results['network_risk_before']:.1f} to {results['network_risk_after']:.1f}"],
    ]
    metric_table = Table(metrics, colWidths=[2.8 * inch, 2.4 * inch])
    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F7FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7E1E8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(metric_table)
    story.append(Paragraph("Investment scenario and recommended investments", heading))
    investment_rows = [["Rank", "Road", "Treatment", "Cost", "PCI", "Risk"]]
    for _, road in results["roads"].iterrows():
        investment_rows.append([
            str(int(road["Priority Rank"])),
            road["Road Name"],
            road["Treatment"],
            f"${road['Estimated Cost']:,.0f}",
            f"{road['PCI']:.0f}",
            f"{road['Risk Score']:.0f}",
        ])
    investment_table = Table(
        investment_rows,
        repeatRows=1,
        colWidths=[0.45 * inch, 1.45 * inch, 1.25 * inch, 1.05 * inch, 0.5 * inch, 0.5 * inch],
    )
    investment_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#005EA2")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7E1E8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(investment_table)
    story.append(Paragraph("Why these roads are prioritized", heading))
    for _, road in results["roads"].iterrows():
        story.append(Paragraph(
            f"<b>{int(road['Priority Rank'])}. {road['Road Name']}</b> - {road['Risk Reason']}",
            body,
        ))
    story.append(Paragraph("Scenario assumptions", heading))
    story.append(Paragraph(
        "Priorities use Paventra's transparent Phase 1 rules: PCI/condition, traffic exposure, "
        "asset age, and freeze-thaw exposure. The planning impact assumes selected projects "
        "remove their current risk-score points. It is not an engineering forecast or construction estimate.",
        body,
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f"<b>{config.pilot_disclaimer}</b> Roadway records, PCI values, costs, and map locations "
        "are synthetic or illustrative demonstration inputs. This report is a planning discussion aid, "
        f"not an engineering determination or an {config.official_action_label}.",
        body,
    ))
    doc.build(story)
    return stream.getvalue()


def render_municipality_report(
    config: MunicipalityConfig,
    report_bytes: bytes,
) -> None:
    """Render a report that was explicitly requested and prepared by the dashboard."""

    import streamlit as st

    st.subheader("Executive report")
    st.caption(f"Download a concise briefing for discussion with {config.leadership_label}.")
    st.download_button(
        "Download executive briefing (PDF)",
        data=report_bytes,
        file_name=municipality_report_filename(config),
        mime="application/pdf",
        use_container_width=False,
    )
