# Developer Registration Handoff — Grass Lake Charter Township

> Registration is not automatic. This packet is an operator handoff, not code review.

- Package path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\grass_lake`
- Manifest path: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\grass_lake\manifest.json`
- Municipality slug: `grass_lake`
- Readiness: **Ready for Registration**
- Source checksum: `3b5586c8d567632d75feda63f60f1cdfa454f8b3ddba8cc8ba17275ade7b6e89`
- Canonical artifact: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\grass_lake\canonical_review.csv`
- Validation summary: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\grass_lake\validation_summary.json`
- Mapping review: `C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\grass_lake\mapping_review.csv`

## Suggested registry snippet

```python
# Suggested developer-reviewed registration only; do not paste without review.
from pathlib import Path
from pilot.municipality_onboarding import load_onboarding_manifest

_reviewed_grass_lake = load_onboarding_manifest(
    Path(r"C:\Users\djlew\OneDrive\Desktop\Paventra Project\Paventra-Municipal-Platform\Paventra-Jackson-Clean\generated\municipalities\grass_lake\manifest.json")
)
MUNICIPALITIES[_reviewed_grass_lake.slug] = _reviewed_grass_lake
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
