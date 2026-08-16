import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd
from pyproj import Transformer

from gis.engine import create_network_map
from pilot.municipality_admin import save_real_import_draft
from pilot.municipality_package_lifecycle import (
    PackageLifecycleState, begin_real_import_review, mark_real_import_ready,
    refresh_real_import_readiness, validate_real_import_package,
)
from pilot.municipality_registration import (
    get_persistent_registration, promote_registration, verify_registered_municipality,
)
from pilot.municipality_data_versions import (
    activate_update, begin_update_review, compare_candidate_to_active,
    create_update_workspace, mark_update_ready, rollback_active_version,
    validate_update_workspace,
)
from pilot.municipality_spatial import (
    SPATIAL_ARTIFACT_NAME, geometry_signatures, load_spatial_artifact,
    save_spatial_source, validate_spatial_workspace,
)
from test_municipality_registration import _identity, _source_mapping


def _draft(root: Path, slug: str = "spatial_harbor") -> Path:
    source, mapping = _source_mapping()
    return save_real_import_draft(
        _identity(slug), source, mapping=mapping, defaults={},
        data_status="provisional", source_owner="Harbor Township GIS office",
        acquired_date="2026-08-15", source_reference="HT roads and GIS delivery",
        generated_root=root,
    )


def _geojson(package: Path, *, missing_last=False, geometry_type="LineString") -> bytes:
    manifest = json.loads((package / "manifest.json").read_text())
    source = pd.read_csv(package / manifest["source_csv_path"])
    source_id = next(key for key, value in manifest["column_mapping"].items() if value == "segment_id")
    latitude = next(key for key, value in manifest["column_mapping"].items() if value == "latitude")
    longitude = next(key for key, value in manifest["column_mapping"].items() if value == "longitude")
    if missing_last:
        source = source.iloc[:-1]
    features = []
    for _, row in source.iterrows():
        coordinates = [[float(row[longitude]) - .001, float(row[latitude])], [float(row[longitude]) + .001, float(row[latitude])]]
        if geometry_type == "Point":
            coordinates = coordinates[0]
        features.append({
            "type": "Feature", "properties": {"GIS_SEG": str(row[source_id])},
            "geometry": {"type": geometry_type, "coordinates": coordinates},
        })
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


def _attach(package: Path, content: bytes, *, crs="EPSG:4326") -> None:
    save_spatial_source(
        package, content, source_id_field="GIS_SEG", canonical_id_field="segment_id",
        source_crs=crs, source_owner="Harbor Township GIS office",
        acquired_date="2026-08-15", source_reference="HT roads.geojson",
        provenance_confirmed=True,
    )


class MunicipalitySpatialTests(unittest.TestCase):
    def test_geojson_validates_joins_and_writes_normalized_artifact(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            _attach(package, _geojson(package))
            validated = validate_real_import_package(package)
            self.assertEqual(validated.lifecycle_state, PackageLifecycleState.VALIDATED)
            review = json.loads((package / "spatial_review.json").read_text())
            self.assertEqual(review["result"], "PASS")
            self.assertEqual(review["matched_count"], review["canonical_row_count"])
            artifact = load_spatial_artifact(package)
            self.assertTrue(artifact["features"])
            self.assertEqual(
                {feature["geometry"]["type"] for feature in artifact["features"]},
                {"LineString"},
            )
            self.assertEqual(len(geometry_signatures(package)), len(artifact["features"]))

    def test_missing_crs_unmatched_ids_and_wrong_geometry_block_validation(self):
        cases = (
            (_geojson, {"missing_last": True}, "EPSG:4326", "no spatial feature"),
            (_geojson, {"geometry_type": "Point"}, "EPSG:4326", "Only LineString"),
            (_geojson, {}, "", "CRS guessing is not allowed"),
        )
        for builder, arguments, crs, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as name:
                package = _draft(Path(name))
                _attach(package, builder(package, **arguments), crs=crs)
                failed = validate_real_import_package(package)
                self.assertEqual(failed.lifecycle_state, PackageLifecycleState.VALIDATION_REQUIRED)
                self.assertTrue(any(expected in issue.message for issue in failed.blocking_issues))

    def test_geometry_change_invalidates_registration_readiness(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            _attach(package, _geojson(package))
            validate_real_import_package(package)
            begin_real_import_review(package)
            mark_real_import_ready(package)
            artifact = package / SPATIAL_ARTIFACT_NAME
            document = json.loads(artifact.read_text())
            document["features"][0]["geometry"]["coordinates"][0][0] += .01
            artifact.write_text(json.dumps(document))
            inspection = refresh_real_import_readiness(package)
            self.assertEqual(inspection.lifecycle_state, PackageLifecycleState.VALIDATION_REQUIRED)

    def test_declared_crs_is_transformed_to_epsg4326(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            document = json.loads(_geojson(package))
            transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
            for feature in document["features"]:
                feature["geometry"]["coordinates"] = [
                    list(transformer.transform(*point))
                    for point in feature["geometry"]["coordinates"]
                ]
            _attach(package, json.dumps(document).encode(), crs="EPSG:3857")
            self.assertFalse(validate_real_import_package(package).blocking_issues)
            artifact = load_spatial_artifact(package)
            longitude, latitude = artifact["features"][0]["geometry"]["coordinates"][0]
            self.assertTrue(-180 <= longitude <= 180)
            self.assertTrue(-90 <= latitude <= 90)

    def test_embedded_crs_is_detected_and_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            document = json.loads(_geojson(package))
            document["crs"] = {
                "type": "name", "properties": {"name": "EPSG:4326"}
            }
            document["features"][1]["properties"]["GIS_SEG"] = document["features"][0]["properties"]["GIS_SEG"]
            _attach(package, json.dumps(document).encode(), crs="")
            failed = validate_real_import_package(package)
            self.assertTrue(any("unique" in issue.message for issue in failed.blocking_issues))
            review = json.loads((package / "spatial_review.json").read_text())
            self.assertEqual(review["source_crs"], "EPSG:4326")

    def test_multilinestring_is_supported(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            document = json.loads(_geojson(package))
            geometry = document["features"][0]["geometry"]
            geometry["type"] = "MultiLineString"
            geometry["coordinates"] = [geometry["coordinates"]]
            _attach(package, json.dumps(document).encode())
            self.assertFalse(validate_real_import_package(package).blocking_issues)
            types = {
                feature["geometry"]["type"]
                for feature in load_spatial_artifact(package)["features"]
            }
            self.assertIn("MultiLineString", types)

    def test_registration_preserves_and_verifies_geometry(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            package = _draft(base / "packages", "spatial_registration")
            _attach(package, _geojson(package))
            validate_real_import_package(package)
            begin_real_import_review(package)
            mark_real_import_ready(package)
            def corrupt_spatial_verifier(staging):
                artifact = staging / "versions" / "1" / SPATIAL_ARTIFACT_NAME
                artifact.write_text(artifact.read_text() + " ")
                return verify_registered_municipality(staging)

            with self.assertRaisesRegex(ValueError, "rolled back"):
                promote_registration(
                    package, confirmation_slug="spatial_registration", confirmed=True,
                    registration_root=base / "registrations", generated_root=base / "packages",
                    archived_root=base / "archived", verifier=corrupt_spatial_verifier,
                )
            self.assertFalse((base / "registrations" / "spatial_registration").exists())
            registered = promote_registration(
                package, confirmation_slug="spatial_registration", confirmed=True,
                registration_root=base / "registrations", generated_root=base / "packages",
                archived_root=base / "archived",
            )
            self.assertTrue((registered.config.data_directory / SPATIAL_ARTIFACT_NAME).is_file())
            metadata = json.loads(registered.metadata_path.read_text())
            self.assertEqual(metadata["spatial_feature_count"], len(load_spatial_artifact(registered.config.data_directory)["features"]))

    def test_map_prefers_lines_and_retains_coordinate_fallback(self):
        roads = pd.DataFrame([{
            "Road ID": "R-1", "segment_id": "S-1", "Road Name": "Main",
            "Latitude": 42.0, "Longitude": -84.0, "Risk Score": 75,
            "PCI": 40, "Traffic": "High", "Age": 20, "Freeze_Thaw": "High",
            "Treatment": "Overlay", "Estimated Cost": 1000, "Risk Reason": "Condition",
            "Risk Level": "High",
            "Surface Type": "Asphalt", "ADT": 1000, "Road Length": 1.0,
        }])
        geometry = {"type": "FeatureCollection", "features": [{
            "type": "Feature", "properties": {"road_id": "R-1", "segment_id": "S-1"},
            "geometry": {"type": "LineString", "coordinates": [[-84.01, 42.0], [-83.99, 42.0]]},
        }]}
        line_html = create_network_map(roads, selected_ids={"R-1"}, road_geometry=geometry).get_root().render()
        marker_html = create_network_map(roads).get_root().render()
        self.assertIn("LineString", line_html)
        self.assertIn("#FFD54F", line_html)
        self.assertIn("markerClusterGroup", marker_html)

    def test_geometry_is_version_specific_and_rollback_restores_v1(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            packages, registrations, updates = (
                base / "packages", base / "registrations", base / "updates"
            )
            package = _draft(packages, "spatial_versions")
            v1_geometry = _geojson(package)
            _attach(package, v1_geometry)
            validate_real_import_package(package)
            begin_real_import_review(package)
            mark_real_import_ready(package)
            registered = promote_registration(
                package, confirmation_slug="spatial_versions", confirmed=True,
                registration_root=registrations, generated_root=packages,
                archived_root=base / "archived",
            )
            v1_signatures = geometry_signatures(registered.config.data_directory)
            v2_document = json.loads(v1_geometry)
            v2_document["features"][0]["geometry"]["coordinates"][0][0] += .005
            source, _ = _source_mapping()
            workspace = create_update_workspace(
                "spatial_versions", source,
                source_owner="Harbor Township GIS office", acquired_date="2026-08-16",
                source_reference="HT version 2 delivery", data_status="provisional",
                provenance_confirmed=True, registration_root=registrations,
                workspace_root=updates, spatial_content=json.dumps(v2_document).encode(),
                spatial_source_id_field="GIS_SEG", spatial_source_crs="EPSG:4326",
            )
            validate_update_workspace(workspace, registration_root=registrations)
            comparison = compare_candidate_to_active(workspace, registration_root=registrations)
            self.assertEqual(comparison.geometry_changed_count, 1)
            begin_update_review(workspace, registration_root=registrations)
            mark_update_ready(workspace, registration_root=registrations)
            def corrupt_v2_verifier(registration):
                artifact = registration / "versions" / "2" / SPATIAL_ARTIFACT_NAME
                artifact.write_text(artifact.read_text() + " ")
                return verify_registered_municipality(registration)

            with self.assertRaisesRegex(ValueError, "previous active version was restored"):
                activate_update(
                    workspace, confirmation="spatial_versions version 2", confirmed=True,
                    registration_root=registrations, verifier=corrupt_v2_verifier,
                )
            self.assertEqual(
                get_persistent_registration("spatial_versions", registrations).active_data_version,
                1,
            )
            v2 = activate_update(
                workspace, confirmation="spatial_versions version 2", confirmed=True,
                registration_root=registrations,
            )
            self.assertNotEqual(v1_signatures, geometry_signatures(v2.config.data_directory))
            restored = rollback_active_version(
                "spatial_versions", 1, confirmation="spatial_versions version 1",
                confirmed=True, registration_root=registrations,
            )
            self.assertEqual(v1_signatures, geometry_signatures(restored.config.data_directory))


if __name__ == "__main__":
    unittest.main()
