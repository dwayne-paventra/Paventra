from pathlib import Path
from html import escape

from PIL import Image
import streamlit as st


DASHBOARD_SECTIONS = (
    "Dashboard",
    "Network Map",
    "Pavement Analytics",
    "Reports",
)
OPERATOR_SECTIONS = (
    "Municipality Portfolio",
    "Municipality Onboarding",
)
NAVIGATION_SECTIONS = DASHBOARD_SECTIONS + OPERATOR_SECTIONS
DEFAULT_DASHBOARD_SECTION = DASHBOARD_SECTIONS[0]
DEFAULT_OPERATOR_SECTION = OPERATOR_SECTIONS[1]

_DASHBOARD_STATE_KEY = "paventra_dashboard_section"
_OPERATOR_STATE_KEY = "paventra_operator_view"
_OPERATOR_VIEWS = {
    "Municipality Portfolio": "portfolio",
    "Municipality Onboarding": "onboarding",
}


def navigate_to_section(target: str, *, current_section: str) -> None:
    """Navigate through the shared branded menu without changing agency context."""
    if target not in NAVIGATION_SECTIONS:
        raise ValueError(f"Unknown Paventra navigation destination: {target!r}")

    if target in DASHBOARD_SECTIONS:
        st.session_state[_DASHBOARD_STATE_KEY] = target
        if current_section in OPERATOR_SECTIONS:
            st.switch_page("dashboard.py")
        else:
            st.rerun()
        return

    st.session_state[_OPERATOR_STATE_KEY] = _OPERATOR_VIEWS[target]
    if current_section in DASHBOARD_SECTIONS:
        st.switch_page("pages/1_Municipality_Onboarding.py")
    else:
        st.rerun()


def _button_key(section: str) -> str:
    return "paventra_nav_" + section.lower().replace(" ", "_")


def _render_navigation_group(
    heading: str,
    sections: tuple[str, ...],
    *,
    active_section: str,
) -> str | None:
    st.markdown(f'<p class="paventra-nav-heading">{heading}</p>', unsafe_allow_html=True)
    for section in sections:
        if st.button(
            section,
            key=_button_key(section),
            type="primary" if section == active_section else "secondary",
            width="stretch",
        ):
            navigate_to_section(section, current_section=active_section)
            return section
    return None


def render_sidebar(
    pilot_mode: bool = False,
    pilot_notice: str | None = None,
    pilot_title: str | None = None,
    active_section: str = DEFAULT_DASHBOARD_SECTION,
) -> str:
    """Render the single shared Paventra navigation surface.

    The original function name and first three arguments remain compatible with
    older callers. The return value is the active section unless a navigation
    button initiated a rerun/page switch.
    """
    if active_section not in NAVIGATION_SECTIONS:
        raise ValueError(f"Unknown active Paventra navigation section: {active_section!r}")

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { background: #0b3c5d; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] h2 { color: #f7fafc; }
        [data-testid="stSidebar"] .stCaptionContainer { color: #c7d7e5; }
        [data-testid="stSidebar"] .paventra-nav-heading {
            color: #a9c1d3;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            margin: 1.1rem 0 0.4rem;
            text-transform: uppercase;
        }
        [data-testid="stSidebar"] .paventra-agency-card {
            background: rgba(255,255,255,.09);
            border: 1px solid rgba(255,255,255,.18);
            border-radius: 8px;
            color: #ffffff;
            font-size: .9rem;
            font-weight: 700;
            line-height: 1.3;
            margin: .8rem 0 .25rem;
            overflow-wrap: anywhere;
            padding: .65rem .7rem;
        }
        [data-testid="stSidebar"] .stButton button p {
            text-align: left;
            width: 100%;
        }
        [data-testid="stSidebar"] button[kind="secondary"] {
            background: #173f5f;
            border-color: #315f7c;
            color: #f7fafc;
        }
        [data-testid="stSidebar"] button[kind="secondary"]:hover {
            background: #24577a;
            border-color: #759bb6;
            color: #ffffff;
        }
        [data-testid="stSidebar"] button[kind="primary"] {
            background: #b42318;
            border-color: #d34b40;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
        st.image(Image.open(logo_path), width=140)
        st.markdown("## Paventra")
        st.caption("Road Investment Intelligence")

        if pilot_mode and pilot_title:
            st.markdown(
                f'<div class="paventra-agency-card">{escape(pilot_title)}</div>',
                unsafe_allow_html=True,
            )
        if pilot_mode and pilot_notice:
            st.info(pilot_notice)

        selected = _render_navigation_group(
            "Analysis",
            DASHBOARD_SECTIONS,
            active_section=active_section,
        )
        if selected is None:
            selected = _render_navigation_group(
                "Municipality Management",
                OPERATOR_SECTIONS,
                active_section=active_section,
            )
        return selected or active_section
