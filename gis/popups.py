"""
Popup builder for Paventra GIS.
"""

from __future__ import annotations

import pandas as pd


def build_popup(road: pd.Series) -> str:
    """
    Build the HTML popup for a road.
    """

    pci = road.get("PCI", "Not available")
    risk_reason = road.get("Risk Reason", "Risk factors are not available.")
    estimated_cost = road.get("Estimated Cost")
    priority_rank = road.get("Priority Rank")
    cost_display = f"${float(estimated_cost):,.0f}" if pd.notna(estimated_cost) else "Not available"
    priority_display = f"#{int(priority_rank)}" if pd.notna(priority_rank) else "Not currently recommended"

    return f"""
    <div style="width:260px">

    <h3 style="margin-bottom:10px;">
    🛣️ {road["Road Name"]}
    </h3>

    <hr>

    <b>PCI</b><br>
    {pci}

    <br><br>

    <b>Risk Level</b><br>
    {road["Risk Level"]}

    <br><br>

    <b>Risk Score</b><br>
    {road["Risk Score"]}

    <br><br>

    <b>Why it is a priority</b><br>
    {risk_reason}

    <br><br>

    <b>Recommended Treatment</b><br>
    {road["Treatment"]}

    <br><br>

    <b>Estimated Cost</b><br>
    {cost_display}

    <br><br>

    <b>Priority Rank</b><br>
    {priority_display}

    <br><br>

    <b>Traffic Level</b><br>
    {road["Traffic"]}

    <br><br>

    <b>Average Daily Traffic (ADT)</b><br>
    {road["ADT"]:,}

    <br><br>

    <b>Surface Type</b><br>
    {road["Surface Type"]}

    <br><br>

    <b>Speed Limit</b><br>
    {road["Speed Limit"]} mph

    <br><br>

    <b>Road Length</b><br>
    {road["Road Length"]} miles

    </div>
    """
