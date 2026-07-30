import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import os

from report import generate_report
from charts import budget_chart, capital_chart
from recommendations import get_recommendations
from utils import get_logo
from config import *

import folium
from streamlit_folium import st_folium

from streamlit_option_menu import option_menu
from PIL import Image

from predictor import calculate_risk

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

# ------------------------------------------------
# Page Configuration
# ------------------------------------------------

st.set_page_config(
    page_title="Paventra",
    page_icon="🛣️",
    layout="wide"
)

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

uploaded_file = st.file_uploader(
    "Upload a CSV file",
    type=["csv"]
)
required_columns = [
    "Road_ID",
    "Road_Name",
    "Condition",
    "Traffic",
    "Age",
    "Freeze_Thaw"
]
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

roads["Risk Score"] = roads.apply(
    lambda row: calculate_risk(
        row["Condition"],
        row["Traffic"],
        row["Age"],
        row["Freeze_Thaw"]
    ),
    axis=1
)

st.markdown("---")
st.subheader("🗺️ Road Network Map")

# Center map
m = folium.Map(
    location=[42.3335, -83.0460],
    zoom_start=13
)

# Add roads
for _, row in roads.iterrows():

    if row["Risk Score"] >= 75:
        color = "red"
    elif row["Risk Score"] >= 45:
        color = "orange"
    else:
        color = "green"

    folium.CircleMarker(
        location=[row["Latitude"], row["Longitude"]],
        radius=8,
        popup=f"{row['Road Name']}<br>Risk Score: {row['Risk Score']}",
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.8,
    ).add_to(m)

st_folium(m, width=1000, height=500)

# ------------------------------------------------
# Risk Level
# ------------------------------------------------

def risk_level(score):

    if score >= 75:
        return "High"

    elif score >= 45:
        return "Medium"

    else:
        return "Low"

roads["Risk Level"] = roads["Risk Score"].apply(risk_level)

# ------------------------------------------------
# Sidebar
# ------------------------------------------------

logo = Image.open("assets/logo.png")

st.sidebar.image(logo, width=140)

st.sidebar.markdown("## Paventra")
st.sidebar.caption("AI-Powered Road Intelligence")

selected = option_menu(
    menu_title=None,
    options=[
        "Dashboard",
        "Network Map",
        "AI Predictions",
        "Reports",
        "Settings"
    ],
    icons=[
        "speedometer2",
        "geo-alt",
        "cpu",
        "bar-chart",
        "gear"
    ],
    default_index=0,
)

st.sidebar.divider()

condition_filter = st.sidebar.multiselect(
    "Road Condition",
    options=roads["Condition"].unique(),
    default=roads["Condition"].unique()
)

traffic_filter = st.sidebar.multiselect(
    "Traffic",
    options=roads["Traffic"].unique(),
    default=roads["Traffic"].unique()
)

roads = roads[
    roads["Condition"].isin(condition_filter)
]

roads = roads[
    roads["Traffic"].isin(traffic_filter)
]
# ------------------------------------------------
# Header
# ------------------------------------------------

st.title("🛣️ Paventra")

st.markdown("### Upload Your Road Inventory")

st.subheader("AI-Powered Predictive Pavement Maintenance")

st.write(
    "Helping transportation agencies prioritize maintenance using data-driven insights."
)

st.divider()

# ------------------------------------------------
# KPI Cards
# ------------------------------------------------

roads_total = len(roads)

avg_risk = round(roads["Risk Score"].mean(),1)

high_risk = len(roads[roads["Risk Level"]=="High"])

low_risk = len(roads[roads["Risk Level"]=="Low"])

c1,c2,c3,c4 = st.columns(4)

c1.metric("Roads Analyzed", roads_total)

c2.metric("Average Risk", avg_risk)

c3.metric("High Risk Roads", high_risk)

c4.metric("Low Risk Roads", low_risk)

st.markdown("---")
st.subheader("🗺️ Interactive Road Network")

fig = px.scatter_map(
    roads,
    lat="Latitude",
    lon="Longitude",
    color="Risk Level",
    hover_name="Road Name",
    hover_data={
        "Condition": True,
        "Traffic": True,
        "Age": True,
        "Risk Score": True,
        "Latitude": False,
        "Longitude": False,
    },
    zoom=11,
    height=600
)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("🚧 Road Intelligence")

selected_road = st.selectbox(
    "Select a Road",
    roads["Road Name"]
)

road = roads[roads["Road Name"] == selected_road].iloc[0]

left, right = st.columns(2)

with left:
    st.metric("Risk Score", road["Risk Score"])
    st.metric("Risk Level", road["Risk Level"])
    st.metric("Condition", road["Condition"])

with right:
    st.metric("Traffic", road["Traffic"])
    st.metric("Age", road["Age"])
treatment = road["Treatment"]

if (
    pd.isna(treatment)
    or str(treatment).lower() == "none"
    or str(treatment).lower() == "nan"
):
    treatment = "Not Assigned"

st.metric("Treatment", treatment)

st.markdown("---")

st.subheader("🤖 AI Maintenance Advisor")
risk = road["Risk Level"]
condition = road["Condition"]
traffic = road["Traffic"]

if risk == "High":
    recommendation = """
🔴 **Priority: Critical**

- Schedule immediate maintenance.
- Perform a detailed pavement inspection.
- Allocate repair funding as soon as possible.
"""

elif risk == "Medium":
    recommendation = """
🟡 **Priority: Moderate**

- Monitor pavement condition.
- Schedule preventative maintenance.
- Inspect within the next 6 months.
"""

else:
    recommendation = """
🟢 **Priority: Low**

- Continue routine inspections.
- No immediate repairs required.
- Reassess during the next maintenance cycle.
"""

st.info(recommendation)

st.markdown("### 📊 AI Analysis")

st.write(
    f"""
The selected road is **{condition}** with **{traffic}** traffic
and has a **{risk}** risk rating.

Based on these conditions, Paventra recommends the maintenance
strategy shown above to maximize pavement life while minimizing
future repair costs.
"""
)

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

materials = estimated_cost * 0.40
labor = estimated_cost * 0.25
equipment = estimated_cost * 0.15
traffic_control = estimated_cost * 0.08
engineering = estimated_cost * 0.05
contingency = estimated_cost * 0.07

budget_df = pd.DataFrame({
    "Category": [
        "Materials",
        "Labor",
        "Equipment",
        "Traffic Control",
        "Engineering & Inspection",
        "Contingency"
    ],
    "Cost ($)": [
        materials,
        labor,
        equipment,
        traffic_control,
        engineering,
        contingency
    ],
    "Percent": [
        "40%",
        "25%",
        "15%",
        "8%",
        "5%",
        "7%"
    ]
})

st.dataframe(
    budget_df.style.hide(axis="index").format({
        "Cost ($)": "${:,.0f}"
    }),
    use_container_width=True
)

fig_budget = px.pie(
    budget_df,
    names="Category",
    values="Cost ($)",
    hole=0.55,
    title="Project Budget Allocation"
)

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
fig_plan = px.line(
    capital_df,
    x="Fiscal Year",
    y="Recommended Budget",
    markers=True,
    title="Three-Year Capital Investment"
)

fig_plan.update_traces(
    line=dict(width=5),
    marker=dict(size=10)
)

fig_plan.update_layout(
    template="plotly_white",
    title_x=0.5,
    yaxis_title="Budget ($)",
    xaxis_title="Fiscal Year"
)

fig_plan.update_yaxes(tickprefix="$", separatethousands=True)

fig_plan.update_traces(line=dict(width=4))
fig_plan.update_layout(
    xaxis_title="Fiscal Year",
    yaxis_title="Recommended Budget ($)",
    template="plotly_white"
)

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