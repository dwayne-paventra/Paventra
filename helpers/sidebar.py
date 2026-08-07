from PIL import Image
import streamlit as st
from streamlit_option_menu import option_menu


def render_sidebar():

    with st.sidebar:

        logo = Image.open("assets/logo.png")

        st.image(logo, width=140)

        st.markdown("## Paventra")
        st.caption("AI-Powered Road Intelligence")

        selected = option_menu(
            menu_title=None,
            options=[
                "Dashboard",
                "Network Map",
                "AI Predictions",
                "Reports",
                "Settings",
            ],
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