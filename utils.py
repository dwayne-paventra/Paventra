import streamlit as st


def metric_card(title, value, color="#005EA2"):
    st.markdown(
        f"""
        <div style="
            background:white;
            border-left:8px solid {color};
            padding:20px;
            border-radius:10px;
            box-shadow:0 2px 8px rgba(0,0,0,.12);
            margin-bottom:10px;
        ">
            <h5 style="margin:0;color:gray;">{title}</h5>
            <h2 style="margin:0;color:{color};">{value}</h2>
        </div>
        """,
        unsafe_allow_html=True
    )