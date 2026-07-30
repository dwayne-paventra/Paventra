import streamlit as st


def render_network_map():
    """
    Render the Network Map section.
    """

    st.subheader("🗺️ Michigan Road Network")

    st.info(
        """
Interactive road map coming in the next sprint.

Future versions will include:

• Road segments
• AI failure predictions
• Maintenance recommendations
• Weather overlays
• Traffic data
"""
    )

    st.markdown("---")