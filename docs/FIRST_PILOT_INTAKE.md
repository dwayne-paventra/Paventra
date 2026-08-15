# First real pilot: intake-to-launch procedure

This is the operational contract for accepting the first real municipality inventory into Paventra. Use the copyable [FIRST_PILOT_CHECKLIST.md](FIRST_PILOT_CHECKLIST.md) as the engagement record, then follow [MUNICIPALITY_ONBOARDING.md](MUNICIPALITY_ONBOARDING.md) for commands. The canonical fields are defined in [CANONICAL_INVENTORY.md](CANONICAL_INVENTORY.md), and status and source semantics are authoritative in [DATA_PROVENANCE.md](DATA_PROVENANCE.md).

This procedure records what a municipality supplied and what Paventra configured or transformed. It does not establish ownership, authorization, accuracy, completeness, certification, authenticity, or municipal approval.

## Intake contract

Do not begin mapping until the municipality has supplied enough information to interpret the delivery without guessing.

### Municipality-provided facts

| Required information | What to record |
| --- | --- |
| Agency identity | Formal agency name, preferred short name, entity/government type, and state or jurisdiction. |
| Requested terminology | Leadership term and the phrase the agency wants used for an official agency action or determination. |
| Source custodian | Agency, department, office, or role responsible for the delivery. A personal name, personal email, or other sensitive contact detail is not required. |
| Source dataset | Original delivered filename or filenames and the unchanged file bytes. |
| Source timing | Date Paventra received the file and, when known, the date the agency extracted or produced it. |
| Source reference | Delivery ID, source-system label, original filename, or other municipality-provided reference. |
| Dataset description | The municipality's description of coverage, observation date, units, identifiers, and intended purpose. |
| Intended status/use | Requested use and whether the inventory should be treated as `illustrative`, `provisional`, or `official`. |
| Field definitions | Meaning, units, and valid values for ambiguous source headers or codes. |
| Known limitations | Missing roads or fields, stale observations, estimated values, geographic exclusions, or other known constraints. |

If a value is unknown, record it as unresolved in the checklist. Do not convert an unknown fact into a Paventra assumption without flagging it for review.

### Paventra-derived or configured values

Paventra prepares the municipality slug and internal ID, source-to-canonical mappings, canonical defaults, treatment normalization through the existing shared pipeline, map center and zoom, inventory adapter, scenario catalog, source checksum, canonical review export, and reviewed registry integration. These are transformations and application configuration, not municipality-supplied facts.

The checklist must identify the basis for every default. Defaults apply to every row and are unsuitable for values that vary by road unless the municipality confirms the value is uniform.

## Initial status posture

`provisional` is the normal starting status for real municipality-supplied data. It keeps the source and analysis visibly subject to agency validation while preserving the existing three-state contract:

- `illustrative` is for synthetic, fictional, or demonstration inputs.
- `provisional` is for real or supplied inputs not designated official.
- `official` is an explicit software representation chosen deliberately in configuration.

`official` does not prove approval, certification, authorship, authentication, or authority. Paventra does not infer it from a filename, source owner, checksum, data quality, or municipal participation. A request to use `official` must be recorded as a deliberate configuration decision; it does not create an approval or signature workflow.

## Controlled source path

Use this sequence for every real delivery:

```text
municipal delivery
  -> preserved raw copy
  -> byte-identical working copy
  -> manifest and mappings
  -> dry run
  -> temporary canonical review CSV
  -> reviewed registry entry
  -> application acceptance
```

1. Save the delivered file as `source_roads.raw.csv`; never edit it.
2. Create `source_roads.csv` as the working copy and keep it byte-identical for the first-pilot workflow.
3. Point manifest v3 at `source_roads.csv`. Run the documented two-pass checksum dry run and record the CLI's actual SHA-256 in both the manifest and checklist.
4. Preserve the raw file, working file, manifest, intake record, and review notes according to the engagement's controlled storage practice.

The checksum proves only that the configured source bytes equal the declared digest. It does not authenticate the source. If source values need correction, stop and request a revised municipal delivery, preserve it as a new raw version, and repeat intake. Do not silently alter the configured working CSV. Mapping, canonical defaults, and shared normalization do not alter the preserved delivery.

## Mapping and default review checkpoint

Before registration, populate the checklist's mapping/default review table using the manifest and dry-run output. For each source field, record its municipality-supplied meaning and units, canonical destination, any normalization, and unresolved interpretation question. Separately list every canonical default and why it is believed to apply to all rows.

The review record must show:

- every source-to-canonical mapping;
- every canonical default;
- treatment-label normalization performed by the existing pipeline;
- source fields not used or not interpretable;
- assumptions and questions requiring municipal clarification.

Provide this compact semantic record and the canonical review summary to the municipality. The municipality does not need to review Python. This is a review checkpoint, not an electronic approval or certification workflow. Any unresolved issue that materially affects pilot use blocks registration.

## Canonical review artifact

Generate the temporary canonical CSV with the documented onboarding command. It is a transformation/review artifact, not a replacement for the municipal delivery and normally should not be committed.

Review and record:

- expected source and canonical row counts;
- exactly 23 canonical columns in documented order;
- non-empty, unique road and segment identifiers;
- PCI and condition values;
- ADT and traffic values where supplied;
- treatment values and expected normalization;
- usable coordinates and jurisdiction coverage;
- one consistent configured data status;
- correct mappings, defaults, source labels, and dates.

Delete the temporary export after review unless a controlled engagement record explicitly requires it. Never delete or replace the preserved raw delivery.

## Developer registration review

After operator and semantic review, the minimum expected developer change is:

1. Load the reviewed manifest in `pilot/municipality_registry.py` using `load_onboarding_manifest`.
2. Add that configuration to `MUNICIPALITIES` under its slug.
3. Inspect the registry diff and confirm it contains only the manifest-loading constant and registry entry.
4. Import/run registry startup validation and run the complete verification suite.

A normal onboarding must not change `dashboard.py`, shared analytics, risk or treatment logic, optimizer/scenario calculations, GIS behavior, generic components, or report behavior. If it appears to require any such change, stop onboarding and review the need as a platform/product change. Do not hide municipality behavior in slug/name branches, and do not add automatic registry discovery.

## Pre-launch acceptance

Complete the detailed checklist before launch. Acceptance covers manifest and checksum validation, canonical review, configured status and provenance, identity and terminology, inventory, recommendations, map, scenarios, executive presentation, PDF identity/status/provenance, Streamlit AppTest, full regressions, live HTTP health, Python compilation, and `git diff --check`.

Explicitly inspect visible UI and report output for accidental Jackson, demo, Pine Ridge, city-only, or other unrelated terminology. Compatibility module names are acceptable internals; customer-visible leakage is not.

## Decision states

- **GO** — Required onboarding checks pass and no unresolved interpretation issue materially affects the intended pilot.
- **CONDITIONAL GO** — The pilot can proceed with explicitly documented, bounded limitations that do not undermine its intended use. Record each condition, owner, effect, and planned resolution.
- **NO-GO** — Material mapping, provenance, validation, status, application, or regression issues remain unresolved.

This is an engineering and operational readiness decision, not municipal certification.
