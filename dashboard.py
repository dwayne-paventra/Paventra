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
from helpers.map_helpers import create_network_map
from streamlit_option_menu import option_menu
from utils import metric_card
from predictor import calculate_risk
from helpers.cost_helpers import calculate_project_budget
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from helpers.sidebar import render_sidebar
from components.kpi_cards import render_kpi_cards
from components.network_map import render_network_map
from components.executive import render_executive_dashboard
from components.road_detail import render_road_detail
from components.ai_panel import render_ai_panel

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

def risk_level(score):
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"

roads["Risk Level"] = roads["Risk Score"].apply(risk_level)

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

fig_map = create_network_map(roads)

st.plotly_chart(
    fig_map,
    use_container_width=True
)

st.markdown("---")

road = render_road_detail(roads)

risk = road["Risk Level"]
condition = road["Condition"]
traffic = road["Traffic"]
treatment = road["Treatment"]

render_ai_panel(road)

st.subheader("💰 Maintenance Cost Estimator")

length = road["Road Length"]
lanes = road["Lanes"]

lane_miles = length * lanes

cost_per_lane_mile = {
    "Crack Seal": 18000,
    "Overlay": 180000,
    "Reconstruction": 950000,
    "Not Assigned": 0,
    "None": 0
}

estimated_cost = lane_miles * cost_per_lane_mile.get(
    treatment,
    0
)

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "Estimated Project Cost",
        f"${estimated_cost:,.0f}"
    )

with col2:
    st.metric(
        "Lane Miles",
        f"{lane_miles:.1f}"
    )

st.markdown("### 📊 Executive Budget Breakdown")

budget_df, estimated_cost = calculate_project_budget(risk)

st.dataframe(
    budget_df.style.hide(axis="index").format({
        "Cost ($)": "${:,.0f}"
    }),
    use_container_width=True
)

fig_budget = create_budget_chart(budget_df)

st.plotly_chart(
    fig_budget,
    use_container_width=True
)

st.divider()

st.subheader("📅 Multi-Year Capital Improvement Plan")

# Allocate budget across three fiscal years based on risk
if risk == "High":
    year1 = estimated_cost * 0.40
    year2 = estimated_cost * 0.35
    year3 = estimated_cost * 0.25

elif risk == "Medium":
    year1 = estimated_cost * 0.30
    year2 = estimated_cost * 0.40
    year3 = estimated_cost * 0.30

else:
    year1 = estimated_cost * 0.20
    year2 = estimated_cost * 0.30
    year3 = estimated_cost * 0.50

# Build Capital Improvement Plan table
capital_df = pd.DataFrame({
    "Fiscal Year": [
        "FY2026",
        "FY2027",
        "FY2028"
    ],
    "Recommended Budget": [
        year1,
        year2,
        year3
    ]
})

# Display the table
st.dataframe(
    capital_df.style.hide(axis="index").format({
        "Recommended Budget": "${:,.0f}"
    }),
    use_container_width=True
)

# Create line chart
fig_plan = create_capital_chart(capital_df)

# Display chart
st.plotly_chart(
    fig_plan,
    use_container_width=True
)

st.divider()

left, right = st.columns(2)

with left:
    fig = px.pie(
        roads,
        names="Risk Level",
        title="Risk Distribution",
        color="Risk Level",
        color_discrete_map={
            "Low": "#2ECC71",
            "Medium": "#F39C12",
            "High": "#E74C3C"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

with right:
    fig2 = px.bar(
        roads,
        x="Condition",
        title="Road Condition Breakdown",
        color="Condition"
    )

    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

if st.button("📄 Generate Executive Report"):

    pdf_file = generate_report(
        road_name=road_name,
        pci=pci,
        condition=condition,
        risk=risk,
        estimated_cost=estimated_cost,
        capital_df=capital_df
    )

    st.success("Executive report generated!")

    with open(pdf_file, "rb") as pdf:
        st.download_button(
            "⬇ Download Executive Report",
            pdf,
            file_name=pdf_file,
            mime="application/pdf"
        )

render_network_map()

st.subheader("🛣️ Road Asset Details")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Length", f"{road['Road Length']} mi")

with col2:
    st.metric("Lanes", road["Lanes"])

with col3:
    st.metric("Surface", road["Surface Type"])

col4, col5 = st.columns(2)

with col4:
    st.metric("Speed Limit", f"{road['Speed Limit']} mph")

with col5:
    st.metric("Average Daily Traffic", f"{int(road['ADT']):,}")

st.divider()

st.subheader("🚧 Road Inventory")

display = roads.copy()

display["Risk Level"] = display["Risk Level"].replace({
    "Low": "🟢 Low",
    "Medium": "🟡 Medium",
    "High": "🔴 High"
})

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True
)