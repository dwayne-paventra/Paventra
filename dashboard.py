import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from helpers.executive import render_executive_dashboard
from styles import load_css
from report import generate_report
from charts import create_budget_chart, create_capital_chart
from recommendations import get_recommendations
from config import *
from helpers.dashboard_helpers import calculate_dashboard_metrics
import folium
from streamlit_folium import st_folium
from streamlit_option_menu import option_menu
from utils import metric_card
from predictor import calculate_risk
from helpers.cost_helpers import (
    calculate_project_budget,
    estimate_road_cost,
)
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from helpers.sidebar import render_sidebar
from components.kpi_cards import render_kpi_cards
from components.network_map import render_network_map
from components.executive import render_executive_dashboard
from components.road_detail import render_road_detail
from components.ai_panel import render_ai_panel
from components.budget_panel import render_budget_panel
from components.charts_panel import render_charts_panel
from components.reports_panel import render_reports_panel
from components.inventory_panel import render_inventory_panel
from helpers.data_helpers import prepare_road_data
import components.scenario_panel as scenario_panel
import inspect
from components.optimizer_panel import render_optimizer_panel

print("Scenario panel module:", inspect.getfile(scenario_panel))

render_scenario_panel = scenario_panel.render_scenario_panel

# ------------------------------------------------
# Page Configuration
# ------------------------------------------------

st.set_page_config(
    page_title="Paventra",
    page_icon="🛣️",
    layout="wide"
)

load_css()

# ------------------------------------------------
# Custom Styling
# ------------------------------------------------

st.markdown("""
<style>

.main{
    background-color:#f7f9fb;
}

.metric-container{
    background:white;
    padding:15px;
    border-radius:12px;
    box-shadow:0px 2px 8px rgba(0,0,0,.08);
}

h1{
    color:#0B3C5D;
}

</style>
""", unsafe_allow_html=True)

# ------------------------------------------------
# Load Data
# ------------------------------------------------
selected = render_sidebar()

st.title("🛣 Paventra")

st.markdown(
    """
### AI-Powered Pavement Asset Intelligence

Helping transportation agencies prioritize maintenance using predictive analytics, AI, and capital planning.

---
"""
)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "🏗 Estimated Network Value",
        "$42.8M",
        "+2.1%"
    )

with col2:
    st.metric(
        "💰 Estimated Funding Need",
        "$10.6M",
        "-4%"
    )

with col3:
    st.metric(
        "🧠 AI Confidence",
        "97%",
        "+1%"
    )

st.divider()

# ---------------------------------------------------------
# Upload Road Inventory
# ---------------------------------------------------------

required_columns = [
    "Road Name",
    "Condition",
    "Traffic",
    "Age",
    "Freeze_Thaw",
    "Latitude",
    "Longitude"
]

uploaded_file = st.file_uploader(
    "Upload a CSV file",
    type=["csv"]
)

if uploaded_file is not None:

    roads = pd.read_csv(uploaded_file)

    missing = [
        col for col in required_columns
        if col not in roads.columns
    ]

    if missing:
        st.error(f"Missing columns: {', '.join(missing)}")
        st.stop()

    st.success("Road inventory uploaded successfully!")

else:

    roads = pd.read_csv("data/roads.csv")

# ---------------------------------------------------------
# Calculate Risk Scores
# ---------------------------------------------------------

roads["Risk Score"] = roads.apply(
    lambda row: calculate_risk(
        row["Condition"],
        row["Traffic"],
        row["Age"],
        row["Freeze_Thaw"]
    ),
    axis=1
)

# Prepare derived fields
roads = prepare_road_data(roads)

roads["Estimated Cost"] = roads.apply(
    lambda row: estimate_road_cost(
        row["Treatment"],
        row["Road Length"],
        row["Lanes"],
    ),
    axis=1,
)
st.write(
    roads[
        [
            "Road Name",
            "Treatment",
            "Estimated Cost"
        ]
    ]
)

metrics = calculate_dashboard_metrics(roads)

# ---------------------------------------------------------
# Dashboard Metrics
# ---------------------------------------------------------

render_executive_dashboard(metrics)

# ------------------------------------------------
# KPI Cards
# ------------------------------------------------

render_kpi_cards(metrics)

st.subheader("🗺️ Interactive Road Network")

render_network_map(roads)

render_scenario_panel(roads)

render_optimizer_panel(roads)

st.markdown("---")

road = render_road_detail(roads)

risk = road["Risk Level"]
condition = road["Condition"]
traffic = road["Traffic"]
treatment = road["Treatment"]

render_ai_panel(road)

estimated_cost = render_budget_panel(road)

capital_df = render_charts_panel(
    roads,
    risk,
    estimated_cost,
)

render_reports_panel(
    road,
    estimated_cost,
    capital_df,
)

render_inventory_panel(road)
