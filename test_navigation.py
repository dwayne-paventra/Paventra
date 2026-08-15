import shutil
from pathlib import Path
import tomllib
import unittest
from unittest.mock import MagicMock, patch

from helpers import sidebar
from pilot.municipality_admin import (
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    create_illustrative_demo_package,
    review_illustrative_demo,
)


class NavigationTests(unittest.TestCase):
    def test_navigation_inventory_has_only_real_destinations(self):
        self.assertEqual(
            sidebar.DASHBOARD_SECTIONS,
            ("Dashboard", "Network Map", "Pavement Analytics", "Reports"),
        )
        self.assertEqual(
            sidebar.OPERATOR_SECTIONS,
            ("Municipality Portfolio", "Municipality Onboarding"),
        )
        self.assertNotIn("Settings", sidebar.NAVIGATION_SECTIONS)
        self.assertNotIn("AI Predictions", sidebar.NAVIGATION_SECTIONS)

    def test_native_sidebar_navigation_is_disabled_by_supported_config(self):
        config_path = Path(__file__).resolve().parent / ".streamlit" / "config.toml"
        with config_path.open("rb") as config_file:
            config = tomllib.load(config_file)
        self.assertFalse(config["client"]["showSidebarNavigation"])

    def test_navigation_preserves_municipality_context(self):
        state = {
            "paventra_runtime_municipality_slug": "generated_demo",
            "paventra_selected_municipality_slug": "jackson",
        }
        fake_streamlit = MagicMock()
        fake_streamlit.session_state = state
        with patch.object(sidebar, "st", fake_streamlit):
            sidebar.navigate_to_section(
                "Pavement Analytics", current_section="Dashboard"
            )
            self.assertEqual(state["paventra_dashboard_section"], "Pavement Analytics")
            fake_streamlit.rerun.assert_called_once_with()

            sidebar.navigate_to_section(
                "Municipality Portfolio", current_section="Pavement Analytics"
            )
            self.assertEqual(state["paventra_operator_view"], "portfolio")
            fake_streamlit.switch_page.assert_called_once_with(
                "pages/1_Municipality_Onboarding.py"
            )

        self.assertEqual(state["paventra_runtime_municipality_slug"], "generated_demo")
        self.assertEqual(state["paventra_selected_municipality_slug"], "jackson")

    def test_active_destination_uses_primary_button_styling(self):
        fake_streamlit = MagicMock()
        fake_streamlit.button.return_value = False
        with patch.object(sidebar, "st", fake_streamlit):
            sidebar._render_navigation_group(
                "Analysis",
                sidebar.DASHBOARD_SECTIONS,
                active_section="Network Map",
            )

        button_calls = {
            call.args[0]: call.kwargs for call in fake_streamlit.button.call_args_list
        }
        self.assertEqual(button_calls["Network Map"]["type"], "primary")
        self.assertEqual(button_calls["Dashboard"]["type"], "secondary")

    def test_permanent_municipality_navigation_reaches_existing_flows(self):
        from streamlit.testing.v1 import AppTest

        for slug, expected_title in (
            ("jackson", "Jackson Municipal Pilot"),
            ("onboarding_demo", "Pine Ridge Township Pilot"),
        ):
            with self.subTest(slug=slug):
                app = AppTest.from_file("dashboard.py", default_timeout=30)
                app.session_state["paventra_selected_municipality_slug"] = slug
                app.run()
                self.assertFalse(app.exception)
                self.assertEqual([item.value for item in app.title], [expected_title])

                app.button(key="paventra_nav_pavement_analytics").click().run()
                self.assertFalse(app.exception)
                self.assertTrue(app.radio)
                self.assertEqual(
                    app.session_state["paventra_dashboard_section"],
                    "Pavement Analytics",
                )

                app.button(key="paventra_nav_network_map").click().run()
                self.assertFalse(app.exception)
                self.assertTrue(app.selectbox)

                app.button(key="paventra_nav_reports").click().run()
                self.assertFalse(app.exception)
                app.button(key="municipality_generate_report").click().run()
                self.assertFalse(app.exception)
                self.assertTrue(app.download_button)
                self.assertEqual(
                    app.session_state["paventra_selected_municipality_slug"], slug
                )

    def test_generated_context_survives_dashboard_operator_round_trip(self):
        from streamlit.testing.v1 import AppTest

        slug = "phase18_navigation_generated"
        target = GENERATED_MUNICIPALITIES_ROOT / slug
        if target.exists():
            shutil.rmtree(target)
        try:
            package = create_illustrative_demo_package(
                review_illustrative_demo(
                    MunicipalityIdentity(
                        formal_name="Phase 18 Navigation Township",
                        short_name="Phase 18",
                        entity_type="township",
                        state="Michigan",
                        slug=slug,
                        leadership_label="township leadership",
                        official_action_label="official township determination",
                        map_center=(42.25, -84.4),
                        map_zoom=12,
                        scenario_catalog_id="standard",
                        pilot_label="Municipal Pilot",
                    ),
                    road_count=5,
                )
            )
            self.assertEqual(package.config.slug, slug)

            app = AppTest.from_file("dashboard.py", default_timeout=30)
            app.session_state["paventra_runtime_municipality_slug"] = slug
            app.run()
            self.assertFalse(app.exception)
            expected_title = "Phase 18 Municipal Pilot"
            self.assertEqual([item.value for item in app.title], [expected_title])

            app.button(key="paventra_nav_municipality_portfolio").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(
                app.session_state["paventra_runtime_municipality_slug"], slug
            )
            self.assertIn("Municipality Portfolio", [item.value for item in app.header])
            app.button(key="paventra_nav_dashboard").click().run()
            self.assertFalse(app.exception)
            self.assertEqual([item.value for item in app.title], [expected_title])
            self.assertEqual(
                app.session_state["paventra_runtime_municipality_slug"], slug
            )

            operator = AppTest.from_file(
                "pages/1_Municipality_Onboarding.py", default_timeout=30
            )
            operator.session_state["paventra_runtime_municipality_slug"] = slug
            operator.session_state["paventra_operator_view"] = "onboarding"
            operator.run()
            self.assertFalse(operator.exception)
            self.assertIn(
                "Municipality Onboarding & Demo Builder",
                [item.value for item in operator.title],
            )
            self.assertEqual(
                operator.session_state["paventra_runtime_municipality_slug"], slug
            )
        finally:
            if target.exists():
                shutil.rmtree(target)


if __name__ == "__main__":
    unittest.main()
