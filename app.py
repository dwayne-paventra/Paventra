import pandas as pd
from predictor import calculate_risk

print("=" * 40)
print("        PAVENTRA MVP v0.1")
print("=" * 40)

# Load road data
roads = pd.read_csv("data/roads.csv")

st.write("Road Data Columns:")
st.write(roads.columns.tolist())

# Calculate a risk score for each road
roads["Risk Score"] = roads.apply(
    lambda row: calculate_risk(
        row["Condition"],
        row["Traffic"],
        row["Age"],
        row["Freeze_Thaw"]
    ),
    axis=1
)

# Display the results
print("\nRoad Risk Assessment:\n")
print(roads)