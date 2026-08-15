import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import pandas as pd

from components.jackson_assumptions import render_jackson_assumptions
from components.jackson_executive import render_jackson_executive_overview
from components.jackson_map import render_jackson_map
from components.jackson_recommendations import render_jackson_recommendations
from components.municipality_report import (
    build_municipality_report,
    municipality_report_filename,
    municipality_report_title,
    render_municipality_report,
)
from components.jackson_scenarios import (
    render_jackson_scenario_impact,
    render_jackson_scenario_selector,
)
from pilot.jackson_scenarios import (
    JACKSON_SCENARIOS,
    build_jackson_scenario_results,
    get_jackson_scenario,
)
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_registry import (
    ACTIVE_MUNICIPALITY,
    DEMO_ROAD_COMMISSION_MUNICIPALITY,
    MUNICIPALITIES,
)
from pilot.municipality_scenarios import (
    MUNICIPALITY_SCENARIOS,
    build_municipality_scenario_results,
    get_municipality_scenario,
    get_scenario_catalog,
)


PROJECT_ROOT = Path(__file__).resolve().parent


class MunicipalityPresentationTests(unittest.TestCase):
    def test_generic_scenario_selection_is_municipality_neutral(self):
        self.assertEqual(JACKSON_SCENARIOS, MUNICIPALITY_SCENARIOS)
        for scenario_name in MUNICIPALITY_SCENARIOS:
            scenario = get_municipality_scenario(scenario_name)
            self.assertEqual(scenario, MUNICIPALITY_SCENARIOS[scenario_name])
            self.assertIsNot(scenario, MUNICIPALITY_SCENARIOS[scenario_name])

        with self.assertRaisesRegex(KeyError, "Unknown scenario"):
            get_municipality_scenario("Not configured")

    def test_scenario_catalog_selection_comes_from_config(self):
        standard = get_scenario_catalog(
            MUNICIPALITIES["jackson"].scenario_catalog_id
        )
        demo_city = get_scenario_catalog(
            MUNICIPALITIES["demo_city"].scenario_catalog_id
        )
        road_commission = get_scenario_catalog(
            DEMO_ROAD_COMMISSION_MUNICIPALITY.scenario_catalog_id
        )

        self.assertEqual(standard, demo_city)
        self.assertEqual(standard["Balanced Annual Program"]["budget"], 3_000_000)
        self.assertEqual(
            road_commission["Balanced Annual Program"]["budget"],
            3_500_000,
        )
        standard["Balanced Annual Program"]["budget"] = 1
        self.assertEqual(
            get_scenario_catalog("standard")["Balanced Annual Program"]["budget"],
            3_000_000,
        )
        with self.assertRaisesRegex(ValueError, "Unknown scenario catalog"):
            get_scenario_catalog("missing")

    def test_each_municipality_completes_inventory_scenario_report_flow(self):
        for slug, config in MUNICIPALITIES.items():
            with self.subTest(municipality=slug):
                roads = load_municipality_inventory(config)
                results = build_municipality_scenario_results(
                    roads,
                    "Balanced Annual Program",
                    config.scenario_catalog_id,
                )
                report = build_municipality_report(config, roads, results)

                self.assertGreater(len(results["roads"]), 0)
                self.assertLessEqual(results["spent"], results["scenario"]["budget"])
                self.assertTrue(report.startswith(b"%PDF"))
                self.assertGreater(len(report), 1_000)
                self.assertEqual(
                    municipality_report_title(config),
                    f"{config.short_name} Transportation Investment Scenario",
                )
                self.assertEqual(
                    municipality_report_filename(config),
                    f"{slug}_transportation_investment_scenario.pdf",
                )

    def test_non_city_report_uses_configured_agency_wording(self):
        config = DEMO_ROAD_COMMISSION_MUNICIPALITY
        with patch("streamlit.caption") as caption, patch(
            "streamlit.download_button"
        ) as download_button, patch("streamlit.subheader"):
            render_municipality_report(config, b"%PDF-demo")

        caption.assert_called_once_with(
            "Download a concise briefing for discussion with road commission leadership."
        )
        self.assertEqual(
            download_button.call_args.kwargs["file_name"],
            "demo_road_commission_transportation_investment_scenario.pdf",
        )
        self.assertNotIn("City", municipality_report_title(config))

    def test_jackson_scenario_compatibility_wrappers_match_generic_results(self):
        config = MUNICIPALITIES["jackson"]
        roads = load_municipality_inventory(config)
        generic = build_municipality_scenario_results(
            roads,
            "Balanced Annual Program",
        )
        compatible = build_jackson_scenario_results(
            roads,
            "Balanced Annual Program",
        )

        self.assertEqual(
            get_jackson_scenario("Balanced Annual Program"),
            get_municipality_scenario("Balanced Annual Program"),
        )
        self.assertEqual(compatible["selected_ids"], generic["selected_ids"])
        self.assertEqual(compatible["spent"], generic["spent"])
        pd.testing.assert_frame_equal(compatible["roads"], generic["roads"])

    def test_jackson_component_wrappers_delegate_with_legacy_signatures(self):
        roads = object()
        results = {"marker": "results"}

        with patch(
            "components.jackson_executive.render_municipality_executive_overview"
        ) as generic:
            render_jackson_executive_overview(roads, results)
            generic.assert_called_once_with(ACTIVE_MUNICIPALITY, roads, results)

        with patch(
            "components.jackson_assumptions.render_municipality_assumptions"
        ) as generic:
            render_jackson_assumptions()
            generic.assert_called_once_with(ACTIVE_MUNICIPALITY)

        with patch(
            "components.jackson_recommendations.render_municipality_recommendations"
        ) as generic:
            render_jackson_recommendations(results)
            generic.assert_called_once_with(ACTIVE_MUNICIPALITY, results)

        with patch("components.jackson_map.render_municipality_map") as generic:
            render_jackson_map(roads, results)
            generic.assert_called_once_with(
                ACTIVE_MUNICIPALITY,
                roads,
                results,
                selection_key="jackson_road_selection",
            )

        with patch(
            "components.jackson_scenarios.render_municipality_scenario_selector",
            return_value="Balanced Annual Program",
        ) as generic:
            self.assertEqual(
                render_jackson_scenario_selector(),
                "Balanced Annual Program",
            )
            generic.assert_called_once_with(
                JACKSON_SCENARIOS,
                session_key="jackson_scenario",
            )

        with patch(
            "components.jackson_scenarios.render_municipality_scenario_impact"
        ) as generic:
            render_jackson_scenario_impact(results)
            generic.assert_called_once_with(results)

    def test_streamlit_full_flow_for_all_registered_agencies(self):
        script = """
import os
from streamlit.testing.v1 import AppTest

app = AppTest.from_file('dashboard.py', default_timeout=30)
app.run()
assert not app.exception, [str(item.value) for item in app.exception]
assert os.environ['EXPECTED_TITLE'] in [item.value for item in app.title]
assert any(os.environ['EXPECTED_FORMAL'] in item.value for item in app.markdown)
assert any(os.environ['EXPECTED_STATUS'] in item.value for item in app.caption)

next(button for button in app.button if button.label == 'Open investment briefing').click().run()
assert not app.exception, [str(item.value) for item in app.exception]
assert app.radio and app.radio[0].value == 'Balanced Annual Program'

app.radio[0].set_value('Address Urgent Needs').run()
assert not app.exception, [str(item.value) for item in app.exception]
assert os.environ['EXPECTED_BUDGET'] in [item.value for item in app.metric if item.label == 'Budget']
next(button for button in app.button if button.label == 'Open interactive network map').click().run()
assert not app.exception, [str(item.value) for item in app.exception]
assert app.selectbox and app.selectbox[0].label == 'Select a road to review'
next(button for button in app.button if button.label == 'Generate executive briefing').click().run()
assert not app.exception, [str(item.value) for item in app.exception]
assert any(os.environ['EXPECTED_LEADERSHIP'] in item.value for item in app.caption)
"""
        for slug, config in MUNICIPALITIES.items():
            with self.subTest(municipality=slug):
                environment = os.environ.copy()
                environment["PAVENTRA_MUNICIPALITY"] = slug
                environment["EXPECTED_TITLE"] = config.pilot_name
                environment["EXPECTED_FORMAL"] = config.formal_name
                environment["EXPECTED_LEADERSHIP"] = config.leadership_label
                environment["EXPECTED_STATUS"] = config.data_provenance.analysis_label
                environment["EXPECTED_BUDGET"] = "${:,.0f}".format(
                    get_scenario_catalog(config.scenario_catalog_id)[
                        "Address Urgent Needs"
                    ]["budget"]
                )
                completed = subprocess.run(
                    [sys.executable, "-c", script],
                    cwd=PROJECT_ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    msg=f"{completed.stdout}\n{completed.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
