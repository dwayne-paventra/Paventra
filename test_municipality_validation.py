from dataclasses import replace
from pathlib import Path
import unittest

from pilot.municipality_config import validate_municipality_config
from pilot.municipality_registry import (
    JACKSON_MUNICIPALITY,
    MUNICIPALITIES,
    validate_municipality_registry,
)
from pilot.municipality_scenarios import (
    SCENARIO_CATALOGS,
    validate_scenario_catalogs,
)


KNOWN_ADAPTERS = {
    "canonical_demo": lambda config: config,
    "mapped_csv": lambda config: config,
}


class MunicipalityValidationTests(unittest.TestCase):
    def test_committed_registry_is_valid(self):
        validate_municipality_registry(
            MUNICIPALITIES,
            inventory_adapters=KNOWN_ADAPTERS,
            scenario_catalogs=SCENARIO_CATALOGS,
            default_slug="jackson",
        )

    def test_required_identity_and_terminology_fields_are_validated(self):
        for field_name in (
            "municipality_id",
            "slug",
            "formal_name",
            "short_name",
            "entity_type",
            "pilot_label",
            "leadership_label",
            "official_action_label",
        ):
            with self.subTest(field=field_name):
                invalid = replace(JACKSON_MUNICIPALITY, **{field_name: " "})
                with self.assertRaisesRegex(ValueError, f"field '{field_name}'"):
                    validate_municipality_config(invalid)

    def test_invalid_entity_type_is_rejected(self):
        invalid = replace(JACKSON_MUNICIPALITY, entity_type="corporation")
        with self.assertRaisesRegex(ValueError, "field 'entity_type'.*unsupported"):
            validate_municipality_config(invalid)

    def test_invalid_map_coordinates_are_rejected(self):
        invalid_latitude = replace(JACKSON_MUNICIPALITY, map_center=(91.0, -84.4))
        with self.assertRaisesRegex(ValueError, "field 'map_center.latitude'"):
            validate_municipality_config(invalid_latitude)

        invalid_longitude = replace(JACKSON_MUNICIPALITY, map_center=(42.2, -181.0))
        with self.assertRaisesRegex(ValueError, "field 'map_center.longitude'"):
            validate_municipality_config(invalid_longitude)

    def test_invalid_map_zoom_and_data_path_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "field 'map_zoom'"):
            validate_municipality_config(
                replace(JACKSON_MUNICIPALITY, map_zoom=23)
            )
        with self.assertRaisesRegex(ValueError, "field 'data_path'"):
            validate_municipality_config(
                replace(JACKSON_MUNICIPALITY, data_path=Path())
            )

    def test_unknown_inventory_adapter_fails_registry_validation(self):
        invalid = replace(JACKSON_MUNICIPALITY, inventory_adapter="missing")
        with self.assertRaisesRegex(
            ValueError,
            "Municipality 'jackson' field 'inventory_adapter'.*unknown adapter 'missing'",
        ):
            validate_municipality_registry(
                {invalid.slug: invalid},
                inventory_adapters=KNOWN_ADAPTERS,
                scenario_catalogs=SCENARIO_CATALOGS,
            )

    def test_unknown_scenario_catalog_fails_registry_validation(self):
        invalid = replace(JACKSON_MUNICIPALITY, scenario_catalog_id="missing")
        with self.assertRaisesRegex(
            ValueError,
            "Municipality 'jackson' field 'scenario_catalog_id'.*unknown catalog 'missing'",
        ):
            validate_municipality_registry(
                {invalid.slug: invalid},
                inventory_adapters=KNOWN_ADAPTERS,
                scenario_catalogs=SCENARIO_CATALOGS,
            )

    def test_duplicate_municipality_slug_is_rejected(self):
        duplicate = replace(
            JACKSON_MUNICIPALITY,
            municipality_id="duplicate-id",
        )
        with self.assertRaisesRegex(ValueError, "Duplicate municipality slug 'jackson'"):
            validate_municipality_registry(
                {"first": JACKSON_MUNICIPALITY, "second": duplicate},
                inventory_adapters=KNOWN_ADAPTERS,
                scenario_catalogs=SCENARIO_CATALOGS,
            )

    def test_duplicate_municipality_id_is_rejected(self):
        duplicate = replace(
            JACKSON_MUNICIPALITY,
            slug="duplicate",
            formal_name="Duplicate Municipality",
            short_name="Duplicate",
        )
        with self.assertRaisesRegex(ValueError, "Duplicate municipality ID 'jackson-mi'"):
            validate_municipality_registry(
                {"jackson": JACKSON_MUNICIPALITY, "duplicate": duplicate},
                inventory_adapters=KNOWN_ADAPTERS,
                scenario_catalogs=SCENARIO_CATALOGS,
            )

    def test_malformed_scenario_catalog_is_rejected(self):
        malformed_catalogs = {
            "bad": {
                "Broken Scenario": {
                    "budget": -1,
                    "goal": "Reduce Highest Risk",
                    "strategy": "Highest Risk",
                    "description": "Invalid negative budget.",
                }
            }
        }
        with self.assertRaisesRegex(ValueError, "field 'budget'.*positive"):
            validate_scenario_catalogs(malformed_catalogs)

        missing_field_catalogs = {
            "bad": {
                "Broken Scenario": {
                    "budget": 1_000_000,
                    "goal": "Reduce Highest Risk",
                    "strategy": "Highest Risk",
                }
            }
        }
        with self.assertRaisesRegex(ValueError, "missing required fields: description"):
            validate_scenario_catalogs(missing_field_catalogs)

        invalid_parameter_catalogs = {
            "bad": {
                "Broken Scenario": {
                    "budget": 1_000_000,
                    "goal": "",
                    "strategy": "Highest Risk",
                    "description": "Invalid empty goal.",
                }
            }
        }
        with self.assertRaisesRegex(ValueError, "field 'goal'.*non-empty string"):
            validate_scenario_catalogs(invalid_parameter_catalogs)


if __name__ == "__main__":
    unittest.main()
