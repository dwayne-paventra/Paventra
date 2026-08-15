# Canonical road inventory contract

This document describes the contract implemented by `pilot/canonical_inventory.py` and the additional source checks performed by `pilot/municipality_onboarding.py`. It is a reference for preparing a manifest, not a separate schema.

Every field below is a required canonical column. Most fields may be supplied by one source column in `column_mapping` or by one value in `canonical_defaults`. Supplying both for the same canonical field is an error. In manifest version 2 or 3, top-level `data_status` is the authoritative onboarding intent and is injected when no row status is supplied.

| Canonical name | Expected type | Meaning | Example | Mapping or default |
| --- | --- | --- | --- | --- |
| `road_id` | Text | Municipality road or asset identifier | `RD-001` | Either; mapping is strongly recommended because onboarding requires non-empty, unique values. |
| `segment_id` | Text | Unique roadway segment identifier | `SEG-001` | Either; mapping is strongly recommended because onboarding requires non-empty, unique values. |
| `road_name` | Text | Public road or street name | `Main Street` | Either |
| `from_street` | Text | Beginning cross street or limit | `First Avenue` | Either |
| `to_street` | Text | Ending cross street or limit | `Oak Road` | Either |
| `jurisdiction` | Text | Agency responsible for the segment | `Example Township` | Either; often a default when every row has the same owner. |
| `latitude` | Number | Segment map latitude | `42.2459` | Either; must be between -90 and 90. |
| `longitude` | Number | Segment map longitude | `-84.4013` | Either; must be between -180 and 180. |
| `road_length_miles` | Number | Segment length in miles | `0.75` | Either |
| `lanes` | Number | Number of travel lanes used for lane-mile calculations | `2` | Either |
| `surface_type` | Text | Pavement or surface material | `Asphalt` | Either; often a default for a uniform inventory. |
| `functional_class` | Text | Roadway functional classification | `Collector` | Either |
| `pci` | Number | Pavement Condition Index | `67` | Either; must be between 0 and 100. |
| `condition_date` | Text | Date associated with the condition observation | `2026-07-01` | Either; currently retained as text, not parsed as a date. |
| `traffic_level` | Text | Qualitative traffic exposure | `Medium` | Either; `High` and `Medium` affect current risk scoring, while other values receive no traffic contribution. |
| `adt` | Number | Average daily traffic | `7200` | Either; retained for analysis but not scored by the current Phase 1 risk rules. |
| `age_years` | Number | Approximate asset or pavement age in years | `12` | Either |
| `freeze_thaw` | Text | Qualitative freeze-thaw exposure | `High` | Either; `High` and `Medium` affect current risk scoring. |
| `recommended_treatment` | Text | Proposed pavement treatment | `Mill and Overlay` | Either; normalized after validation as described below. |
| `treatment_cost_per_lane_mile` | Number | Planning cost per lane mile for the treatment | `400000` | Either |
| `data_status` | Text | Inventory provenance state | `provisional` | Manifest v2/v3 uses top-level `data_status`. A mapped/default row value is accepted only when every row agrees with configuration. |
| `data_source` | Text | Human-readable source description | `2026 pavement survey` | Either |
| `data_updated_at` | Text | Source freshness or update date | `2026-08-14` | Either; currently retained as text, not parsed as a date. |

## Current validation behavior

- All 23 columns must exist after mappings and defaults are applied.
- `road_id` and `segment_id` must be present and unique during mapped onboarding.
- Numeric fields are converted with pandas numeric coercion. Blank or non-numeric values become invalid and produce an error containing the source CSV row numbers.
- Latitude and longitude use the ranges shown above. PCI must be from 0 through 100.
- `data_status` accepts the canonical values `illustrative`, `provisional`, and `official`. The legacy value `Illustrative demonstration data` remains an alias for `illustrative`.
- All rows must resolve to one status. When municipality configuration declares an expected status, the inventory must agree. Loaded and exported canonical data uses the lowercase canonical identifier.
- Missing, unsupported, mixed, or configuration-contradicting status values fail validation; status is never inferred from source names or content.
- Other text fields are retained as supplied unless treatment normalization applies.
- There are no warning-only validation results. A dry run either passes or returns an error and a nonzero exit code.

## Treatment normalization

After canonical validation, treatment labels are normalized by the shared enrichment pipeline. An empty string, `none`, and `no treatment` become `Not Assigned`. `mill & overlay`, `mill and overlay`, `mill & fill`, and `mill and fill` become `Mill & Fill`. Crack seal, overlay, and reconstruction are standardized for capitalization. Other labels are retained after surrounding whitespace is removed.

## Mapping and default precedence

There is no precedence rule for ordinary canonical fields. If a canonical field appears as a mapping target and in `canonical_defaults`, onboarding fails. Remove one of the two definitions. Defaults apply the same value to every source row, so they are appropriate for agency-wide constants but usually inappropriate for unique identifiers.

`data_status` has an additional safeguard. Manifest v2/v3 requires explicit top-level intent. If the source mapping or defaults also supply row status, every row must resolve to that same configured value. A contradiction fails before export. Manifest v1 remains supported as an illustrative-only compatibility contract.

Dataset-level source owner, acquisition date, source reference, and optional checksum are deliberately not canonical road columns. They belong to `MunicipalityConfig.source_provenance`, so they are validated and reported once without duplicating identical metadata across every segment. Canonical exports remain deterministic and unchanged. See [DATA_PROVENANCE.md](DATA_PROVENANCE.md).

See [MUNICIPALITY_ONBOARDING.md](MUNICIPALITY_ONBOARDING.md) for the operator workflow.
