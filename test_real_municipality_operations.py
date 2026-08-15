import json
from pathlib import Path
import shutil
import tempfile
import unittest

from pilot.municipality_admin import (
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    build_municipality_portfolio,
    create_illustrative_demo_package,
    review_illustrative_demo,
    save_real_import_draft,
)
from pilot.municipality_package_lifecycle import (
    PackageLifecycleState,
    begin_real_import_review,
    inspect_real_import_package,
    mark_real_import_ready,
    read_package_history,
    record_package_reopened,
    refresh_real_import_readiness,
    registration_packet_path,
    suggested_registry_snippet,
    validate_real_import_package,
)
from pilot.municipality_registry import MUNICIPALITIES, ONBOARDING_DEMO_MUNICIPALITY


def _identity(slug: str = "real_ops_rehearsal") -> MunicipalityIdentity:
    return MunicipalityIdentity(
        formal_name="Riverview Township Public Works",
        short_name="Riverview Township",
        entity_type="township",
        state="Michigan",
        slug=slug,
        leadership_label="township leadership",
        official_action_label="official township determination",
        map_center=(42.401, -84.215),
        map_zoom=12,
        scenario_catalog_id="standard",
        pilot_label="Municipal Pilot",
    )


def _source_and_mapping():
    source = ONBOARDING_DEMO_MUNICIPALITY.data_path.read_bytes()
    mapping = dict(ONBOARDING_DEMO_MUNICIPALITY.source_column_mapping)
    mapping.pop("Source_Status")
    return source, mapping


def _save(root: Path, slug: str, mapping, *, defaults=None):
    source, _ = _source_and_mapping()
    return save_real_import_draft(
        _identity(slug),
        source,
        mapping=mapping,
        defaults=defaults or {},
        data_status="provisional",
        source_owner="Riverview Township public works office",
        acquired_date="2026-08-15",
        source_reference="Municipality delivery RV-2026-08.csv",
        source_field_meanings={"Street_Name": "Locally maintained road name"},
        generated_root=root,
    )


class RealMunicipalityOperationsTests(unittest.TestCase):
    def test_lifecycle_vocabulary_is_stable_and_separate_from_data_status(self):
        self.assertEqual(
            [state.value for state in PackageLifecycleState],
            [
                "Draft",
                "Validation Required",
                "Validated",
                "Review Required",
                "Ready for Registration",
                "Registered",
                "Archived",
            ],
        )
        self.assertNotIn("provisional", {state.value for state in PackageLifecycleState})

    def test_incomplete_draft_has_blocking_issues_and_failed_validation(self):
        _, complete_mapping = _source_and_mapping()
        partial_mapping = {next(iter(complete_mapping)): next(iter(complete_mapping.values()))}
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            package = _save(root, "incomplete_real_ops", partial_mapping)
            draft = inspect_real_import_package(package)
            self.assertEqual(draft.lifecycle_state, PackageLifecycleState.DRAFT)
            self.assertTrue(draft.blocking_issues)
            self.assertTrue(any(issue.field == "segment_id" for issue in draft.blocking_issues))

            failed = validate_real_import_package(package)
            self.assertEqual(
                failed.lifecycle_state, PackageLifecycleState.VALIDATION_REQUIRED
            )
            self.assertTrue(failed.blocking_issues)
            summary = json.loads((package / "validation_summary.json").read_text())
            self.assertGreater(summary["blocking_issue_count"], 0)
            events = read_package_history(package)
            self.assertEqual(events[-1]["event"], "validation failed")

    def test_full_validation_review_ready_reopen_and_handoff(self):
        _, mapping = _source_and_mapping()
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            package = _save(root, "full_real_ops", mapping)
            self.assertEqual(
                inspect_real_import_package(package).lifecycle_state,
                PackageLifecycleState.DRAFT,
            )
            validated = validate_real_import_package(package)
            self.assertEqual(validated.lifecycle_state, PackageLifecycleState.VALIDATED)
            self.assertFalse(validated.blocking_issues)
            self.assertTrue((package / "canonical_review.csv").is_file())
            self.assertTrue((package / "mapping_review.csv").is_file())
            self.assertTrue((package / "operator_review.md").is_file())

            review = begin_real_import_review(package)
            self.assertEqual(review.lifecycle_state, PackageLifecycleState.REVIEW_REQUIRED)
            ready = mark_real_import_ready(package)
            self.assertEqual(
                ready.lifecycle_state, PackageLifecycleState.READY_FOR_REGISTRATION
            )
            packet = registration_packet_path(package)
            packet_text = packet.read_text(encoding="utf-8")
            self.assertIn("Developer Registration Handoff", packet_text)
            self.assertIn("Ready for Registration", packet_text)
            self.assertIn("full_real_ops", packet_text)
            self.assertIn("Run the complete test suite", packet_text)

            reopened = record_package_reopened(package)
            self.assertEqual(
                reopened.lifecycle_state, PackageLifecycleState.READY_FOR_REGISTRATION
            )
            self.assertEqual(read_package_history(package)[-1]["event"], "reopened")

            entries = build_municipality_portfolio(generated_root=root)
            entry = next(item for item in entries if item.slug == "full_real_ops")
            self.assertEqual(entry.readiness_state, "Real Import — Ready for Registration")
            self.assertFalse(entry.dashboard_launchable)

    def test_ready_package_change_is_invalidated_and_can_be_revalidated(self):
        source, mapping = _source_and_mapping()
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            package = _save(root, "stale_real_ops", mapping)
            validate_real_import_package(package)
            begin_real_import_review(package)
            mark_real_import_ready(package)

            manifest_path = package / "manifest.json"
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            document["map_zoom"] = 13
            manifest_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
            invalidated = refresh_real_import_readiness(package)
            self.assertEqual(
                invalidated.lifecycle_state, PackageLifecycleState.VALIDATION_REQUIRED
            )
            persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertNotIn("readiness_fingerprint", persisted)
            self.assertIn("NOT READY", (package / "registration_packet.md").read_text())
            with self.assertRaisesRegex(ValueError, "not Ready"):
                registration_packet_path(package)

            updated_identity = _identity("stale_real_ops")
            updated_identity = MunicipalityIdentity(
                **{**updated_identity.__dict__, "map_zoom": 13}
            )
            save_real_import_draft(
                updated_identity,
                source,
                mapping=mapping,
                defaults={},
                data_status="provisional",
                source_owner="Riverview Township public works office",
                acquired_date="2026-08-15",
                source_reference="Municipality delivery RV-2026-08.csv",
                generated_root=root,
            )
            validate_real_import_package(package)
            begin_real_import_review(package)
            ready_again = mark_real_import_ready(package)
            self.assertEqual(
                ready_again.lifecycle_state,
                PackageLifecycleState.READY_FOR_REGISTRATION,
            )

    def test_warnings_do_not_replace_blocking_gate_and_snippet_is_review_only(self):
        _, mapping = _source_and_mapping()
        latitude_source = next(
            source for source, target in mapping.items() if target == "latitude"
        )
        mapping.pop(latitude_source)
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            package = _save(root, "warning_real_ops", mapping, defaults={"latitude": 42.4})
            inspection = inspect_real_import_package(package)
            self.assertFalse(inspection.blocking_issues)
            self.assertTrue(any(issue.field == "latitude" for issue in inspection.warnings))
            validated = validate_real_import_package(package)
            self.assertEqual(validated.lifecycle_state, PackageLifecycleState.VALIDATED)

            snippet = suggested_registry_snippet(
                "warning_real_ops", package / "manifest.json"
            )
            self.assertIn("Suggested developer-reviewed registration only", snippet)
            self.assertIn("load_onboarding_manifest", snippet)
            self.assertNotIn("git", snippet.lower())

    def test_permanent_and_illustrative_packages_keep_existing_protections(self):
        registry_snapshot = dict(MUNICIPALITIES)
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            demo = create_illustrative_demo_package(
                review_illustrative_demo(
                    MunicipalityIdentity(
                        formal_name="Operations Demo Township",
                        short_name="Operations Demo",
                        entity_type="township",
                        state="Michigan",
                        slug="ops_demo",
                        leadership_label="township leadership",
                        official_action_label="official township determination",
                        map_center=(42.3, -84.3),
                        map_zoom=12,
                        scenario_catalog_id="standard",
                    ),
                    generated_root=root,
                ),
                generated_root=root,
            )
            entries = build_municipality_portfolio(generated_root=root)
            demo_entry = next(item for item in entries if item.slug == "ops_demo")
            permanent = next(item for item in entries if item.slug == "jackson")
            self.assertEqual(demo_entry.readiness_state, "Generated Illustrative Demo")
            self.assertTrue(demo.runtime_launchable)
            self.assertEqual(permanent.readiness_state, "Permanent / Registered")
            self.assertTrue(permanent.permanent)
        self.assertEqual(MUNICIPALITIES, registry_snapshot)

    def test_portfolio_can_reopen_real_import_after_new_apptest_session(self):
        from streamlit.testing.v1 import AppTest

        slug = "phase20_portfolio_reopen"
        target = GENERATED_MUNICIPALITIES_ROOT / slug
        if target.exists():
            shutil.rmtree(target)
        try:
            _, mapping = _source_and_mapping()
            _save(GENERATED_MUNICIPALITIES_ROOT, slug, mapping)
            app = AppTest.from_file(
                "pages/1_Municipality_Onboarding.py", default_timeout=30
            )
            app.session_state["paventra_operator_view"] = "portfolio"
            app.run()
            self.assertFalse(app.exception)
            app.text_input(key="portfolio_search").set_value(slug).run()
            selector = app.selectbox(key="portfolio_selected")
            self.assertEqual(len(selector.options), 2)
            selector.set_value(selector.options[1]).run()
            self.assertFalse(app.exception)
            self.assertTrue(
                any(button.label == "Continue real-import review" for button in app.button)
            )
            app.button(key=f"resume_real_import_{slug}").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["paventra_operator_view"], "onboarding")
            # AppTest retains the multipage script frame after a same-page
            # rerun; a fresh run mirrors the next Streamlit request/restart.
            app.run()
            self.assertFalse(app.exception)
            self.assertIn(
                "Reopened persisted workspace",
                " ".join(item.value for item in app.success),
                {
                    "headers": [item.value for item in app.header],
                    "titles": [item.value for item in app.title],
                    "errors": [item.value for item in app.error],
                    "buttons": [item.label for item in app.button],
                },
            )
            self.assertTrue(any(button.label == "Validate saved package" for button in app.button))
            app.button(key="validate_saved_import").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                inspect_real_import_package(target).lifecycle_state,
                PackageLifecycleState.VALIDATED,
            )
            app.button(key="begin_import_review").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                inspect_real_import_package(target).lifecycle_state,
                PackageLifecycleState.REVIEW_REQUIRED,
            )
            app.button(key="mark_import_ready").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                inspect_real_import_package(target).lifecycle_state,
                PackageLifecycleState.READY_FOR_REGISTRATION,
            )
            self.assertTrue(
                any(
                    button.label == "Download registration packet"
                    for button in app.download_button
                )
            )
        finally:
            if target.exists():
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()
