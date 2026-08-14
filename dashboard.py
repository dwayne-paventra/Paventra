"""Paventra Streamlit dashboard entry point."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import json

import streamlit as st

from pilot.jackson_config import (
    JACKSON_DEMO_DATA_PATH,
    PILOT_DISCLAIMER,
    is_jackson_pilot_mode,
)


@st.cache_data(show_spinner=False)
def load_cached_jackson_inventory(data_path: str, modified_at_ns: int):
    """Cache Jackson validation and risk enrichment until its source changes."""

    del modified_at_ns  # Deliberately part of the cache key.
    from pilot.jackson_data import load_jackson_streamlit_inventory

    return load_jackson_streamlit_inventory(data_path)


@st.cache_data(show_spinner=False)
def build_cached_jackson_scenario(roads, scenario_name: str, dataset_version: int, assumptions_version: str):
    """Cache a scenario by its data version and transparent assumptions."""

    del dataset_version, assumptions_version  # Deliberately part of the cache key.
    from pilot.jackson_scenarios import build_jackson_scenario_results

    return build_jackson_scenario_results(roads, scenario_name)


@st.cache_data(show_spinner=False)
def build_cached_jackson_report(roads, results: dict, dataset_version: int, report_date: str, report_version: str) -> bytes:
    """Build the requested PDF once per data, scenario, date, and template version."""

    del dataset_version, report_date, report_version  # Deliberately part of the cache key.
    from components.jackson_report import build_jackson_report

    return build_jackson_report(roads, results)


def render_jackson_pilot() -> None:
    """Render the Jackson briefing without loading optional GIS or PDF dependencies."""

    from helpers.sidebar import render_sidebar
    from components.jackson_executive import render_jackson_executive_overview

    render_sidebar(pilot_mode=True, pilot_notice=PILOT_DISCLAIMER)

    data_path = Path(JACKSON_DEMO_DATA_PATH)
    dataset_version = data_path.stat().st_mtime_ns
    jackson_roads = load_cached_jackson_inventory(str(data_path), dataset_version)

    render_jackson_executive_overview(jackson_roads)
    if st.button("Open investment briefing", key="jackson_open_briefing"):
        st.session_state["jackson_briefing_open"] = True
    if not st.session_state.get("jackson_briefing_open", False):
        return

    from pilot.jackson_scenarios import JACKSON_SCENARIOS
    from components.jackson_assumptions import render_jackson_assumptions
    from components.jackson_recommendations import render_jackson_recommendations
    from components.jackson_scenarios import render_jackson_scenario_impact, render_jackson_scenario_selector

    selected_scenario = render_jackson_scenario_selector()
    assumptions_version = json.dumps(JACKSON_SCENARIOS, sort_keys=True)
    jackson_results = build_cached_jackson_scenario(
        jackson_roads, selected_scenario, dataset_version, assumptions_version
    )

    st.markdown("### Investment recommendations")
    render_jackson_recommendations(jackson_results)
    render_jackson_scenario_impact(jackson_results)

    st.markdown("### Network Explorer")
    if st.button("Open interactive network map", key="jackson_open_map"):
        st.session_state["jackson_map_open"] = True
    if st.session_state.get("jackson_map_open", False):
        # Folium and GeoPandas are intentionally imported only after this action.
        from components.jackson_map import render_jackson_map

        render_jackson_map(jackson_roads, jackson_results)

    st.markdown("### Executive report")
    if st.button("Generate executive briefing", key="jackson_generate_report"):
        st.session_state["jackson_report_requested"] = True
    if st.session_state.get("jackson_report_requested", False):
        report_bytes = build_cached_jackson_report(
            jackson_roads,
            jackson_results,
            dataset_version,
            date.today().isoformat(),
            "jackson-pilot-report-v1.1",
        )
        from components.jackson_report import render_jackson_report

        render_jackson_report(report_bytes)

    render_jackson_assumptions()

# ------------------------------------------------
# Page Configuration
# ------------------------------------------------

st.set_page_config(
    page_title="Paventra",
    page_icon="🛣️",
    layout="wide"
)

jackson_pilot_mode = is_jackson_pilot_mode()

from styles import load_css

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

.pilot-notice{
    background:#EAF2F8;
    border-left:4px solid #005EA2;
    border-radius:6px;
    color:#17324D;
    font-size:.88rem;
    line-height:1.35;
    margin:.5rem 0 1rem 0;
    padding:.65rem .8rem;
}

.pilot-notice-sidebar{
    font-size:.78rem;
    margin:.55rem 0 .85rem 0;
    padding:.55rem .65rem;
}

</style>
""", unsafe_allow_html=True)

# ------------------------------------------------
# Jackson Municipal Pilot
# ------------------------------------------------

if jackson_pilot_mode:
    render_jackson_pilot()
    st.stop()

# Legacy dependencies are intentionally loaded only outside Jackson Pilot mode.
import inspect
import time

import pandas as pd

from charts import create_budget_chart, create_capital_chart
from config import *
from predictor import calculate_risk
from recommendations import get_recommendations
from report import generate_report
from utils import metric_card
from helpers.cost_helpers import calculate_project_budget, estimate_road_cost
from helpers.dashboard_helpers import calculate_dashboard_metrics
from helpers.data_helpers import prepare_road_data
from helpers.optimizer_helpers import optimize_budget
from helpers.sidebar import render_sidebar
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
from components.project_builder import render_project_panel
from components.scenario_panel import render_scenario_panel
from gis.styles import risk_color
from gis.county_summary import build_county_summary
from gis.county_map import build_county_heatmap

selected = render_sidebar(pilot_mode=False)

# ------------------------------------------------
# Load Data
# ------------------------------------------------

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

    @st.cache_data
    def load_roads():
        data_path = Path(JACKSON_DEMO_DATA_PATH)
        return load_cached_jackson_inventory(
            str(data_path),
            data_path.stat().st_mtime_ns,
        )

    roads = load_roads()

    all_roads = roads.copy()

    county_options = sorted(
    roads["County"].dropna().unique()
    )

    county_options.insert(
        0,
        "All Counties"
    )

@st.cache_data
def prepare_cached_roads(roads):

    roads = roads.copy()

    # -----------------------------
    # Risk Score
    # -----------------------------

    roads["Risk Score"] = roads.apply(
        lambda row: calculate_risk(
            row["Condition"],
            row["Traffic"],
            row["Age"],
            row["Freeze_Thaw"],
            row.get("PCI"),
        ),
        axis=1,
    )

    # -----------------------------
    # Prepare Derived Fields
    # -----------------------------

    roads = prepare_road_data(
        roads
    )

    # -----------------------------
    # Estimated Cost
    # -----------------------------

    roads["Estimated Cost"] = roads.apply(
        lambda row: estimate_road_cost(
            row["Treatment"],
            row["Road Length"],
            row["Lanes"],
        ),
        axis=1,
    )

    return roads

# ---------------------------------------------------------
# Calculate Risk Scores
# ---------------------------------------------------------

roads = prepare_cached_roads(
    roads
)

# ------------------------------------------------
# County Filter
# ------------------------------------------------
with st.sidebar:

    st.markdown("---")

    st.subheader("Filters")

    selected_county = st.selectbox(
        "County",
        county_options,
        index=1,
    )

# Filter data

if selected_county != "All Counties":

    roads = roads[
        roads["County"] == selected_county
    ]

with st.sidebar:
    st.caption(
        f"{len(roads):,} roads in selection"
    )

    t = time.perf_counter()

    county_summary = build_county_summary(
        all_roads
    )

    st.write("County Summary:", round(time.perf_counter() - t, 2), "seconds")

st.subheader("🗺️ Michigan County Risk Overview")

st.caption(
    "Average pavement risk score aggregated by county."
)

metric = st.selectbox(
    "County Metric",
    [
        "Average Risk",
        "Average Condition",
        "Average ADT",
        "Road Count",
    ],
)

metric_lookup = {
    "Average Risk": "Average_Risk",
    "Average Condition": "Average_Condition",
    "Average ADT": "Average_ADT",
    "Road Count": "Roads",
}

selected_metric = metric_lookup[metric]

from streamlit_folium import st_folium

t = time.perf_counter()

county_map = build_county_heatmap(
    county_summary,
    metric=selected_metric,
)

st.write("County heatmap:", round(time.perf_counter() - t, 2), "seconds")

st_folium(
    county_map,
    width=None,
    height=700,
)

# ---------------------------------------------------------
# Dashboard Metrics
# ---------------------------------------------------------

metrics = calculate_dashboard_metrics(roads)

# ------------------------------------------------
# Executive Dashboard
# ------------------------------------------------

render_executive_dashboard(metrics)

# ------------------------------------------------
# Network Overview
# ------------------------------------------------

render_kpi_cards(metrics)

budget, goal, strategy = render_optimizer_panel()

t = time.perf_counter()

optimizer_results = optimize_budget(
    roads,
    budget,
    goal,
    strategy,
)

st.write("optimizer:", round(time.perf_counter() - t, 2), "seconds")

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
# Scenario Planning
# ------------------------------------------------

# ------------------------------------------------
# Interactive Road Network
# ------------------------------------------------

center_on = None

if optimizer_results["selected_ids"]:

    selected_id = optimizer_results["selected_ids"][0]

    match = roads[
        roads["Road ID"].astype(str)
        == str(selected_id)
    ]

    if not match.empty:

        center_on = match.iloc[0]

left, right = st.columns([3, 1])

with left:

    t = time.perf_counter()

    render_network_map(
        roads,
        optimizer_results["selected_ids"],
        center_on=center_on,
        show_geometry=center_on is not None,
    )

    st.write("network map:", round(time.perf_counter() - t, 2), "seconds")

with right:
    render_project_panel()

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
