"""
Legend rendering for Paventra GIS.
"""

from __future__ import annotations

import folium


def add_legend(road_map):
    """
    Add the Paventra legend to the map.
    """

    legend = """
    <div style="
        position: fixed;
        bottom: 28px;
        left: 28px;
        z-index: 9999;
        background: rgba(255,255,255,.96);
        border: 1px solid #c9d6df;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(11,60,93,.18);
        color: #17324d;
        font: 12px Arial, sans-serif;
        padding: 10px 12px;
        min-width: 145px;">
      <div style="font-weight:700;margin-bottom:7px">Calculated risk</div>
      <div><span style="color:red">●</span> High (80–100)</div>
      <div><span style="color:orange">●</span> Elevated (60–79)</div>
      <div><span style="color:blue">●</span> Moderate (40–59)</div>
      <div><span style="color:green">●</span> Lower (&lt;40)</div>
      <div style="border-top:1px solid #d7e1e8;margin-top:7px;padding-top:7px">
        <span style="color:#f59e0b">★</span> Funded priority project
      </div>
    </div>
    """

    road_map.get_root().html.add_child(
        folium.Element(legend)
    )
