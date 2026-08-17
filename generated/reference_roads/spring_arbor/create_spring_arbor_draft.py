from pathlib import Path

from pilot.municipality_admin import (
    MunicipalityIdentity,
    save_real_import_draft,
)

root = Path.cwd()

csv_path = (
    root
    / "generated"
    / "reference_roads"
    / "spring_arbor"
    / "spring_arbor_provisional_inventory.csv"
)

identity = MunicipalityIdentity(
    formal_name="Spring Arbor Township",
    short_name="Spring Arbor",
    entity_type="township",
    state="Michigan",
    slug="spring_arbor",
    leadership_label="township leadership",
    official_action_label="official township determination",
    map_center=(42.2147422611423, -84.5332642294177),
    map_zoom=12,
    scenario_catalog_id="standard",
)

columns = [
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
]

mapping = {column: column for column in columns}

source_content = csv_path.read_bytes()

workspace = save_real_import_draft(
    identity,
    source_content,
    mapping=mapping,
    defaults={},
    data_status="provisional",
    source_owner="Paventra rehearsal derived from State of Michigan GIS Open Data",
    acquired_date="2026-08-16",
    source_reference="State of Michigan GIS Open Data — All Roads (v17a), Spring Arbor rehearsal subset",
    source_field_meanings={
        "road_id": "Paventra rehearsal road identifier",
        "segment_id": "Paventra deterministic rehearsal segment identifier paired to GIS geometry",
        "road_name": "Road name derived from Michigan GIS RDNAME",
        "road_length_miles": "Road segment length converted from Michigan GIS LENGTH",
        "pci": "Provisional Paventra rehearsal assumption; not township-supplied PCI",
        "adt": "Provisional Paventra rehearsal assumption; not township-supplied traffic count",
        "recommended_treatment": "Provisional Paventra rehearsal assumption",
        "treatment_cost_per_lane_mile": "Provisional Paventra rehearsal assumption",
    },
)

print(f"Workspace: {workspace}")
