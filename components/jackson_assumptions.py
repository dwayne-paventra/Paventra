"""Accessible data and planning assumptions for the Jackson Pilot."""

from __future__ import annotations

import streamlit as st


def render_jackson_assumptions() -> None:
    """Explain the demonstration boundary and the inputs for a real pilot."""

    with st.expander("Pilot Assumptions & Data"):
        st.markdown(
            "**This is an illustrative demonstration, not an official City of Jackson analysis.** "
            "Roadway records, PCI values, treatment costs, and map locations/geometry are demonstration inputs unless separately validated. "
            "Scenario outcomes are planning estimates, not engineering forecasts or professional determinations. "
            "No City of Jackson endorsement is implied."
        )
        st.markdown("**A validation pilot would replace these inputs with:**")
        st.markdown(
            "- Official street and GIS inventory\n"
            "- Pavement-condition / PCI data and inspection dates\n"
            "- Traffic information where available\n"
            "- Treatment history and local unit costs\n"
            "- Capital-plan and budget assumptions"
        )
