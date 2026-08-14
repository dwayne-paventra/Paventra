from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from pilot.canonical_inventory import CANONICAL_COLUMNS, validate_canonical_schema
from pilot.municipality_onboarding import (
    load_onboarding_manifest,
    main,
    parse_onboarding_manifest,
    prepare_manifest_inventory,
)
from pilot.municipality_registry import (
    MUNICIPALITIES,
    ONBOARDING_DEMO_COLUMN_MAPPING,
    ONBOARDING_DEMO_MANIFEST_PATH,
    ONBOARDING_DEMO_MUNICIPALITY,
    validate_municipality_registry,
)


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_PATH = PROJECT_ROOT / "data" / "onboarding_demo" / "source_roads.csv"


class MunicipalityManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(
            ONBOARDING_DEMO_MANIFEST_PATH.read_text(encoding="utf-8")
        )

    def _write_manifest(self, directory: Path, **updates) -> Path:
        manifest = deepcopy(self.manifest)
        manifest["source_csv_path"] = str(SOURCE_PATH)
        manifest.update(updates)
        path = directory / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_pine_ridge_manifest_constructs_existing_config_model(self):
        config = load_onboarding_manifest(ONBOARDING_DEMO_MANIFEST_PATH)

        self.assertEqual(config, ONBOARDING_DEMO_MUNICIPALITY)
        self.assertEqual(config.data_path, SOURCE_PATH)
        self.assertEqual(
            dict(config.source_column_mapping),
            ONBOARDING_DEMO_COLUMN_MAPPING,
        )
        self.assertEqual(config.canonical_defaults, {})
        self.assertIs(MUNICIPALITIES[config.slug], ONBOARDING_DEMO_MUNICIPALITY)
        validate_municipality_registry()

    def test_manifest_requires_every_declarative_field(self):
        invalid = deepcopy(self.manifest)
        del invalid["formal_name"]

        with self.assertRaisesRegex(
            ValueError,
            "missing required fields: formal_name",
        ):
            parse_onboarding_manifest(invalid, ONBOARDING_DEMO_MANIFEST_PATH)

    def test_manifest_rejects_invalid_json_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            malformed = directory / "malformed.json"
            malformed.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contains invalid JSON"):
                load_onboarding_manifest(malformed)

            invalid = deepcopy(self.manifest)
            invalid["typo_field"] = "value"
            with self.assertRaisesRegex(ValueError, "unknown fields: typo_field"):
                parse_onboarding_manifest(invalid, malformed)

    def test_manifest_reuses_config_adapter_and_catalog_validation(self):
        cases = (
            ("formal_name", "", "field 'formal_name'"),
            ("inventory_adapter", "missing", "unknown adapter 'missing'"),
            ("scenario_catalog_id", "missing", "unknown catalog 'missing'"),
            ("map_center", [120, -84], "map_center.latitude"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                invalid = deepcopy(self.manifest)
                invalid[field] = value
                with self.assertRaisesRegex(ValueError, expected):
                    parse_onboarding_manifest(
                        invalid,
                        ONBOARDING_DEMO_MANIFEST_PATH,
                    )

    def test_manifest_source_and_mapping_fail_clearly(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            missing_source = self._write_manifest(
                directory,
                source_csv_path="missing.csv",
            )
            with self.assertRaisesRegex(ValueError, "source inventory CSV was not found"):
                prepare_manifest_inventory(missing_source)

            mapping = deepcopy(self.manifest["column_mapping"])
            del mapping["Street_Name"]
            missing_mapping = self._write_manifest(
                directory,
                column_mapping=mapping,
            )
            with self.assertRaisesRegex(
                ValueError,
                "missing source mappings or defaults for canonical fields: road_name",
            ):
                prepare_manifest_inventory(missing_mapping)

    def test_manifest_defaults_are_applied_by_existing_mapper(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            mapping = deepcopy(self.manifest["column_mapping"])
            del mapping["Source_Label"]
            manifest = self._write_manifest(
                directory,
                column_mapping=mapping,
                canonical_defaults={"data_source": "Manifest default"},
            )

            _, inventory = prepare_manifest_inventory(manifest)

            self.assertTrue(inventory["data_source"].eq("Manifest default").all())

    def test_dry_run_reports_success_without_writing(self):
        before = set(ONBOARDING_DEMO_MANIFEST_PATH.parent.iterdir())
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(
                [
                    "--manifest",
                    str(ONBOARDING_DEMO_MANIFEST_PATH),
                    "--dry-run",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(before, set(ONBOARDING_DEMO_MANIFEST_PATH.parent.iterdir()))
        self.assertIn("Municipality: Pine Ridge Township (onboarding_demo)", stdout.getvalue())
        self.assertIn("Source rows: 5", stdout.getvalue())
        self.assertIn("Inventory adapter: mapped_csv", stdout.getvalue())
        self.assertIn("Scenario catalog: standard", stdout.getvalue())
        self.assertIn("no files written (dry run)", stdout.getvalue())
        self.assertIn("Validation result: PASS", stdout.getvalue())

    def test_dry_run_failure_returns_nonzero(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(
                [
                    "--manifest",
                    str(PROJECT_ROOT / "missing-manifest.json"),
                    "--dry-run",
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("Onboarding failed:", stderr.getvalue())
        self.assertIn("manifest was not found", stderr.getvalue())

    def test_export_is_canonical_valid_and_deterministically_ordered(self):
        with tempfile.TemporaryDirectory() as directory_name:
            output = Path(directory_name) / "pine_ridge_canonical.csv"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--manifest",
                        str(ONBOARDING_DEMO_MANIFEST_PATH),
                        "--output",
                        str(output),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output.is_file())
            exported = pd.read_csv(output)
            self.assertEqual(tuple(exported.columns), CANONICAL_COLUMNS)
            self.assertEqual(len(exported), 5)
            validate_canonical_schema(exported)
            self.assertIn(f"Output: {output.resolve()}", stdout.getvalue())

    def test_export_refuses_overwrite_unless_forced(self):
        with tempfile.TemporaryDirectory() as directory_name:
            output = Path(directory_name) / "pine_ridge_canonical.csv"
            arguments = [
                "--manifest",
                str(ONBOARDING_DEMO_MANIFEST_PATH),
                "--output",
                str(output),
            ]
            self.assertEqual(main(arguments), 0)
            original = output.read_bytes()

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(main(arguments), 1)
            self.assertEqual(output.read_bytes(), original)
            self.assertIn("use --force to overwrite", stderr.getvalue())

            self.assertEqual(main([*arguments, "--force"]), 0)
            exported = pd.read_csv(output)
            self.assertEqual(tuple(exported.columns), CANONICAL_COLUMNS)


if __name__ == "__main__":
    unittest.main()
