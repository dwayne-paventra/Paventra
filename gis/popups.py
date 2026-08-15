"""Presentation-ready popup builder for the Paventra network map."""

from __future__ import annotations

from html import escape

import pandas as pd


def build_popup(road: pd.Series) -> str:
    """Build a concise, escaped segment summary for a map marker."""

    estimated_cost = road.get("Estimated Cost")
    priority_rank = road.get("Priority Rank")
    cost_display = (
        f"${float(estimated_cost):,.0f}"
        if pd.notna(estimated_cost)
        else "Not available"
    )
    priority_display = (
        f"#{int(priority_rank)}"
        if pd.notna(priority_rank)
        else "Not funded in selected strategy"
    )
    road_name = escape(str(road["Road Name"]))
    risk_level = escape(str(road["Risk Level"]))
    treatment = escape(str(road["Treatment"]))
    traffic = escape(str(road["Traffic"]))
    surface = escape(str(road["Surface Type"]))
    risk_reason = escape(
        str(road.get("Risk Reason", "Risk factors are not available."))
    )

    return f"""
    <div style="width:270px;font-family:Arial,sans-serif;color:#17324d">
      <h3 style="margin:0 0 8px;color:#0b3c5d">{road_name}</h3>
      <div style="font-size:12px;color:#52697a;margin-bottom:10px">Paventra segment summary</div>
      <table style="width:100%;border-collapse:collapse;font-size:13px">
        <tr><td><b>PCI</b></td><td>{float(road['PCI']):.0f}</td></tr>
        <tr><td><b>Calculated risk</b></td><td>{float(road['Risk Score']):.0f} · {risk_level}</td></tr>
        <tr><td><b>Priority rank</b></td><td>{priority_display}</td></tr>
        <tr><td><b>Treatment</b></td><td>{treatment}</td></tr>
        <tr><td><b>Planning cost</b></td><td>{cost_display}</td></tr>
        <tr><td><b>Traffic</b></td><td>{traffic} · {float(road['ADT']):,.0f} ADT</td></tr>
        <tr><td><b>Surface</b></td><td>{surface}</td></tr>
        <tr><td><b>Length</b></td><td>{float(road['Road Length']):.2f} miles</td></tr>
      </table>
      <div style="margin-top:10px;padding:8px;background:#f3f7fa;border-radius:5px">
        <b>Priority factors</b><br>{risk_reason}
      </div>
    </div>
    """
