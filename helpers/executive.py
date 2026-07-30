import streamlit as st


def render_executive_dashboard(metrics):
    """
    Displays the Executive Network Health section.
    """

    st.subheader("📊 Executive Network Health")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.metric(
            "Network Health",
            f"{metrics['network_health']:.1f}/100"
        )

        color = metrics["health_color"]
        status = metrics["health_status"]

        st.markdown(
            f"### :{color}[{status}]"
        )

    with col2:
        st.progress(metrics["network_health"] / 100)

        st.write("Overall Pavement Network Condition")

    st.divider()