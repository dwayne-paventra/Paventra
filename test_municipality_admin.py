from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest

import pandas as pd

from pilot.canonical_inventory import CANONICAL_COLUMNS, validate_canonical_schema
from pilot.municipality_admin import (
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    archive_generated_demo,
    assert_slug_available,
    build_municipality_portfolio,
    clone_illustrative_demo,
    create_illustrative_demo_package,
    create_real_import_package,
    generate_synthetic_canonical_inventory,
    filter_municipality_portfolio,
    list_generated_municipalities,
    load_generated_municipality,
    review_illustrative_demo,
    review_real_import,
    restore_archived_demo,
    suggest_column_mappings,
    suggest_municipality_slug,
)
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_registry import MUNICIPALITIES, ONBOARDING_DEMO_MUNICIPALITY


PROJECT_ROOT = Path(__file__).resolve().parent


def _identity(slug="sample_borough", formal_name="Sample Borough"):
    return MunicipalityIdentity(
        formal_name=formal_name,
        short_name=formal_name.replace(" Borough", ""),
        entity_type="municipality",
        state="Michigan",
        slug=slug,
        leadership_label="agency leadership",
        official_action_label="official agency determination",
        map_center=(42.42, -84.24),
        map_zoom=12,
        scenario_catalog_id="standard",
    )


class MunicipalityAdminTests(unittest.TestCase):
    def test_slug_generation_is_normalized_and_clear(self):
        self.assertEqual(suggest_municipality_slug(" City of Démo  Heights "), "city_of_demo_heights")
        self.assertEqual(suggest_municipality_slug("Road Commission #7"), "road_commission_7")
        with self.assertRaisesRegex(ValueError, "letters or numbers"):
            suggest_municipality_slug("---")

    def test_column_suggestions_are_editable_and_do_not_duplicate_targets(self):
        suggestions = suggest_column_mappings(
            ["Street_Name", "PCI_Score", "AADT", "Lat", "Lon", "Road Name", "Mystery"]
        )
        self.assertEqual(suggestions["Street_Name"], "road_name")
        self.assertEqual(suggestions["PCI_Score"], "pci")
        self.assertEqual(suggestions["AADT"], "adt")
        self.assertEqual(suggestions["Lat"], "latitude")
        self.assertEqual(suggestions["Lon"], "longitude")
        self.assertIsNone(suggestions["Road Name"])
        self.assertIsNone(suggestions["Mystery"])

    def test_synthetic_inventory_is_varied_valid_and_always_illustrative(self):
        roads = generate_synthetic_canonical_inventory(_identity(), road_count=12)
        self.assertEqual(tuple(roads.columns), CANONICAL_COLUMNS)
        self.assertEqual(len(roads), 12)
        self.assertTrue(roads["data_status"].eq("illustrative").all())
        self.assertTrue(roads["road_id"].is_unique)
        self.assertTrue(roads["segment_id"].is_unique)
        self.assertGreater(roads["pci"].nunique(), 3)
        self.assertGreater(roads["functional_class"].nunique(), 2)
        self.assertGreater(roads["traffic_level"].nunique(), 2)
        self.assertTrue(roads["road_name"].str.contains("Synthetic Demonstration").all())
        validate_canonical_schema(
            roads,
            expected_data_status="illustrative",
            municipality_slug="sample_borough",
        )

    def test_real_import_reuses_mapping_defaults_and_provisional_status(self):
        source = ONBOARDING_DEMO_MUNICIPALITY.data_path.read_bytes()
        mapping = dict(ONBOARDING_DEMO_MUNICIPALITY.source_column_mapping)
        mapping.pop("Source_Status")
        review = review_real_import(
            _identity("real_import_rehearsal", "Real Import Rehearsal"),
            source,
            mapping=mapping,
            defaults={},
            data_status="provisional",
            source_owner="Rehearsal public works office",
            acquired_date="2026-08-15",
            source_reference="temporary supplied inventory",
        )
        self.assertEqual(review.source_rows, 5)
        self.assertTrue(review.canonical["data_status"].eq("provisional").all())
        self.assertEqual(len(review.mapping), 22)
        self.assertEqual(review.defaults, {})
        self.assertEqual(review.treatment_normalizations["Mill and Overlay"], "Mill & Fill")

    def test_real_import_applies_only_visible_defaults(self):
        source = ONBOARDING_DEMO_MUNICIPALITY.data_path.read_bytes()
        mapping = dict(ONBOARDING_DEMO_MUNICIPALITY.source_column_mapping)
        mapping.pop("Source_Status")
        mapping.pop("Owner")
        review = review_real_import(
            _identity("visible_defaults", "Visible Defaults"),
            source,
            mapping=mapping,
            defaults={"jurisdiction": "Visible Defaults Public Works"},
            data_status="provisional",
            source_owner="Public works office",
            acquired_date="2026-08-15",
            source_reference="delivery with uniform jurisdiction",
        )
        self.assertEqual(
            review.defaults,
            {"jurisdiction": "Visible Defaults Public Works"},
        )
        self.assertTrue(
            review.canonical["jurisdiction"].eq("Visible Defaults Public Works").all()
        )

    def test_package_safety_duplicate_protection_and_registry_isolation(self):
        registry_snapshot = dict(MUNICIPALITIES)
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            first_review = review_illustrative_demo(
                _identity("runtime_demo_one", "Runtime Demo One"),
                generated_root=root,
            )
            first = create_illustrative_demo_package(first_review, generated_root=root)
            second_review = review_illustrative_demo(
                _identity("runtime_demo_two", "Runtime Demo Two"),
                generated_root=root,
            )
            second = create_illustrative_demo_package(second_review, generated_root=root)

            self.assertTrue(first.manifest_path.is_file())
            self.assertTrue(first.canonical_review_path.is_file())
            self.assertTrue((first.manifest_path.parent / "package_metadata.json").is_file())
            self.assertTrue(first.runtime_launchable)
            self.assertEqual(len(list_generated_municipalities(generated_root=root)), 2)
            loaded = load_generated_municipality("runtime_demo_one", generated_root=root)
            self.assertEqual(loaded.formal_name, "Runtime Demo One")
            self.assertGreater(len(load_municipality_inventory(loaded)), 0)
            with self.assertRaisesRegex(ValueError, "already exists"):
                assert_slug_available("runtime_demo_one", generated_root=root)
            with self.assertRaisesRegex(ValueError, "permanently registered"):
                assert_slug_available("jackson", generated_root=root)
            self.assertNotEqual(first.manifest_path, second.manifest_path)

        self.assertEqual(MUNICIPALITIES, registry_snapshot)

    def test_real_package_is_ready_for_review_not_runtime_registration(self):
        source = ONBOARDING_DEMO_MUNICIPALITY.data_path.read_bytes()
        mapping = dict(ONBOARDING_DEMO_MUNICIPALITY.source_column_mapping)
        mapping.pop("Source_Status")
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            review = review_real_import(
                _identity("real_package", "Real Package"),
                source,
                mapping=mapping,
                defaults={},
                data_status="provisional",
                source_owner="Road office",
                acquired_date="2026-08-15",
                source_reference="delivery.csv",
                generated_root=root,
            )
            package = create_real_import_package(review, source, generated_root=root)
            self.assertFalse(package.runtime_launchable)
            self.assertEqual(package.source_path.read_bytes(), source)
            self.assertEqual((package.manifest_path.parent / "source_roads.raw.csv").read_bytes(), source)
            self.assertEqual(package.config.normalized_data_status, "provisional")

    def test_demo_creation_rejects_nonillustrative_review(self):
        with tempfile.TemporaryDirectory() as directory_name:
            review = review_illustrative_demo(
                _identity("unsafe_demo", "Unsafe Demo"),
                generated_root=Path(directory_name),
            )
            unsafe = replace(review, config=replace(review.config, data_status="provisional"))
            with self.assertRaisesRegex(ValueError, "must use illustrative"):
                create_illustrative_demo_package(unsafe, generated_root=Path(directory_name))

    def test_portfolio_combines_registered_and_generated_metadata_without_inventory_loading(self):
        with tempfile.TemporaryDirectory() as directory_name:
            active = Path(directory_name) / "active"
            archived = Path(directory_name) / "archive"
            review = review_illustrative_demo(
                _identity("portfolio_demo", "Portfolio Demo"),
                road_count=7,
                generated_root=active,
            )
            create_illustrative_demo_package(review, generated_root=active)
            entries = build_municipality_portfolio(
                generated_root=active,
                archived_root=archived,
            )
            permanent = next(entry for entry in entries if entry.slug == "jackson")
            generated = next(entry for entry in entries if entry.slug == "portfolio_demo")
            self.assertEqual(permanent.readiness_state, "Permanent / Registered")
            self.assertTrue(permanent.permanent)
            self.assertGreater(permanent.road_count, 0)
            self.assertEqual(generated.readiness_state, "Generated Illustrative Demo")
            self.assertEqual(generated.road_count, 7)
            self.assertFalse(generated.permanent)
            self.assertTrue(generated.dashboard_launchable)
            self.assertEqual(generated.validation_summary, "PASS")

            filtered = filter_municipality_portfolio(
                entries,
                search="portfolio",
                source_scopes=["Generated"],
                readiness_states=["Generated Illustrative Demo"],
            )
            self.assertEqual([entry.slug for entry in filtered], ["portfolio_demo"])

    def test_invalid_generated_manifest_is_visible_as_validation_required(self):
        with tempfile.TemporaryDirectory() as directory_name:
            active = Path(directory_name) / "active"
            invalid = active / "broken_demo"
            invalid.mkdir(parents=True)
            (invalid / "manifest.json").write_text(
                '{"slug": "broken_demo", "formal_name": "Broken Demo"}',
                encoding="utf-8",
            )
            entries = build_municipality_portfolio(generated_root=active)
            broken = next(entry for entry in entries if entry.slug == "broken_demo")
            self.assertEqual(broken.readiness_state, "Validation Required")
            self.assertIsNone(broken.config)
            self.assertIn("manifest", broken.validation_summary.lower())

    def test_archive_restore_and_path_safeguards_are_recoverable(self):
        with tempfile.TemporaryDirectory() as directory_name:
            active = Path(directory_name) / "active"
            archived = Path(directory_name) / "archive"
            review = review_illustrative_demo(
                _identity("archive_demo", "Archive Demo"),
                generated_root=active,
            )
            create_illustrative_demo_package(review, generated_root=active)
            destination = archive_generated_demo(
                "archive_demo", generated_root=active, archived_root=archived
            )
            self.assertTrue(destination.is_dir())
            self.assertFalse((active / "archive_demo").exists())
            with self.assertRaisesRegex(ValueError, "is archived"):
                assert_slug_available(
                    "archive_demo", generated_root=active, archived_root=archived
                )
            hidden = build_municipality_portfolio(
                generated_root=active, archived_root=archived
            )
            self.assertNotIn("archive_demo", {entry.slug for entry in hidden})
            visible = build_municipality_portfolio(
                generated_root=active, archived_root=archived, include_archived=True
            )
            archived_entry = next(entry for entry in visible if entry.slug == "archive_demo")
            self.assertEqual(archived_entry.readiness_state, "Archived Generated Demo")
            self.assertFalse(archived_entry.dashboard_launchable)
            restored = restore_archived_demo(
                "archive_demo", generated_root=active, archived_root=archived
            )
            self.assertEqual(restored, active / "archive_demo")
            self.assertTrue(restored.is_dir())
            with self.assertRaisesRegex(ValueError, "normalized"):
                archive_generated_demo(
                    "../archive_demo", generated_root=active, archived_root=archived
                )
            with self.assertRaisesRegex(ValueError, "Permanent municipality"):
                archive_generated_demo(
                    "jackson", generated_root=active, archived_root=archived
                )

    def test_real_import_cannot_be_archived_or_cloned_as_demo(self):
        source = ONBOARDING_DEMO_MUNICIPALITY.data_path.read_bytes()
        mapping = dict(ONBOARDING_DEMO_MUNICIPALITY.source_column_mapping)
        mapping.pop("Source_Status")
        with tempfile.TemporaryDirectory() as directory_name:
            active = Path(directory_name) / "active"
            archived = Path(directory_name) / "archive"
            review = review_real_import(
                _identity("real_lifecycle", "Real Lifecycle"),
                source,
                mapping=mapping,
                defaults={},
                data_status="provisional",
                source_owner="Road office",
                acquired_date="2026-08-15",
                source_reference="delivery.csv",
                generated_root=active,
            )
            create_real_import_package(review, source, generated_root=active)
            with self.assertRaisesRegex(ValueError, "illustrative demo"):
                archive_generated_demo(
                    "real_lifecycle", generated_root=active, archived_root=archived
                )
            with self.assertRaisesRegex(ValueError, "illustrative demo"):
                clone_illustrative_demo(
                    "real_lifecycle",
                    _identity("unsafe_clone", "Unsafe Clone"),
                    generated_root=active,
                )

    def test_clone_regenerates_synthetic_inventory_under_new_identity(self):
        with tempfile.TemporaryDirectory() as directory_name:
            active = Path(directory_name) / "active"
            review = review_illustrative_demo(
                _identity("clone_source", "Clone Source"),
                road_count=9,
                generated_root=active,
            )
            create_illustrative_demo_package(review, generated_root=active)
            clone = clone_illustrative_demo(
                "clone_source",
                _identity("clone_target", "Clone Target"),
                generated_root=active,
            )
            roads = load_municipality_inventory(clone.config)
            self.assertEqual(clone.config.formal_name, "Clone Target")
            self.assertEqual(clone.config.normalized_data_status, "illustrative")
            self.assertEqual(len(roads), 9)
            self.assertTrue(roads["jurisdiction"].eq("Clone Target").all())

    def test_operator_page_landing_and_demo_creation(self):
        from streamlit.testing.v1 import AppTest

        slug = "apptest_runtime_demo"
        target = GENERATED_MUNICIPALITIES_ROOT / slug
        if target.exists():
            shutil.rmtree(target)
        try:
            app = AppTest.from_file(
                "pages/1_Municipality_Onboarding.py", default_timeout=30
            ).run()
            self.assertFalse(app.exception)
            self.assertIn(
                "Municipality Onboarding & Demo Builder",
                [item.value for item in app.title],
            )
            self.assertEqual(
                [option for option in app.radio[0].options],
                [
                    "Create Illustrative Demo",
                    "Import Municipality Data",
                    "Municipality Portfolio",
                ],
            )
            app.text_input(key="demo_formal_name").set_value("AppTest Runtime Demo")
            app.text_input(key="demo_short_name").set_value("AppTest")
            app.text_input(key="demo_slug").set_value(slug)
            app.run()
            app.button(key="validate_demo").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any(item.value == "Final review" for item in app.subheader))
            app.button(key="create_demo").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(target.is_dir())
            self.assertTrue(any(button.label == "Open Municipality Dashboard" for button in app.button))
        finally:
            if target.exists():
                shutil.rmtree(target)

    def test_operator_page_real_import_defaults_to_provisional(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(
            "pages/1_Municipality_Onboarding.py", default_timeout=30
        ).run()
        app.radio[0].set_value("Import Municipality Data").run()
        self.assertFalse(app.exception)
        self.assertTrue(any(item.value == "Import Municipality Data" for item in app.header))
        self.assertEqual(app.selectbox(key="import_status").value, "provisional")
        self.assertTrue(any(item.label == "Upload municipality road inventory CSV" for item in app.get("file_uploader")))

    def test_operator_portfolio_lists_filters_and_shows_details(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(
            "pages/1_Municipality_Onboarding.py", default_timeout=30
        ).run()
        app.radio[0].set_value("Municipality Portfolio").run()
        self.assertFalse(app.exception)
        self.assertTrue(any(item.value == "Municipality Portfolio" for item in app.header))
        self.assertTrue(any("Showing 4 of 4" in item.value for item in app.get("markdown")))
        app.text_input(key="portfolio_search").set_value("jackson").run()
        self.assertTrue(any("Showing 1 of 4" in item.value for item in app.get("markdown")))
        app.selectbox(key="portfolio_selected").set_value("City of Jackson — jackson").run()
        self.assertFalse(app.exception)
        self.assertTrue(
            any(item.value == "Municipality details: City of Jackson" for item in app.subheader)
        )
        self.assertEqual(
            [tab.label for tab in app.tabs],
            ["Overview", "Provenance", "Validation Summary", "Manifest"],
        )

    def test_registered_municipality_can_be_selected_without_environment_variable(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file("dashboard.py", default_timeout=30)
        app.session_state["paventra_selected_municipality_slug"] = "demo_city"
        app.run()
        self.assertFalse(app.exception)
        self.assertIn("Demo City Municipal Pilot", [item.value for item in app.title])

    def test_runtime_demo_launches_through_existing_dashboard_flow(self):
        from streamlit.testing.v1 import AppTest

        slug = "runtime_dashboard_apptest"
        target = GENERATED_MUNICIPALITIES_ROOT / slug
        if target.exists():
            shutil.rmtree(target)
        try:
            review = review_illustrative_demo(
                _identity(slug, "Runtime Dashboard Agency"),
                road_count=10,
            )
            create_illustrative_demo_package(review)
            app = AppTest.from_file("dashboard.py", default_timeout=30)
            app.session_state["paventra_runtime_municipality_slug"] = slug
            app.run()
            self.assertFalse(app.exception)
            self.assertIn(
                "Runtime Dashboard Agency Municipal Pilot",
                [item.value for item in app.title],
            )
            self.assertTrue(
                any("Illustrative demonstration analysis" in item.value for item in app.caption)
            )
            next(
                button for button in app.button
                if button.label == "Open investment briefing"
            ).click().run()
            self.assertFalse(app.exception)
            app.radio[0].set_value("Address Urgent Needs").run()
            self.assertFalse(app.exception)
            next(
                button for button in app.button
                if button.label == "Open interactive network map"
            ).click().run()
            self.assertFalse(app.exception)
            next(
                button for button in app.button
                if button.label == "Generate executive briefing"
            ).click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.download_button)
        finally:
            if target.exists():
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()
