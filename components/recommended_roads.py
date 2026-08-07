from __future__ import annotations

import streamlit as st


def render_recommended_roads(results):

    st.subheader("📋 Recommended Roads")

    if results["roads"].empty:

        st.warning(
            "No roads fit within this budget."
        )

    else:

        st.dataframe(
            results["roads"],
            use_container_width=True,
        )

    st.divider()