from dataclasses import replace
import unittest

import pandas as pd

from pilot.canonical_inventory import CANONICAL_COLUMNS
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_onboarding import (
    load_onboarded_canonical_inventory,
    map_source_to_canonical,
    validate_onboarding_configuration,
)
from pilot.municipality_registry import (
    MUNICIPALITIES,
    ONBOARDING_DEMO_COLUMN_MAPPING,
    ONBOARDING_DEMO_MUNICIPALITY,
    validate_municipality_registry,
)


class MunicipalityOnboardingTests(unittest.TestCase):
    def setUp(self):
        self.config = ONBOARDING_DEMO_MUNICIPALITY
        self.source = pd.read_csv(self.config.data_path)

    def test_successful_source_mapping_produces_canonical_schema(self):
        canonical = map_source_to_canonical(
            self.config,
            self.source,
            ONBOARDING_DEMO_COLUMN_MAPPING,
        )

        self.assertEqual(tuple(canonical.columns), CANONICAL_COLUMNS)
        self.assertEqual(canonical["road_name"].iloc[0], "Pine Ridge Road")
        self.assertTrue(canonical["road_id"].is_unique)
        self.assertTrue(canonical["segment_id"].is_unique)
        self.assertTrue(canonical["latitude"].between(-90, 90).all())
        self.assertTrue(canonical["longitude"].between(-180, 180).all())

    def test_onboarded_canonical_inventory_uses_shared_enrichment(self):
        enriched = load_onboarded_canonical_inventory(self.config)

        self.assertTrue(set(CANONICAL_COLUMNS).issubset(enriched.columns))
        self.assertTrue({"risk_score", "risk_level", "risk_reason"}.issubset(enriched.columns))
        self.assertEqual(enriched["recommended_treatment"].iloc[0], "Mill & Fill")

    def test_missing_mapping_reports_missing_canonical_field(self):
        mapping = dict(ONBOARDING_DEMO_COLUMN_MAPPING)
        mapping.pop("Street_Name")

        with self.assertRaisesRegex(
            ValueError,
            "Municipality 'onboarding_demo'.*missing source mappings.*road_name",
        ):
            map_source_to_canonical(self.config, self.source, mapping)

    def test_mapping_to_missing_source_column_is_rejected(self):
        mapping = dict(ONBOARDING_DEMO_COLUMN_MAPPING)
        mapping.pop("Street_Name")
        mapping["Missing_Street_Name"] = "road_name"

        with self.assertRaisesRegex(
            ValueError,
            "missing mapped columns: 'Missing_Street_Name' -> 'road_name'",
        ):
            map_source_to_canonical(self.config, self.source, mapping)

    def test_invalid_numeric_source_value_is_rejected(self):
        invalid = self.source.copy()
        invalid["PCI_Score"] = invalid["PCI_Score"].astype(object)
        invalid.loc[0, "PCI_Score"] = "not-a-number"

        with self.assertRaisesRegex(
            ValueError,
            r"canonical numeric field 'pci'.*source CSV rows: \[2\]",
        ):
            map_source_to_canonical(self.config, invalid)

    def test_duplicate_road_identifier_is_rejected(self):
        invalid = self.source.copy()
        invalid.loc[1, "Asset_ID"] = invalid.loc[0, "Asset_ID"]

        with self.assertRaisesRegex(
            ValueError,
            "canonical field 'road_id' must be unique.*PRT-001",
        ):
            map_source_to_canonical(self.config, invalid)

    def test_unusable_coordinates_are_rejected(self):
        invalid = self.source.copy()
        invalid.loc[0, "Lat_Value"] = 120

        with self.assertRaisesRegex(
            ValueError,
            "canonical field 'latitude' must be between -90 and 90",
        ):
            map_source_to_canonical(self.config, invalid)

    def test_shared_canonical_validation_rejects_invalid_status(self):
        invalid = self.source.copy()
        invalid.loc[0, "Source_Status"] = "Unverified source"

        with self.assertRaisesRegex(
            ValueError,
            "canonical inventory validation failed: Canonical demonstration inventory",
        ):
            map_source_to_canonical(self.config, invalid)

    def test_invalid_config_adapter_and_catalog_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown adapter 'missing'"):
            validate_onboarding_configuration(
                replace(self.config, inventory_adapter="missing")
            )
        with self.assertRaisesRegex(ValueError, "unknown catalog 'missing'"):
            validate_onboarding_configuration(
                replace(self.config, scenario_catalog_id="missing")
            )
        with self.assertRaisesRegex(ValueError, "field 'formal_name'"):
            validate_onboarding_configuration(
                replace(self.config, formal_name="")
            )

    def test_registered_onboarding_inventory_uses_existing_ui_contract(self):
        validate_municipality_registry()
        roads = load_municipality_inventory(self.config)

        self.assertIs(MUNICIPALITIES["onboarding_demo"], self.config)
        self.assertGreater(len(roads), 0)
        self.assertTrue(roads["Agency"].eq("Pine Ridge").all())
        self.assertTrue(roads["County"].eq(roads["Agency"]).all())
        self.assertTrue({"Risk Score", "Estimated Cost", "Treatment"}.issubset(roads.columns))


if __name__ == "__main__":
    unittest.main()
