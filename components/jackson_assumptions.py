"""Municipality assumptions with a Jackson compatibility entry point."""

from __future__ import annotations

import streamlit as st

from pilot.municipality_config import MunicipalityConfig


def render_municipality_assumptions(config: MunicipalityConfig) -> None:
    """Explain the demonstration boundary and the inputs for a real pilot."""

    with st.expander("Pilot Assumptions & Data"):
        st.markdown(
            f"**This is an illustrative demonstration, not an official {config.display_name} analysis.** "
            "Roadway records, PCI values, treatment costs, and map locations/geometry are demonstration inputs unless separately validated. "
            "Scenario outcomes are planning estimates, not engineering forecasts or professional determinations. "
            f"No {config.display_name} endorsement is implied."
        )
        st.markdown("**A validation pilot would replace these inputs with:**")
        st.markdown(
            "- Official street and GIS inventory\n"
            "- Pavement-condition / PCI data and inspection dates\n"
            "- Traffic information where available\n"
            "- Treatment history and local unit costs\n"
            "- Capital-plan and budget assumptions"
        )


def render_jackson_assumptions() -> None:
    """Compatibility wrapper for the original active-municipality entry point."""

    from pilot.municipality_registry import ACTIVE_MUNICIPALITY

    render_municipality_assumptions(ACTIVE_MUNICIPALITY)
