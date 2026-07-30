def calculate_risk(condition, traffic, age, freeze):
    score = 0

    # Existing pavement condition
    if condition == "Poor":
        score += 40
    elif condition == "Fair":
        score += 20

    # Traffic level
    if traffic == "High":
        score += 25
    elif traffic == "Medium":
        score += 10

    # Road age
    if age >= 15:
        score += 20
    elif age >= 10:
        score += 10

    # Freeze-thaw cycles
    if freeze == "High":
        score += 15
    elif freeze == "Medium":
        score += 8

    return score

def risk_level(score):
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"