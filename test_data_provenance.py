from contextlib import nullcontext, redirect_stdout
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
from components.municipality_assumptions import render_municipality_assumptions
from pilot.canonical_inventory import (
    CANONICAL_COLUMNS,
    load_canonical_inventory,
    validate_canonical_schema,
)
from pilot.data_provenance import (
    DataProvenanceStatus,
    LEGACY_ILLUSTRATIVE_STATUS,
    get_data_provenance,
    normalize_data_status,
    normalize_inventory_data_status,
)
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_onboarding import (
    export_canonical_inventory,
    main,
    map_source_to_canonical,
    parse_onboarding_manifest,
)
from pilot.municipality_registry import (
    DEMO_CITY_MUNICIPALITY,
    DEMO_ROAD_COMMISSION_MUNICIPALITY,
    JACKSON_MUNICIPALITY,
    ONBOARDING_DEMO_MANIFEST_PATH,
    ONBOARDING_DEMO_MUNICIPALITY,
)
from pilot.municipality_scenarios import build_municipality_scenario_results
from pilot.source_provenance import SourceProvenance


PROJECT_ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = PROJECT_ROOT / "docs" / "manifest.template.json"


class DataProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.raw = pd.read_csv(JACKSON_MUNICIPALITY.data_path)
        self.source_provenance = SourceProvenance(
            owner="City of Jackson",
            acquired_date="2026-08-15",
            reference="Jackson inventory delivery",
        )

    def test_supported_statuses_and_legacy_alias_normalize_deterministically(self):
        cases = {
            "illustrative": "illustrative",
            " ILLUSTRATIVE ": "illustrative",
            LEGACY_ILLUSTRATIVE_STATUS: "illustrative",
            "provisional": "provisional",
            "OFFICIAL": "official",
            DataProvenanceStatus.OFFICIAL: "official",
        }
        for supplied, expected in cases.items():
            with self.subTest(supplied=supplied):
                self.assertEqual(normalize_data_status(supplied), expected)

        with self.assertRaisesRegex(ValueError, "unsupported data status 'unverified'"):
            normalize_data_status("unverified")

    def test_each_status_validates_and_uses_centralized_language(self):
        for status, expected_label in (
            ("illustrative", "Illustrative demonstration analysis"),
            ("provisional", "Provisional analysis"),
            ("official", "Official-data analysis"),
        ):
            with self.subTest(status=status):
                roads = self.raw.assign(data_status=status)
                validate_canonical_schema(roads, expected_data_status=status)
                definition = get_data_provenance(status)
                self.assertEqual(definition.analysis_label, expected_label)
                self.assertIn(status.capitalize(), definition.label)

    def test_status_aware_config_and_report_flow_for_all_states(self):
        roads = load_municipality_inventory(JACKSON_MUNICIPALITY)
        results = build_municipality_scenario_results(
            roads,
            "Balanced Annual Program",
            JACKSON_MUNICIPALITY.scenario_catalog_id,
        )
        for status, notice_text in (
            ("illustrative", "Not an official City of Jackson analysis"),
            ("provisional", "have not been designated official"),
            ("official", "explicitly configured as official"),
        ):
            with self.subTest(status=status):
                config = replace(
                    JACKSON_MUNICIPALITY,
                    data_status=status,
                    source_provenance=(
                        None if status == "illustrative" else self.source_provenance
                    ),
                )
                status_roads = roads.assign(data_status=status)
                report = build_municipality_report(config, status_roads, results)
                self.assertIn(notice_text, config.pilot_disclaimer)
                self.assertTrue(report.startswith(b"%PDF"))

    def test_provisional_and_official_ui_assumptions_are_visibly_labeled(self):
        for status, expected in (
            ("provisional", "Provisional analysis"),
            ("official", "Official-data analysis"),
        ):
            with self.subTest(status=status), patch(
                "streamlit.expander",
                return_value=nullcontext(),
            ), patch("streamlit.markdown") as markdown:
                render_municipality_assumptions(
                    replace(
                        JACKSON_MUNICIPALITY,
                        data_status=status,
                        source_provenance=self.source_provenance,
                    )
                )
                rendered = " ".join(
                    str(call.args[0]) for call in markdown.call_args_list
                )
                self.assertIn(expected, rendered)

    def test_legacy_rows_load_as_stable_canonical_status(self):
        loaded = load_canonical_inventory(
            JACKSON_MUNICIPALITY.data_path,
            expected_data_status="illustrative",
            municipality_slug="jackson",
        )

        self.assertTrue(loaded["data_status"].eq("illustrative").all())

    def test_mixed_and_config_contradicting_statuses_fail(self):
        mixed = self.raw.copy()
        mixed.loc[0, "data_status"] = "provisional"
        with self.assertRaisesRegex(ValueError, "must be consistent across all rows"):
            validate_canonical_schema(mixed)

        provisional = self.raw.assign(data_status="provisional")
        with self.assertRaisesRegex(
            ValueError,
            "resolves to 'provisional' but configured data_status is 'illustrative'",
        ):
            validate_canonical_schema(
                provisional,
                expected_data_status="illustrative",
                municipality_slug="jackson",
            )

    def test_existing_registered_demos_remain_illustrative(self):
        existing_demos = (
            JACKSON_MUNICIPALITY,
            DEMO_CITY_MUNICIPALITY,
            DEMO_ROAD_COMMISSION_MUNICIPALITY,
            ONBOARDING_DEMO_MUNICIPALITY,
        )
        for config in existing_demos:
            with self.subTest(municipality=config.slug):
                self.assertEqual(config.normalized_data_status, "illustrative")
                roads = load_municipality_inventory(config)
                self.assertTrue(roads["data_status"].eq("illustrative").all())
                self.assertIn("Not an official", config.pilot_disclaimer)

    def test_manifest_v3_requires_explicit_status_and_v1_is_illustrative_only(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        missing = deepcopy(template)
        del missing["data_status"]
        with self.assertRaisesRegex(ValueError, "missing required fields: data_status"):
            parse_onboarding_manifest(missing, TEMPLATE_PATH)

        config = parse_onboarding_manifest(template, TEMPLATE_PATH)
        self.assertEqual(config.normalized_data_status, "provisional")
        self.assertEqual(config.onboarding_manifest_version, 3)
        self.assertEqual(ONBOARDING_DEMO_MUNICIPALITY.normalized_data_status, "illustrative")

    def test_mapped_status_must_agree_with_configuration(self):
        source = pd.read_csv(ONBOARDING_DEMO_MUNICIPALITY.data_path)
        provisional_config = replace(
            ONBOARDING_DEMO_MUNICIPALITY,
            data_status="provisional",
        )
        with self.assertRaisesRegex(
            ValueError,
            "resolves to 'illustrative' but configured data_status is 'provisional'",
        ):
            map_source_to_canonical(provisional_config, source)

    def test_export_preserves_status_and_rejects_expected_status_mismatch(self):
        provisional = normalize_inventory_data_status(
            self.raw.assign(data_status="provisional"),
            expected_status="provisional",
        )
        with tempfile.TemporaryDirectory() as directory_name:
            output = Path(directory_name) / "provisional.csv"
            export_canonical_inventory(
                provisional,
                output,
                expected_data_status="provisional",
                municipality_slug="test_agency",
            )
            exported = pd.read_csv(output)
            self.assertEqual(tuple(exported.columns), CANONICAL_COLUMNS)
            self.assertTrue(exported["data_status"].eq("provisional").all())

            with self.assertRaisesRegex(ValueError, "configured data_status is 'official'"):
                export_canonical_inventory(
                    provisional,
                    Path(directory_name) / "contradiction.csv",
                    expected_data_status="official",
                    municipality_slug="test_agency",
                )

            with self.assertRaisesRegex(ValueError, "configured data_status is 'illustrative'"):
                export_canonical_inventory(
                    provisional,
                    Path(directory_name) / "implicit-status.csv",
                )

    def test_report_rejects_status_contradiction(self):
        roads = load_municipality_inventory(JACKSON_MUNICIPALITY)
        results = build_municipality_scenario_results(
            roads,
            "Balanced Annual Program",
            JACKSON_MUNICIPALITY.scenario_catalog_id,
        )
        contradictory = roads.assign(data_status="provisional")
        with self.assertRaisesRegex(ValueError, "configured data_status is 'illustrative'"):
            build_municipality_report(JACKSON_MUNICIPALITY, contradictory, results)

    def test_dry_run_reports_resolved_status(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main([
                "--manifest",
                str(ONBOARDING_DEMO_MANIFEST_PATH),
                "--dry-run",
            ])
        self.assertEqual(exit_code, 0)
        self.assertIn("Data status: Illustrative (illustrative)", stdout.getvalue())

    def test_v2_provisional_manifest_injects_and_exports_canonical_status(self):
        manifest = json.loads(
            ONBOARDING_DEMO_MANIFEST_PATH.read_text(encoding="utf-8")
        )
        manifest["manifest_version"] = 2
        manifest["data_status"] = "provisional"
        manifest["source_csv_path"] = str(ONBOARDING_DEMO_MUNICIPALITY.data_path)
        manifest["column_mapping"].pop("Source_Status")

        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            manifest_path = directory / "manifest.json"
            output_path = directory / "provisional.csv"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main([
                    "--manifest",
                    str(manifest_path),
                    "--output",
                    str(output_path),
                ])

            self.assertEqual(exit_code, 0)
            exported = pd.read_csv(output_path)
            self.assertTrue(exported["data_status"].eq("provisional").all())
            self.assertIn("Data status: Provisional (provisional)", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
