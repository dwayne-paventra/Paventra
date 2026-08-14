"""Data and planning assumptions for any configured public agency."""

from __future__ import annotations

import streamlit as st

from pilot.municipality_config import MunicipalityConfig


def render_municipality_assumptions(config: MunicipalityConfig) -> None:
    """Explain the demonstration boundary and the inputs for a real pilot."""

    with st.expander("Pilot Assumptions & Data"):
        st.markdown(
            f"**This is an illustrative demonstration, not an official {config.formal_name} analysis.** "
            "Roadway records, PCI values, treatment costs, and map locations/geometry are demonstration inputs unless separately validated. "
            "Scenario outcomes are planning estimates, not engineering forecasts or professional determinations. "
            f"No {config.formal_name} endorsement is implied."
        )
        st.markdown("**A validation pilot would replace these inputs with:**")
        st.markdown(
            "- Official roadway and GIS inventory\n"
            "- Pavement-condition / PCI data and inspection dates\n"
            "- Traffic information where available\n"
            "- Treatment history and local unit costs\n"
            "- Capital-plan and budget assumptions"
        )
