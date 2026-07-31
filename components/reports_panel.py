"""
Reports Panel component.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from report import generate_report


def render_reports_panel(
    road: pd.Series,
    estimated_cost: float,
    capital_df: pd.DataFrame,
) -> None:
    """
    Render executive report section.
    """

    if st.button("📄 Generate Executive Report"):

        pdf_file = generate_report(
            road_name=road["Road Name"],
            pci=road["PCI"],
            condition=road["Condition"],
            risk=road["Risk Level"],
            estimated_cost=estimated_cost,
            capital_df=capital_df,
        )

        st.success("Executive report generated!")

        with open(pdf_file, "rb") as pdf:

            st.download_button(
                "⬇ Download Executive Report",
                pdf,
                file_name=pdf_file,
                mime="application/pdf",
            )