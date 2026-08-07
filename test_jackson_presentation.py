import unittest

from components.jackson_report import build_jackson_report
from pilot.jackson_data import load_jackson_streamlit_inventory
from pilot.jackson_scenarios import build_jackson_scenario_results


class JacksonPresentationTests(unittest.TestCase):
    def setUp(self):
        self.roads = load_jackson_streamlit_inventory()
        self.results = build_jackson_scenario_results(
            self.roads,
            "Balanced Annual Program",
        )

    def test_scenario_returns_ranked_fundable_projects(self):
        self.assertGreater(len(self.results["roads"]), 0)
        self.assertTrue(self.results["roads"]["Estimated Cost"].gt(0).all())
        self.assertEqual(
            self.results["roads"]["Priority Rank"].tolist(),
            list(range(1, len(self.results["roads"]) + 1)),
        )
        self.assertLessEqual(self.results["spent"], self.results["scenario"]["budget"])

    def test_executive_report_is_a_pdf(self):
        report = build_jackson_report(self.roads, self.results)
        self.assertTrue(report.startswith(b"%PDF"))
        self.assertGreater(len(report), 1_000)

    def test_executive_report_does_not_require_a_selected_road(self):
        """The portfolio report remains available before the map selects a road."""

        report = build_jackson_report(self.roads, self.results)
        self.assertTrue(report.startswith(b"%PDF"))
