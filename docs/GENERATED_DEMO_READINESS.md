# Generated Demo Readiness

Before a live meeting, open the generated municipality from **Municipality Portfolio** and confirm:

- Municipality name, entity type, leadership wording, and official-action wording are correct.
- The dashboard clearly identifies the inventory as illustrative synthetic data.
- The configured map center is acceptable and generated road markers are visible.
- Every scenario option works and recommendations load.
- The executive PDF generates with the correct title and filename.
- No unrelated municipality name or compatibility terminology is visible.
- The Portfolio can find and reopen the demo after Streamlit restarts.

The generated package is stored on disk and survives Streamlit restarts. The currently selected dashboard is session state only; after a restart, return to **Municipality Portfolio** and open the saved package again. No environment-variable or file editing is required.

## Operator inputs that still require local knowledge

Paventra does not perform online address lookup or geocoding. The operator must obtain and verify decimal latitude, decimal longitude, and a reasonable map zoom from an approved local source. Leadership and official-action terminology must also be confirmed with the agency; Paventra cannot infer legal terminology safely.
