from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from components.municipality_report import build_municipality_report
from pilot.municipality_config import validate_municipality_config
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_onboarding import (
    main,
    parse_onboarding_manifest,
    prepare_manifest_inventory,
)
from pilot.municipality_registry import (
    JACKSON_MUNICIPALITY,
    ONBOARDING_DEMO_MANIFEST_PATH,
    ONBOARDING_DEMO_MUNICIPALITY,
)
from pilot.municipality_scenarios import build_municipality_scenario_results
from pilot.source_provenance import (
    SourceProvenance,
    compute_source_checksum,
    verify_source_checksum,
)


class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.v1_manifest = json.loads(
            ONBOARDING_DEMO_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        self.source_path = ONBOARDING_DEMO_MUNICIPALITY.data_path
        self.actual_checksum = compute_source_checksum(self.source_path)

    def _v3_manifest(self, **updates):
        manifest = deepcopy(self.v1_manifest)
        manifest.update({
            "manifest_version": 3,
            "data_status": "provisional",
            "source_csv_path": str(self.source_path),
            "source_owner": "Pine Ridge Township",
            "source_acquired_date": "2026-08-15",
            "source_reference": "Pine Ridge source_roads.csv delivery",
        })
        manifest["column_mapping"].pop("Source_Status")
        manifest.update(updates)
        return manifest

    def _write_manifest(self, directory: Path, manifest: dict) -> Path:
        path = directory / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_v1_and_v2_compatibility_do_not_claim_source_metadata(self):
        v1 = parse_onboarding_manifest(self.v1_manifest, ONBOARDING_DEMO_MANIFEST_PATH)
        self.assertEqual(v1.normalized_data_status, "illustrative")
        self.assertIsNone(v1.source_provenance)
        self.assertIn("synthetic or illustrative", v1.source_provenance_label)

        v2_manifest = deepcopy(self.v1_manifest)
        v2_manifest["manifest_version"] = 2
        v2_manifest["data_status"] = "provisional"
        v2 = parse_onboarding_manifest(v2_manifest, ONBOARDING_DEMO_MANIFEST_PATH)
        self.assertEqual(v2.normalized_data_status, "provisional")
        self.assertIsNone(v2.source_provenance)
        self.assertIn("unavailable under legacy manifest version 2", v2.source_provenance_label)

    def test_v3_constructs_dataset_level_source_provenance(self):
        config = parse_onboarding_manifest(
            self._v3_manifest(),
            ONBOARDING_DEMO_MANIFEST_PATH,
        )

        self.assertEqual(config.onboarding_manifest_version, 3)
        self.assertEqual(config.source_provenance.owner, "Pine Ridge Township")
        self.assertEqual(config.source_provenance.acquired_date, "2026-08-15")
        self.assertEqual(
            config.source_provenance.reference,
            "Pine Ridge source_roads.csv delivery",
        )
        self.assertIsNone(config.source_provenance.checksum)

        changed = replace(
            config,
            source_provenance=replace(
                config.source_provenance,
                reference="A different delivery reference",
            ),
        )
        self.assertNotEqual(
            config.source_provenance_cache_key,
            changed.source_provenance_cache_key,
        )

    def test_v3_illustrative_manifest_may_omit_source_metadata(self):
        manifest = self._v3_manifest(data_status="illustrative")
        for field in (
            "source_owner",
            "source_acquired_date",
            "source_reference",
        ):
            manifest.pop(field)
        config = parse_onboarding_manifest(manifest, ONBOARDING_DEMO_MANIFEST_PATH)

        self.assertEqual(config.normalized_data_status, "illustrative")
        self.assertIsNone(config.source_provenance)
        self.assertIn("synthetic or illustrative", config.source_provenance_label)

    def test_v3_onboards_provisional_and_official_without_changing_status(self):
        for status in ("provisional", "official"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory_name:
                manifest_path = self._write_manifest(
                    Path(directory_name),
                    self._v3_manifest(data_status=status),
                )
                config, inventory = prepare_manifest_inventory(manifest_path)

                self.assertEqual(config.normalized_data_status, status)
                self.assertTrue(inventory["data_status"].eq(status).all())
                self.assertEqual(config.source_provenance.owner, "Pine Ridge Township")

    def test_new_provisional_and_official_configs_require_source_metadata(self):
        for status in ("provisional", "official"):
            with self.subTest(status=status), self.assertRaisesRegex(
                ValueError,
                "requires source provenance metadata",
            ):
                validate_municipality_config(
                    replace(JACKSON_MUNICIPALITY, data_status=status)
                )

    def test_acquisition_date_and_required_text_validation(self):
        cases = (
            ("source_owner", "", "field 'source_owner'"),
            ("source_acquired_date", "2026/08/15", "must use ISO date"),
            ("source_acquired_date", "2026-02-30", "not a valid calendar date"),
            ("source_reference", " ", "field 'source_reference'"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field, value=value):
                manifest = self._v3_manifest(**{field: value})
                with self.assertRaisesRegex(ValueError, expected):
                    parse_onboarding_manifest(manifest, ONBOARDING_DEMO_MANIFEST_PATH)

    def test_checksum_format_and_match_validation(self):
        invalid = self._v3_manifest(source_checksum="not-a-sha256")
        with self.assertRaisesRegex(ValueError, "64-character hexadecimal SHA-256"):
            parse_onboarding_manifest(invalid, ONBOARDING_DEMO_MANIFEST_PATH)

        provenance = SourceProvenance(
            owner="Pine Ridge Township",
            acquired_date="2026-08-15",
            reference="Pine Ridge delivery",
            checksum=self.actual_checksum.upper(),
        )
        result = verify_source_checksum(
            self.source_path,
            provenance,
            municipality_slug="onboarding_demo",
        )
        self.assertTrue(result.matched)
        self.assertEqual(result.actual, self.actual_checksum)
        self.assertEqual(result.declared, self.actual_checksum)

    def test_checksum_mismatch_fails_before_inventory_export(self):
        manifest = self._v3_manifest(source_checksum="0" * 64)
        with tempfile.TemporaryDirectory() as directory_name:
            manifest_path = self._write_manifest(Path(directory_name), manifest)
            with self.assertRaisesRegex(
                ValueError,
                "source_checksum.*does not match.*declared.*actual",
            ):
                prepare_manifest_inventory(manifest_path)

            output = Path(directory_name) / "should-not-exist.csv"
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = main([
                    "--manifest", str(manifest_path), "--output", str(output)
                ])
            self.assertEqual(exit_code, 1)
            self.assertFalse(output.exists())
            self.assertIn("does not match", stderr.getvalue())

    def test_declared_checksum_is_enforced_by_canonical_adapter(self):
        config = replace(
            JACKSON_MUNICIPALITY,
            source_provenance=SourceProvenance(
                owner="Paventra",
                acquired_date="2026-08-15",
                reference="Jackson demonstration source",
                checksum="0" * 64,
            ),
        )
        with self.assertRaisesRegex(ValueError, "source_checksum.*does not match"):
            load_municipality_inventory(config)

    def test_cli_dry_run_reports_source_provenance_and_checksum_match(self):
        manifest = self._v3_manifest(source_checksum=self.actual_checksum)
        with tempfile.TemporaryDirectory() as directory_name:
            manifest_path = self._write_manifest(Path(directory_name), manifest)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main([
                    "--manifest", str(manifest_path), "--dry-run"
                ])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("Data status: Provisional (provisional)", output)
        self.assertIn("Source owner: Pine Ridge Township", output)
        self.assertIn("Source acquired: 2026-08-15", output)
        self.assertIn("Source reference: Pine Ridge source_roads.csv delivery", output)
        self.assertIn(f"Actual SHA-256: {self.actual_checksum}", output)
        self.assertIn("Declared checksum match: yes", output)

    def test_report_surfaces_owner_date_and_reference(self):
        provenance = SourceProvenance(
            owner="City of Jackson",
            acquired_date="2026-08-15",
            reference="Jackson inventory delivery",
            checksum=compute_source_checksum(JACKSON_MUNICIPALITY.data_path),
        )
        config = replace(
            JACKSON_MUNICIPALITY,
            data_status="provisional",
            source_provenance=provenance,
        )
        roads = load_municipality_inventory(JACKSON_MUNICIPALITY).assign(
            data_status="provisional"
        )
        results = build_municipality_scenario_results(
            roads,
            "Balanced Annual Program",
            config.scenario_catalog_id,
        )
        captured_story = []

        class CapturingDocument:
            def build(self, story, **page_callbacks):
                self.page_callbacks = page_callbacks
                captured_story.extend(story)

        with patch(
            "components.municipality_report.SimpleDocTemplate",
            return_value=CapturingDocument(),
        ):
            build_municipality_report(config, roads, results)

        rendered = " ".join(
            item.getPlainText() for item in captured_story if hasattr(item, "getPlainText")
        )
        self.assertIn("Dataset source provenance", rendered)
        self.assertIn("Source owner: City of Jackson", rendered)
        self.assertIn("Acquired: 2026-08-15", rendered)
        self.assertIn("Jackson inventory delivery", rendered)
        self.assertIn("integrity comparison only", rendered)


if __name__ == "__main__":
    unittest.main()
