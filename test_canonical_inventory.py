import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from pilot.canonical_inventory import (
    CANONICAL_COLUMNS,
    load_canonical_inventory,
    load_streamlit_inventory,
    normalize_treatment,
    validate_canonical_schema,
)
from pilot.jackson_data import (
    JACKSON_CANONICAL_COLUMNS,
    load_jackson_canonical_data,
    load_jackson_streamlit_inventory,
    validate_jackson_schema,
)
from pilot.municipality_registry import (
    DEMO_CITY_MUNICIPALITY,
    JACKSON_MUNICIPALITY,
)


class CanonicalInventoryTests(unittest.TestCase):
    def test_schema_validation_is_municipality_neutral(self):
        for config in (JACKSON_MUNICIPALITY, DEMO_CITY_MUNICIPALITY):
            with self.subTest(municipality=config.slug):
                roads = pd.read_csv(config.data_path)
                validate_canonical_schema(roads)

    def test_invalid_inventory_has_generic_error(self):
        roads = pd.read_csv(DEMO_CITY_MUNICIPALITY.data_path).drop(
            columns=["road_name"]
        )

        with self.assertRaisesRegex(
            ValueError,
            "Canonical inventory is missing required columns: road_name",
        ):
            validate_canonical_schema(roads)

    def test_shared_pipeline_loads_both_municipalities(self):
        for config in (JACKSON_MUNICIPALITY, DEMO_CITY_MUNICIPALITY):
            with self.subTest(municipality=config.slug):
                roads = load_streamlit_inventory(config.data_path, config.name)
                self.assertGreater(len(roads), 0)
                self.assertTrue(roads["County"].eq(config.name).all())
                self.assertIn("Risk Score", roads.columns)
                self.assertIn("Estimated Cost", roads.columns)

    def test_jackson_compatibility_wrappers_match_shared_pipeline(self):
        self.assertEqual(JACKSON_CANONICAL_COLUMNS, CANONICAL_COLUMNS)

        raw = pd.read_csv(JACKSON_MUNICIPALITY.data_path)
        validate_jackson_schema(raw)
        assert_frame_equal(
            load_jackson_canonical_data(),
            load_canonical_inventory(JACKSON_MUNICIPALITY.data_path),
        )
        assert_frame_equal(
            load_jackson_streamlit_inventory(),
            load_streamlit_inventory(
                JACKSON_MUNICIPALITY.data_path,
                JACKSON_MUNICIPALITY.name,
            ),
        )

    def test_treatment_normalization_remains_shared(self):
        self.assertEqual(normalize_treatment("Mill & Overlay"), "Mill & Fill")
        self.assertEqual(normalize_treatment("none"), "Not Assigned")
