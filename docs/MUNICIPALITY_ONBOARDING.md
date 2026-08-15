# Municipality onboarding runbook

This runbook is for the person preparing a new Paventra municipality inventory. It assumes PowerShell is open at the `Paventra-Jackson-Clean` repository root.

The onboarding tools validate and transform data. They do not register a municipality automatically, modify the dashboard, or change the source file.

## Before starting

Confirm Python and the project dependencies are available:

```powershell
python --version
python -m pip install -r requirements.txt
```

Choose a lowercase municipality slug containing letters, numbers, and underscores, such as `example_township`. Use the same slug consistently in directory names, the manifest, the registry, and `PAVENTRA_MUNICIPALITY`.

## 1. Preserve the received inventory

Create a dedicated directory and preserve an unchanged raw copy. Work from a second copy:

```powershell
New-Item -ItemType Directory -Path data\example_township
Copy-Item C:\Incoming\roads.csv data\example_township\source_roads.raw.csv
Copy-Item data\example_township\source_roads.raw.csv data\example_township\source_roads.csv
```

Never edit `source_roads.raw.csv`. If corrections are necessary, make them in `source_roads.csv` and record what changed outside Paventra according to the project’s data-governance practice.

## 2. Copy and edit the manifest

```powershell
Copy-Item docs\manifest.template.json data\example_township\manifest.json
```

Open the new manifest and replace every example identity and label. Keep `manifest_version` set to `3`. Version is required; missing or unsupported versions fail before any deeper processing. Version 1 remains illustrative-only compatibility; version 2 retains data-status compatibility without asserting source metadata.

Set top-level `data_status` deliberately:

- `illustrative` for synthetic or demonstration data;
- `provisional` for real or supplied data that has not been designated official;
- `official` only when the manifest author explicitly intends the inventory to be represented as official.

Paventra does not infer official status from filenames, source labels, or data quality. Do not use `official` to imply an approval, signature, or certification workflow that occurred elsewhere. See [DATA_PROVENANCE.md](DATA_PROVENANCE.md) for the full status contract.

Record dataset-level traceability separately:

```json
"source_owner": "Example Township",
"source_acquired_date": "2026-08-15",
"source_reference": "roads_2026.csv email delivery"
```

For provisional or official data, owner, acquisition date, and reference are required. Illustrative data may omit this metadata or identify an explicitly synthetic source. Use a real acquisition date in strict `YYYY-MM-DD` format. The reference may be a filename, delivery ID, source-system label, or descriptive URL label; it does not need to resolve on the internet. `source_checksum` is optional. If supplied, it must be the 64-character SHA-256 digest of the unchanged source CSV.

To declare a checksum without using a separate hashing tool, use a two-pass dry run: first omit `source_checksum`, run the dry run, copy its `Actual SHA-256` value into the manifest, and run the dry run again. The second run must report `Declared checksum match: yes`. Do not change the source between the two runs.

For the current mapped CSV workflow, keep:

```json
"inventory_adapter": "mapped_csv",
"scenario_catalog_id": "standard"
```

Use an entity type supported by the application: `agency`, `city`, `county`, `municipality`, `road commission`, `township`, or `village`. Set `map_center` to `[latitude, longitude]` and choose a zoom from 0 through 22; 11 or 12 is a useful local starting point.

## 3. Map source columns

Inspect the header row of `source_roads.csv`. In `column_mapping`, put the source header on the left and its canonical Paventra name on the right:

```json
"Street_Name": "road_name",
"PCI_Score": "pci",
"Length_Miles": "road_length_miles"
```

Spelling and capitalization on the left must exactly match the CSV header. Each source column can map once, and each canonical field can have only one source.

Use `canonical_defaults` for a value that truly applies to every row:

```json
"jurisdiction": "Example Township",
"surface_type": "Asphalt"
```

A canonical field cannot be both a mapping target and a default. Neither wins; the overlap is an error. `data_status` normally belongs only at the manifest top level; if a legacy/source row status is also mapped, it must agree on every row. Review all required fields and their current behavior in [CANONICAL_INVENTORY.md](CANONICAL_INVENTORY.md).

## 4. Run a dry run

```powershell
python -m pilot.municipality_onboarding --manifest data\example_township\manifest.json --dry-run
```

Success prints the municipality, manifest version, resolved data status, concise source metadata, actual SHA-256, checksum comparison, row counts, adapter/catalog, and `Validation result: PASS`. It writes no files and returns exit code 0:

```powershell
$LASTEXITCODE
```

Validation failures return exit code 1. Command-usage errors return 2.

## 5. Resolve common failures

| Message topic | What to check |
| --- | --- |
| Missing or unsupported `manifest_version` | New manifests use numeric version `3`. Do not guess or reuse an unsupported version. |
| Missing manifest field | Compare the manifest with `docs\manifest.template.json`. |
| Unknown manifest field | Correct the spelling or remove the field; each manifest version rejects undeclared fields. |
| Invalid or contradictory `data_status` | Use `illustrative`, `provisional`, or `official`; ensure any mapped row status agrees with top-level intent. |
| Invalid source metadata | Provide a non-empty owner/reference and a real acquisition date formatted `YYYY-MM-DD`. |
| Invalid checksum format | Supply exactly 64 hexadecimal characters or omit `source_checksum`. |
| Checksum mismatch | Confirm the manifest digest belongs to the exact source CSV bytes. Do not auto-update the declaration merely to silence the error. |
| Unknown adapter or catalog | Use an ID already registered in Paventra. Normal mapped onboarding uses `mapped_csv` and `standard`. |
| Missing mapped source column | Match the left side of `column_mapping` exactly to the CSV header. |
| Missing canonical field | Add a source mapping or a canonical default for the named field. |
| Invalid numeric value | Inspect the reported source CSV rows for blanks, units, commas, or text in numeric columns. |
| Duplicate identifier | Correct repeated `road_id` or `segment_id` values in the working source copy. Do not invent duplicates to fill blanks. |
| Invalid coordinates | Latitude must be -90 through 90; longitude must be -180 through 180. Check for swapped fields. |
| Invalid PCI | PCI must be numeric and from 0 through 100. |
| Mapping/default overlap | Remove either the source mapping or the default for that canonical field. |

The current command reports errors, not warnings. Correct the working source or manifest and repeat the dry run until it passes.

## 6. Optionally export and review canonical data

```powershell
python -m pilot.municipality_onboarding --manifest data\example_township\manifest.json --output data\example_township\canonical_review.csv
```

The output is written only after validation and checksum comparison and uses deterministic canonical column order. Review identifiers, road names, coordinates, PCI, treatment, cost, and source labels. Existing files are protected. Replace one only after deliberate review:

```powershell
python -m pilot.municipality_onboarding --manifest data\example_township\manifest.json --output data\example_township\canonical_review.csv --force
```

The dashboard continues to load the mapped source through the same canonical pipeline; the review export is not a second analytics path. Dataset-level provenance stays in configuration and is not duplicated into the 23 canonical road columns.

SHA-256 is an integrity comparison, not proof of municipal approval, authorship, authenticity, or data quality. The operator is responsible for preserving the received source, recording accurate metadata, and confirming any declared digest before registry review.

## 7. Request the manual registry change

Onboarding intentionally does not auto-edit Python. A reviewer must add the manifest-backed configuration to `pilot/municipality_registry.py`, following Pine Ridge’s pattern:

```python
EXAMPLE_TOWNSHIP_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "example_township" / "manifest.json"
)
EXAMPLE_TOWNSHIP_MUNICIPALITY = load_onboarding_manifest(
    EXAMPLE_TOWNSHIP_MANIFEST_PATH
)
```

Then add the config to `MUNICIPALITIES` using its slug. Registry startup validation will reject duplicate IDs/slugs, unknown adapters, and unknown scenario catalogs.

## 8. Launch the municipality

```powershell
$env:PAVENTRA_MUNICIPALITY = "example_township"
python -m streamlit run dashboard.py
```

Open the displayed local URL and verify the identity, executive overview, investment briefing, scenario selection, network map, and report. When finished:

```powershell
Remove-Item Env:PAVENTRA_MUNICIPALITY
```

## 9. Completion checks

Run these from the repository root:

```powershell
python -m unittest discover -v
python -m compileall -q .
git diff --check
python -m unittest test_municipality_presentation.MunicipalityPresentationTests.test_streamlit_full_flow_for_all_registered_agencies -v
```

With Streamlit running, check its local health endpoint:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501/_stcore/health
```

Onboarding is complete only when the dry run passes, canonical review is acceptable, the registry change is reviewed, the selected municipality launches, its full flow works, and the repository verification suite passes.
