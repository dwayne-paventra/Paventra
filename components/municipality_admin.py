"""Streamlit municipality onboarding and generated-demo management UI."""

from __future__ import annotations

from datetime import date
import io

import pandas as pd
import streamlit as st

from pilot.canonical_inventory import CANONICAL_COLUMNS
from pilot.municipality_admin import (
    GENERATED_MUNICIPALITIES_ROOT,
    MunicipalityIdentity,
    assert_slug_available,
    create_illustrative_demo_package,
    create_real_import_package,
    list_generated_municipalities,
    review_illustrative_demo,
    review_real_import,
    suggest_column_mappings,
    suggest_municipality_slug,
)
from pilot.municipality_config import SUPPORTED_ENTITY_TYPES
from pilot.municipality_data import load_municipality_inventory
from pilot.municipality_registry import MUNICIPALITIES
from pilot.municipality_scenarios import SCENARIO_CATALOGS


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
            "Pilot label", value=default_label, key=f"{prefix}_pilot_label"
        )
        latitude = st.number_input(
            "Map center latitude", value=42.25, format="%.6f", key=f"{prefix}_latitude"
        )
        longitude = st.number_input(
            "Map center longitude", value=-84.40, format="%.6f", key=f"{prefix}_longitude"
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


def _render_real_import() -> None:
    st.header("Import Municipality Data")
    st.info(
        "Real uploads default to provisional. Official is never inferred and remains only an "
        "explicit software designation—not municipal certification or approval."
    )
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

    content = None
    headers: list[str] = []
    if uploaded is not None:
        try:
            content, headers = _read_uploaded_headers(uploaded)
        except ValueError as exc:
            st.error(str(exc))

    mapping: dict[str, str] = {}
    defaults: dict[str, str] = {}
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

    if st.button("Validate Import", key="validate_import", disabled=content is None):
        try:
            assert_slug_available(identity.slug)
            review = review_real_import(
                identity,
                content,
                mapping=mapping,
                defaults=defaults,
                data_status=status,
                source_owner=owner,
                acquired_date=acquired.isoformat(),
                source_reference=reference,
                declared_checksum=declared_checksum or None,
            )
            st.session_state["import_review"] = review
            st.session_state["import_source_content"] = content
            st.session_state.pop("import_package", None)
        except (TypeError, ValueError) as exc:
            st.error(str(exc))

    review = st.session_state.get("import_review")
    if review is not None:
        _review_summary(review)
        current_checksum = None if content is None else review.checksum
        changed = (
            not _identity_matches_config(identity, review.config)
            or review.config.normalized_data_status != status
            or dict(review.mapping) != mapping
            or dict(review.defaults) != defaults
            or review.config.source_provenance.owner != owner
            or review.config.source_provenance.acquired_date != acquired.isoformat()
            or review.config.source_provenance.reference != reference
            or st.session_state.get("import_source_content") != content
            or current_checksum is None
        )
        if changed:
            st.warning("Import inputs changed after validation. Validate again before creation.")
        elif st.button("Create Municipality", key="create_import"):
            try:
                package = create_real_import_package(review, content)
                st.session_state["import_package"] = package
                st.success(f"Validated import package created at {package.manifest_path.parent}.")
            except (OSError, TypeError, ValueError) as exc:
                st.error(str(exc))

    package = st.session_state.get("import_package")
    if package is not None:
        st.success("Ready for registration")
        st.code(
            "Load the reviewed manifest with load_onboarding_manifest, then add its "
            f"configuration to MUNICIPALITIES under slug '{package.config.slug}'."
        )
        st.caption(
            "Permanent registration remains a developer-reviewed source change. The UI does not "
            "rewrite Python, Git, or accepted municipality configuration."
        )


def _safe_inventory_count(config) -> str:
    try:
        return str(len(load_municipality_inventory(config)))
    except (OSError, TypeError, ValueError):
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


def render_municipality_admin() -> None:
    """Render the operator-facing municipality workflow."""

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
            "View Existing Municipalities",
        ],
        horizontal=True,
    )
    if mode == "Create Illustrative Demo":
        _render_demo_builder()
    elif mode == "Import Municipality Data":
        _render_real_import()
    else:
        _render_existing_municipalities()
