# Developer Registration Handoff — Summit Township

> Registration is not automatic. This packet is an operator handoff, not code review.

- Package path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\summit`
- Manifest path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\summit\manifest.json`
- Municipality slug: `summit`
- Readiness: **Ready for Registration**
- Source checksum: `d22e72a530d0e73c4abac9ee6569e621bfe75032f4a4dd6f2e181279936ae39d`
- Canonical artifact: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\summit\canonical_review.csv`
- Validation summary: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\summit\validation_summary.json`
- Mapping review: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\summit\mapping_review.csv`

## Suggested registry snippet

```python
# Suggested developer-reviewed registration only; do not paste without review.
from pathlib import Path
from pilot.municipality_onboarding import load_onboarding_manifest

_reviewed_summit = load_onboarding_manifest(
    Path(r"C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\summit\manifest.json")
)
MUNICIPALITIES[_reviewed_summit.slug] = _reviewed_summit
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
