# ------------------------------------------------
# Standard Library
# ------------------------------------------------

# (None currently)

# ------------------------------------------------
# Third-Party Libraries
# ------------------------------------------------

import pandas as pd
import streamlit as st

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

# ------------------------------------------------
# Project Modules
# ------------------------------------------------

from charts import create_budget_chart, create_capital_chart
from config import *
from predictor import calculate_risk
from recommendations import get_recommendations
from report import generate_report
from styles import load_css
from utils import metric_card

# ------------------------------------------------
# Helpers
# ------------------------------------------------

from helpers.cost_helpers import (
    calculate_project_budget,
    estimate_road_cost,
)
from helpers.dashboard_helpers import calculate_dashboard_metrics
from helpers.data_helpers import prepare_road_data
from helpers.optimizer_helpers import optimize_budget
from helpers.sidebar import render_sidebar

# ------------------------------------------------
# Components
# ------------------------------------------------

from components.ai_panel import render_ai_panel
from components.ai_summary import render_ai_summary
from components.analytics_dashboard import render_analytics_dashboard
from components.budget_panel import render_budget_panel
from components.charts_panel import render_charts_panel
from components.dashboard_metrics import render_dashboard_metrics
from components.executive import render_executive_dashboard
from components.inventory_panel import render_inventory_panel
from components.kpi_cards import render_kpi_cards
from components.network_map import render_network_map
from components.optimizer_panel import render_optimizer_panel
from components.recommended_roads import render_recommended_roads
from components.reports_panel import render_reports_panel
from components.road_detail import render_road_detail

import components.scenario_panel as scenario_panel


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

st.title("🚧 Paventra")

st.caption(
    "AI-Powered Transportation Asset Management Platform"
)

st.markdown(
    """
Analyze roadway conditions, optimize maintenance budgets,
prioritize infrastructure investments, and support transportation
decision-making using artificial intelligence.
    """
)

st.divider()

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

metrics = calculate_dashboard_metrics(roads)

# ---------------------------------------------------------
# Dashboard Metrics
# ---------------------------------------------------------

# ------------------------------------------------
# Executive Dashboard
# ------------------------------------------------

render_executive_dashboard(metrics)

# ------------------------------------------------
# Network Overview
# ------------------------------------------------

render_kpi_cards(metrics)

budget, goal, strategy = render_optimizer_panel()

optimizer_results = optimize_budget(
    roads,
    budget,
    goal,
    strategy,
)

optimizer_results = optimize_budget(
    roads,
    budget,
    goal,
    strategy,
)

render_dashboard_metrics(
    roads,
    optimizer_results,
)

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------
# AI Recommendation
# ------------------------------------------------

render_ai_summary(
    optimizer_results,
)

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------
# Network Analytics
# ------------------------------------------------

render_analytics_dashboard(
    roads,
)

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------
# Budget Optimizer Results
# ------------------------------------------------

render_recommended_roads(
    optimizer_results,
)

st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------
# Interactive Road Network
# ------------------------------------------------

render_network_map(
    roads,
    optimizer_results["selected_ids"],
)

# ------------------------------------------------
# Scenario Planning
# ------------------------------------------------

render_scenario_panel(
    roads,
)

st.markdown("---")

# ------------------------------------------------
# Individual Road Analysis
# ------------------------------------------------

road = render_road_detail(
    roads,
)

risk = road["Risk Level"]
condition = road["Condition"]
traffic = road["Traffic"]
treatment = road["Treatment"]

render_ai_panel(
    road,
)

estimated_cost = render_budget_panel(
    road,
)

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

render_inventory_panel(
    road,
)
