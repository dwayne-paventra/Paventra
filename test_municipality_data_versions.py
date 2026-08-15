import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pandas as pd

from components.municipality_report import (
    build_municipality_report,
    municipality_report_data_version,
)
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_data_versions import (
    UPDATE_WORKSPACES_ROOT,
    UpdateLifecycleState,
    activate_update,
    activation_preview,
    begin_update_review,
    compare_candidate_to_active,
    create_update_workspace,
    inspect_update_workspace,
    list_update_workspaces,
    mark_update_ready,
    next_data_version,
    rollback_active_version,
    validate_update_workspace,
    version_history,
)
from pilot.municipality_registration import (
    PERSISTENT_MUNICIPALITIES_ROOT,
    get_persistent_registration,
    promote_registration,
    rollback_registration,
)
from pilot.municipality_admin import GENERATED_MUNICIPALITIES_ROOT
from pilot.municipality_registry import (
    BUILTIN_MUNICIPALITIES,
    MUNICIPALITIES,
    refresh_persistent_municipalities,
)
from pilot.municipality_scenarios import build_municipality_scenario_results
from test_municipality_registration import _ready_package, _source_mapping


PROJECT_ROOT = Path(__file__).resolve().parent


def _changed_source(*, changed_schema: bool = False, invalid_numeric: bool = False) -> bytes:
    source, _ = _source_mapping()
    from io import BytesIO

    frame = pd.read_csv(BytesIO(source))
    if invalid_numeric:
        frame["PCI_Score"] = frame["PCI_Score"].astype(object)
    frame.loc[0, "PCI_Score"] = "bad" if invalid_numeric else 52
    frame.loc[0, "Daily_Traffic"] = 12500
    frame.loc[1, "Proposed_Treatment"] = "Reconstruction"
    frame.loc[2, "Lat_Value"] = 42.1988
    if changed_schema:
        frame = frame.rename(columns={"PCI_Score": "Condition_Index"})
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


class MunicipalityDataVersionTests(unittest.TestCase):
    def _registered(self, base: Path, slug: str = "versioned_harbor"):
        packages = base / "packages"
        registrations = base / "registrations"
        package = _ready_package(slug, packages)
        registered = promote_registration(
            package,
            confirmation_slug=slug,
            confirmed=True,
            registration_root=registrations,
            protected_slugs=BUILTIN_MUNICIPALITIES,
            generated_root=packages,
            archived_root=base / "archived",
        )
        return registered, registrations, base / "updates"

    def _candidate(self, base: Path, slug: str = "versioned_harbor"):
        registered, registrations, updates = self._registered(base, slug)
        workspace = create_update_workspace(
            slug,
            _changed_source(),
            source_owner="Harbor Township asset management office",
            acquired_date="2026-08-16",
            source_reference="Inventory export HT-2026-08-v2.csv",
            data_status="provisional",
            provenance_confirmed=True,
            registration_root=registrations,
            workspace_root=updates,
        )
        return registered, registrations, updates, workspace

    def _ready_candidate(self, base: Path, slug: str = "versioned_harbor"):
        registered, registrations, updates, workspace = self._candidate(base, slug)
        validate_update_workspace(workspace, registration_root=registrations)
        begin_update_review(workspace, registration_root=registrations)
        mark_update_ready(workspace, registration_root=registrations)
        return registered, registrations, updates, workspace

    def test_next_version_mapping_reuse_and_explicit_provenance(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            registered, registrations, updates = self._registered(base)
            self.assertEqual(registered.active_data_version, 1)
            self.assertEqual(registered.config.data_version, 1)
            self.assertEqual(next_data_version("versioned_harbor", registration_root=registrations), 2)
            with self.assertRaisesRegex(ValueError, "explicit operator confirmation"):
                create_update_workspace(
                    "versioned_harbor", _changed_source(),
                    source_owner="owner", acquired_date="2026-08-16",
                    source_reference="reference", data_status="provisional",
                    provenance_confirmed=False, registration_root=registrations,
                    workspace_root=updates,
                )
            workspace = create_update_workspace(
                "versioned_harbor", _changed_source(),
                source_owner="New version owner", acquired_date="2026-08-16",
                source_reference="New extraction", data_status="provisional",
                provenance_confirmed=True, registration_root=registrations,
                workspace_root=updates,
            )
            inspection = inspect_update_workspace(workspace, registration_root=registrations)
            self.assertTrue(inspection.mapping_reused)
            self.assertTrue(inspection.defaults_reused)
            manifest = json.loads((workspace / "manifest.json").read_text())
            self.assertEqual(manifest["source_owner"], "New version owner")
            self.assertEqual(manifest["column_mapping"], dict(registered.config.source_column_mapping))
            self.assertEqual(list_update_workspaces("versioned_harbor", workspace_root=updates), (workspace,))
            with self.assertRaisesRegex(ValueError, "already exists"):
                create_update_workspace(
                    "versioned_harbor", _changed_source(),
                    source_owner="owner", acquired_date="2026-08-16",
                    source_reference="reference", data_status="provisional",
                    provenance_confirmed=True, registration_root=registrations,
                    workspace_root=updates,
                )

    def test_phase21_version_one_registration_remains_compatible(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            registered, registrations, _ = self._registered(base)
            metadata = json.loads(registered.metadata_path.read_text())
            for field in (
                "available_data_versions", "previous_active_data_version",
                "active_version_activated_at_utc", "version_records",
            ):
                metadata.pop(field, None)
            registered.metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
            version_metadata = registered.registration_path / "versions" / "1" / "version.json"
            version_metadata.unlink()
            compatible = get_persistent_registration("versioned_harbor", registrations)
            self.assertEqual(compatible.active_data_version, 1)
            self.assertEqual(compatible.config.data_version, 1)
            self.assertEqual(next_data_version(
                "versioned_harbor", registration_root=registrations
            ), 2)

    def test_changed_schema_and_invalid_numeric_require_correction(self):
        for changed_schema, invalid_numeric, expected in (
            (True, False, "PCI_Score"),
            (False, True, "numeric"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory_name:
                base = Path(directory_name)
                _, registrations, updates = self._registered(base)
                workspace = create_update_workspace(
                    "versioned_harbor",
                    _changed_source(changed_schema=changed_schema, invalid_numeric=invalid_numeric),
                    source_owner="owner", acquired_date="2026-08-16",
                    source_reference="new source", data_status="provisional",
                    provenance_confirmed=True, registration_root=registrations,
                    workspace_root=updates,
                )
                result = validate_update_workspace(workspace, registration_root=registrations)
                self.assertEqual(result.state, UpdateLifecycleState.VALIDATION_REQUIRED)
                summary = (workspace / "validation_summary.json").read_text()
                self.assertIn(expected, summary)

    def test_deterministic_version_comparison(self):
        with tempfile.TemporaryDirectory() as directory_name:
            _, registrations, _, workspace = self._candidate(Path(directory_name))
            validated = validate_update_workspace(workspace, registration_root=registrations)
            self.assertEqual(validated.state, UpdateLifecycleState.VALIDATED)
            comparison = compare_candidate_to_active(workspace, registration_root=registrations)
            self.assertEqual(comparison.old_row_count, 5)
            self.assertEqual(comparison.new_row_count, 5)
            self.assertEqual(comparison.pci_change_count, 1)
            self.assertEqual(comparison.adt_change_count, 1)
            self.assertEqual(comparison.treatment_change_count, 1)
            self.assertEqual(comparison.coordinate_change_count, 1)
            self.assertFalse(comparison.added_segment_ids)
            self.assertFalse(comparison.removed_segment_ids)

    def test_stale_candidate_blocks_activation_preview(self):
        with tempfile.TemporaryDirectory() as directory_name:
            _, registrations, _, workspace = self._ready_candidate(Path(directory_name))
            preview = activation_preview(workspace, registration_root=registrations)
            self.assertEqual(preview.result, "PASS")
            with (workspace / "source_roads.csv").open("ab") as source:
                source.write(b"\n")
            stale = activation_preview(workspace, registration_root=registrations)
            self.assertEqual(stale.result, "BLOCKED")
            self.assertTrue(any("stale" in issue.message.lower() for issue in stale.blocking_issues))
            self.assertEqual(
                inspect_update_workspace(workspace, registration_root=registrations).state,
                UpdateLifecycleState.VALIDATION_REQUIRED,
            )
            self.assertEqual(get_persistent_registration(
                "versioned_harbor", registrations
            ).active_data_version, 1)

    def test_atomic_activation_restart_report_history_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            _, registrations, _, workspace = self._ready_candidate(base)
            original_v1 = (
                get_persistent_registration("versioned_harbor", registrations)
                .registration_path / "versions" / "1" / "canonical_inventory.csv"
            ).read_bytes()
            preview = activation_preview(workspace, registration_root=registrations)
            activated = activate_update(
                workspace,
                confirmation="versioned_harbor version 2",
                confirmed=True,
                registration_root=registrations,
            )
            self.assertEqual(activated.active_data_version, 2)
            self.assertEqual(activated.config.data_version, 2)
            metadata = json.loads(activated.metadata_path.read_text())
            self.assertEqual(metadata["available_data_versions"], [1, 2])
            self.assertEqual(metadata["previous_active_data_version"], 1)
            self.assertTrue((activated.registration_path / "versions" / "1").is_dir())
            self.assertTrue((activated.registration_path / "versions" / "2").is_dir())
            self.assertEqual(
                (activated.registration_path / "versions" / "1" / "canonical_inventory.csv").read_bytes(),
                original_v1,
            )
            self.assertEqual(next_data_version(
                "versioned_harbor", registration_root=registrations
            ), 3)
            roads = load_municipality_inventory(activated.config)
            self.assertEqual(float(roads.loc[roads["Road ID"] == "PRT-001", "PCI"].iloc[0]), 52)
            results = build_municipality_scenario_results(
                roads, "Balanced Annual Program", activated.config.scenario_catalog_id
            )
            report = build_municipality_report(activated.config, roads, results)
            self.assertTrue(report.startswith(b"%PDF"))
            self.assertEqual(municipality_report_data_version(activated.config, roads), "2")
            rows = version_history("versioned_harbor", registration_root=registrations)
            self.assertEqual([row["state"] for row in rows], ["Superseded", "Active"])

            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join((
                str(PROJECT_ROOT / ".phase22-test-deps"), str(PROJECT_ROOT)
            ))
            code = (
                "from pilot.municipality_registration import get_persistent_registration; "
                f"r=get_persistent_registration('versioned_harbor', r'{registrations}'); "
                "print(r.active_data_version, r.config.data_version)"
            )
            completed = subprocess.run(
                [sys.executable, "-c", code], cwd=PROJECT_ROOT, env=environment,
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("2 2", completed.stdout)

            rolled_back = rollback_active_version(
                "versioned_harbor", 1,
                confirmation="versioned_harbor version 1", confirmed=True,
                registration_root=registrations,
                workspace_root=base / "updates",
            )
            self.assertEqual(rolled_back.active_data_version, 1)
            self.assertEqual(rolled_back.config.data_version, 1)
            self.assertTrue((rolled_back.registration_path / "versions" / "2").is_dir())
            self.assertEqual(
                inspect_update_workspace(workspace, registration_root=registrations).state,
                UpdateLifecycleState.ROLLED_BACK,
            )
            rollback_code = (
                "from pilot.municipality_registration import get_persistent_registration; "
                f"r=get_persistent_registration('versioned_harbor', r'{registrations}'); "
                "print(r.active_data_version, r.config.data_version)"
            )
            rollback_process = subprocess.run(
                [sys.executable, "-c", rollback_code], cwd=PROJECT_ROOT, env=environment,
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(rollback_process.returncode, 0, rollback_process.stderr)
            self.assertIn("1 1", rollback_process.stdout)
            reactivated = rollback_active_version(
                "versioned_harbor", 2,
                confirmation="versioned_harbor version 2", confirmed=True,
                registration_root=registrations,
                workspace_root=base / "updates",
            )
            self.assertEqual(reactivated.active_data_version, 2)
            self.assertEqual(
                inspect_update_workspace(workspace, registration_root=registrations).state,
                UpdateLifecycleState.ACTIVE,
            )
            self.assertEqual(preview.current_active_version, 1)

    def test_failed_activation_and_failed_rollback_restore_active_pointer(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            _, registrations, _, workspace = self._ready_candidate(base)

            def fail(_):
                raise ValueError("simulated verification failure")

            with self.assertRaisesRegex(ValueError, "previous active version was restored"):
                activate_update(
                    workspace,
                    confirmation="versioned_harbor version 2", confirmed=True,
                    registration_root=registrations, verifier=fail,
                )
            registered = get_persistent_registration("versioned_harbor", registrations)
            self.assertEqual(registered.active_data_version, 1)
            self.assertFalse((registered.registration_path / "versions" / "2").exists())

            activated = activate_update(
                workspace,
                confirmation="versioned_harbor version 2", confirmed=True,
                registration_root=registrations,
            )
            with self.assertRaisesRegex(ValueError, "prior active version was restored"):
                rollback_active_version(
                    "versioned_harbor", 1,
                    confirmation="versioned_harbor version 1", confirmed=True,
                    registration_root=registrations, workspace_root=base / "updates",
                    verifier=fail,
                )
            self.assertEqual(get_persistent_registration(
                "versioned_harbor", registrations
            ).active_data_version, activated.active_data_version)

    def test_generated_and_builtin_municipalities_are_outside_update_workflow(self):
        with tempfile.TemporaryDirectory() as directory_name:
            for slug in ("jackson", "napoleon_township"):
                with self.subTest(slug=slug), self.assertRaises(ValueError):
                    create_update_workspace(
                        slug, _changed_source(), source_owner="owner",
                        acquired_date="2026-08-16", source_reference="source",
                        data_status="provisional", provenance_confirmed=True,
                        registration_root=Path(directory_name) / "registrations",
                        workspace_root=Path(directory_name) / "updates",
                    )

    def test_portfolio_version_history_preview_and_activation(self):
        from streamlit.testing.v1 import AppTest

        slug = "phase22_portfolio_version"
        package = GENERATED_MUNICIPALITIES_ROOT / slug
        registration = PERSISTENT_MUNICIPALITIES_ROOT / slug
        workspace = UPDATE_WORKSPACES_ROOT / "2" / slug
        for target in (package, registration, workspace):
            if target.exists():
                shutil.rmtree(target)
        try:
            ready = _ready_package(slug, GENERATED_MUNICIPALITIES_ROOT)
            promote_registration(
                ready, confirmation_slug=slug, confirmed=True,
                protected_slugs=BUILTIN_MUNICIPALITIES,
            )
            refresh_persistent_municipalities()
            app = AppTest.from_file(
                "pages/1_Municipality_Onboarding.py", default_timeout=30
            )
            app.session_state["paventra_operator_view"] = "portfolio"
            app.run()
            app.text_input(key="portfolio_search").set_value(slug).run()
            app.selectbox(key="portfolio_selected").set_value(
                f"Harbor Township Public Works — {slug} — Permanent / Registered"
            ).run()
            self.assertFalse(app.exception)
            self.assertTrue(any(item.value == "Data Version History" for item in app.subheader))
            self.assertTrue(app.file_uploader(key=f"version_upload_{slug}"))
            app.file_uploader(key=f"version_upload_{slug}").upload(
                "candidate_v2.csv", _changed_source(), "text/csv"
            )
            app.text_input(key=f"version_owner_{slug}").set_value("Portfolio source owner")
            app.text_input(key=f"version_reference_{slug}").set_value("Portfolio update source")
            app.checkbox(key=f"version_provenance_confirm_{slug}").set_value(True)
            app.run()
            self.assertFalse(app.button(key=f"version_create_{slug}").disabled)
            app.button(key=f"version_create_{slug}").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(workspace.is_dir())
            app.button(key=f"version_validate_{slug}").click().run()
            self.assertFalse(app.exception)
            app.button(key=f"version_review_{slug}").click().run()
            self.assertFalse(app.exception)
            app.button(key=f"version_ready_{slug}").click().run()
            self.assertFalse(app.exception)
            app.button(key=f"version_preview_{slug}").click().run()
            self.assertFalse(app.exception)
            expected = f"{slug} version 2"
            app.text_input(key=f"version_activate_text_{slug}").set_value(expected)
            app.checkbox(key=f"version_activate_confirm_{slug}").set_value(True)
            app.run()
            self.assertFalse(app.button(key=f"version_activate_{slug}").disabled)
            app.button(key=f"version_activate_{slug}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(get_persistent_registration(slug).active_data_version, 2)
            self.assertIn(slug, MUNICIPALITIES)
        finally:
            if registration.exists():
                rollback_registration(slug, confirmation_slug=slug)
            if package.exists():
                shutil.rmtree(package)
            if workspace.exists():
                shutil.rmtree(workspace)
            version_root = UPDATE_WORKSPACES_ROOT / "2"
            if version_root.is_dir() and not any(version_root.iterdir()):
                version_root.rmdir()
            refresh_persistent_municipalities()


if __name__ == "__main__":
    unittest.main()
