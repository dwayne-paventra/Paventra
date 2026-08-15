# Data provenance and analysis status

Paventra uses one status contract from municipality configuration through canonical inventory validation, the dashboard, onboarding exports, and PDF reports. Status describes how the inventory may be represented; it does not change risk, treatment, scenario, or optimizer calculations.

| Canonical status | Use | Application safeguard |
| --- | --- | --- |
| `illustrative` | Synthetic, fictional, or demonstration inputs | UI and reports identify the analysis as illustrative and not official. This is the compatibility-safe default. |
| `provisional` | Real or supplied inputs that have not been designated official | UI and reports visibly identify the analysis as provisional and subject to agency validation. |
| `official` | Inventory intentionally configured to be represented as official | Must be explicit in configuration or a version 2 manifest. Paventra does not infer this status or claim an approval, signature, or certification workflow. |

`Illustrative demonstration data` remains an accepted legacy row value and normalizes to `illustrative`. New canonical exports use the lowercase canonical values.

## Source of truth and contradiction handling

`MunicipalityConfig.data_status` is the intended status for the running application. Canonical `data_status` rows are retained as provenance evidence and every row must agree with configuration. Missing, invalid, mixed, or contradictory values stop loading or export before UI/report rendering.

For a version 2 onboarding manifest, top-level `data_status` supplies configuration intent. If source mapping or `canonical_defaults` also supplies `data_status`, it is checked rather than allowed to override configuration. When neither supplies a row status, the top-level value is injected into the canonical inventory.

Manifest version 1 remains supported for existing deployments and has fixed illustrative semantics. It cannot be used to declare provisional or official intent. New manifests use version 2.

## What official does not mean

Selecting `official` does not create or imply a data-approval workflow, agency signature, professional engineering determination, or Paventra certification. It is an explicit representation choice made in configuration. Scenario results remain planning estimates under every status.
