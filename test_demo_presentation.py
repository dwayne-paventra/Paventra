import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from components import municipality_report as report_module
from components.municipality_report import (
    build_municipality_report,
    municipality_report_filename,
    municipality_report_title,
)
from pilot.canonical_inventory import CANONICAL_COLUMNS
from pilot.municipality_admin import (
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    build_municipality_portfolio,
    create_illustrative_demo_package,
    review_illustrative_demo,
)
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_scenarios import (
    build_municipality_scenario_results,
    get_scenario_catalog,
)
from pilot.source_provenance import compute_source_checksum


PROJECT_ROOT = Path(__file__).resolve().parent
UNRELATED_IDENTITIES = (
    "City of Jackson",
    "Pine Ridge",
    "City of Demo City",
    "Demo County Road Commission",
)


def _identity(
    slug: str,
    formal_name: str,
    *,
    short_name: str | None = None,
    entity_type: str = "municipality",
    pilot_label: str = "Municipal Pilot",
) -> MunicipalityIdentity:
    return MunicipalityIdentity(
        formal_name=formal_name,
        short_name=short_name or formal_name,
        entity_type=entity_type,
        state="Michigan",
        slug=slug,
        leadership_label=f"{entity_type} leadership",
        official_action_label=f"official {entity_type} determination",
        map_center=(42.25, -84.40),
        map_zoom=12,
        scenario_catalog_id="standard",
        pilot_label=pilot_label,
    )


class GeneratedDemoPresentationTests(unittest.TestCase):
    def test_entity_types_generate_clean_reports_and_packages(self):
        cases = (
            ("township", "Cedar Township"),
            ("city", "City of Lakeview"),
            ("village", "Village of Northfield"),
            ("road commission", "West County Road Commission"),
            ("agency", "Regional Streets Authority"),
        )
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            for index, (entity_type, formal_name) in enumerate(cases):
                with self.subTest(entity_type=entity_type):
                    slug = f"presentation_{index}"
                    review = review_illustrative_demo(
                        _identity(slug, formal_name, entity_type=entity_type),
                        road_count=6,
                        generated_root=root,
                    )
                    package = create_illustrative_demo_package(
                        review, generated_root=root
                    )
                    roads = load_municipality_inventory(package.config)
                    results = build_municipality_scenario_results(
                        roads,
                        "Balanced Annual Program",
                        package.config.scenario_catalog_id,
                    )
                    captured = []
                    original_paragraph = report_module.Paragraph

                    def capture_paragraph(text, style):
                        captured.append(str(text))
                        return original_paragraph(text, style)

                    with patch.object(
                        report_module, "Paragraph", side_effect=capture_paragraph
                    ):
                        report = build_municipality_report(
                            package.config, roads, results
                        )

                    visible_report_text = " ".join(captured)
                    self.assertTrue(report.startswith(b"%PDF"))
                    self.assertIn(package.config.pilot_name, visible_report_text)
                    self.assertIn(
                        municipality_report_title(package.config), visible_report_text
                    )
                    self.assertEqual(
                        municipality_report_filename(package.config),
                        f"{slug}_transportation_investment_scenario.pdf",
                    )
                    for unrelated in UNRELATED_IDENTITIES:
                        self.assertNotIn(unrelated, visible_report_text)

                    manifest = json.loads(package.manifest_path.read_text(encoding="utf-8"))
                    metadata = json.loads(
                        (package.manifest_path.parent / "package_metadata.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    source = pd.read_csv(package.source_path)
                    self.assertEqual(manifest["manifest_version"], 3)
                    self.assertEqual(manifest["data_status"], "illustrative")
                    self.assertEqual(
                        manifest["source_owner"], "Paventra synthetic demo generator"
                    )
                    self.assertEqual(
                        manifest["source_checksum"],
                        compute_source_checksum(package.source_path),
                    )
                    self.assertEqual(tuple(source.columns), CANONICAL_COLUMNS)
                    self.assertTrue(source["jurisdiction"].eq(formal_name).all())
                    self.assertEqual(metadata["package_type"], "illustrative_demo")
                    self.assertEqual(metadata["road_count"], 6)

    def test_generated_package_is_discovered_by_a_fresh_python_process(self):
        with tempfile.TemporaryDirectory() as directory_name:
            root = Path(directory_name)
            slug = "restart_persistence_demo"
            review = review_illustrative_demo(
                _identity(slug, "Restart Persistence Township", entity_type="township"),
                generated_root=root,
            )
            create_illustrative_demo_package(review, generated_root=root)
            environment = os.environ.copy()
            environment["GENERATED_ROOT"] = str(root)
            environment["GENERATED_SLUG"] = slug
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import os; from pathlib import Path; "
                        "from pilot.municipality_admin import load_generated_municipality; "
                        "c=load_generated_municipality(os.environ['GENERATED_SLUG'], "
                        "generated_root=Path(os.environ['GENERATED_ROOT'])); "
                        "print(c.slug, c.pilot_name)"
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
            self.assertIn(
                "restart_persistence_demo Restart Persistence Township Municipal Pilot",
                completed.stdout,
            )
            entries = build_municipality_portfolio(generated_root=root)
            persisted = next(entry for entry in entries if entry.slug == slug)
            self.assertEqual(persisted.formal_name, "Restart Persistence Township")
            self.assertTrue(persisted.dashboard_launchable)

    def test_long_generated_identity_completes_dashboard_flow_without_leakage(self):
        from streamlit.testing.v1 import AppTest

        slug = "long_identity_presentation_apptest"
        target = GENERATED_MUNICIPALITIES_ROOT / slug
        if target.exists():
            shutil.rmtree(target)
        formal_name = (
            "Great Lakes Intergovernmental Transportation Coordination Authority"
        )
        try:
            review = review_illustrative_demo(
                _identity(
                    slug,
                    formal_name,
                    entity_type="agency",
                    pilot_label=f"{formal_name} Demonstration",
                ),
                road_count=8,
            )
            package = create_illustrative_demo_package(review)
            app = AppTest.from_file("dashboard.py", default_timeout=30)
            app.session_state["paventra_runtime_municipality_slug"] = slug
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual([item.value for item in app.title], [f"{formal_name} Demonstration"])
            self.assertTrue(
                any(
                    button.label == "Return to Municipality Portfolio"
                    for button in app.button
                )
            )
            visible = " ".join(
                str(item.value)
                for kind in ("title", "caption", "markdown", "subheader", "info", "warning")
                for item in app.get(kind)
            )
            for unrelated in UNRELATED_IDENTITIES:
                self.assertNotIn(unrelated, visible)

            next(
                button for button in app.button
                if button.label == "Open investment briefing"
            ).click().run()
            catalog = get_scenario_catalog(package.config.scenario_catalog_id)
            for scenario_name in catalog:
                app.radio[0].set_value(scenario_name).run()
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
            self.assertTrue(
                any(
                    button.label == "Download executive briefing (PDF)"
                    for button in app.download_button
                )
            )
            full_flow_visible = " ".join(
                str(item.value)
                for kind in (
                    "title", "caption", "markdown", "subheader", "info", "warning"
                )
                for item in app.get(kind)
            )
            for unrelated in UNRELATED_IDENTITIES:
                self.assertNotIn(unrelated, full_flow_visible)

            portfolio = AppTest.from_file(
                "pages/1_Municipality_Onboarding.py", default_timeout=30
            ).run()
            portfolio.radio[0].set_value("Municipality Portfolio").run()
            portfolio.text_input(key="portfolio_search").set_value(slug).run()
            selector = portfolio.selectbox(key="portfolio_selected")
            self.assertEqual(len(selector.options), 2)
            selector.set_value(selector.options[1]).run()
            self.assertFalse(portfolio.exception)
            self.assertIn(
                f"Municipality details: {formal_name}",
                [item.value for item in portfolio.subheader],
            )

            restarted = AppTest.from_file("dashboard.py", default_timeout=30)
            restarted.session_state["paventra_runtime_municipality_slug"] = slug
            restarted.run()
            self.assertFalse(restarted.exception)
            self.assertEqual(
                [item.value for item in restarted.title],
                [f"{formal_name} Demonstration"],
            )
            restarted.button(key="municipality_return_to_portfolio").click().run()
            self.assertFalse(restarted.exception)
            self.assertIn(
                "Municipality Onboarding & Demo Builder",
                [item.value for item in restarted.title],
            )
        finally:
            if target.exists():
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()
