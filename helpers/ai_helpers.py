"""
AI helper functions for Paventra.
"""


def get_ai_recommendation(risk: str) -> str:
    """
    Return the maintenance recommendation based on risk.
    """

    if risk == "High":
        return """
🔴 **Priority: Critical**

- Schedule immediate maintenance.
- Perform a detailed pavement inspection.
- Allocate repair funding as soon as possible.
"""

    if risk == "Medium":
        return """
🟡 **Priority: Moderate**

- Monitor pavement condition.
- Schedule preventative maintenance.
- Inspect within the next 6 months.
"""

    return """
🟢 **Priority: Low**

- Continue routine inspections.
- No immediate repairs required.
- Reassess during the next maintenance cycle.
"""