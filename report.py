from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter


def generate_report(
    road_name,
    pci,
    condition,
    risk,
    estimated_cost,
    capital_df,
    filename="Paventra_Report.pdf"
):
    """
    Generates a PDF executive report.
    Returns the filename that was created.
    """

    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(
        filename,
        pagesize=letter
    )

    story = []

    # Title
    story.append(
        Paragraph("<b>Paventra Executive Report</b>", styles["Title"])
    )

    story.append(
        Paragraph("<br/>", styles["BodyText"])
    )

    # Road Summary
    story.append(
        Paragraph("<b>Road Summary</b>", styles["Heading2"])
    )

    story.append(
        Paragraph(f"Road: {road_name}", styles["BodyText"])
    )

    story.append(
        Paragraph(f"PCI Score: {pci}", styles["BodyText"])
    )

    story.append(
        Paragraph(f"Condition: {condition}", styles["BodyText"])
    )

    story.append(
        Paragraph(f"Risk: {risk}", styles["BodyText"])
    )

    story.append(
        Paragraph(
            f"Estimated Cost: ${estimated_cost:,.0f}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph("<br/>", styles["BodyText"])
    )

    # Capital Plan
    story.append(
        Paragraph("<b>Capital Improvement Plan</b>", styles["Heading2"])
    )

    for _, row in capital_df.iterrows():

        story.append(

            Paragraph(

                f"{row['Fiscal Year']}: "
                f"${row['Recommended Budget']:,.0f}",

                styles["BodyText"]

            )

        )

    doc.build(story)

    return filename