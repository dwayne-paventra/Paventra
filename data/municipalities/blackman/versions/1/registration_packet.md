# Developer Registration Handoff — Blackman Charter Township

> Registration is not automatic. This packet is an operator handoff, not code review.

- Package path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\blackman`
- Manifest path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\blackman\manifest.json`
- Municipality slug: `blackman`
- Readiness: **Ready for Registration**
- Source checksum: `dcd728f03f87c437c35845a7bb42fae39d86b6ca59a8b8179096dbd04627833e`
- Canonical artifact: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\blackman\canonical_review.csv`
- Validation summary: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\blackman\validation_summary.json`
- Mapping review: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\blackman\mapping_review.csv`

## Suggested registry snippet

```python
# Suggested developer-reviewed registration only; do not paste without review.
from pathlib import Path
from pilot.municipality_onboarding import load_onboarding_manifest

_reviewed_blackman = load_onboarding_manifest(
    Path(r"C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\blackman\manifest.json")
)
MUNICIPALITIES[_reviewed_blackman.slug] = _reviewed_blackman
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
