"""Streamlit multipage entry point for municipality operators."""

import streamlit as st

from components.municipality_admin import render_municipality_admin


st.set_page_config(page_title="Municipality Onboarding", page_icon="🛣️", layout="wide")
render_municipality_admin()
