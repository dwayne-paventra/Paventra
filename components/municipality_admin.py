"""Streamlit municipality onboarding and generated-demo management UI."""

from __future__ import annotations

import csv
from datetime import date
import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from pilot.canonical_inventory import CANONICAL_COLUMNS
from pilot.municipality_admin import (
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    assert_slug_available,
    create_illustrative_demo_package,
    list_generated_municipalities,
    review_illustrative_demo,
    save_real_import_draft,
    suggest_column_mappings,
    suggest_municipality_slug,
)
from pilot.municipality_config import SUPPORTED_ENTITY_TYPES
from pilot.municipality_registry import MUNICIPALITIES
from pilot.municipality_scenarios import SCENARIO_CATALOGS
from pilot.municipality_package_lifecycle import (
    PackageLifecycleState,
    begin_real_import_review,
    build_mapping_review,
    inspect_real_import_package,
    mark_real_import_ready,
    read_package_history,
    record_package_reopened,
    registration_packet_path,
    suggested_registry_snippet,
    validate_real_import_package,
)
from components.municipality_portfolio import render_municipality_portfolio
from pilot.municipality_spatial import (
    SPATIAL_INPUT_NAME, SPATIAL_REVIEW_NAME, save_spatial_source,
)


_UNMAPPED = "— Not mapped —"


def _identity_fields(prefix: str, *, default_label: str = "Municipal Pilot") -> MunicipalityIdentity:
    left, right = st.columns(2)
    with left:
        formal_name = st.text_input("Formal agency name", key=f"{prefix}_formal_name")
        short_name = st.text_input("Short display name", key=f"{prefix}_short_name")
        entity_type = st.selectbox(
            "Entity type",
            sorted(SUPPORTED_ENTITY_TYPES),
            key=f"{prefix}_entity_type",
        )
        state = st.text_input("State or jurisdiction", value="Michigan", key=f"{prefix}_state")
        suggested = ""
        if short_name.strip() or formal_name.strip():
            suggested = suggest_municipality_slug(short_name or formal_name)
        slug_key = f"{prefix}_slug"
        previous_suggestion_key = f"{prefix}_previous_slug_suggestion"
        previous_suggestion = st.session_state.get(previous_suggestion_key, "")
        current_slug = st.session_state.get(slug_key, "")
        if suggested and (not current_slug or current_slug == previous_suggestion):
            st.session_state[slug_key] = suggested
        st.session_state[previous_suggestion_key] = suggested
        slug = st.text_input(
            "Municipality slug",
            help="Suggested automatically; lowercase letters, numbers, and underscores only.",
            key=slug_key,
        )
    with right:
        leadership = st.text_input(
            "Leadership terminology",
            value="municipal leadership",
            key=f"{prefix}_leadership",
        )
        official_action = st.text_input(
            "Official-action terminology",
            value="official agency determination",
            key=f"{prefix}_official_action",
        )
        pilot_label = st.text_input(
            "Pilot label",
            value=default_label,
            help=(
                "Use a generic label such as 'Municipal Pilot' or 'Demonstration'. "
                "If the label already includes the municipality name, Paventra will not repeat it."
            ),
            key=f"{prefix}_pilot_label",
        )
        latitude = st.number_input(
            "Map center latitude",
            value=42.25,
            format="%.6f",
            help="Enter a locally verified decimal latitude; online address lookup is not available.",
            key=f"{prefix}_latitude",
        )
        longitude = st.number_input(
            "Map center longitude",
            value=-84.40,
            format="%.6f",
            help="Enter a locally verified decimal longitude; online address lookup is not available.",
            key=f"{prefix}_longitude",
        )
        map_zoom = st.number_input(
            "Map zoom", min_value=0, max_value=22, value=12, step=1, key=f"{prefix}_zoom"
        )
        scenario_catalog = st.selectbox(
            "Scenario catalog",
            sorted(SCENARIO_CATALOGS),
            key=f"{prefix}_scenario_catalog",
        )
    return MunicipalityIdentity(
        formal_name=formal_name.strip(),
        short_name=short_name.strip(),
        entity_type=entity_type,
        state=state.strip(),
        slug=slug.strip(),
        leadership_label=leadership.strip(),
        official_action_label=official_action.strip(),
        map_center=(float(latitude), float(longitude)),
        map_zoom=int(map_zoom),
        scenario_catalog_id=scenario_catalog,
        pilot_label=pilot_label.strip(),
    )


def _identity_matches_config(identity: MunicipalityIdentity, config) -> bool:
    return (
        identity.formal_name == config.formal_name
        and identity.short_name == config.short_name
        and identity.entity_type == config.entity_type
        and identity.state == config.state
        and identity.slug == config.slug
        and identity.leadership_label == config.leadership_label
        and identity.official_action_label == config.official_action_label
        and identity.map_center == tuple(config.map_center)
        and identity.map_zoom == config.map_zoom
        and identity.scenario_catalog_id == config.scenario_catalog_id
        and identity.pilot_label == config.pilot_label
    )


def _review_summary(review) -> None:
    config = review.config
    st.subheader("Final review")
    st.dataframe(
        pd.DataFrame([
            {
                "Formal name": config.formal_name,
                "Slug": config.slug,
                "Entity": config.entity_type,
                "Status": config.normalized_data_status,
                "Road segments": len(review.canonical),
                "Mappings": len(review.mapping),
                "Defaults": len(review.defaults),
                "Scenario catalog": config.scenario_catalog_id,
                "Validation": "PASS",
            }
        ]),
        hide_index=True,
        width="stretch",
    )
    st.caption(config.source_provenance_label)
    st.write("Map center:", config.map_center, "Zoom:", config.map_zoom)
    if review.mapping:
        with st.expander("Source mappings"):
            st.dataframe(
                pd.DataFrame(
                    [{"Source field": source, "Canonical field": target}
                     for source, target in review.mapping.items()]
                ),
                hide_index=True,
                width="stretch",
            )
    if review.defaults:
        with st.expander("Visible canonical defaults"):
            st.dataframe(
                pd.DataFrame(
                    [{"Canonical field": field, "Applied to every row": value}
                     for field, value in review.defaults.items()]
                ),
                hide_index=True,
                width="stretch",
            )
    if review.treatment_normalizations:
        st.info(
            "Treatment normalization: "
            + ", ".join(
                f"{source} → {target}"
                for source, target in review.treatment_normalizations.items()
            )
        )
    if review.unknown_treatments:
        st.warning(
            "Unrecognized treatment labels are retained unchanged: "
            + ", ".join(review.unknown_treatments)
        )
    st.code(f"SHA-256: {review.checksum}")


def _open_dashboard_button(config, *, runtime: bool) -> None:
    if st.button("Open Municipality Dashboard", type="primary", key=f"open_{config.slug}"):
        st.session_state.pop("paventra_runtime_municipality_slug", None)
        st.session_state.pop("paventra_selected_municipality_slug", None)
        key = (
            "paventra_runtime_municipality_slug"
            if runtime
            else "paventra_selected_municipality_slug"
        )
        st.session_state[key] = config.slug
        st.switch_page("dashboard.py")


def _render_demo_builder() -> None:
    st.header("Create Illustrative Demo")
    st.warning(
        "Generated roads are synthetic demonstration data. They are not municipality-supplied, "
        "observed, official, or suitable for engineering decisions."
    )
    identity = _identity_fields("demo")
    road_count = st.slider("Synthetic road segments", 5, 30, 10, key="demo_road_count")

    if st.button("Validate Demo", key="validate_demo"):
        try:
            assert_slug_available(identity.slug)
            st.session_state["demo_review"] = review_illustrative_demo(
                identity, road_count=road_count
            )
            st.session_state.pop("demo_package", None)
        except (TypeError, ValueError) as exc:
            st.error(str(exc))

    review = st.session_state.get("demo_review")
    if review is not None:
        _review_summary(review)
        if not _identity_matches_config(identity, review.config) or len(review.canonical) != road_count:
            st.warning("Identity changed after validation. Validate the demo again before creation.")
        elif st.button("Create Municipality", key="create_demo"):
            try:
                package = create_illustrative_demo_package(review)
                st.session_state["demo_package"] = package
                st.success(
                    f"Temporary illustrative package created at {package.manifest_path.parent}."
                )
            except (OSError, TypeError, ValueError) as exc:
                st.error(str(exc))

    package = st.session_state.get("demo_package")
    if package is not None:
        st.success("Validated runtime demo is ready.")
        st.caption(
            "This package is isolated from the permanent registry. Remove its generated folder "
            "manually after the sales/demo engagement; automatic deletion is intentionally omitted."
        )
        _open_dashboard_button(package.config, runtime=True)


def _read_uploaded_headers(uploaded) -> tuple[bytes, list[str]]:
    content = uploaded.getvalue()
    try:
        frame = pd.read_csv(io.BytesIO(content), nrows=5)
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError(f"Uploaded source CSV could not be read: {exc}") from exc
    return content, [str(column) for column in frame.columns]


def _hydrate_real_import_workspace(slug: str) -> tuple[Path, bytes, list[str]]:
    """Restore persisted operator inputs without requiring JSON or folder access."""

    package_path = GENERATED_MUNICIPALITIES_ROOT / slug
    manifest_path = package_path / "manifest.json"
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if document.get("package_type") != "real_import":
        raise ValueError(f"Generated package '{slug}' is not a real municipality import.")
    source_path = package_path / str(document["source_csv_path"])
    content = source_path.read_bytes()
    _, headers = _read_uploaded_headers(type("Upload", (), {"getvalue": lambda self: content})())

    values = {
        "import_formal_name": document.get("formal_name", ""),
        "import_short_name": document.get("short_name", ""),
        "import_entity_type": document.get("entity_type", "municipality"),
        "import_state": document.get("state", "Michigan"),
        "import_slug": document.get("slug", slug),
        "import_leadership": document.get("leadership_label", "municipal leadership"),
        "import_official_action": document.get(
            "official_action_label", "official agency determination"
        ),
        "import_pilot_label": document.get("pilot_label", "Municipal Pilot"),
        "import_latitude": float(document.get("map_center", [42.25, -84.4])[0]),
        "import_longitude": float(document.get("map_center", [42.25, -84.4])[1]),
        "import_zoom": int(document.get("map_zoom", 12)),
        "import_scenario_catalog": document.get("scenario_catalog_id", "standard"),
        "import_status": document.get("data_status", "provisional"),
        "import_owner": document.get("source_owner", ""),
        "import_acquired": date.fromisoformat(document.get("source_acquired_date")),
        "import_reference": document.get("source_reference", ""),
        "import_declared_checksum": document.get("source_checksum", ""),
    }
    for key, value in values.items():
        st.session_state[key] = value
    mapping = document.get("column_mapping", {})
    meanings = document.get("source_field_meanings", {})
    defaults = document.get("canonical_defaults", {})
    for index, header in enumerate(headers):
        st.session_state[f"mapping_{index}_{header}"] = mapping.get(header, _UNMAPPED)
        st.session_state[f"meaning_{index}_{header}"] = meanings.get(header, "")
    for canonical, value in defaults.items():
        st.session_state[f"default_{canonical}"] = str(value)
    st.session_state["import_previous_slug_suggestion"] = document.get("slug", slug)
    st.session_state["paventra_real_import_hydrated"] = slug
    record_package_reopened(package_path)
    return package_path, content, headers


def _render_operational_review(package_path: Path) -> None:
    """Render concise validation, mapping, lifecycle, and handoff surfaces."""

    inspection = inspect_real_import_package(package_path)
    document = inspection.manifest
    st.subheader("Real municipality package workspace")
    st.dataframe(
        pd.DataFrame([{
            "Municipality": document.get("formal_name", ""),
            "Entity": document.get("entity_type", ""),
            "Data status": document.get("data_status", ""),
            "Source owner": document.get("source_owner", ""),
            "Acquired": document.get("source_acquired_date", ""),
            "Source rows": inspection.source_rows,
            "Canonical rows": inspection.canonical_rows,
            "Mappings": len(document.get("column_mapping", {})),
            "Defaults": len(document.get("canonical_defaults", {})),
            "Scenario": document.get("scenario_catalog_id", ""),
            "Map": f"{document.get('map_center')} / zoom {document.get('map_zoom')}",
            "Readiness": inspection.lifecycle_state.value,
        }]),
        hide_index=True,
        width="stretch",
    )
    st.caption(f"Source reference: {document.get('source_reference', '')}")
    st.code(f"SHA-256: {document.get('source_checksum', '')}")

    blocking = inspection.blocking_issues
    warnings = inspection.warnings
    if blocking:
        st.error(f"{len(blocking)} blocking issue(s) prevent registration readiness.")
        for issue in blocking:
            st.write(f"**BLOCKING — {issue.field}:** {issue.message}")
    else:
        st.success("No blocking package issues are currently detected.")
    if warnings:
        st.warning(f"{len(warnings)} non-blocking warning(s) require review.")
        for issue in warnings:
            st.write(f"**WARNING — {issue.field}:** {issue.message}")

    with st.expander("Mapping and default review", expanded=True):
        st.dataframe(build_mapping_review(document), hide_index=True, width="stretch")
    spatial_input = package_path / SPATIAL_INPUT_NAME
    if spatial_input.is_file():
        with st.expander("Road geometry and spatial provenance", expanded=True):
            settings = json.loads(spatial_input.read_text(encoding="utf-8"))
            st.write(
                f"GeoJSON join: `{settings.get('source_id_field')}` → "
                f"`{settings.get('canonical_id_field')}` · source CRS "
                f"`{settings.get('declared_source_crs') or 'embedded GeoJSON CRS'}` · "
                "runtime CRS `EPSG:4326`"
            )
            st.caption(
                f"Geometry source: {settings.get('source_reference')} · "
                f"owner {settings.get('source_owner')} · acquired {settings.get('acquired_date')}"
            )
            review_path = package_path / SPATIAL_REVIEW_NAME
            if review_path.is_file():
                review = json.loads(review_path.read_text(encoding="utf-8"))
                st.dataframe(pd.DataFrame([{
                    "Features": review.get("feature_count"),
                    "Matched": review.get("matched_count"),
                    "Canonical rows": review.get("canonical_row_count"),
                    "Unmatched canonical": len(review.get("unmatched_canonical_ids", [])),
                    "Unmatched GIS": len(review.get("unmatched_source_ids", [])),
                    "Duplicate GIS IDs": len(review.get("duplicate_source_ids", [])),
                    "Source CRS": review.get("source_crs"),
                    "Target CRS": review.get("target_crs"),
                    "Result": review.get("result"),
                }]), hide_index=True, width="stretch")

    state = inspection.lifecycle_state
    if st.button("Validate saved package", key="validate_saved_import"):
        result = validate_real_import_package(package_path)
        if result.blocking_issues:
            st.error("Validation failed. Correct the blocking issues and save the draft again.")
        else:
            st.success("Validation passed. The package is Validated and ready for operator review.")
        st.rerun()
    if state == PackageLifecycleState.VALIDATED:
        if st.button("Begin operator review", key="begin_import_review"):
            begin_real_import_review(package_path)
            st.rerun()
    elif state == PackageLifecycleState.REVIEW_REQUIRED:
        st.info(
            "Review identity, provenance, mapping/default origins, validation warnings, map, "
            "scenario catalog, and canonical review artifact before confirming readiness."
        )
        if st.button(
            "Confirm review complete — Ready for Registration",
            key="mark_import_ready",
            type="primary",
        ):
            mark_real_import_ready(package_path)
            st.rerun()
    elif state == PackageLifecycleState.READY_FOR_REGISTRATION:
        st.success("Ready for Registration — final registration remains developer-controlled.")
        packet = registration_packet_path(package_path)
        st.subheader("Developer Registration Handoff")
        st.write("Package path:", str(package_path))
        st.write("Manifest path:", str(inspection.manifest_path))
        st.write("Slug:", document.get("slug", ""))
        st.write("Readiness:", state.value)
        st.code(suggested_registry_snippet(str(document.get("slug", "")), inspection.manifest_path))
        st.download_button(
            "Download registration packet",
            data=packet.read_bytes(),
            file_name=f"{document.get('slug', 'municipality')}_registration_packet.md",
            mime="text/markdown",
            key="download_registration_packet",
        )
        with st.expander("Developer verification checklist", expanded=True):
            st.markdown(
                "- [ ] Inspect manifest\n"
                "- [ ] Inspect mappings/defaults\n"
                "- [ ] Confirm checksum\n"
                "- [ ] Add registry entry\n"
                "- [ ] Run registry/startup validation\n"
                "- [ ] Run full tests and AppTest\n"
                "- [ ] Generate and inspect report\n"
                "- [ ] Run health check\n"
                "- [ ] Inspect Git diff\n"
                "- [ ] Commit only after review"
            )

    history = read_package_history(package_path)
    with st.expander("Package history (operational log, not a security audit)"):
        st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")


def _render_real_import() -> None:
    st.header("Import Municipality Data")
    st.info(
        "Real uploads default to provisional. Official is never inferred and remains only an "
        "explicit software designation—not municipal certification or approval."
    )
    st.markdown(
        "**Workflow:** Import Municipality Data → Configure Identity/Provenance → "
        "Map Columns → Apply Defaults → Validate → Review → Ready for Registration"
    )
    resumed_slug = st.session_state.get("paventra_real_import_slug")
    resumed_package: Path | None = None
    persisted_content: bytes | None = None
    persisted_headers: list[str] = []
    if resumed_slug and st.session_state.get("paventra_real_import_hydrated") != resumed_slug:
        try:
            resumed_package, persisted_content, persisted_headers = _hydrate_real_import_workspace(
                resumed_slug
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            st.error(f"Real-import workspace could not be reopened: {exc}")
            st.session_state.pop("paventra_real_import_slug", None)
    elif resumed_slug:
        resumed_package = GENERATED_MUNICIPALITIES_ROOT / resumed_slug
        try:
            document = json.loads((resumed_package / "manifest.json").read_text(encoding="utf-8"))
            persisted_content = (resumed_package / document["source_csv_path"]).read_bytes()
            frame = pd.read_csv(io.BytesIO(persisted_content), nrows=5)
            persisted_headers = [str(column) for column in frame.columns]
        except (OSError, KeyError, json.JSONDecodeError, pd.errors.ParserError) as exc:
            st.error(f"Persisted source could not be reopened: {exc}")

    if resumed_package is not None:
        st.success(f"Reopened persisted workspace: {resumed_slug}")
        if st.button("Start a new real import", key="start_new_real_import"):
            for key in list(st.session_state):
                if key.startswith(("import_", "mapping_", "meaning_", "default_")):
                    del st.session_state[key]
            st.session_state.pop("paventra_real_import_slug", None)
            st.session_state.pop("paventra_real_import_hydrated", None)
            st.rerun()

    identity = _identity_fields("import")
    uploaded = st.file_uploader("Upload municipality road inventory CSV", type=["csv"])
    status = st.selectbox(
        "Data status",
        ["provisional", "illustrative", "official"],
        key="import_status",
    )
    owner = st.text_input("Source owner or custodian", key="import_owner")
    acquired = st.date_input("Acquisition date", value=date.today(), key="import_acquired")
    reference = st.text_input("Source reference", key="import_reference")
    declared_checksum = st.text_input(
        "Declared SHA-256 (optional)", key="import_declared_checksum"
    )
    with st.expander("Optional municipal road geometry (GeoJSON)"):
        st.caption(
            "Upload LineString/MultiLineString GeoJSON. Shapefile bundles are not accepted in "
            "this workflow because their required sidecar files cannot be preserved atomically."
        )
        spatial_upload = st.file_uploader(
            "Upload road geometry GeoJSON", type=["geojson", "json"], key="import_spatial_upload"
        )
        spatial_id_field = st.text_input(
            "GeoJSON identifier property", value="segment_id", key="import_spatial_id_field"
        )
        spatial_canonical_id = st.selectbox(
            "Join to canonical identifier", ["segment_id", "road_id"], key="import_spatial_canonical_id"
        )
        spatial_crs = st.text_input(
            "Source CRS (required if GeoJSON has no CRS)", value="EPSG:4326", key="import_spatial_crs"
        )
        spatial_reference = st.text_input(
            "Geometry source reference", key="import_spatial_reference"
        )
        spatial_confirmed = st.checkbox(
            "I confirm the geometry source, acquisition date, and CRS declaration.",
            key="import_spatial_confirmed",
        )

    content = persisted_content
    headers: list[str] = persisted_headers
    if uploaded is not None:
        try:
            content, headers = _read_uploaded_headers(uploaded)
        except ValueError as exc:
            st.error(str(exc))

    mapping: dict[str, str] = {}
    defaults: dict[str, str] = {}
    meanings: dict[str, str] = {}
    if headers:
        suggestions = suggest_column_mappings(headers)
        st.subheader("Map source columns")
        st.caption("Suggestions are editable. Ambiguous or duplicate matches are never finalized automatically.")
        options = [_UNMAPPED, *CANONICAL_COLUMNS]
        for index, header in enumerate(headers):
            suggestion = suggestions[header]
            default_index = options.index(suggestion) if suggestion else 0
            selected = st.selectbox(
                f"{header} →",
                options,
                index=default_index,
                key=f"mapping_{index}_{header}",
            )
            if selected != _UNMAPPED:
                mapping[header] = selected
            meaning = st.text_input(
                f"Source meaning (optional): {header}",
                key=f"meaning_{index}_{header}",
            )
            if meaning.strip():
                meanings[header] = meaning.strip()

        mapped_targets = set(mapping.values())
        default_candidates = [
            column for column in CANONICAL_COLUMNS
            if column not in mapped_targets and column != "data_status"
        ]
        with st.expander("Canonical defaults for unmapped fields", expanded=True):
            st.caption(
                "Every non-empty value below is applied to every source row and remains visible in review."
            )
            for column in default_candidates:
                value = st.text_input(
                    f"Default: {column}",
                    key=f"default_{column}",
                )
                if value != "":
                    defaults[column] = value

    if st.button("Save or update draft", key="save_import_draft", disabled=content is None):
        try:
            if resumed_slug and identity.slug != resumed_slug:
                raise ValueError(
                    "A reopened package slug cannot be changed in place. Start a new import for a new slug."
                )
            package_path = save_real_import_draft(
                identity,
                content,
                mapping=mapping,
                defaults=defaults,
                data_status=status,
                source_owner=owner,
                acquired_date=acquired.isoformat(),
                source_reference=reference,
                declared_checksum=declared_checksum or None,
                source_field_meanings=meanings,
            )
            if spatial_upload is not None:
                save_spatial_source(
                    package_path,
                    spatial_upload.getvalue(),
                    source_id_field=spatial_id_field,
                    canonical_id_field=spatial_canonical_id,
                    source_crs=spatial_crs,
                    source_owner=owner,
                    acquired_date=acquired.isoformat(),
                    source_reference=spatial_reference,
                    provenance_confirmed=spatial_confirmed,
                )
            st.session_state["paventra_real_import_slug"] = identity.slug
            st.session_state["paventra_real_import_hydrated"] = identity.slug
            st.success(f"Draft workspace saved at {package_path}.")
            st.rerun()
        except (OSError, TypeError, ValueError) as exc:
            st.error(str(exc))
    if resumed_package is not None and resumed_package.is_dir():
        _render_operational_review(resumed_package)


def _safe_inventory_count(config) -> str:
    try:
        with config.data_path.open("r", encoding="utf-8-sig", newline="") as source:
            rows = csv.reader(source)
            next(rows)
            return str(sum(1 for _ in rows))
    except (OSError, StopIteration, UnicodeError, csv.Error):
        return "Unavailable"


def _render_existing_municipalities() -> None:
    st.header("View Existing Municipalities")
    st.subheader("Permanent registry")
    for slug, config in MUNICIPALITIES.items():
        left, right = st.columns([4, 1])
        left.write(
            f"**{config.formal_name}** — `{slug}` · {config.entity_type} · "
            f"{config.normalized_data_status} · {_safe_inventory_count(config)} roads · "
            f"catalog `{config.scenario_catalog_id}`"
        )
        with right:
            _open_dashboard_button(config, runtime=False)

    st.subheader("Generated working area")
    generated = list_generated_municipalities()
    if not generated:
        st.caption("No generated municipality packages are currently available.")
    for config in generated:
        st.write(
            f"**{config.formal_name}** — `{config.slug}` · {config.entity_type} · "
            f"{config.normalized_data_status} · {_safe_inventory_count(config)} roads · "
            f"catalog `{config.scenario_catalog_id}`"
        )
        if config.normalized_data_status == "illustrative":
            _open_dashboard_button(config, runtime=True)
        else:
            st.caption("Ready for developer-reviewed permanent registration.")
    st.caption(f"Generated packages are isolated under {GENERATED_MUNICIPALITIES_ROOT}.")


def render_municipality_admin(*, operator_view: str = "onboarding") -> None:
    """Render the operator-facing municipality workflow."""

    if operator_view == "portfolio":
        render_municipality_portfolio()
        return
    if operator_view != "onboarding":
        raise ValueError(f"Unknown municipality operator view: {operator_view!r}")

    st.title("Municipality Onboarding & Demo Builder")
    st.caption(
        "Create synthetic sales demos or prepare validated real municipality packages without "
        "editing Python, JSON, Git, or environment variables."
    )
    mode = st.radio(
        "Choose a workflow",
        [
            "Create Illustrative Demo",
            "Import Municipality Data",
        ],
        horizontal=True,
        key="municipality_admin_workflow",
    )
    if mode == "Create Illustrative Demo":
        _render_demo_builder()
    elif mode == "Import Municipality Data":
        _render_real_import()
