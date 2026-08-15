import shutil
import unittest
from unittest.mock import patch

from components import municipality_report as report_module
from components.municipality_presentation import summarize_network_for_presentation
from components.municipality_report import (
    build_municipality_report,
    municipality_report_filename,
)
from gis.engine import create_network_map
from pilot.municipality_admin import (
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    create_illustrative_demo_package,
    load_generated_municipality,
    review_illustrative_demo,
)
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_registry import MUNICIPALITIES
from pilot.municipality_scenarios import build_municipality_scenario_results


NAPOLEON_SLUG = "napoleon_township"


def _scenario(config, roads):
    return build_municipality_scenario_results(
        roads,
        "Balanced Annual Program",
        config.scenario_catalog_id,
    )


class PresentationPolishTests(unittest.TestCase):
    def test_executive_summary_reuses_validated_inventory_and_scenario_values(self):
        config = MUNICIPALITIES["jackson"]
        roads = load_municipality_inventory(config)
        results = _scenario(config, roads)
        summary = summarize_network_for_presentation(roads, results)

        self.assertEqual(summary.average_pci, float(roads["PCI"].mean()))
        self.assertEqual(
            summary.network_health,
            max(0.0, 100.0 - float(roads["Risk Score"].mean())),
        )
        self.assertEqual(
            summary.high_risk_segments,
            int((roads["Risk Level"] == "High").sum()),
        )
        self.assertEqual(
            summary.estimated_investment_need,
            float(roads["Estimated Cost"].sum()),
        )
        self.assertEqual(summary.strategy_name, "Balanced Annual Program")
        self.assertEqual(summary.strategy_budget, results["scenario"]["budget"])
        self.assertEqual(summary.next_road, results["roads"].iloc[0]["Road Name"])

    def test_first_screen_answers_executive_questions_for_registered_agencies(self):
        from streamlit.testing.v1 import AppTest

        required_metrics = {
            "Network Health",
            "Average PCI",
            "High-Risk Segments",
            "Estimated Investment Need",
        }
        for slug, config in MUNICIPALITIES.items():
            with self.subTest(slug=slug):
                app = AppTest.from_file("dashboard.py", default_timeout=30)
                app.session_state["paventra_selected_municipality_slug"] = slug
                app.run()
                self.assertFalse(app.exception)
                self.assertEqual([item.value for item in app.title], [config.pilot_name])
                self.assertTrue(required_metrics.issubset({item.label for item in app.metric}))
                visible = " ".join(
                    str(item.value)
                    for kind in ("markdown", "caption")
                    for item in app.get(kind)
                )
                self.assertIn("Current investment strategy", visible)
                self.assertIn("Balanced Annual Program", visible)
                self.assertIn("Recommended next action", visible)
                self.assertIn(config.formal_name, visible)

    def test_village_and_county_generated_presentations_are_configuration_driven(self):
        from streamlit.testing.v1 import AppTest

        cases = (
            ("phase19_village", "Village of Presentation Harbor", "village"),
            ("phase19_county", "Presentation County", "county"),
        )
        targets = [GENERATED_MUNICIPALITIES_ROOT / slug for slug, _, _ in cases]
        for target in targets:
            if target.exists():
                shutil.rmtree(target)
        try:
            for slug, formal_name, entity_type in cases:
                with self.subTest(entity_type=entity_type):
                    identity = MunicipalityIdentity(
                        formal_name=formal_name,
                        short_name=formal_name,
                        entity_type=entity_type,
                        state="Michigan",
                        slug=slug,
                        leadership_label=f"{entity_type} leadership",
                        official_action_label=f"official {entity_type} determination",
                        map_center=(42.25, -84.4),
                        map_zoom=12,
                        scenario_catalog_id="standard",
                        pilot_label="Municipal Pilot",
                    )
                    package = create_illustrative_demo_package(
                        review_illustrative_demo(identity, road_count=6)
                    )
                    app = AppTest.from_file("dashboard.py", default_timeout=30)
                    app.session_state["paventra_runtime_municipality_slug"] = slug
                    app.run()
                    self.assertFalse(app.exception)
                    self.assertEqual(
                        [item.value for item in app.title],
                        [package.config.pilot_name],
                    )
                    visible = " ".join(
                        str(item.value)
                        for kind in ("caption", "markdown")
                        for item in app.get(kind)
                    )
                    self.assertIn(formal_name, visible)
                    self.assertNotIn("City of Jackson", visible)
        finally:
            for target in targets:
                if target.exists():
                    shutil.rmtree(target)

    def test_napoleon_presentation_flow_preserves_identity_and_disclosure(self):
        from streamlit.testing.v1 import AppTest

        config = load_generated_municipality(NAPOLEON_SLUG)
        app = AppTest.from_file("dashboard.py", default_timeout=30)
        app.session_state["paventra_runtime_municipality_slug"] = NAPOLEON_SLUG
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual([item.value for item in app.title], [config.pilot_name])

        app.button(key="paventra_nav_pavement_analytics").click().run()
        self.assertFalse(app.exception)
        self.assertEqual([item.value for item in app.title], ["Pavement Analytics"])
        workflow = [item.value for item in app.subheader]
        self.assertLess(workflow.index("1. Current network"), workflow.index("2. Investment strategy"))
        self.assertLess(workflow.index("2. Investment strategy"), workflow.index("3. Recommended investments"))
        self.assertLess(workflow.index("3. Recommended investments"), workflow.index("4. Expected program impact"))
        analytics_text = " ".join(
            str(item.value)
            for kind in ("caption", "markdown")
            for item in app.get(kind)
        )
        self.assertIn(config.formal_name, analytics_text)
        self.assertIn("Scenario assumption", analytics_text)
        self.assertIn("not a machine-learning prediction", analytics_text)
        app.radio[0].set_value("Address Urgent Needs").run()
        self.assertFalse(app.exception)
        app.button(key="paventra_nav_dashboard").click().run()
        self.assertFalse(app.exception)
        dashboard_text = " ".join(
            str(item.value)
            for kind in ("caption", "markdown")
            for item in app.get(kind)
        )
        self.assertIn("Address Urgent Needs", dashboard_text)

        app.button(key="paventra_nav_network_map").click().run()
        self.assertFalse(app.exception)
        self.assertEqual([item.value for item in app.title], ["Network Map"])
        self.assertTrue(any("Illustrative map" in item.value for item in app.info))
        self.assertEqual(app.selectbox[0].label, "Select a road to review")

        app.button(key="paventra_nav_reports").click().run()
        self.assertFalse(app.exception)
        self.assertEqual([item.value for item in app.title], ["Reports"])
        app.button(key="municipality_generate_report").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.download_button)
        self.assertTrue(
            any(
                "napoleon_township_transportation_investment_scenario.pdf"
                in item.value
                for item in app.caption
            )
        )
        self.assertEqual(
            app.session_state["paventra_runtime_municipality_slug"],
            NAPOLEON_SLUG,
        )

        app.button(key="paventra_nav_municipality_portfolio").click().run()
        self.assertFalse(app.exception)
        self.assertIn("Municipality Portfolio", [item.value for item in app.header])
        self.assertEqual(
            app.session_state["paventra_runtime_municipality_slug"],
            NAPOLEON_SLUG,
        )

    def test_napoleon_map_uses_configured_center_inventory_and_neutral_layers(self):
        config = load_generated_municipality(NAPOLEON_SLUG)
        roads = load_municipality_inventory(config)
        results = _scenario(config, roads)
        map_roads = roads.copy()
        ranks = results["roads"].set_index("Road ID")["Priority Rank"].to_dict()
        map_roads["Priority Rank"] = map_roads["Road ID"].map(ranks)
        road_map = create_network_map(
            map_roads,
            selected_ids=results["selected_ids"],
            map_center=config.map_center,
            zoom_start=config.map_zoom,
        )
        rendered = road_map.get_root().render()

        self.assertEqual(tuple(road_map.location), tuple(config.map_center))
        self.assertIn("Road Network", rendered)
        self.assertIn("Priority Projects", rendered)
        self.assertIn("Calculated risk", rendered)
        self.assertNotIn("AI Recommendations", rendered)
        for road_name in roads["Road Name"].unique():
            self.assertIn(str(road_name), rendered)

    def test_napoleon_pdf_has_its_identity_status_summary_and_no_leakage(self):
        config = load_generated_municipality(NAPOLEON_SLUG)
        roads = load_municipality_inventory(config)
        results = _scenario(config, roads)
        paragraphs = []
        tables = []
        original_paragraph = report_module.Paragraph
        original_table = report_module.Table

        def capture_paragraph(text, style):
            paragraphs.append(str(text))
            return original_paragraph(text, style)

        def capture_table(data, *args, **kwargs):
            tables.append(data)
            return original_table(data, *args, **kwargs)

        with patch.object(report_module, "Paragraph", side_effect=capture_paragraph), patch.object(
            report_module, "Table", side_effect=capture_table
        ):
            report = build_municipality_report(config, roads, results)

        visible = " ".join(paragraphs + [str(table) for table in tables])
        self.assertTrue(report.startswith(b"%PDF"))
        self.assertEqual(
            municipality_report_filename(config),
            "napoleon_township_transportation_investment_scenario.pdf",
        )
        self.assertIn("Napoleon Township", visible)
        self.assertIn("Illustrative", visible)
        self.assertIn("Average PCI", visible)
        self.assertIn("Estimated investment need", visible)
        self.assertIn("Balanced Annual Program", visible)
        self.assertIn(config.pilot_disclaimer, visible)
        for unrelated in (
            "City of Jackson",
            "Pine Ridge Township",
            "City of Demo City",
            "Demo County Road Commission",
        ):
            self.assertNotIn(unrelated, visible)


if __name__ == "__main__":
    unittest.main()
