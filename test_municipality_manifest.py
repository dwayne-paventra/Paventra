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
    MANIFEST_OPTIONAL_FIELDS,
    MANIFEST_REQUIRED_FIELDS,
    build_cli_parser,
    load_onboarding_manifest,
    main,
    parse_onboarding_manifest,
    prepare_manifest_inventory,
)
from pilot.onboarding_manifest_contract import (
    CURRENT_MANIFEST_VERSION,
    get_manifest_contract,
    get_optional_manifest_fields,
    get_required_manifest_fields,
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
TEMPLATE_PATH = PROJECT_ROOT / "docs" / "manifest.template.json"
CANONICAL_DOC_PATH = PROJECT_ROOT / "docs" / "CANONICAL_INVENTORY.md"


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

        self.assertEqual(self.manifest["manifest_version"], 1)
        self.assertGreater(CURRENT_MANIFEST_VERSION, 1)
        self.assertEqual(config.normalized_data_status, "illustrative")
        self.assertEqual(config, ONBOARDING_DEMO_MUNICIPALITY)
        self.assertEqual(config.data_path, SOURCE_PATH)
        self.assertEqual(
            dict(config.source_column_mapping),
            ONBOARDING_DEMO_COLUMN_MAPPING,
        )
        self.assertEqual(config.canonical_defaults, {})
        self.assertIs(MUNICIPALITIES[config.slug], ONBOARDING_DEMO_MUNICIPALITY)
        validate_municipality_registry()

    def test_manifest_version_is_required_and_checked_first(self):
        invalid = deepcopy(self.manifest)
        del invalid["manifest_version"]
        del invalid["formal_name"]

        with self.assertRaisesRegex(
            ValueError,
            r"manifest\.json'.*missing required field 'manifest_version'",
        ):
            parse_onboarding_manifest(invalid, ONBOARDING_DEMO_MANIFEST_PATH)

    def test_unsupported_manifest_version_identifies_path_and_value(self):
        invalid = {"manifest_version": 99}

        with self.assertRaisesRegex(
            ValueError,
            r"manifest\.json'.*unsupported 'manifest_version' value '99'",
        ):
            parse_onboarding_manifest(invalid, ONBOARDING_DEMO_MANIFEST_PATH)

    def test_manifest_version_must_be_an_integer(self):
        invalid = deepcopy(self.manifest)
        invalid["manifest_version"] = "1"

        with self.assertRaisesRegex(
            ValueError,
            r"field 'manifest_version' must be an integer.*'1'",
        ):
            parse_onboarding_manifest(invalid, ONBOARDING_DEMO_MANIFEST_PATH)

    def test_contract_helpers_match_parser_fields(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        contract = get_manifest_contract(CURRENT_MANIFEST_VERSION)

        self.assertEqual(
            get_required_manifest_fields(),
            MANIFEST_REQUIRED_FIELDS,
        )
        self.assertEqual(
            get_optional_manifest_fields(),
            MANIFEST_OPTIONAL_FIELDS,
        )
        self.assertEqual(
            MANIFEST_OPTIONAL_FIELDS,
            (
                "source_owner",
                "source_acquired_date",
                "source_reference",
                "source_checksum",
            ),
        )
        self.assertTrue(set(template).issubset(contract))
        self.assertTrue(set(MANIFEST_REQUIRED_FIELDS).issubset(template))
        for field, definition in contract.items():
            with self.subTest(field=field):
                if definition.required:
                    self.assertIn(field, template)
                    self.assertIsInstance(
                        template[field],
                        definition.accepted_types,
                    )

    def test_operator_template_is_contract_valid_and_complete(self):
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        config = load_onboarding_manifest(TEMPLATE_PATH)
        supplied_canonical_fields = set(template["column_mapping"].values()) | set(
            template["canonical_defaults"]
        ) | {"data_status"}

        self.assertEqual(template["manifest_version"], CURRENT_MANIFEST_VERSION)
        self.assertEqual(config.slug, "example_agency")
        self.assertEqual(config.normalized_data_status, "provisional")
        self.assertEqual(config.source_provenance.owner, "Example Public Works Agency")
        self.assertEqual(supplied_canonical_fields, set(CANONICAL_COLUMNS))

    def test_canonical_documentation_tracks_every_implemented_field(self):
        documentation = CANONICAL_DOC_PATH.read_text(encoding="utf-8")

        for field in CANONICAL_COLUMNS:
            with self.subTest(canonical_field=field):
                self.assertIn(f"| `{field}` |", documentation)

    def test_cli_help_is_operator_friendly_and_exits_successfully(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_context:
            build_cli_parser().parse_args(["--help"])

        help_text = stdout.getvalue()
        self.assertEqual(exit_context.exception.code, 0)
        for expected in (
            "--manifest PATH",
            "--dry-run",
            "--output PATH",
            "--force",
            "without writing files",
            "exit code 0",
            "return exit code 1",
        ):
            with self.subTest(help_text=expected):
                self.assertIn(expected, help_text)

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
        self.assertIn("Manifest version: 1", stdout.getvalue())
        self.assertIn("Source rows: 5", stdout.getvalue())
        self.assertIn("Inventory adapter: mapped_csv", stdout.getvalue())
        self.assertIn("Scenario catalog: standard", stdout.getvalue())
        self.assertIn("Data status: Illustrative (illustrative)", stdout.getvalue())
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
