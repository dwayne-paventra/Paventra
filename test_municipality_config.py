from dataclasses import replace
import os
import unittest
from unittest.mock import patch

from pilot.jackson_config import (
    JACKSON_DEMO_DATA_PATH,
    JACKSON_MAP_CENTER,
    JACKSON_MAP_ZOOM,
    PILOT_DISCLAIMER,
    PILOT_MODE_ENV_VAR,
    PILOT_NAME,
    is_jackson_pilot_mode,
)
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_config import compose_municipality_presentation_title
from pilot.municipality_registry import (
    DEFAULT_MUNICIPALITY_SLUG,
    DEMO_CITY_MUNICIPALITY,
    DEMO_ROAD_COMMISSION_MUNICIPALITY,
    JACKSON_MUNICIPALITY,
    MUNICIPALITIES,
    MUNICIPALITY_ENV_VAR,
    ONBOARDING_DEMO_MUNICIPALITY,
    get_active_municipality_config,
)


class MunicipalityConfigTests(unittest.TestCase):
    def test_presentation_title_avoids_duplicate_identity(self):
        napoleon = replace(
            JACKSON_MUNICIPALITY,
            formal_name="Napoleon Township",
            short_name="Napoleon Township",
            pilot_label="Napoleon Township Demonstration",
        )
        self.assertEqual(napoleon.pilot_name, "Napoleon Township Demonstration")
        self.assertEqual(
            compose_municipality_presentation_title(
                "Napoleon Township", "Township Demonstration", "Napoleon Township"
            ),
            "Napoleon Township Demonstration",
        )

    def test_presentation_title_keeps_generic_labels_for_supported_entities(self):
        cases = {
            "township": "Cedar Township Municipal Pilot",
            "city": "Lakeview Municipal Pilot",
            "village": "Northfield Municipal Pilot",
            "road commission": "West County Municipal Pilot",
            "agency": "Regional Streets Municipal Pilot",
            "county": "Long County Transportation Infrastructure Authority Municipal Pilot",
        }
        for entity_type, expected in cases.items():
            with self.subTest(entity_type=entity_type):
                short_name = expected.removesuffix(" Municipal Pilot")
                config = replace(
                    JACKSON_MUNICIPALITY,
                    entity_type=entity_type,
                    formal_name=short_name,
                    short_name=short_name,
                    pilot_label="Municipal Pilot",
                )
                self.assertEqual(config.pilot_name, expected)

    def test_formal_name_inside_label_is_not_repeated(self):
        config = replace(
            JACKSON_MUNICIPALITY,
            formal_name="Charter Township of a Deliberately Long Municipal Name",
            short_name="Long Municipal Name",
            pilot_label=(
                "Charter Township of a Deliberately Long Municipal Name Demonstration"
            ),
        )
        self.assertEqual(config.pilot_name, config.pilot_label)

    def test_jackson_is_the_default_active_municipality(self):
        with patch.dict(os.environ, {}, clear=True):
            active = get_active_municipality_config()

        self.assertEqual(DEFAULT_MUNICIPALITY_SLUG, "jackson")
        self.assertIs(active, JACKSON_MUNICIPALITY)
        self.assertEqual(active.name, "Jackson")
        self.assertEqual(active.state, "Michigan")
        self.assertEqual(active.display_name, "City of Jackson")
        self.assertEqual(active.entity_type, "city")
        self.assertEqual(active.formal_name, "City of Jackson")
        self.assertEqual(active.short_name, "Jackson")
        self.assertEqual(active.name, active.short_name)
        self.assertEqual(active.display_name, active.formal_name)
        self.assertEqual(active.leadership_label, "municipal leadership")
        self.assertEqual(active.scenario_catalog_id, "standard")
        self.assertEqual(active.pilot_name, "Jackson Municipal Pilot")
        self.assertEqual(active.normalized_data_status, "illustrative")
        self.assertTrue(active.data_path.is_file())

        self.assertEqual(PILOT_NAME, active.pilot_name)
        self.assertEqual(PILOT_DISCLAIMER, active.pilot_disclaimer)
        self.assertEqual(JACKSON_DEMO_DATA_PATH, active.data_path)
        self.assertEqual(JACKSON_MAP_CENTER, active.map_center)
        self.assertEqual(JACKSON_MAP_ZOOM, active.map_zoom)

    def test_explicit_jackson_selection_resolves_to_existing_config(self):
        with patch.dict(os.environ, {MUNICIPALITY_ENV_VAR: " JACKSON "}, clear=True):
            active = get_active_municipality_config()

        self.assertIs(active, JACKSON_MUNICIPALITY)

    def test_demo_city_resolves_from_environment(self):
        with patch.dict(
            os.environ,
            {MUNICIPALITY_ENV_VAR: "demo_city"},
            clear=True,
        ):
            active = get_active_municipality_config()

        self.assertIs(active, DEMO_CITY_MUNICIPALITY)
        self.assertEqual(active.name, "Demo City")
        self.assertEqual(active.display_name, "City of Demo City")
        self.assertEqual(active.formal_name, "City of Demo City")
        self.assertEqual(active.scenario_catalog_id, "standard")
        self.assertTrue(active.data_path.is_file())

    def test_non_city_agency_resolves_with_its_own_terminology(self):
        with patch.dict(
            os.environ,
            {MUNICIPALITY_ENV_VAR: "demo_road_commission"},
            clear=True,
        ):
            active = get_active_municipality_config()

        self.assertIs(active, DEMO_ROAD_COMMISSION_MUNICIPALITY)
        self.assertEqual(active.entity_type, "road commission")
        self.assertEqual(active.formal_name, "Demo County Road Commission")
        self.assertEqual(active.short_name, "Demo County")
        self.assertEqual(active.pilot_name, "Demo County Road Commission Pilot")
        self.assertEqual(active.leadership_label, "road commission leadership")
        self.assertEqual(
            active.official_action_label,
            "official road commission determination",
        )
        self.assertEqual(active.scenario_catalog_id, "road_commission_demo")

    def test_onboarding_demo_resolves_from_environment(self):
        with patch.dict(
            os.environ,
            {MUNICIPALITY_ENV_VAR: "onboarding_demo"},
            clear=True,
        ):
            active = get_active_municipality_config()

        self.assertIs(active, ONBOARDING_DEMO_MUNICIPALITY)
        self.assertEqual(active.formal_name, "Pine Ridge Township")
        self.assertEqual(active.inventory_adapter, "mapped_csv")
        self.assertTrue(active.data_path.is_file())

    def test_jackson_pilot_mode_keeps_legacy_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(is_jackson_pilot_mode())

        with patch.dict(os.environ, {PILOT_MODE_ENV_VAR: "legacy"}, clear=True):
            self.assertFalse(is_jackson_pilot_mode())

    def test_all_registered_municipalities_load_valid_inventories(self):
        required_columns = {
            "Road ID", "Road Name", "Agency", "County", "PCI", "Risk Score",
            "Risk Level", "Estimated Cost", "Latitude", "Longitude",
        }

        for slug, config in MUNICIPALITIES.items():
            with self.subTest(municipality=slug):
                roads = load_municipality_inventory(config)
                self.assertGreater(len(roads), 0)
                self.assertTrue(required_columns.issubset(roads.columns))
                self.assertTrue(roads["Agency"].eq(config.short_name).all())
                self.assertTrue(roads["County"].eq(roads["Agency"]).all())
                self.assertTrue(roads["Road ID"].str.strip().ne("").all())
                self.assertTrue(roads["Risk Score"].between(0, 100).all())
                self.assertTrue(
                    roads["data_status"].eq(config.normalized_data_status).all()
                )

    def test_unknown_municipality_has_clear_error(self):
        with patch.dict(
            os.environ,
            {MUNICIPALITY_ENV_VAR: "missing"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "Unknown municipality 'missing'"):
                get_active_municipality_config()
