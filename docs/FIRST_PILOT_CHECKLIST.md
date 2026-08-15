# First real pilot intake and acceptance record

Copy this file for one engagement. Replace bracketed prompts; use `Unknown` or `Not applicable` rather than leaving a required item ambiguous. Do not record unnecessary sensitive personal information.

Authoritative procedure: [FIRST_PILOT_INTAKE.md](FIRST_PILOT_INTAKE.md). Command runbook: [MUNICIPALITY_ONBOARDING.md](MUNICIPALITY_ONBOARDING.md).

## Record control

- Engagement/reference: [value]
- Checklist owner/role: [value]
- Started: [YYYY-MM-DD]
- Last updated: [YYYY-MM-DD]
- Intended pilot use: [value]

## Agency identity and terminology

- Formal agency name, municipality supplied: [value]
- Preferred short name, municipality supplied: [value]
- Entity/government type: [agency/city/county/municipality/road commission/township/village]
- State/jurisdiction: [value]
- Requested leadership terminology: [value]
- Requested official-action terminology: [value]
- Paventra slug: [value]
- Paventra municipality ID: [value]
- Pilot mode/label: [value]

## Source custodian and dataset description

- Source owner/custodian agency, department, office, or role: [value]
- Delivery filename(s): [value]
- Date received by Paventra: [YYYY-MM-DD]
- Municipality extraction/production date, if supplied: [YYYY-MM-DD/Unknown]
- Source reference or delivery ID: [value]
- Municipality's dataset description: [value]
- Geographic and asset coverage: [value]
- Observation/condition date meaning: [value]
- Intended use: [value]
- Known omissions, limitations, estimates, or stale fields: [value]
- Municipality-provided field dictionary/reference: [value/Not provided]

## Status designation

- Requested/configured status: [illustrative/provisional/official]
- Reason for status: [value]
- If not provisional, deliberate reason: [value/Not applicable]
- Confirmed that `official` is only a software designation and not Paventra certification or proof of municipal authorization: [Yes/Not applicable]

## Raw-source preservation and checksum

- Preserved raw path/name: [source_roads.raw.csv]
- Working-copy path/name: [source_roads.csv]
- Raw source unchanged: [Yes/No]
- Working copy remains byte-identical to preserved delivery: [Yes/No]
- Manifest version: [3]
- Configured source path: [value]
- CLI-computed SHA-256: [64 hexadecimal characters]
- Manifest-declared SHA-256: [value]
- Second dry run reports declared checksum match `yes`: [Yes/No]
- Checksum limitation acknowledged: byte integrity only; no source authentication or approval: [Yes/No]
- Revised delivery/version notes, if any: [value/None]

## Source-field definitions and mapping review

Add one row for every mapped, unused, or unresolved source field.

| Source field | Municipality-supplied meaning/units | Canonical field or `Unused` | Paventra normalization | Question/assumption | Resolution |
| --- | --- | --- | --- | --- | --- |
| [header] | [meaning/units] | [canonical name] | [none/value] | [question/none] | [resolved/unresolved] |

### Canonical defaults proposed by Paventra

| Canonical field | Proposed value | Why it applies to every row | Municipality clarification needed | Resolution |
| --- | --- | --- | --- | --- |
| [field] | [value] | [basis] | [yes/no and question] | [resolved/unresolved] |

### Mapping review summary

- Mapped source-field count: [value]
- Canonical-default count: [value]
- Source fields not used: [value/None]
- Fields that could not be interpreted: [value/None]
- Treatment labels expected to normalize: [source value -> canonical value/None]
- Material questions still unresolved: [value/None]
- Semantic interpretation shared for municipal review: [date/reference]

## Manifest and dry-run record

- Manifest path: [value]
- Inventory adapter: [normally `mapped_csv`]
- Scenario catalog: [normally `standard`]
- Map center and zoom: [latitude, longitude, zoom]
- Dry-run command: `python -m pilot.municipality_onboarding --manifest [path] --dry-run`
- Dry-run date: [YYYY-MM-DD]
- Source rows reported: [value]
- Canonical rows reported: [value]
- Mappings reported: [value]
- Defaults reported: [value]
- Identity/status/provenance output reviewed: [Pass/Fail]
- Adapter/catalog output reviewed: [Pass/Fail]
- Validation result: [PASS/FAIL]
- Errors and resolution: [value/None]

## Temporary canonical review artifact

- Export command/path: [value]
- Artifact retained only temporarily or in controlled engagement records: [Yes/No]
- Expected row count matches: [Pass/Fail]
- Exactly 23 canonical columns in documented order: [Pass/Fail]
- Road IDs non-empty and unique: [Pass/Fail]
- Segment IDs non-empty and unique: [Pass/Fail]
- PCI/condition values semantically correct: [Pass/Fail]
- ADT/traffic values correct where supplied: [Pass/Fail/Not applicable]
- Treatment values and normalization correct: [Pass/Fail]
- Coordinates and jurisdiction coverage usable: [Pass/Fail]
- Data status consistent on every row: [Pass/Fail]
- Mapping/default results match the review record: [Pass/Fail]
- Review limitations/findings: [value/None]
- Temporary export removed after review: [Yes/No/Controlled retention]
- Preserved raw delivery remains unchanged: [Yes/No]

## Developer registration review

- Manifest reviewed and ready to load: [Yes/No]
- Manifest loaded with `load_onboarding_manifest`: [Yes/No]
- Configuration added to `MUNICIPALITIES` under matching slug: [Yes/No]
- Registry diff contains only expected explicit registration: [Pass/Fail]
- Registry/startup validation: [Pass/Fail]
- No municipality slug/name branch added to shared code: [Pass/Fail]
- No municipality-specific dashboard, analytics, optimizer, scenario, GIS, generic component, or report change: [Pass/Fail]
- Unexpected product/platform requirement and disposition: [value/None]

## Pre-launch application acceptance

- Manifest v3 validation: [Pass/Fail]
- Declared checksum match: [Pass/Fail]
- Canonical inventory validation: [Pass/Fail]
- Configured status displayed correctly: [Pass/Fail]
- Source owner/date/reference displayed correctly: [Pass/Fail]
- Formal identity and requested terminology: [Pass/Fail]
- Inventory loads with expected count: [Pass/Fail]
- Recommendations render: [Pass/Fail]
- Map renders and road selection works: [Pass/Fail]
- Scenario switching and expected catalog work: [Pass/Fail]
- Executive presentation works: [Pass/Fail]
- PDF generates: [Pass/Fail]
- PDF identity/status/provenance correct: [Pass/Fail]
- No Jackson/demo/Pine Ridge/unrelated or city-only terminology leakage: [Pass/Fail]
- Municipality AppTest full flow: [Pass/Fail]
- Existing registered-municipality AppTest regressions: [Pass/Fail]
- Complete unit-test suite: [count and result]
- Live Streamlit HTTP health: [Pass/Fail]
- Python compilation: [Pass/Fail]
- `git diff --check`: [Pass/Fail]
- Temporary processes, exports, dependencies, and rehearsal registration removed: [Yes/No]

## Launch decision

- Decision: [GO/CONDITIONAL GO/NO-GO]
- Intended use evaluated: [value]
- Rationale: [value]
- Unresolved material issues: [value/None]

For **CONDITIONAL GO**, list every bounded condition:

| Condition/limitation | Effect on intended use | Owner/role | Resolution or monitoring plan |
| --- | --- | --- | --- |
| [value] | [value] | [value] | [value] |

This decision records engineering and operational readiness only. It is not municipal certification, approval, or authentication.
