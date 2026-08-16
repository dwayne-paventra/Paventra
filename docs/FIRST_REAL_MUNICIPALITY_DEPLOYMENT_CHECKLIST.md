# First real municipality deployment checklist

Use this concise checklist with the Municipality Onboarding and Municipality Portfolio screens. It records operational readiness, not municipal certification, engineering approval, or source authentication.

## 1. Identity and intended use

- [ ] Confirm formal name, short name, entity type, state, terminology, slug, and pilot label with the municipal contact.
- [ ] Record the intended audience and use of the deployment.
- [ ] Set data status explicitly (`provisional`, `official`, or `illustrative`); never infer `official`.
- [ ] Confirm map center, zoom, and scenario catalog.

## 2. Source and provenance

- [ ] Record source owner/custodian, acquisition date, and a traceable source reference.
- [ ] Preserve the delivered inventory and GIS files in the onboarding workspace.
- [ ] Confirm inventory checksum and every GIS bundle component checksum.
- [ ] Record known omissions, stale fields, assumptions, and municipality-supplied field definitions.

## 3. Inventory mapping and defaults

- [ ] Review every suggested source-to-canonical mapping; resolve ambiguous and required unmapped fields.
- [ ] Add a plain-language source meaning where the header alone is unclear.
- [ ] Review every default and confirm it legitimately applies to every row.
- [ ] Do not default identifiers, PCI, coordinates, or other critical fields merely to pass validation.
- [ ] Resolve duplicate identifiers and invalid numeric values in the delivered working data.

## 4. GIS review

- [ ] Upload one complete GeoJSON or shapefile bundle and confirm its CRS and provenance.
- [ ] Select the stable source identifier and exact canonical target (`segment_id` preferred).
- [ ] Require 100% exact ID coverage, unique IDs, valid line geometry, and zero unmatched features/segments.
- [ ] Review geometry bounds and visually confirm the network shape, placement, risk/treatment styling, and popups.
- [ ] Confirm validated line geometry is used instead of marker fallback.

## 5. Validation and review

- [ ] Run **Validate saved package** and resolve every blocking issue.
- [ ] Review the canonical artifact, mapping/default table, warnings, provenance, scenario, and map configuration.
- [ ] Reopen the package from Portfolio after a simulated restart.
- [ ] Move through **Begin operator review** and **Ready for Registration** only after review is complete.
- [ ] Download and retain the registration packet with the engagement record.

## 6. Registration

- [ ] In Portfolio, run **Registration Preview** and inspect identity, checksums, row count, destination, and readiness.
- [ ] Type the exact slug, check the explicit confirmation, and select **Register Municipality**.
- [ ] Confirm atomic verification succeeds and Portfolio shows **Permanent / Registered**.
- [ ] Confirm the source onboarding workspace remains separate from permanent version 1.
- [ ] Leave operational acceptance pending until the post-registration checks below pass.

## 7. Municipality-facing acceptance

- [ ] Dashboard shows the correct identity, status, source provenance, and network metrics.
- [ ] Network Map shows supplied road lines at correct bounds with useful popups and no unrelated identity leakage.
- [ ] Pavement Analytics scenarios and recommendations load without changing approved mathematics.
- [ ] Reports generate a valid PDF with correct identity, status, provenance, geometry summary, and data version.
- [ ] Stop and restart Streamlit; confirm the municipality remains discoverable and selectable without an environment variable.
- [ ] Run a live HTTP health check for the selected municipality.

## 8. Update and recovery rehearsal

- [ ] Create a candidate update with new provenance and preserved source/GIS files.
- [ ] Review v1-to-v2 row, PCI, treatment, identifier, coordinate, and geometry differences.
- [ ] Validate, review, preview, and explicitly activate v2.
- [ ] Restart and confirm v2 inventory, map, metrics, and report version persist.
- [ ] Confirm v1 files and checksums remain unchanged and available in version history.
- [ ] Roll back to v1, restart and verify, then reactivate v2 if that is the launch decision.

## 9. Launch decision

- [ ] Run the complete test suite, Python compilation, and `git diff --check`.
- [ ] Run onboarding, Portfolio, registration, versioning, dashboard, map, analytics, and report AppTests.
- [ ] Recheck existing permanent municipalities and the Napoleon illustrative-demo workflow.
- [ ] Remove rehearsal-only packages, processes, dependencies, caches, logs, and reports.
- [ ] Record separate decisions for demo, CSV, GIS, registration, and versioning readiness.

Decision: **GO / CONDITIONAL GO / NO-GO**

Conditions, owner, and resolution date (required for Conditional GO):

| Condition | Operational effect | Owner/role | Resolution or monitoring plan |
| --- | --- | --- | --- |
|  |  |  |  |

