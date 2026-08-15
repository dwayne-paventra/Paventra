"""Streamlit multipage entry point for municipality operators."""

import streamlit as st

from components.municipality_admin import render_municipality_admin
from helpers.sidebar import OPERATOR_SECTIONS, render_sidebar
from pilot.municipality_registry import ACTIVE_MUNICIPALITY, get_municipality_config


st.set_page_config(page_title="Municipality Onboarding", page_icon="🛣️", layout="wide")


def _selected_municipality():
    """Resolve the current permanent or generated municipality context."""
    runtime_slug = st.session_state.get("paventra_runtime_municipality_slug")
    registered_slug = st.session_state.get("paventra_selected_municipality_slug")
    if runtime_slug:
        from pilot.municipality_admin import load_generated_municipality

        return load_generated_municipality(runtime_slug)
    if registered_slug:
        return get_municipality_config(registered_slug)
    return ACTIVE_MUNICIPALITY


try:
    selected_municipality = _selected_municipality()
except ValueError as exc:
    st.error(f"Municipality selection could not be loaded: {exc}")
    st.stop()

operator_view = st.session_state.get("paventra_operator_view", "onboarding")
if operator_view not in {"portfolio", "onboarding"}:
    operator_view = "onboarding"
    st.session_state["paventra_operator_view"] = operator_view
active_section = (
    "Municipality Portfolio" if operator_view == "portfolio" else "Municipality Onboarding"
)
assert active_section in OPERATOR_SECTIONS

render_sidebar(
    pilot_mode=True,
    pilot_notice=selected_municipality.pilot_disclaimer,
    pilot_title=selected_municipality.pilot_name,
    active_section=active_section,
)
render_municipality_admin(operator_view=operator_view)
