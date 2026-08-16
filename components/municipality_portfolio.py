"""Operator-facing portfolio for registered and generated municipalities."""

from __future__ import annotations

from datetime import date
from io import BytesIO
import json

import pandas as pd
import streamlit as st

from components.municipality_spatial_intake import render_spatial_upload_controls

from pilot.municipality_admin import (
    ARCHIVED_MUNICIPALITIES_ROOT,
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    archive_generated_demo,
    build_municipality_portfolio,
    clone_illustrative_demo,
    filter_municipality_portfolio,
    restore_archived_demo,
    suggest_column_mappings,
    suggest_municipality_slug,
)
from pilot.canonical_inventory import CANONICAL_COLUMNS
from pilot.municipality_data_versions import (
    UpdateLifecycleState,
    activate_update,
    activation_preview,
    begin_update_review,
    create_update_workspace,
    inspect_update_workspace,
    list_update_workspaces,
    mark_update_ready,
    rollback_active_version,
    validate_update_workspace,
    version_history,
)
from pilot.municipality_package_lifecycle import (
    build_mapping_review,
    inspect_real_import_package,
    read_package_history,
    registration_packet_path,
    suggested_registry_snippet,
)
from pilot.municipality_registration import (
    RegistrationState,
    accept_registration,
    preview_registration,
    promote_registration,
    rollback_registration,
)
from pilot.municipality_registry import (
    BUILTIN_MUNICIPALITIES,
    refresh_persistent_municipalities,
)
from pilot.municipality_spatial import SPATIAL_REVIEW_NAME, load_spatial_metadata


def _open_dashboard(config, *, runtime: bool) -> None:
    if st.button("Open Municipality Dashboard", type="primary", key=f"portfolio_open_{config.slug}"):
        st.session_state.pop("paventra_runtime_municipality_slug", None)
        st.session_state.pop("paventra_selected_municipality_slug", None)
        selection_key = (
            "paventra_runtime_municipality_slug"
            if runtime
            else "paventra_selected_municipality_slug"
        )
        st.session_state[selection_key] = config.slug
        st.session_state["paventra_dashboard_section"] = "Dashboard"
        st.switch_page("dashboard.py")


def _clone_form(entry) -> None:
    config = entry.config
    if config is None:
        return
    with st.expander("Clone illustrative demo"):
        formal_name = st.text_input("New formal agency name", key=f"clone_formal_{entry.slug}")
        short_name = st.text_input("New short display name", key=f"clone_short_{entry.slug}")
        suggested = ""
        if short_name.strip() or formal_name.strip():
            suggested = suggest_municipality_slug(short_name or formal_name)
        slug = st.text_input(
            "New municipality slug", value=suggested, key=f"clone_slug_{entry.slug}"
        )
        st.caption(
            "Cloning regenerates synthetic roads under the new identity. It never copies "
            "provisional or official municipality data."
        )
        if st.button("Create cloned demo", key=f"clone_create_{entry.slug}"):
            try:
                identity = MunicipalityIdentity(
                    formal_name=formal_name.strip(),
                    short_name=short_name.strip(),
                    entity_type=config.entity_type,
                    state=config.state,
                    slug=slug.strip(),
                    leadership_label=config.leadership_label,
                    official_action_label=config.official_action_label,
                    map_center=tuple(config.map_center),
                    map_zoom=config.map_zoom,
                    scenario_catalog_id=config.scenario_catalog_id,
                    pilot_label=config.pilot_label,
                )
                package = clone_illustrative_demo(entry.slug, identity)
                st.success(f"Cloned illustrative demo created at {package.manifest_path.parent}.")
            except (OSError, TypeError, ValueError) as exc:
                st.error(str(exc))


def _persistent_version_controls(entry) -> None:
    spatial_metadata = load_spatial_metadata(entry.config.data_directory)
    st.subheader("Active GIS details")
    st.dataframe(pd.DataFrame([{
        "Geometry available": "Yes" if spatial_metadata else "No",
        "Source format": spatial_metadata.get("source_format", "—") if spatial_metadata else "—",
        "Feature count": spatial_metadata.get("feature_count", 0) if spatial_metadata else 0,
        "Match coverage": (
            f"{spatial_metadata.get('match_coverage_percent', 0):.1f}%"
            if spatial_metadata else "—"
        ),
        "Source CRS": spatial_metadata.get("source_crs", "—") if spatial_metadata else "—",
        "Geometry version": entry.config.data_version or "Built-in",
    }]), hide_index=True, width="stretch")
    """Render permanent-version history and isolated candidate update controls."""

    st.subheader("Data Version History")
    history = version_history(entry.slug)
    st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
    st.caption(
        "Historical versions are immutable. Active/superseded labels come from the explicit "
        "registration pointer, not the highest directory number."
    )
    prior_versions = [
        item["data_version"] for item in history
        if item["data_version"] != entry.active_data_version
    ]
    if prior_versions:
        target = st.selectbox(
            "View or roll back to version",
            prior_versions,
            key=f"version_history_target_{entry.slug}",
        )
        selected = next(item for item in history if item["data_version"] == target)
        st.dataframe(pd.DataFrame([selected]), hide_index=True, width="stretch")
        st.write(
            "Compare to active:",
            {
                "selected_version": target,
                "active_version": entry.active_data_version,
                "row_count_change": (
                    selected.get("row_count") - next(
                        item.get("row_count") for item in history
                        if item["data_version"] == entry.active_data_version
                    )
                    if isinstance(selected.get("row_count"), int)
                    and isinstance(next(
                        item.get("row_count") for item in history
                        if item["data_version"] == entry.active_data_version
                    ), int)
                    else "Unavailable"
                ),
                "data_status_change": (
                    selected.get("data_status"),
                    next(item.get("data_status") for item in history
                         if item["data_version"] == entry.active_data_version),
                ),
            },
        )
        rollback_text = st.text_input(
            f"Type `{entry.slug} version {target}` to confirm version rollback",
            key=f"version_rollback_text_{entry.slug}",
        )
        rollback_confirmed = st.checkbox(
            "I understand rollback changes only the active pointer and deletes no versions",
            key=f"version_rollback_confirm_{entry.slug}",
        )
        if st.button(
            "Roll Back Active Data Version",
            key=f"version_rollback_{entry.slug}",
            disabled=(
                not rollback_confirmed
                or rollback_text != f"{entry.slug} version {target}"
            ),
        ):
            try:
                rollback_active_version(
                    entry.slug,
                    target,
                    confirmation=rollback_text,
                    confirmed=rollback_confirmed,
                )
                refresh_persistent_municipalities()
                st.success(f"Data version {target} is now active; no version was deleted.")
                st.rerun()
            except (OSError, TypeError, ValueError) as exc:
                st.error(str(exc))

    with st.expander("Upload New Inventory", expanded=False):
        st.caption(
            "Creates the deterministic next candidate version. Current active and historical "
            "versions remain untouched until explicit activation."
        )
        uploaded = st.file_uploader(
            "Upload candidate road inventory CSV",
            type=["csv"],
            key=f"version_upload_{entry.slug}",
        )
        spatial_selection = render_spatial_upload_controls(
            key_prefix=f"version_spatial_{entry.slug}",
            no_gis_message=(
                "No replacement GIS file: the active version's reviewed geometry will be "
                "inherited. If none exists, marker fallback remains available."
            ),
        )
        owner = st.text_input("Source owner", key=f"version_owner_{entry.slug}")
        acquired = st.date_input(
            "Acquisition or extraction date",
            value=date.today(),
            key=f"version_date_{entry.slug}",
        )
        reference = st.text_input("Source reference", key=f"version_reference_{entry.slug}")
        status_options = ["provisional", "official", "illustrative"]
        status = st.selectbox(
            "Candidate data status",
            status_options,
            index=status_options.index(entry.data_status)
            if entry.data_status in status_options else 0,
            key=f"version_status_{entry.slug}",
        )
        mapping: dict[str, str] = {}
        defaults: dict[str, str] = {}
        content = uploaded.getvalue() if uploaded is not None else b""
        headers: list[str] = []
        if content:
            try:
                headers = list(pd.read_csv(BytesIO(content), nrows=0).columns)
            except Exception as exc:
                st.error(f"Candidate CSV headers could not be read: {exc}")
        if headers:
            active_mapping = dict(entry.config.source_column_mapping or {})
            suggestions = suggest_column_mappings(headers)
            st.caption("Mappings are prefilled from the active version where columns still match.")
            for index, header in enumerate(headers):
                initial = (
                    active_mapping.get(header)
                    if active_mapping
                    else suggestions.get(header)
                )
                options = ["Unmapped", *CANONICAL_COLUMNS]
                selected = st.selectbox(
                    header,
                    options,
                    index=options.index(initial) if initial in options else 0,
                    key=f"version_mapping_{entry.slug}_{index}",
                )
                if selected != "Unmapped":
                    mapping[header] = selected
            mapped = set(mapping.values())
            with st.expander("Defaults for unresolved canonical fields"):
                for column in CANONICAL_COLUMNS:
                    if column in mapped:
                        continue
                    value = st.text_input(
                        column,
                        value=str((entry.config.canonical_defaults or {}).get(column, "")),
                        key=f"version_default_{entry.slug}_{column}",
                    )
                    if value.strip():
                        defaults[column] = value.strip()
        provenance_confirmed = st.checkbox(
            "I confirm this source provenance and data status for the candidate version",
            key=f"version_provenance_confirm_{entry.slug}",
        )
        if st.button(
            "Create Candidate Update",
            key=f"version_create_{entry.slug}",
            disabled=not (content and provenance_confirmed),
        ):
            try:
                active_mapping = dict(entry.config.source_column_mapping or {})
                active_defaults = dict(entry.config.canonical_defaults or {})
                if spatial_selection.source_type != "none" and spatial_selection.preview is None:
                    raise ValueError("Complete and resolve the selected GIS upload before creating the candidate.")
                if spatial_selection.preview is not None and not spatial_selection.source_id_field:
                    raise ValueError("Select a usable GIS identifier field before creating the candidate.")
                workspace = create_update_workspace(
                    entry.slug,
                    content,
                    source_owner=owner,
                    acquired_date=acquired.isoformat(),
                    source_reference=reference,
                    data_status=status,
                    mapping=None if mapping == active_mapping else mapping,
                    defaults=None if defaults == active_defaults else defaults,
                    provenance_confirmed=provenance_confirmed,
                    spatial_content=spatial_selection.geojson_content,
                    spatial_shapefile_files=spatial_selection.shapefile_files,
                    spatial_source_id_field=spatial_selection.source_id_field,
                    spatial_canonical_id_field=spatial_selection.canonical_id_field,
                    spatial_source_crs=spatial_selection.source_crs,
                )
                st.success(f"Candidate update workspace created: {workspace}")
                st.rerun()
            except (OSError, TypeError, ValueError) as exc:
                st.error(str(exc))

    workspaces = list_update_workspaces(entry.slug)
    if not workspaces:
        return
    labels = {
        f"Version {inspect_update_workspace(path).candidate_version}": path
        for path in workspaces
    }
    selected_label = st.selectbox(
        "Candidate update workspace",
        list(labels),
        key=f"version_workspace_{entry.slug}",
    )
    workspace = labels[selected_label]
    inspection = inspect_update_workspace(workspace)
    st.write(
        "Candidate state:", inspection.state.value,
        "· Candidate version:", inspection.candidate_version,
        "· Mapping reused:", inspection.mapping_reused,
        "· Defaults reused:", inspection.defaults_reused,
    )
    if inspection.blocking_issues:
        for issue in inspection.blocking_issues:
            st.error(f"{issue.field}: {issue.message}")
    spatial_review_path = workspace / SPATIAL_REVIEW_NAME
    if spatial_review_path.is_file():
        spatial_review = json.loads(spatial_review_path.read_text(encoding="utf-8"))
        st.subheader("Candidate GIS exact-match preview")
        st.dataframe(pd.DataFrame([{
            "Result": spatial_review.get("result"),
            "Features": spatial_review.get("feature_count"),
            "Canonical": spatial_review.get("canonical_row_count"),
            "Exact matches": spatial_review.get("matched_count"),
            "Match coverage": f"{spatial_review.get('match_percentage', 0):.1f}%",
            "GIS-only": len(spatial_review.get("unmatched_source_ids", [])),
            "Canonical-only": len(spatial_review.get("unmatched_canonical_ids", [])),
            "Duplicate GIS": len(spatial_review.get("duplicate_source_ids", [])),
            "Duplicate canonical": len(spatial_review.get("duplicate_canonical_ids", [])),
            "Source CRS": spatial_review.get("source_crs"),
            "Target CRS": spatial_review.get("target_crs"),
        }]), hide_index=True, width="stretch")
        st.json({
            "Exact-match sample": spatial_review.get("matched_ids", [])[:5],
            "GIS-only sample": spatial_review.get("unmatched_source_ids", [])[:5],
            "Canonical-only sample": spatial_review.get("unmatched_canonical_ids", [])[:5],
        })
        if spatial_review.get("result") == "BLOCKING":
            st.error("Candidate geometry cannot be activated until every blocking exact-match or geometry issue is corrected.")
    if inspection.comparison is not None:
        comparison = inspection.comparison.as_dict()
        st.subheader("Version Comparison")
        st.dataframe(pd.DataFrame([{
            key: value for key, value in comparison.items()
            if key not in {"issues", "added_segment_ids", "removed_segment_ids",
                           "added_road_ids", "removed_road_ids"}
        }]), hide_index=True, width="stretch")
        st.json({
            key: comparison[key]
            for key in ("added_segment_ids", "removed_segment_ids",
                        "added_road_ids", "removed_road_ids", "issues")
        })
    if inspection.state in {UpdateLifecycleState.DRAFT, UpdateLifecycleState.VALIDATION_REQUIRED}:
        if st.button("Validate Candidate Update", key=f"version_validate_{entry.slug}"):
            validate_update_workspace(workspace)
            st.rerun()
    elif inspection.state == UpdateLifecycleState.VALIDATED:
        if st.button("Begin Candidate Review", key=f"version_review_{entry.slug}"):
            begin_update_review(workspace)
            st.rerun()
    elif inspection.state == UpdateLifecycleState.REVIEW_REQUIRED:
        if st.button("Mark Ready for Activation", key=f"version_ready_{entry.slug}"):
            mark_update_ready(workspace)
            st.rerun()
    elif inspection.state == UpdateLifecycleState.READY_FOR_ACTIVATION:
        if st.button("Activation Preview", key=f"version_preview_{entry.slug}"):
            st.session_state[f"version_preview_result_{entry.slug}"] = activation_preview(workspace)
        preview = st.session_state.get(f"version_preview_result_{entry.slug}")
        if preview is not None:
            st.dataframe(pd.DataFrame([{
                "Municipality": preview.formal_name,
                "Current version": preview.current_active_version,
                "Candidate version": preview.candidate_version,
                "Current source checksum": preview.current_source_checksum,
                "Candidate source checksum": preview.candidate_source_checksum,
                "Current canonical checksum": preview.current_canonical_checksum,
                "Candidate canonical checksum": preview.candidate_canonical_checksum,
                "Old rows": preview.old_row_count,
                "New rows": preview.new_row_count,
                "Row change": preview.row_count_change,
                "Status change": f"{preview.current_data_status} → {preview.candidate_data_status}",
                "Source owner": preview.source_owner,
                "Source date": preview.source_date,
                "Source reference": preview.source_reference,
                "Destination": str(preview.activation_destination),
                "Result": preview.result,
            }]), hide_index=True, width="stretch")
            expected = f"{entry.slug} version {preview.candidate_version}"
            text = st.text_input(
                f"Type `{expected}` to confirm activation",
                key=f"version_activate_text_{entry.slug}",
            )
            confirmed = st.checkbox(
                "I confirm activation changes the active dataset pointer",
                key=f"version_activate_confirm_{entry.slug}",
            )
            if st.button(
                "Activate Candidate Version",
                key=f"version_activate_{entry.slug}",
                disabled=(preview.result != "PASS" or not confirmed or text != expected),
            ):
                try:
                    activate_update(
                        workspace, confirmation=text, confirmed=confirmed
                    )
                    refresh_persistent_municipalities()
                    st.success(f"Data version {preview.candidate_version} activated and verified.")
                    st.session_state.pop(f"version_preview_result_{entry.slug}", None)
                    st.rerun()
                except (OSError, TypeError, ValueError) as exc:
                    st.error(str(exc))


def _details(entry) -> None:
    st.subheader(f"Municipality details: {entry.formal_name}")
    config = entry.config
    raw_manifest = None
    if entry.manifest_path is not None and entry.manifest_path.is_file():
        try:
            candidate = json.loads(entry.manifest_path.read_text(encoding="utf-8"))
            raw_manifest = candidate if isinstance(candidate, dict) else None
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    overview, provenance, validation, manifest = st.tabs(
        ["Overview", "Provenance", "Validation Summary", "Manifest"]
    )
    with overview:
        st.dataframe(
            pd.DataFrame([{
                "Formal name": entry.formal_name,
                "Short name": entry.short_name,
                "Slug": entry.slug,
                "Entity type": entry.entity_type,
                "Data status": entry.data_status,
                "Source type": entry.source_type,
                "Package type": entry.package_type,
                "Scenario catalog": entry.scenario_catalog_id,
                "Roads": entry.road_count if entry.road_count is not None else "Unavailable",
                "Generated": entry.generated_date or "Not generated",
                "Permanent": entry.permanent,
                "Readiness": entry.readiness_state,
            }]),
            hide_index=True,
            width="stretch",
        )
        st.caption("Package or data location")
        st.code(str(entry.package_path))
        if entry.registration_version is not None:
            st.write("Registration version:", entry.registration_version)
            st.write("Registration date:", entry.registration_date)
            st.write("Active data version:", entry.active_data_version)
            st.write("Available data versions:", list(entry.available_data_versions))
            st.write(
                "Registration acceptance:",
                "Accepted" if entry.registration_state == RegistrationState.ACCEPTED
                else "Pending Acceptance",
            )
            st.write("Registered data location:", str(entry.registered_data_path))
            st.caption(
                "Acceptance confirms Paventra operational verification only; it is not "
                "municipal, engineering, or legal approval."
            )
        if config is not None:
            st.write("Map center:", config.map_center, "Zoom:", config.map_zoom)
            st.write("Terminology:", config.leadership_label, "·", config.official_action_label)
        if entry.dashboard_launchable and config is not None:
            _open_dashboard(config, runtime=not entry.permanent)
        elif entry.package_type == "real_import":
            st.info("Developer review and permanent registry registration are required before launch.")
            if st.button("Continue real-import review", key=f"resume_real_import_{entry.slug}"):
                st.session_state["paventra_real_import_slug"] = entry.slug
                st.session_state.pop("paventra_real_import_hydrated", None)
                st.session_state["paventra_operator_view"] = "onboarding"
                st.session_state["municipality_admin_workflow"] = "Import Municipality Data"
                st.rerun()
    with provenance:
        if config is None and raw_manifest is None:
            st.warning("Provenance is unavailable until this package passes manifest validation.")
        elif config is not None:
            st.write(config.source_provenance_label)
            source = config.source_provenance
            if source is not None:
                st.write("Source owner:", source.owner)
                st.write("Acquired date:", source.acquired_date)
                st.write("Source reference:", source.reference)
                st.code(f"SHA-256: {source.checksum}")
        else:
            st.write("Source owner:", raw_manifest.get("source_owner", "Unavailable"))
            st.write("Acquired date:", raw_manifest.get("source_acquired_date", "Unavailable"))
            st.write("Source reference:", raw_manifest.get("source_reference", "Unavailable"))
            st.code(f"SHA-256: {raw_manifest.get('source_checksum', 'Unavailable')}")
    with validation:
        if entry.readiness_state == "Validation Required":
            st.error(entry.validation_summary)
        else:
            st.success(entry.validation_summary)
        st.write("Inventory adapter:", config.inventory_adapter if config else "Unavailable")
        st.write("Scenario catalog:", entry.scenario_catalog_id)
        st.write("Manifest version:", entry.manifest_version or "Not manifest-backed")
        if entry.package_type == "real_import" and raw_manifest is not None:
            inspection = inspect_real_import_package(entry.package_path)
            st.write(
                f"Blocking issues: {len(inspection.blocking_issues)} · "
                f"Warnings: {len(inspection.warnings)}"
            )
            st.dataframe(
                build_mapping_review(raw_manifest), hide_index=True, width="stretch"
            )
            history = read_package_history(entry.package_path)
            if history:
                st.caption("Persisted package history — operational log, not a security audit")
                st.dataframe(pd.DataFrame(history), hide_index=True, width="stretch")
    with manifest:
        if entry.manifest_path is None or not entry.manifest_path.is_file():
            st.caption("This permanent registry entry is configured in application source.")
        else:
            try:
                st.json(json.loads(entry.manifest_path.read_text(encoding="utf-8")))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                st.error(f"Manifest could not be displayed: {exc}")
        if entry.package_type == "real_import" and raw_manifest is not None:
            st.subheader("Developer Registration Handoff")
            st.write("Package path:", str(entry.package_path))
            st.write("Manifest path:", str(entry.manifest_path))
            st.write("Slug:", entry.slug)
            st.write("Readiness:", entry.readiness_state)
            st.code(suggested_registry_snippet(entry.slug, entry.manifest_path))
            if entry.readiness_state == "Real Import — Ready for Registration":
                try:
                    packet = registration_packet_path(entry.package_path)
                    st.download_button(
                        "Download registration packet",
                        data=packet.read_bytes(),
                        file_name=f"{entry.slug}_registration_packet.md",
                        mime="text/markdown",
                        key=f"portfolio_packet_{entry.slug}",
                    )
                except (OSError, ValueError) as exc:
                    st.error(str(exc))

                if st.button(
                    "Registration Preview",
                    key=f"registration_preview_{entry.slug}",
                ):
                    st.session_state[f"registration_preview_result_{entry.slug}"] = (
                        preview_registration(
                            entry.package_path,
                            protected_slugs=BUILTIN_MUNICIPALITIES,
                        )
                    )
                preview = st.session_state.get(
                    f"registration_preview_result_{entry.slug}"
                )
                if preview is not None:
                    st.subheader("Review Registration")
                    st.dataframe(
                        pd.DataFrame([{
                            "Formal name": preview.formal_name,
                            "Short name": preview.short_name,
                            "Slug": preview.slug,
                            "Entity": preview.entity_type,
                            "Data status": preview.data_status,
                            "Source owner": preview.source_owner,
                            "Source date": preview.source_date,
                            "Source reference": preview.source_reference,
                            "Source checksum": preview.source_checksum,
                            "Canonical checksum": preview.canonical_checksum,
                            "Segments": preview.segment_count,
                            "Map center": preview.map_center,
                            "Map zoom": preview.map_zoom,
                            "Scenario": preview.scenario_catalog_id,
                            "Adapter": preview.inventory_adapter,
                            "Leadership term": preview.leadership_label,
                            "Action term": preview.official_action_label,
                            "Permanent path": str(preview.intended_path),
                            "Registration version": preview.registration_version,
                            "Result": preview.result,
                        }]),
                        hide_index=True,
                        width="stretch",
                    )
                    if preview.blocking_issues:
                        for issue in preview.blocking_issues:
                            st.error(f"{issue.field}: {issue.message}")
                    confirmation = st.text_input(
                        f"Type `{entry.slug}` to confirm",
                        key=f"registration_confirm_text_{entry.slug}",
                    )
                    confirmed = st.checkbox(
                        f"I confirm registration of {entry.slug}",
                        key=f"registration_confirm_checkbox_{entry.slug}",
                    )
                    if st.button(
                        "Register Municipality",
                        key=f"register_municipality_{entry.slug}",
                        type="primary",
                        disabled=(
                            preview.result != "PASS"
                            or not confirmed
                            or confirmation != entry.slug
                        ),
                    ):
                        try:
                            registered = promote_registration(
                                entry.package_path,
                                confirmation_slug=confirmation,
                                confirmed=confirmed,
                                protected_slugs=BUILTIN_MUNICIPALITIES,
                            )
                            refresh_persistent_municipalities()
                            st.success(
                                f"Registered {registered.config.formal_name}; operational "
                                "acceptance remains pending."
                            )
                            st.session_state.pop(
                                f"registration_preview_result_{entry.slug}", None
                            )
                            st.rerun()
                        except (OSError, TypeError, ValueError) as exc:
                            st.error(str(exc))

    if entry.permanent and entry.registration_version is not None:
        st.subheader("Persistent Registration Controls")
        if entry.registration_state == RegistrationState.PENDING_ACCEPTANCE:
            st.info(
                "This registration passed automated operational verification and is pending "
                "acceptance. Acceptance is not municipal or legal certification."
            )
            accept_confirmed = st.checkbox(
                f"I confirm operational acceptance of {entry.slug}",
                key=f"accept_registration_confirm_{entry.slug}",
            )
            if st.button(
                "Accept Registration",
                key=f"accept_registration_{entry.slug}",
                disabled=not accept_confirmed,
            ):
                try:
                    accept_registration(entry.slug)
                    refresh_persistent_municipalities()
                    st.success("Registration accepted operationally.")
                    st.rerun()
                except (OSError, TypeError, ValueError) as exc:
                    st.error(str(exc))
            with st.expander("Controlled rollback before acceptance"):
                rollback_text = st.text_input(
                    f"Type `{entry.slug}` to confirm rollback",
                    key=f"rollback_registration_text_{entry.slug}",
                )
                rollback_confirmed = st.checkbox(
                    f"I confirm rollback of pending registration {entry.slug}",
                    key=f"rollback_registration_confirm_{entry.slug}",
                )
                if st.button(
                    "Rollback Pending Registration",
                    key=f"rollback_registration_{entry.slug}",
                    disabled=(
                        not rollback_confirmed or rollback_text != entry.slug
                    ),
                ):
                    try:
                        rollback_registration(
                            entry.slug,
                            confirmation_slug=rollback_text,
                            protected_slugs=BUILTIN_MUNICIPALITIES,
                        )
                        refresh_persistent_municipalities()
                        st.success("Pending registration rolled back; onboarding history preserved.")
                        st.rerun()
                    except (OSError, TypeError, ValueError) as exc:
                        st.error(str(exc))
        else:
            st.warning(
                "Accepted registrations cannot be casually rolled back. Removal is restricted "
                "to a deliberate developer-controlled process."
            )
        _persistent_version_controls(entry)

    if entry.package_type == "illustrative_demo":
        with st.expander("Pre-meeting demo readiness checklist"):
            st.markdown(
                "- [ ] Municipality name and terminology are correct\n"
                "- [ ] Illustrative status is clearly visible\n"
                "- [ ] Map center and generated road markers look acceptable\n"
                "- [ ] Every scenario, recommendations, and PDF report load\n"
                "- [ ] No unrelated municipality wording is visible\n"
                "- [ ] Portfolio can reopen this demo"
            )

    if not entry.permanent and not entry.archived and entry.package_type == "illustrative_demo":
        _clone_form(entry)
        st.warning(
            f"Archive moves only generated demo '{entry.slug}' to recoverable storage. "
            "It does not delete the package."
        )
        confirmed = st.checkbox(
            f"I confirm archive of generated demo {entry.slug}",
            key=f"archive_confirm_{entry.slug}",
        )
        if st.button(
            "Archive generated demo", key=f"archive_{entry.slug}", disabled=not confirmed
        ):
            try:
                destination = archive_generated_demo(entry.slug)
                st.success(f"Archived recoverably at {destination}.")
                st.rerun()
            except (OSError, TypeError, ValueError) as exc:
                st.error(str(exc))
    elif entry.archived:
        if st.button("Restore archived demo", key=f"restore_{entry.slug}"):
            try:
                destination = restore_archived_demo(entry.slug)
                st.success(f"Restored generated demo at {destination}.")
                st.rerun()
            except (OSError, TypeError, ValueError) as exc:
                st.error(str(exc))


def render_municipality_portfolio() -> None:
    """Render searchable metadata and safe generated-demo lifecycle controls."""

    st.header("Municipality Portfolio")
    st.caption(
        "Permanent registry entries and generated working packages. Archived demos are hidden "
        "by default; portfolio listing does not load or enrich every road inventory."
    )
    st.caption(
        "Generated packages persist on disk across Streamlit restarts. Dashboard selection is "
        "session-specific, so reopen a generated demo here after a restart."
    )
    include_archived = st.checkbox("Include archived generated demos", key="portfolio_archived")
    entries = build_municipality_portfolio(include_archived=include_archived)
    search = st.text_input("Search by municipality name or slug", key="portfolio_search")
    columns = st.columns(4)
    with columns[0]:
        entity_types = st.multiselect(
            "Entity type", sorted({entry.entity_type for entry in entries})
        )
    with columns[1]:
        statuses = st.multiselect(
            "Data status", sorted({entry.data_status for entry in entries})
        )
    with columns[2]:
        scopes = st.multiselect("Source", ["Permanent", "Generated", "Archived"])
    with columns[3]:
        readiness = st.multiselect(
            "Readiness", sorted({entry.readiness_state for entry in entries})
        )
    filtered = filter_municipality_portfolio(
        entries,
        search=search,
        entity_types=entity_types,
        data_statuses=statuses,
        source_scopes=scopes,
        readiness_states=readiness,
    )
    st.write(f"Showing {len(filtered)} of {len(entries)} municipalities")
    st.dataframe(
        pd.DataFrame([{
            "Municipality": entry.formal_name,
            "Slug": entry.slug,
            "Entity": entry.entity_type,
            "Status": entry.data_status,
            "Source": entry.source_type,
            "Roads": entry.road_count if entry.road_count is not None else "Unavailable",
            "Generated": entry.generated_date or "—",
            "Permanent": entry.permanent,
            "Readiness": entry.readiness_state,
            "Registration version": entry.registration_version or "—",
            "Registration date": entry.registration_date or "—",
            "Active data version": entry.active_data_version or "—",
        } for entry in filtered]),
        hide_index=True,
        width="stretch",
    )
    if not filtered:
        st.info("No municipalities match the current portfolio filters.")
        return
    slug_counts = {
        entry.slug: sum(1 for candidate in filtered if candidate.slug == entry.slug)
        for entry in filtered
    }
    labels = {
        (
            f"{entry.formal_name} — {entry.slug}"
            if slug_counts[entry.slug] == 1
            else f"{entry.formal_name} — {entry.slug} — {entry.readiness_state}"
        ): entry
        for entry in filtered
    }
    selected = labels.get(st.selectbox(
        "View details", ["Select a municipality"] + list(labels), key="portfolio_selected"
    ))
    if selected is not None:
        _details(selected)
    st.caption(f"Generated packages: {GENERATED_MUNICIPALITIES_ROOT}")
    if include_archived:
        st.caption(f"Recoverable archive: {ARCHIVED_MUNICIPALITIES_ROOT}")
