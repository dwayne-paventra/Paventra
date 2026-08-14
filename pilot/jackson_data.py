"""Canonical data contract and compatibility adapter for the Jackson Pilot."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pilot.jackson_config import JACKSON_MUNICIPALITY
from predictor import calculate_risk_details


JACKSON_CANONICAL_COLUMNS = (
    "road_id",
    "segment_id",
    "road_name",
    "from_street",
    "to_street",
    "jurisdiction",
    "latitude",
    "longitude",
    "road_length_miles",
    "lanes",
    "surface_type",
    "functional_class",
    "pci",
    "condition_date",
    "traffic_level",
    "adt",
    "age_years",
    "freeze_thaw",
    "recommended_treatment",
    "treatment_cost_per_lane_mile",
    "data_status",
    "data_source",
    "data_updated_at",
)

_NUMERIC_COLUMNS = (
    "latitude", "longitude", "road_length_miles", "lanes", "pci", "adt",
    "age_years", "treatment_cost_per_lane_mile",
)

_LEGACY_COLUMNS = {
    "road_id": "Road ID",
    "road_name": "Road Name",
    "pci": "PCI",
    "traffic_level": "Traffic",
    "age_years": "Age",
    "freeze_thaw": "Freeze_Thaw",
    "recommended_treatment": "Treatment",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "road_length_miles": "Road Length",
    "lanes": "Lanes",
    "surface_type": "Surface Type",
    "adt": "ADT",
}


def normalize_treatment(value: object) -> str:
    """Normalize common treatment labels into the pilot's controlled vocabulary."""

    normalized = str(value or "").strip().lower()
    aliases = {
        "": "Not Assigned",
        "none": "Not Assigned",
        "no treatment": "Not Assigned",
        "mill & overlay": "Mill & Fill",
        "mill and overlay": "Mill & Fill",
        "mill & fill": "Mill & Fill",
        "mill and fill": "Mill & Fill",
        "crack seal": "Crack Seal",
        "overlay": "Overlay",
        "reconstruction": "Reconstruction",
    }
    return aliases.get(normalized, str(value).strip())


def validate_jackson_schema(roads: pd.DataFrame) -> None:
    """Validate the minimum canonical contract for a Jackson demo inventory."""

    missing = [column for column in JACKSON_CANONICAL_COLUMNS if column not in roads.columns]
    if missing:
        raise ValueError("Jackson data is missing required columns: " + ", ".join(missing))

    if roads["segment_id"].isna().any() or roads["segment_id"].duplicated().any():
        raise ValueError("segment_id must be present and unique.")

    for column in _NUMERIC_COLUMNS:
        values = pd.to_numeric(roads[column], errors="coerce")
        if values.isna().any():
            raise ValueError(f"{column} must contain numeric values.")

    if not roads["pci"].between(0, 100).all():
        raise ValueError("pci must be between 0 and 100.")

    if not roads["data_status"].eq("Illustrative demonstration data").all():
        raise ValueError("Jackson demonstration data must be explicitly marked illustrative.")


def load_jackson_canonical_data(path: str | Path = JACKSON_MUNICIPALITY.data_path) -> pd.DataFrame:
    """Load, validate, and enrich the canonical illustrative Jackson dataset."""

    roads = pd.read_csv(path)
    validate_jackson_schema(roads)
    roads = roads.copy()
    roads["recommended_treatment"] = roads["recommended_treatment"].map(normalize_treatment)

    details = roads.apply(
        lambda row: calculate_risk_details(
            condition=row["pci"],
            traffic=row["traffic_level"],
            age=row["age_years"],
            freeze=row["freeze_thaw"],
            pci=row["pci"],
            adt=row["adt"],
        ),
        axis=1,
    )
    roads["risk_score"] = details.map(lambda detail: detail["score"])
    roads["risk_level"] = details.map(lambda detail: detail["level"])
    roads["risk_reason"] = details.map(lambda detail: detail["reason"])
    return roads


def to_streamlit_inventory(
    roads: pd.DataFrame,
    municipality_name: str = JACKSON_MUNICIPALITY.name,
) -> pd.DataFrame:
    """Adapt the canonical contract to the existing, title-cased Streamlit UI."""

    inventory = roads.rename(columns=_LEGACY_COLUMNS).copy()
    inventory["Condition"] = inventory["PCI"]
    inventory["Risk Score"] = inventory["risk_score"]
    inventory["Risk Level"] = inventory["risk_level"]
    inventory["Risk Reason"] = inventory["risk_reason"]
    inventory["Speed Limit"] = 25
    inventory["County"] = municipality_name
    inventory["Lane Miles"] = inventory["Road Length"] * inventory["Lanes"]
    inventory["Estimated Cost"] = (
        inventory["Lane Miles"] * inventory["treatment_cost_per_lane_mile"]
    )
    return inventory


def load_jackson_streamlit_inventory(
    path: str | Path = JACKSON_MUNICIPALITY.data_path,
    municipality_name: str = JACKSON_MUNICIPALITY.name,
) -> pd.DataFrame:
    """Load the pilot dataset in a form compatible with the current dashboard."""

    return to_streamlit_inventory(
        load_jackson_canonical_data(path),
        municipality_name=municipality_name,
    )
