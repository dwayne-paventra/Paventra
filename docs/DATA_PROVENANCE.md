# Data provenance and analysis status

Paventra uses one status contract from municipality configuration through canonical inventory validation, the dashboard, onboarding exports, and PDF reports. Status describes how the inventory may be represented; it does not change risk, treatment, scenario, or optimizer calculations.

| Canonical status | Use | Application safeguard |
| --- | --- | --- |
| `illustrative` | Synthetic, fictional, or demonstration inputs | UI and reports identify the analysis as illustrative and not official. This is the compatibility-safe default. |
| `provisional` | Real or supplied inputs that have not been designated official | UI and reports visibly identify the analysis as provisional and subject to agency validation. |
| `official` | Inventory intentionally configured to be represented as official | Must be explicit in configuration or a version 2/3 manifest. Paventra does not infer this status or claim an approval, signature, or certification workflow. |

`Illustrative demonstration data` remains an accepted legacy row value and normalizes to `illustrative`. New canonical exports use the lowercase canonical values.

## Source of truth and contradiction handling

`MunicipalityConfig.data_status` is the intended status for the running application. Canonical `data_status` rows are retained as provenance evidence and every row must agree with configuration. Missing, invalid, mixed, or contradictory values stop loading or export before UI/report rendering.

For a version 2 or 3 onboarding manifest, top-level `data_status` supplies configuration intent. If source mapping or `canonical_defaults` also supplies `data_status`, it is checked rather than allowed to override configuration. When neither supplies a row status, the top-level value is injected into the canonical inventory.

Manifest version 1 remains supported for existing deployments and has fixed illustrative semantics. It cannot be used to declare provisional or official intent. Version 2 retains explicit status compatibility but has no source-provenance contract. New manifests use version 3.

## Source provenance is separate

Data status answers how Paventra characterizes an analysis. Source provenance answers where the dataset came from and how the received file can be traced. Source metadata never infers, promotes, or changes `data_status`.

Manifest version 3 stores source metadata once at the dataset/configuration level:

- `source_owner`: the human-readable agency, organization, or person supplying or owning the dataset;
- `source_acquired_date`: the strict ISO `YYYY-MM-DD` date when Paventra received the source;
- `source_reference`: an original filename, delivery ID, URL label, or source-system reference; it need not be a live URL;
- `source_checksum`: an optional 64-character SHA-256 digest of the original source file.

Owner, acquisition date, and reference are required for provisional or official manifest-v3/configuration data. Illustrative configurations may omit them or identify an explicitly synthetic source; existing demos remain explicitly synthetic/illustrative.

Source provenance is not copied onto every canonical road row. The existing row-level `data_source` field remains part of the canonical compatibility contract, while the dataset-level object is used by onboarding, caching, UI, and reports. Canonical CSV exports therefore retain their existing deterministic 23-column schema.

## Checksum limitations

Onboarding computes the actual SHA-256 digest during dry runs and exports. When `source_checksum` is declared, the actual source file must match before mapping or export can complete. The tool reports the actual digest and whether a declaration matched, but never edits the manifest.

A checksum detects whether bytes differ from the declared source file. It is not proof of who supplied the file, municipal approval, authenticity, data quality, or professional certification.

## What official does not mean

Selecting `official` does not create or imply a data-approval workflow, agency signature, professional engineering determination, or Paventra certification. It is an explicit representation choice made in configuration. Scenario results remain planning estimates under every status.
