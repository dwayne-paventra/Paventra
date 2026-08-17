# Developer Registration Handoff — Spring Arbor Township

> Registration is not automatic. This packet is an operator handoff, not code review.

- Package path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\spring_arbor`
- Manifest path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\spring_arbor\manifest.json`
- Municipality slug: `spring_arbor`
- Readiness: **Ready for Registration**
- Source checksum: `322abf310ff6b0d143928d225560bfb081451f872090ed31026d313ae47d0c1e`
- Canonical artifact: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\spring_arbor\canonical_review.csv`
- Validation summary: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\spring_arbor\validation_summary.json`
- Mapping review: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\spring_arbor\mapping_review.csv`

## Suggested registry snippet

```python
# Suggested developer-reviewed registration only; do not paste without review.
from pathlib import Path
from pilot.municipality_onboarding import load_onboarding_manifest

_reviewed_spring_arbor = load_onboarding_manifest(
    Path(r"C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\spring_arbor\manifest.json")
)
MUNICIPALITIES[_reviewed_spring_arbor.slug] = _reviewed_spring_arbor
```

## Developer verification checklist

- [ ] Inspect manifest
- [ ] Inspect mappings and defaults
- [ ] Confirm source checksum
- [ ] Add the reviewed registry entry
- [ ] Run registry and startup validation
- [ ] Run the complete test suite
- [ ] Run Streamlit AppTest
- [ ] Generate and inspect the municipality report
- [ ] Run the HTTP health check
- [ ] Inspect the Git diff
- [ ] Commit only after review

## Minimal developer instructions

1. Review every artifact above and choose a durable reviewed data location.
2. Adapt the suggested snippet to the permanent registry source; do not register from an unreviewed working path.
3. Run the checklist and inspect the diff before committing.
