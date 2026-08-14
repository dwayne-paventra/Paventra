import os
import unittest
from pathlib import Path
from unittest.mock import patch

from pilot.jackson_config import (
    DEFAULT_MUNICIPALITY_SLUG,
    JACKSON_DEMO_DATA_PATH,
    JACKSON_MAP_CENTER,
    JACKSON_MAP_ZOOM,
    JACKSON_MUNICIPALITY,
    MUNICIPALITY_ENV_VAR,
    PILOT_DISCLAIMER,
    PILOT_MODE_ENV_VAR,
    PILOT_NAME,
    get_active_municipality_config,
    is_jackson_pilot_mode,
)
from pilot.municipality_config import MunicipalityConfig, resolve_municipality


class MunicipalityConfigTests(unittest.TestCase):
    def test_jackson_is_the_default_active_municipality(self):
        with patch.dict(os.environ, {}, clear=True):
            active = get_active_municipality_config()

        self.assertEqual(DEFAULT_MUNICIPALITY_SLUG, "jackson")
        self.assertIs(active, JACKSON_MUNICIPALITY)
        self.assertEqual(active.name, "Jackson")
        self.assertEqual(active.state, "Michigan")
        self.assertEqual(active.display_name, "City of Jackson")
        self.assertEqual(active.pilot_name, "Jackson Municipal Pilot")
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

    def test_jackson_pilot_mode_keeps_legacy_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(is_jackson_pilot_mode())

        with patch.dict(os.environ, {PILOT_MODE_ENV_VAR: "legacy"}, clear=True):
            self.assertFalse(is_jackson_pilot_mode())

    def test_generic_config_can_represent_another_municipality(self):
        example = MunicipalityConfig(
            municipality_id="example-mi",
            slug="example",
            name="Example",
            state="Michigan",
            display_name="City of Example",
            data_directory=Path("data/example"),
            data_path=Path("data/example/roads.csv"),
            map_center=(42.0, -84.0),
            map_zoom=11,
            pilot_mode="example_pilot",
        )

        resolved = resolve_municipality(
            {"jackson": JACKSON_MUNICIPALITY, "example": example},
            "example",
            "jackson",
        )

        self.assertIs(resolved, example)
        self.assertEqual(resolved.pilot_name, "Example Municipal Pilot")
        self.assertIn("City of Example", resolved.pilot_disclaimer)

    def test_unknown_municipality_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown municipality 'missing'"):
            resolve_municipality(
                {"jackson": JACKSON_MUNICIPALITY},
                "missing",
                "jackson",
            )
