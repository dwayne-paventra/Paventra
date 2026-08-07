from PIL import Image
import streamlit as st
from streamlit_option_menu import option_menu


def render_sidebar(pilot_mode: bool = False, pilot_notice: str | None = None):

    with st.sidebar:

        logo = Image.open("assets/logo.png")

        st.image(logo, width=140)

        st.markdown("## Paventra")
        st.caption("Road investment decision support")

        if pilot_mode:
            st.caption("Jackson Municipal Pilot")
            if pilot_notice:
                st.markdown(
                    f'<div class="pilot-notice pilot-notice-sidebar">{pilot_notice}</div>',
                    unsafe_allow_html=True,
                )
            options = [
                "Network Condition",
                "Risk & Network Map",
                "Investment Recommendations",
                "Budget Scenario",
                "Executive Report",
            ]
        else:
            options = [
                "Dashboard",
                "Network Map",
                "Investment Recommendations",
                "Reports",
                "Settings",
            ]

        selected = option_menu(
            menu_title=None,
            options=options,
            icons=[
                "speedometer2",
                "geo-alt",
                "cpu",
                "bar-chart",
                "gear",
            ],
            default_index=0,
            orientation="vertical",
        )

    return selected
