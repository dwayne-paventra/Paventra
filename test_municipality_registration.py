import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from pilot.municipality_admin import (
    ARCHIVED_MUNICIPALITIES_ROOT,
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    create_illustrative_demo_package,
    review_illustrative_demo,
    save_real_import_draft,
)
from pilot.municipality_package_lifecycle import (
    PackageLifecycleState,
    begin_real_import_review,
    inspect_real_import_package,
    mark_real_import_ready,
    validate_real_import_package,
)
from pilot.municipality_registration import (
    PERSISTENT_MUNICIPALITIES_ROOT,
    RegistrationState,
    accept_registration,
    get_persistent_registration,
    load_persistent_municipalities,
    preview_registration,
    promote_registration,
    rollback_registration,
)
from pilot.municipality_registry import (
    BUILTIN_MUNICIPALITIES,
    MUNICIPALITIES,
    ONBOARDING_DEMO_MUNICIPALITY,
    refresh_persistent_municipalities,
)


PROJECT_ROOT = Path(__file__).resolve().parent


def _identity(slug: str) -> MunicipalityIdentity:
    return MunicipalityIdentity(
        formal_name="Harbor Township Public Works",
        short_name="Harbor Township",
        entity_type="township",
        state="Michigan",
        slug=slug,
        leadership_label="township leadership",
        official_action_label="official township determination",
        map_center=(42.42, -84.18),
        map_zoom=12,
        scenario_catalog_id="standard",
        pilot_label="Municipal Pilot",
    )


def _source_mapping():
    source = ONBOARDING_DEMO_MUNICIPALITY.data_path.read_bytes()
    mapping = dict(ONBOARDING_DEMO_MUNICIPALITY.source_column_mapping)
    mapping.pop("Source_Status")
    return source, mapping


def _ready_package(slug: str, package_root: Path) -> Path:
    source, mapping = _source_mapping()
    package = save_real_import_draft(
        _identity(slug),
        source,
        mapping=mapping,
        defaults={},
        data_status="provisional",
        source_owner="Harbor Township public works office",
        acquired_date="2026-08-15",
        source_reference="Municipality delivery HT-2026-08.csv",
        source_field_meanings={"Street_Name": "Locally maintained road name"},
        generated_root=package_root,
    )
    validate_real_import_package(package)
    begin_real_import_review(package)
    mark_real_import_ready(package)
    return package


class MunicipalityRegistrationTests(unittest.TestCase):
    def test_full_acceptance_rehearsal(self):
        source, mapping = _source_mapping()
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            packages = base / "packages"
            registrations = base / "registrations"
            archived = base / "archived"
            slug = "acceptance_rehearsal"

            partial_mapping = {
                next(iter(mapping)): mapping[next(iter(mapping))]
            }
            package = save_real_import_draft(
                _identity(slug),
                source,
                mapping=partial_mapping,
                defaults={},
                data_status="provisional",
                source_owner="Harbor Township public works office",
                acquired_date="2026-08-15",
                source_reference="Municipality delivery HT-2026-08.csv",
                generated_root=packages,
            )
            failed = validate_real_import_package(package)
            self.assertEqual(
                failed.lifecycle_state, PackageLifecycleState.VALIDATION_REQUIRED
            )
            self.assertTrue(failed.blocking_issues)

            save_real_import_draft(
                _identity(slug),
                source,
                mapping=mapping,
                defaults={},
                data_status="provisional",
                source_owner="Harbor Township public works office",
                acquired_date="2026-08-15",
                source_reference="Municipality delivery HT-2026-08.csv",
                generated_root=packages,
            )
            self.assertEqual(
                validate_real_import_package(package).lifecycle_state,
                PackageLifecycleState.VALIDATED,
            )
            begin_real_import_review(package)
            mark_real_import_ready(package)
            self.assertEqual(
                preview_registration(
                    package,
                    registration_root=registrations,
                    generated_root=packages,
                    archived_root=archived,
                ).result,
                "PASS",
            )
            registered = promote_registration(
                package,
                confirmation_slug=slug,
                confirmed=True,
                registration_root=registrations,
                generated_root=packages,
                archived_root=archived,
            )
            snapshot = registered.config.data_path.read_bytes()
            with (package / "source_roads.csv").open("ab") as working_source:
                working_source.write(b"\n")
            self.assertEqual(registered.config.data_path.read_bytes(), snapshot)
            duplicate = preview_registration(
                package,
                registration_root=registrations,
                generated_root=packages,
                archived_root=archived,
            )
            self.assertEqual(duplicate.result, "BLOCKED")
            self.assertTrue(
                any(issue.field == "registration_path" for issue in duplicate.blocking_issues)
            )
            accepted = accept_registration(slug, registration_root=registrations)
            self.assertEqual(accepted.registration_state, RegistrationState.ACCEPTED)

    def test_preview_rechecks_ready_package_without_promoting_files(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            packages = base / "packages"
            registrations = base / "registrations"
            archived = base / "archived"
            package = _ready_package("preview_harbor", packages)
            preview = preview_registration(
                package,
                registration_root=registrations,
                protected_slugs=BUILTIN_MUNICIPALITIES,
                generated_root=packages,
                archived_root=archived,
            )
            self.assertEqual(preview.result, "PASS")
            self.assertEqual(preview.segment_count, 5)
            self.assertEqual(preview.registration_version, 1)
            self.assertEqual(preview.inventory_adapter, "mapped_csv")
            self.assertFalse(preview.intended_path.exists())
            self.assertIn("registration previewed", (package / "package_history.jsonl").read_text())

    def test_stale_readiness_and_checksum_block_registration(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            packages = base / "packages"
            package = _ready_package("stale_registration", packages)
            with (package / "source_roads.csv").open("ab") as source:
                source.write(b"\n")
            preview = preview_registration(
                package,
                registration_root=base / "registrations",
                generated_root=packages,
                archived_root=base / "archived",
            )
            self.assertEqual(preview.result, "BLOCKED")
            self.assertTrue(
                any(issue.field in {"lifecycle_state", "source_checksum"} for issue in preview.blocking_issues)
            )
            self.assertEqual(
                inspect_real_import_package(package).lifecycle_state,
                PackageLifecycleState.VALIDATION_REQUIRED,
            )

    def test_atomic_promotion_persistent_loading_and_immutable_snapshot(self):
        source, mapping = _source_mapping()
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            packages = base / "packages"
            registrations = base / "registrations"
            archived = base / "archived"
            package = _ready_package("persistent_harbor", packages)
            registered = promote_registration(
                package,
                confirmation_slug="persistent_harbor",
                confirmed=True,
                registration_root=registrations,
                protected_slugs=BUILTIN_MUNICIPALITIES,
                generated_root=packages,
                archived_root=archived,
            )
            self.assertEqual(registered.registration_version, 1)
            self.assertEqual(registered.active_data_version, 1)
            self.assertEqual(
                registered.registration_state, RegistrationState.PENDING_ACCEPTANCE
            )
            metadata = json.loads(registered.metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["active_data_version"], 1)
            self.assertEqual(metadata["validation_result"], "PASS")
            self.assertTrue((registered.registration_path / "versions" / "1" / "canonical_inventory.csv").is_file())
            discovered = load_persistent_municipalities(
                registrations, built_in_slugs=BUILTIN_MUNICIPALITIES
            )
            self.assertEqual(discovered["persistent_harbor"].formal_name, "Harbor Township Public Works")

            snapshot_source = registered.config.data_path.read_bytes()
            save_real_import_draft(
                _identity("persistent_harbor"),
                source,
                mapping=mapping,
                defaults={"jurisdiction": "Updated workspace only"},
                data_status="provisional",
                source_owner="Harbor Township public works office",
                acquired_date="2026-08-15",
                source_reference="Updated working delivery",
                generated_root=packages,
            )
            self.assertEqual(registered.config.data_path.read_bytes(), snapshot_source)
            reloaded = get_persistent_registration("persistent_harbor", registrations)
            self.assertEqual(reloaded.config.source_provenance.reference, "Municipality delivery HT-2026-08.csv")

    def test_failed_post_verification_rolls_back_only_new_registration(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            packages = base / "packages"
            registrations = base / "registrations"
            package = _ready_package("failed_verify", packages)

            def fail_verification(_):
                raise ValueError("simulated dashboard verification failure")

            with self.assertRaisesRegex(ValueError, "rolled back"):
                promote_registration(
                    package,
                    confirmation_slug="failed_verify",
                    confirmed=True,
                    registration_root=registrations,
                    generated_root=packages,
                    archived_root=base / "archived",
                    verifier=fail_verification,
                )
            self.assertFalse((registrations / "failed_verify").exists())
            self.assertTrue(package.is_dir())
            self.assertEqual(
                inspect_real_import_package(package).lifecycle_state,
                PackageLifecycleState.READY_FOR_REGISTRATION,
            )
            self.assertIn(
                "post-registration verification failed",
                (package / "package_history.jsonl").read_text(),
            )

    def test_collision_path_and_illustrative_demo_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            packages = base / "packages"
            package = _ready_package("collision_harbor", packages)
            blocked = preview_registration(
                package,
                registration_root=base / "registrations",
                protected_slugs={"collision_harbor"},
                generated_root=packages,
                archived_root=base / "archived",
            )
            self.assertEqual(blocked.result, "BLOCKED")
            self.assertTrue(any("already permanently registered" in i.message for i in blocked.blocking_issues))

            manifest_path = package / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["slug"] = "../escape"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            escaped = preview_registration(
                package,
                registration_root=base / "registrations",
                generated_root=packages,
                archived_root=base / "archived",
            )
            self.assertEqual(escaped.result, "BLOCKED")
            self.assertTrue(any(issue.field == "slug" for issue in escaped.blocking_issues))

            demo = create_illustrative_demo_package(
                review_illustrative_demo(
                    _identity("illustrative_registration_reject"),
                    generated_root=packages,
                ),
                generated_root=packages,
            )
            demo_preview = preview_registration(
                demo.manifest_path.parent,
                registration_root=base / "registrations",
                generated_root=packages,
                archived_root=base / "archived",
            )
            self.assertEqual(demo_preview.result, "BLOCKED")
            self.assertTrue(any(issue.field == "package_type" for issue in demo_preview.blocking_issues))

    def test_pending_rollback_and_acceptance_protections(self):
        with tempfile.TemporaryDirectory() as directory_name:
            base = Path(directory_name)
            packages = base / "packages"
            registrations = base / "registrations"
            package = _ready_package("rollback_harbor", packages)
            promote_registration(
                package,
                confirmation_slug="rollback_harbor",
                confirmed=True,
                registration_root=registrations,
                generated_root=packages,
                archived_root=base / "archived",
            )
            rollback_registration(
                "rollback_harbor",
                confirmation_slug="rollback_harbor",
                registration_root=registrations,
            )
            self.assertFalse((registrations / "rollback_harbor").exists())
            self.assertEqual(
                inspect_real_import_package(package).lifecycle_state,
                PackageLifecycleState.READY_FOR_REGISTRATION,
            )

            accepted_package = _ready_package("accepted_harbor", packages)
            promote_registration(
                accepted_package,
                confirmation_slug="accepted_harbor",
                confirmed=True,
                registration_root=registrations,
                generated_root=packages,
                archived_root=base / "archived",
            )
            accepted = accept_registration(
                "accepted_harbor", registration_root=registrations
            )
            self.assertEqual(accepted.registration_state, RegistrationState.ACCEPTED)
            with self.assertRaisesRegex(ValueError, "developer-controlled"):
                rollback_registration(
                    "accepted_harbor",
                    confirmation_slug="accepted_harbor",
                    registration_root=registrations,
                )
            with self.assertRaisesRegex(ValueError, "Built-in"):
                rollback_registration(
                    "jackson",
                    confirmation_slug="jackson",
                    registration_root=registrations,
                    protected_slugs=BUILTIN_MUNICIPALITIES,
                )

    def test_malformed_persistent_registration_fails_safe(self):
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            invalid = root / "broken_registration"
            invalid.mkdir()
            (invalid / "registration.json").write_text('{"slug":"broken_registration"}')
            with self.assertRaisesRegex(ValueError, "missing fields"):
                load_persistent_municipalities(root)

    def test_portfolio_registration_preview_and_confirmed_promotion(self):
        from streamlit.testing.v1 import AppTest

        slug = "phase21_ui_registration"
        package = GENERATED_MUNICIPALITIES_ROOT / slug
        registration = PERSISTENT_MUNICIPALITIES_ROOT / slug
        for target in (package, registration):
            if target.exists():
                shutil.rmtree(target)
        try:
            _ready_package(slug, GENERATED_MUNICIPALITIES_ROOT)
            app = AppTest.from_file(
                "pages/1_Municipality_Onboarding.py", default_timeout=30
            )
            app.session_state["paventra_operator_view"] = "portfolio"
            app.run()
            app.text_input(key="portfolio_search").set_value(slug).run()
            app.selectbox(key="portfolio_selected").set_value(
                f"Harbor Township Public Works — {slug}"
            ).run()
            app.button(key=f"registration_preview_{slug}").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any(item.value == "Review Registration" for item in app.subheader))
            app.text_input(key=f"registration_confirm_text_{slug}").set_value(slug)
            app.checkbox(key=f"registration_confirm_checkbox_{slug}").set_value(True)
            app.run()
            self.assertFalse(app.button(key=f"register_municipality_{slug}").disabled)
            app.button(key=f"register_municipality_{slug}").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(registration.is_dir())
            self.assertIn(slug, MUNICIPALITIES)
        finally:
            if registration.exists():
                rollback_registration(slug, confirmation_slug=slug)
            if package.exists():
                shutil.rmtree(package)
            refresh_persistent_municipalities()

    def test_restart_discovery_dashboard_portfolio_and_report(self):
        from streamlit.testing.v1 import AppTest

        slug = "phase21_restart_registration"
        package = GENERATED_MUNICIPALITIES_ROOT / slug
        registration = PERSISTENT_MUNICIPALITIES_ROOT / slug
        for target in (package, registration):
            if target.exists():
                shutil.rmtree(target)
        try:
            _ready_package(slug, GENERATED_MUNICIPALITIES_ROOT)
            promote_registration(
                package,
                confirmation_slug=slug,
                confirmed=True,
                protected_slugs=BUILTIN_MUNICIPALITIES,
            )
            refresh_persistent_municipalities()
            self.assertIn(slug, MUNICIPALITIES)

            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join((
                str(PROJECT_ROOT / ".phase21-test-deps"),
                str(PROJECT_ROOT),
            ))
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from pilot.municipality_registry import MUNICIPALITIES; "
                        f"c=MUNICIPALITIES['{slug}']; print(c.slug, c.formal_name)"
                    ),
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(f"{slug} Harbor Township Public Works", completed.stdout)

            dashboard = AppTest.from_file("dashboard.py", default_timeout=30)
            dashboard.session_state["paventra_selected_municipality_slug"] = slug
            dashboard.run()
            self.assertFalse(dashboard.exception)
            self.assertIn("Harbor Township Municipal Pilot", [item.value for item in dashboard.title])
            dashboard.button(key="paventra_nav_pavement_analytics").click().run()
            self.assertFalse(dashboard.exception)
            dashboard.button(key="paventra_nav_network_map").click().run()
            self.assertFalse(dashboard.exception)
            dashboard.button(key="paventra_nav_reports").click().run()
            dashboard.button(key="municipality_generate_report").click().run()
            self.assertFalse(dashboard.exception)
            self.assertTrue(dashboard.download_button)

            portfolio = AppTest.from_file(
                "pages/1_Municipality_Onboarding.py", default_timeout=30
            )
            portfolio.session_state["paventra_operator_view"] = "portfolio"
            portfolio.run()
            portfolio.text_input(key="portfolio_search").set_value(slug).run()
            self.assertFalse(portfolio.exception)
            self.assertTrue(any("Showing 2 of" in item.value for item in portfolio.get("markdown")))
            accept_registration(slug)
            self.assertEqual(
                get_persistent_registration(slug).registration_state,
                RegistrationState.ACCEPTED,
            )
        finally:
            if registration.exists():
                metadata = json.loads((registration / "registration.json").read_text())
                metadata["registration_state"] = RegistrationState.PENDING_ACCEPTANCE
                (registration / "registration.json").write_text(json.dumps(metadata, indent=2) + "\n")
                rollback_registration(slug, confirmation_slug=slug)
            if package.exists():
                shutil.rmtree(package)
            refresh_persistent_municipalities()


if __name__ == "__main__":
    unittest.main()
