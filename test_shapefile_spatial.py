import json
from pathlib import Path
import tempfile
import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point

from components.municipality_report import build_municipality_report
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_data_versions import (
    activate_update, begin_update_review, compare_candidate_to_active,
    create_update_workspace, mark_update_ready, rollback_active_version,
    validate_update_workspace,
)
from pilot.municipality_package_lifecycle import (
    PackageLifecycleState, begin_real_import_review, mark_real_import_ready,
    validate_real_import_package,
)
from pilot.municipality_registration import (
    get_persistent_registration, promote_registration,
)
from pilot.municipality_scenarios import (
    build_municipality_scenario_results, get_scenario_catalog,
)
from pilot.municipality_spatial import (
    DEFAULT_MAX_BUNDLE_BYTES, SHAPEFILE_SOURCE_DIRECTORY,
    SPATIAL_ARTIFACT_NAME, build_exact_match_preview, geometry_signatures,
    inspect_shapefile_bundle, load_spatial_artifact, save_shapefile_source,
    suggest_spatial_identifier_fields, validate_shapefile_bundle,
    update_spatial_identifier_mapping,
)
from test_municipality_registration import _source_mapping
from test_municipality_spatial import _draft


def _bundle(package: Path, *, ids=None, geometry_type="line", shift=0.0) -> dict[str, bytes]:
    manifest = json.loads((package / "manifest.json").read_text())
    source = pd.read_csv(package / manifest["source_csv_path"])
    source_id = next(
        key for key, value in manifest["column_mapping"].items() if value == "segment_id"
    )
    latitude = next(
        key for key, value in manifest["column_mapping"].items() if value == "latitude"
    )
    longitude = next(
        key for key, value in manifest["column_mapping"].items() if value == "longitude"
    )
    values = list(ids) if ids is not None else source[source_id].astype(str).tolist()
    geometries = []
    for position, (_, row) in enumerate(source.iterrows()):
        lon = float(row[longitude]) + (shift if position == 0 else 0)
        lat = float(row[latitude])
        geometries.append(
            Point(lon, lat)
            if geometry_type == "point"
            else LineString([(lon - .001, lat), (lon + .001, lat)])
        )
    frame = gpd.GeoDataFrame(
        {"GIS_SEG": values, "ROAD_NAME": source.iloc[:len(values)][source.columns[2]].astype(str)},
        geometry=geometries[:len(values)],
        crs="EPSG:4326",
    ).to_crs("EPSG:3857")
    with tempfile.TemporaryDirectory() as directory_name:
        path = Path(directory_name) / "municipal_roads.shp"
        frame.to_file(path)
        return {
            item.name: item.read_bytes()
            for item in path.parent.iterdir()
            if item.suffix.casefold() in {".shp", ".shx", ".dbf", ".prj", ".cpg"}
        }


class ShapefileSpatialTests(unittest.TestCase):
    def test_component_validation_and_clear_missing_errors(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            complete = _bundle(package)
            summary = validate_shapefile_bundle(complete)
            self.assertTrue(summary.bundle_checksum)
            self.assertEqual(summary.total_bytes, sum(map(len, complete.values())))
            for extension in (".shp", ".shx", ".dbf", ".prj"):
                incomplete = {
                    filename: content for filename, content in complete.items()
                    if Path(filename).suffix.casefold() != extension
                }
                with self.subTest(extension=extension), self.assertRaisesRegex(
                    ValueError, f"Missing required shapefile component: {extension}"
                ):
                    validate_shapefile_bundle(incomplete)

    def test_bundle_rejects_mixed_duplicate_unsafe_empty_and_oversize_files(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            complete = _bundle(package)
            shp_name = next(name for name in complete if name.endswith(".shp"))
            mixed = dict(complete)
            mixed["different.shp"] = mixed.pop(shp_name)
            with self.assertRaisesRegex(ValueError, "share one basename"):
                validate_shapefile_bundle(mixed)
            duplicate = dict(complete)
            duplicate["copy.dbf"] = next(
                content for filename, content in complete.items() if filename.endswith(".dbf")
            )
            with self.assertRaisesRegex(ValueError, "Duplicate shapefile component: .dbf"):
                validate_shapefile_bundle(duplicate)
            unsafe = dict(complete)
            unsafe["../municipal_roads.shp"] = unsafe.pop(shp_name)
            with self.assertRaisesRegex(ValueError, "unsafe"):
                validate_shapefile_bundle(unsafe)
            empty = dict(complete)
            empty[shp_name] = b""
            with self.assertRaisesRegex(ValueError, "is empty"):
                validate_shapefile_bundle(empty)
            with self.assertRaisesRegex(ValueError, "operator limit"):
                validate_shapefile_bundle(complete, max_bytes=1)

    def test_fingerprint_is_deterministic_and_changes_with_source_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            complete = _bundle(package)
            first = validate_shapefile_bundle(complete)
            reversed_files = dict(reversed(list(complete.items())))
            self.assertEqual(first.bundle_checksum, validate_shapefile_bundle(reversed_files).bundle_checksum)
            changed = dict(complete)
            cpg = next(filename for filename in changed if filename.endswith(".cpg"))
            changed[cpg] += b" "
            self.assertNotEqual(first.bundle_checksum, validate_shapefile_bundle(changed).bundle_checksum)

    def test_parsing_crs_attributes_identifier_suggestions_and_quality_preview(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            preview = inspect_shapefile_bundle(_bundle(package))
            self.assertEqual(preview.source_format, "Shapefile")
            self.assertEqual(preview.feature_count, 5)
            self.assertIn("GIS_SEG", preview.attribute_columns)
            self.assertIn("3857", preview.source_crs)
            self.assertEqual(preview.geometry_counts["LineString"], 5)
            self.assertEqual(preview.empty_geometry_count, 0)
            self.assertEqual(preview.invalid_geometry_count, 0)
            self.assertEqual(
                suggest_spatial_identifier_fields(["NAME", "asset_id", "segment_id"]),
                ("segment_id", "asset_id"),
            )
            self.assertEqual(suggest_spatial_identifier_fields(["NAME", "TYPE"]), ())

    def test_exact_match_preview_never_changes_or_fuzzes_identifiers(self):
        preview = build_exact_match_preview(
            ["A-1", "A-1", "Road 2"], ["A-1", "ROAD 2", "C-3"],
            source_id_field="GIS_SEG", canonical_id_field="segment_id",
        )
        self.assertEqual(preview.exact_match_count, 1)
        self.assertEqual(preview.duplicate_source_ids, ("A-1",))
        self.assertEqual(preview.source_only_ids, ("Road 2",))
        self.assertEqual(preview.canonical_only_ids, ("C-3", "ROAD 2"))

    def test_save_validate_transform_and_preserve_original_bundle(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            bundle = _bundle(package)
            save_shapefile_source(
                package, bundle, source_id_field="GIS_SEG",
                source_owner="Harbor GIS", acquired_date="2026-08-17",
                source_reference="Harbor GIS export", provenance_confirmed=True,
            )
            validated = validate_real_import_package(package)
            self.assertEqual(validated.lifecycle_state, PackageLifecycleState.VALIDATED)
            review = json.loads((package / "spatial_review.json").read_text())
            self.assertEqual(review["result"], "PASS")
            self.assertEqual(review["match_percentage"], 100.0)
            self.assertEqual(review["linestring_count"], 5)
            artifact = load_spatial_artifact(package)
            self.assertEqual(len(artifact["features"]), 5)
            for filename, content in bundle.items():
                self.assertEqual((package / SHAPEFILE_SOURCE_DIRECTORY / filename).read_bytes(), content)
            metadata = json.loads((package / "spatial_metadata.json").read_text())
            self.assertEqual(metadata["source_format"], "Shapefile")
            self.assertEqual(len(metadata["source_files"]), len(bundle))
            longitude, latitude = artifact["features"][0]["geometry"]["coordinates"][0]
            self.assertTrue(-180 <= longitude <= 180 and -90 <= latitude <= 90)

    def test_operator_errors_for_corrupt_missing_identifier_duplicate_and_mismatch(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            package = _draft(root / "corrupt")
            corrupt = _bundle(package)
            shp = next(filename for filename in corrupt if filename.endswith(".shp"))
            corrupt[shp] = b"not a shapefile"
            with self.assertRaisesRegex(ValueError, "could not be read"):
                inspect_shapefile_bundle(corrupt)

            with self.assertRaisesRegex(ValueError, "identifier column 'UNKNOWN' is missing"):
                save_shapefile_source(
                    package, _bundle(package), source_id_field="UNKNOWN",
                    source_owner="owner", acquired_date="2026-08-17",
                    source_reference="reference", provenance_confirmed=True,
                )

            for slug, ids, geometry_type, expected in (
                ("duplicate_shape", ["PRT-S-001"] * 5, "line", "unique"),
                ("unmatched_shape", ["X-1", "X-2", "X-3", "X-4", "X-5"], "line", "do not match"),
                ("point_shape", None, "point", "Only LineString"),
            ):
                with self.subTest(slug=slug):
                    target = _draft(root / slug, slug)
                    save_shapefile_source(
                        target, _bundle(target, ids=ids, geometry_type=geometry_type),
                        source_id_field="GIS_SEG", source_owner="owner",
                        acquired_date="2026-08-17", source_reference="reference",
                        provenance_confirmed=True,
                    )
                    failed = validate_real_import_package(target)
                    self.assertTrue(any(expected in issue.message for issue in failed.blocking_issues))

    def test_preserved_source_can_be_reopened_and_mapping_corrected_without_reupload(self):
        with tempfile.TemporaryDirectory() as name:
            package = _draft(Path(name))
            save_shapefile_source(
                package, _bundle(package), source_id_field="ROAD_NAME",
                source_owner="owner", acquired_date="2026-08-17",
                source_reference="reference", provenance_confirmed=True,
            )
            failed = validate_real_import_package(package)
            self.assertTrue(failed.blocking_issues)
            update_spatial_identifier_mapping(
                package, source_id_field="GIS_SEG", canonical_id_field="segment_id"
            )
            corrected = validate_real_import_package(package)
            self.assertEqual(corrected.lifecycle_state, PackageLifecycleState.VALIDATED)
            self.assertFalse(corrected.blocking_issues)

    def test_registered_restart_rejects_tampered_original_bundle(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            package = _draft(base / "packages", "shapefile_tamper")
            save_shapefile_source(
                package, _bundle(package), source_id_field="GIS_SEG",
                source_owner="owner", acquired_date="2026-08-17",
                source_reference="reference", provenance_confirmed=True,
            )
            validate_real_import_package(package)
            begin_real_import_review(package)
            mark_real_import_ready(package)
            registered = promote_registration(
                package, confirmation_slug="shapefile_tamper", confirmed=True,
                registration_root=base / "registrations", generated_root=base / "packages",
                archived_root=base / "archived",
            )
            cpg = next(
                path for path in (registered.config.data_directory / SHAPEFILE_SOURCE_DIRECTORY).iterdir()
                if path.suffix.casefold() == ".cpg"
            )
            cpg.write_bytes(cpg.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "fingerprint|checksums"):
                get_persistent_registration("shapefile_tamper", base / "registrations")

    def test_shapefile_registration_v2_activation_restart_report_and_rollback(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            packages, registrations, updates = base / "packages", base / "registrations", base / "updates"
            package = _draft(packages, "shapefile_versions")
            save_shapefile_source(
                package, _bundle(package), source_id_field="GIS_SEG",
                source_owner="Harbor GIS", acquired_date="2026-08-17",
                source_reference="Harbor v1 shapefile", provenance_confirmed=True,
            )
            validate_real_import_package(package)
            begin_real_import_review(package)
            mark_real_import_ready(package)
            registered = promote_registration(
                package, confirmation_slug="shapefile_versions", confirmed=True,
                registration_root=registrations, generated_root=packages,
                archived_root=base / "archived",
            )
            v1 = geometry_signatures(registered.config.data_directory)
            self.assertTrue((registered.config.data_directory / SHAPEFILE_SOURCE_DIRECTORY).is_dir())
            restarted = get_persistent_registration("shapefile_versions", registrations)
            roads = load_municipality_inventory(restarted.config)
            scenario_name = next(iter(get_scenario_catalog(restarted.config.scenario_catalog_id)))
            results = build_municipality_scenario_results(
                roads, scenario_name, restarted.config.scenario_catalog_id
            )
            self.assertTrue(build_municipality_report(restarted.config, roads, results).startswith(b"%PDF"))

            source, _ = _source_mapping()
            workspace = create_update_workspace(
                "shapefile_versions", source, source_owner="Harbor GIS",
                acquired_date="2026-08-18", source_reference="Harbor v2 shapefile",
                data_status="provisional", provenance_confirmed=True,
                registration_root=registrations, workspace_root=updates,
                spatial_shapefile_files=_bundle(package, shift=.005),
                spatial_source_id_field="GIS_SEG",
            )
            validate_update_workspace(workspace, registration_root=registrations)
            comparison = compare_candidate_to_active(workspace, registration_root=registrations)
            self.assertEqual(comparison.geometry_changed_count, 1)
            begin_update_review(workspace, registration_root=registrations)
            mark_update_ready(workspace, registration_root=registrations)
            active_v2 = activate_update(
                workspace, confirmation="shapefile_versions version 2", confirmed=True,
                registration_root=registrations,
            )
            self.assertEqual(active_v2.active_data_version, 2)
            self.assertNotEqual(v1, geometry_signatures(active_v2.config.data_directory))
            restarted_v2 = get_persistent_registration("shapefile_versions", registrations)
            self.assertEqual(restarted_v2.active_data_version, 2)
            restored = rollback_active_version(
                "shapefile_versions", 1,
                confirmation="shapefile_versions version 1", confirmed=True,
                registration_root=registrations,
            )
            self.assertEqual(v1, geometry_signatures(restored.config.data_directory))


if __name__ == "__main__":
    unittest.main()
