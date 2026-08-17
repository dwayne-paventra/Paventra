from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from pilot.municipality_admin import (
    MunicipalityIdentity,
    save_real_import_draft,
)
from pilot.municipality_spatial import save_spatial_source, validate_spatial_workspace
from pilot.municipality_package_lifecycle import (
    validate_real_import_package,
    begin_real_import_review,
    mark_real_import_ready,
)
from pilot.municipality_registration import preview_registration


ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_geojson(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def mean_center(features: list[dict]) -> tuple[float, float]:
    points = []

    for feature in features:
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []

        if geometry.get("type") != "LineString":
            raise ValueError(
                f"Unsupported geometry type: {geometry.get('type')}"
            )

        for lon, lat, *_ in coords:
            points.append((float(lat), float(lon)))

    if not points:
        raise ValueError("No valid coordinates found.")

    latitude = sum(p[0] for p in points) / len(points)
    longitude = sum(p[1] for p in points) / len(points)

    return latitude, longitude


def prepare_municipality(config: dict) -> Path:
    source_path = ROOT / config["source_geojson"]
    geo = load_geojson(source_path)

    fmcd = int(config["fmcd"])

    filtered = [
        feature
        for feature in geo["features"]
        if (
            str(feature.get("properties", {}).get("FMCDL", "")).strip() == str(fmcd)
            or str(feature.get("properties", {}).get("FMCDR", "")).strip() == str(fmcd)
        )
    ]

    if not filtered:
        raise ValueError(
            f"No road features found for FMCD {fmcd}."
        )

    latitude, longitude = mean_center(filtered)

    rows = []

    for index, feature in enumerate(filtered, start=1):
        properties = feature["properties"]
        geometry = feature["geometry"]

        lrs_link = str(properties.get("LRS_LINK", "")).strip()
        road_name = str(properties.get("RDNAME", "")).strip()
        length_meters = float(properties.get("LENGTH", 0))

        if not lrs_link:
            raise ValueError(f"Feature {index} has blank LRS_LINK.")

        if not road_name:
            road_name = "Unnamed Road"

        segment_id = f"{config['segment_prefix']}-{index}-{lrs_link}"
        road_id = f"{config['segment_prefix']}-ROAD-{index}"

        feature.setdefault("properties", {})[
            "PAVENTRA_SEGMENT_ID"
        ] = segment_id

        first_coord = geometry["coordinates"][0]
        lon = float(first_coord[0])
        lat = float(first_coord[1])

        rows.append(
            {
                "road_id": road_id,
                "segment_id": segment_id,
                "road_name": road_name,
                "from_street": "",
                "to_street": "",
                "jurisdiction": config["formal_name"],
                "latitude": lat,
                "longitude": lon,
                "road_length_miles": round(
                    length_meters / 1609.344, 6
                ),
                "lanes": 2,
                "surface_type": "Asphalt",
                "functional_class": "Local",
                "pci": 65,
                "condition_date": config["condition_date"],
                "traffic_level": "Medium",
                "adt": 1000,
                "age_years": 10,
                "freeze_thaw": "Moderate",
                "recommended_treatment": "Crack Seal",
                "treatment_cost_per_lane_mile": 1,
                "data_status": "provisional",
                "data_source":
                    "Michigan GIS Open Data + Paventra rehearsal assumptions",
                "data_updated_at": config["condition_date"],
            }
        )

    output_root = (
        ROOT
        / "generated"
        / "reference_roads"
        / config["slug"]
    )
    output_root.mkdir(parents=True, exist_ok=True)

    csv_path = output_root / f"{config['slug']}_provisional_inventory.csv"
    geo_path = output_root / f"{config['slug']}_rehearsal_roads.geojson"

    pd.DataFrame(rows).to_csv(csv_path, index=False)

    geo_output = {
        "type": "FeatureCollection",
        "features": filtered,
    }

    geo_path.write_text(
        json.dumps(geo_output, indent=2),
        encoding="utf-8",
    )

    identity = MunicipalityIdentity(
        formal_name=config["formal_name"],
        short_name=config["short_name"],
        entity_type=config["entity_type"],
        state="Michigan",
        slug=config["slug"],
        leadership_label=config["leadership_label"],
        official_action_label=config["official_action_label"],
        map_center=(latitude, longitude),
        map_zoom=config.get("map_zoom", 12),
        scenario_catalog_id="standard",
    )

    columns = list(rows[0].keys())
    mapping = {column: column for column in columns}

    workspace = save_real_import_draft(
        identity,
        csv_path.read_bytes(),
        mapping=mapping,
        defaults={},
        data_status="provisional",
        source_owner=
            "Paventra rehearsal derived from State of Michigan GIS Open Data",
        acquired_date=config["source_acquired_date"],
        source_reference=config["source_reference"],
        source_field_meanings={
            "road_id": "Paventra rehearsal road identifier",
            "segment_id":
                "Paventra deterministic rehearsal segment identifier",
            "road_name": "Road name derived from Michigan GIS RDNAME",
            "road_length_miles":
                "Road segment length converted from Michigan GIS LENGTH",
            "pci":
                "Provisional rehearsal assumption; not municipality-supplied PCI",
            "adt":
                "Provisional rehearsal assumption; not municipality-supplied ADT",
            "recommended_treatment":
                "Provisional Paventra rehearsal assumption",
            "treatment_cost_per_lane_mile":
                "Provisional Paventra rehearsal assumption",
        },
    )

    save_spatial_source(
        workspace,
        geo_path.read_bytes(),
        source_id_field="PAVENTRA_SEGMENT_ID",
        canonical_id_field="segment_id",
        source_crs="EPSG:4326",
        source_owner="State of Michigan GIS Open Data",
        acquired_date=config["source_acquired_date"],
        source_reference=config["source_reference"],
        provenance_confirmed=True,
    )

    inspection = validate_real_import_package(workspace)

    if inspection.issues:
        raise RuntimeError(
            f"Canonical validation failed: {inspection.issues}"
        )

    spatial = validate_spatial_workspace(
        workspace,
        workspace / "canonical_review.csv",
    )

    if spatial is None:
        raise RuntimeError("Spatial validation did not return a review.")

    if spatial.issues:
        raise RuntimeError(
            f"Spatial validation failed: {spatial.issues}"
        )

    if spatial.match_percentage != 100:
        raise RuntimeError(
            f"Spatial match was {spatial.match_percentage}%."
        )

    begin_real_import_review(workspace)
    ready = mark_real_import_ready(workspace)

    preview = preview_registration(workspace)

    print()
    print("=" * 60)
    print(config["formal_name"])
    print("=" * 60)
    print(f"Road features:       {spatial.feature_count}")
    print(f"Canonical rows:      {spatial.canonical_row_count}")
    print(f"Matched:             {spatial.matched_count}")
    print(f"Match percentage:    {spatial.match_percentage}%")
    print(f"Invalid geometries:  {spatial.invalid_geometry_count}")
    print(f"Lifecycle:           {ready.lifecycle_state.value}")
    print(f"Registration issues: {len(preview.issues)}")
    print(f"Workspace:           {workspace}")
    print()
    print("READY FOR MANUAL REGISTRATION REVIEW")

    return workspace


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    args = parser.parse_args()

    prepare_municipality(load_config(Path(args.config)))


if __name__ == "__main__":
    main()


