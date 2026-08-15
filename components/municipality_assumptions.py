"""Data and planning assumptions for any configured public agency."""

from __future__ import annotations

import streamlit as st

from pilot.municipality_config import MunicipalityConfig


def render_municipality_assumptions(config: MunicipalityConfig) -> None:
    """Explain the configured provenance boundary and planning assumptions."""

    provenance = config.data_provenance
    with st.expander("Analysis Assumptions & Data"):
        st.markdown(
            f"**{config.pilot_disclaimer}** {provenance.inventory_statement} "
            "Scenario outcomes are planning estimates, not engineering forecasts or professional determinations. "
            f"No {config.formal_name} endorsement is implied."
        )
        st.markdown(f"**{provenance.validation_heading}**")
        st.markdown(
            "- Official roadway and GIS inventory\n"
            "- Pavement-condition / PCI data and inspection dates\n"
            "- Traffic information where available\n"
            "- Treatment history and local unit costs\n"
            "- Capital-plan and budget assumptions"
        )
