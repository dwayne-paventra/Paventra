"""Reviewed, immutable data-version updates for persistent municipalities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

import pandas as pd

from pilot.canonical_inventory import validate_canonical_schema
from pilot.municipality_admin import MunicipalityIdentity, save_real_import_draft
from pilot.municipality_onboarding import load_onboarding_manifest
from pilot.municipality_package_lifecycle import (
    CANONICAL_REVIEW_NAME,
    HISTORY_NAME,
    MAPPING_REVIEW_NAME,
    PackageLifecycleState,
    REGISTRATION_PACKET_NAME,
    REVIEW_SUMMARY_NAME,
    VALIDATION_SUMMARY_NAME,
    begin_real_import_review,
    mark_real_import_ready,
    refresh_real_import_readiness,
    validate_real_import_package,
)
from pilot.municipality_registration import (
    PERSISTENT_MUNICIPALITIES_ROOT,
    REGISTRATION_METADATA_NAME,
    RegisteredMunicipality,
    RegistrationIssue,
    _normalized_slug,
    _read_json,
    _registration_metadata,
    _safe_registration_path,
    _write_json_atomic,
    get_persistent_registration,
    verify_registered_municipality,
)
from pilot.source_provenance import compute_source_checksum


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPDATE_WORKSPACES_ROOT = PROJECT_ROOT / "generated" / "municipality_updates"
UPDATE_METADATA_NAME = "update.json"
UPDATE_HISTORY_NAME = "update_history.jsonl"
COMPARISON_NAME = "version_comparison.json"
VERSION_HISTORY_NAME = "version_history.jsonl"
UPDATE_SCHEMA_VERSION = 1


class UpdateLifecycleState(str, Enum):
    DRAFT = "Draft Update"
    VALIDATION_REQUIRED = "Validation Required"
    VALIDATED = "Validated"
    REVIEW_REQUIRED = "Review Required"
    READY_FOR_ACTIVATION = "Ready for Activation"
    ACTIVE = "Active"
    SUPERSEDED = "Superseded"
    ROLLED_BACK = "Rolled Back"


@dataclass(frozen=True)
class VersionComparison:
    active_version: int
    candidate_version: int
    old_row_count: int
    new_row_count: int
    added_segment_ids: tuple[str, ...]
    removed_segment_ids: tuple[str, ...]
    added_road_ids: tuple[str, ...]
    removed_road_ids: tuple[str, ...]
    changed_identifier_count: int
    pci_change_count: int
    adt_change_count: int
    treatment_change_count: int
    coordinate_change_count: int
    current_source_checksum: str
    candidate_source_checksum: str
    current_data_status: str
    candidate_data_status: str
    issues: tuple[RegistrationIssue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "active_version": self.active_version,
            "candidate_version": self.candidate_version,
            "old_row_count": self.old_row_count,
            "new_row_count": self.new_row_count,
            "row_count_change": self.new_row_count - self.old_row_count,
            "added_segment_ids": list(self.added_segment_ids),
            "removed_segment_ids": list(self.removed_segment_ids),
            "added_road_ids": list(self.added_road_ids),
            "removed_road_ids": list(self.removed_road_ids),
            "changed_identifier_count": self.changed_identifier_count,
            "pci_change_count": self.pci_change_count,
            "adt_change_count": self.adt_change_count,
            "treatment_change_count": self.treatment_change_count,
            "coordinate_change_count": self.coordinate_change_count,
            "current_source_checksum": self.current_source_checksum,
            "candidate_source_checksum": self.candidate_source_checksum,
            "current_data_status": self.current_data_status,
            "candidate_data_status": self.candidate_data_status,
            "issues": [issue.__dict__ for issue in self.issues],
        }


@dataclass(frozen=True)
class UpdateInspection:
    workspace_path: Path
    slug: str
    candidate_version: int
    state: UpdateLifecycleState
    active_version_at_creation: int
    mapping_reused: bool
    defaults_reused: bool
    comparison: VersionComparison | None
    issues: tuple[RegistrationIssue, ...]

    @property
    def blocking_issues(self) -> tuple[RegistrationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)


@dataclass(frozen=True)
class ActivationPreview:
    slug: str
    formal_name: str
    current_active_version: int
    candidate_version: int
    current_source_checksum: str
    candidate_source_checksum: str
    current_canonical_checksum: str
    candidate_canonical_checksum: str
    old_row_count: int | None
    new_row_count: int | None
    row_count_change: int | None
    current_data_status: str
    candidate_data_status: str
    source_owner: str
    source_date: str
    source_reference: str
    activation_destination: Path
    issues: tuple[RegistrationIssue, ...]

    @property
    def blocking_issues(self) -> tuple[RegistrationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    @property
    def result(self) -> str:
        return "BLOCKED" if self.blocking_issues else "PASS"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _version_number(value: object, field: str = "data version") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer.")
    return value


def _workspace_path(slug: str, version: int, root: str | Path) -> Path:
    safe_slug = _normalized_slug(slug)
    safe_version = _version_number(version)
    base = Path(root).resolve()
    version_root = (base / str(safe_version)).resolve()
    workspace = (version_root / safe_slug).resolve()
    if version_root.parent != base or workspace.parent != version_root:
        raise ValueError("Municipality update workspace escaped its configured root.")
    return workspace


def _append_jsonl(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(dict(document), sort_keys=True) + "\n")


def _append_update_event(workspace: Path, event: str, state: UpdateLifecycleState, summary: str) -> None:
    _append_jsonl(workspace / UPDATE_HISTORY_NAME, {
        "timestamp_utc": _utc_timestamp(),
        "event": event,
        "state": state.value,
        "summary": summary,
    })


def _append_version_event(registration: Path, event: str, summary: str, **details: Any) -> None:
    _append_jsonl(registration / VERSION_HISTORY_NAME, {
        "timestamp_utc": _utc_timestamp(),
        "event": event,
        "summary": summary,
        **details,
    })


def _set_workspace_state_if_present(
    slug: str,
    version: int,
    state: UpdateLifecycleState,
    *,
    workspace_root: str | Path,
    event: str,
    summary: str,
) -> None:
    workspace = _workspace_path(slug, version, workspace_root)
    if not (workspace / UPDATE_METADATA_NAME).is_file():
        return
    metadata = _update_metadata(workspace)
    metadata["state"] = state.value
    _write_json_atomic(workspace / UPDATE_METADATA_NAME, metadata)
    _append_update_event(workspace, event, state, summary)


def next_data_version(
    slug: str,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> int:
    registered = get_persistent_registration(slug, registration_root)
    metadata = _registration_metadata(registered.registration_path)
    versions = metadata["available_data_versions"]
    return max(versions) + 1


def _identity_from_registration(registered: RegisteredMunicipality) -> MunicipalityIdentity:
    config = registered.config
    return MunicipalityIdentity(
        formal_name=config.formal_name,
        short_name=config.short_name,
        entity_type=config.entity_type,
        state=config.state,
        slug=config.slug,
        leadership_label=config.leadership_label,
        official_action_label=config.official_action_label,
        map_center=tuple(config.map_center),
        map_zoom=config.map_zoom,
        scenario_catalog_id=config.scenario_catalog_id,
        pilot_label=config.pilot_label,
    )


def create_update_workspace(
    slug: str,
    source_content: bytes,
    *,
    source_owner: str,
    acquired_date: str,
    source_reference: str,
    data_status: str,
    mapping: Mapping[str, str] | None = None,
    defaults: Mapping[str, Any] | None = None,
    source_field_meanings: Mapping[str, str] | None = None,
    provenance_confirmed: bool,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    workspace_root: str | Path = UPDATE_WORKSPACES_ROOT,
) -> Path:
    """Create the deterministic next-version workspace using the shared importer."""

    if not provenance_confirmed:
        raise ValueError("Candidate provenance and data status require explicit operator confirmation.")
    registered = get_persistent_registration(slug, registration_root)
    version = next_data_version(slug, registration_root=registration_root)
    workspace = _workspace_path(slug, version, workspace_root)
    if workspace.exists():
        raise ValueError(
            f"Candidate data version {version} already exists for municipality '{slug}'."
        )
    active_mapping = dict(registered.config.source_column_mapping or {})
    active_defaults = dict(registered.config.canonical_defaults or {})
    resolved_mapping = active_mapping if mapping is None else dict(mapping)
    resolved_defaults = active_defaults if defaults is None else dict(defaults)
    package = save_real_import_draft(
        _identity_from_registration(registered),
        source_content,
        mapping=resolved_mapping,
        defaults=resolved_defaults,
        data_status=data_status,
        source_owner=source_owner,
        acquired_date=acquired_date,
        source_reference=source_reference,
        source_field_meanings=source_field_meanings,
        generated_root=workspace.parent,
        allow_registered_slug=True,
    )
    metadata = {
        "update_schema_version": UPDATE_SCHEMA_VERSION,
        "slug": registered.config.slug,
        "candidate_data_version": version,
        "active_version_at_creation": registered.active_data_version,
        "state": UpdateLifecycleState.DRAFT.value,
        "created_at_utc": _utc_timestamp(),
        "mapping_reused": mapping is None,
        "defaults_reused": defaults is None,
        "provenance_confirmed": True,
        "comparison_path": COMPARISON_NAME,
    }
    _write_json_atomic(package / UPDATE_METADATA_NAME, metadata)
    _append_update_event(
        package,
        "update created",
        UpdateLifecycleState.DRAFT,
        f"Candidate immutable data version {version} workspace created from active version "
        f"{registered.active_data_version}.",
    )
    _append_update_event(
        package,
        "source uploaded",
        UpdateLifecycleState.DRAFT,
        "Operator supplied source and explicitly confirmed version-specific provenance/status.",
    )
    return package


def _update_metadata(workspace: Path) -> dict[str, Any]:
    metadata = _read_json(workspace / UPDATE_METADATA_NAME, "Municipality update metadata")
    required = (
        "update_schema_version", "slug", "candidate_data_version",
        "active_version_at_creation", "state", "created_at_utc",
        "mapping_reused", "defaults_reused", "provenance_confirmed",
        "comparison_path",
    )
    missing = [field for field in required if field not in metadata]
    if missing:
        raise ValueError("Municipality update metadata is missing fields: " + ", ".join(missing))
    if metadata["update_schema_version"] != UPDATE_SCHEMA_VERSION:
        raise ValueError("Municipality update metadata schema version is unsupported.")
    _normalized_slug(metadata["slug"])
    _version_number(metadata["candidate_data_version"], "candidate_data_version")
    _version_number(metadata["active_version_at_creation"], "active_version_at_creation")
    try:
        UpdateLifecycleState(metadata["state"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Municipality update state '{metadata.get('state')}' is invalid.") from exc
    return metadata


def get_update_workspace(
    slug: str,
    version: int,
    *,
    workspace_root: str | Path = UPDATE_WORKSPACES_ROOT,
) -> Path:
    workspace = _workspace_path(slug, version, workspace_root)
    metadata = _update_metadata(workspace)
    if metadata["slug"] != slug or metadata["candidate_data_version"] != version:
        raise ValueError("Municipality update workspace identity/version does not match its path.")
    return workspace


def list_update_workspaces(
    slug: str,
    *,
    workspace_root: str | Path = UPDATE_WORKSPACES_ROOT,
) -> tuple[Path, ...]:
    safe_slug = _normalized_slug(slug)
    root = Path(workspace_root).resolve()
    if not root.is_dir():
        return ()
    found: list[tuple[int, Path]] = []
    for version_root in root.iterdir():
        if not version_root.is_dir() or not version_root.name.isdigit():
            continue
        workspace = version_root / safe_slug
        if workspace.is_dir() and (workspace / UPDATE_METADATA_NAME).is_file():
            metadata = _update_metadata(workspace)
            found.append((metadata["candidate_data_version"], workspace.resolve()))
    return tuple(path for _, path in sorted(found))


def _active_canonical_path(registered: RegisteredMunicipality) -> Path:
    metadata = _registration_metadata(registered.registration_path)
    return (registered.registration_path / metadata["canonical_inventory_path"]).resolve()


def _changed_count(old: pd.DataFrame, new: pd.DataFrame, columns: tuple[str, ...]) -> int:
    common = sorted(set(old.index.astype(str)) & set(new.index.astype(str)))
    if not common:
        return 0
    left = old.copy()
    right = new.copy()
    left.index = left.index.astype(str)
    right.index = right.index.astype(str)
    changes = pd.Series(False, index=common)
    for column in columns:
        old_values = left.loc[common, column].fillna("").astype(str)
        new_values = right.loc[common, column].fillna("").astype(str)
        changes |= old_values.ne(new_values)
    return int(changes.sum())


def compare_candidate_to_active(
    workspace_path: str | Path,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> VersionComparison:
    workspace = Path(workspace_path).resolve()
    update = _update_metadata(workspace)
    registered = get_persistent_registration(update["slug"], registration_root)
    candidate_config = load_onboarding_manifest(workspace / "manifest.json")
    old = pd.read_csv(_active_canonical_path(registered))
    new_path = workspace / CANONICAL_REVIEW_NAME
    if not new_path.is_file():
        raise ValueError("Candidate canonical inventory is missing; validate the update first.")
    new = pd.read_csv(new_path)
    validate_canonical_schema(
        new,
        expected_data_status=candidate_config.normalized_data_status,
        municipality_slug=candidate_config.slug,
    )
    old_segments = set(old["segment_id"].astype(str))
    new_segments = set(new["segment_id"].astype(str))
    old_roads = set(old["road_id"].astype(str))
    new_roads = set(new["road_id"].astype(str))
    old_indexed = old.set_index("segment_id", drop=False)
    new_indexed = new.set_index("segment_id", drop=False)
    issues: list[RegistrationIssue] = [RegistrationIssue(
        "informational", "source_checksum", "Candidate source checksum differs from the active version."
    )]
    if len(old) != len(new):
        issues.append(RegistrationIssue(
            "review recommended", "row_count", "Candidate inventory row count changed."
        ))
    if registered.config.normalized_data_status != candidate_config.normalized_data_status:
        issues.append(RegistrationIssue(
            "review recommended", "data_status", "Candidate data status differs from the active version."
        ))
    comparison = VersionComparison(
        active_version=registered.active_data_version,
        candidate_version=update["candidate_data_version"],
        old_row_count=len(old),
        new_row_count=len(new),
        added_segment_ids=tuple(sorted(new_segments - old_segments)),
        removed_segment_ids=tuple(sorted(old_segments - new_segments)),
        added_road_ids=tuple(sorted(new_roads - old_roads)),
        removed_road_ids=tuple(sorted(old_roads - new_roads)),
        changed_identifier_count=_changed_count(old_indexed, new_indexed, ("road_id",)),
        pci_change_count=_changed_count(old_indexed, new_indexed, ("pci",)),
        adt_change_count=_changed_count(old_indexed, new_indexed, ("adt", "traffic_level")),
        treatment_change_count=_changed_count(old_indexed, new_indexed, ("recommended_treatment",)),
        coordinate_change_count=_changed_count(old_indexed, new_indexed, ("latitude", "longitude")),
        current_source_checksum=compute_source_checksum(registered.config.data_path),
        candidate_source_checksum=compute_source_checksum(candidate_config.data_path),
        current_data_status=registered.config.normalized_data_status,
        candidate_data_status=candidate_config.normalized_data_status,
        issues=tuple(issues),
    )
    _write_json_atomic(workspace / COMPARISON_NAME, comparison.as_dict())
    _append_update_event(
        workspace,
        "comparison generated",
        UpdateLifecycleState.VALIDATED,
        f"Compared active version {comparison.active_version} with candidate version "
        f"{comparison.candidate_version}.",
    )
    return comparison


def _comparison_from_disk(workspace: Path) -> VersionComparison | None:
    path = workspace / COMPARISON_NAME
    if not path.is_file():
        return None
    value = _read_json(path, "Version comparison")
    return VersionComparison(
        active_version=value["active_version"],
        candidate_version=value["candidate_version"],
        old_row_count=value["old_row_count"],
        new_row_count=value["new_row_count"],
        added_segment_ids=tuple(value["added_segment_ids"]),
        removed_segment_ids=tuple(value["removed_segment_ids"]),
        added_road_ids=tuple(value["added_road_ids"]),
        removed_road_ids=tuple(value["removed_road_ids"]),
        changed_identifier_count=value["changed_identifier_count"],
        pci_change_count=value["pci_change_count"],
        adt_change_count=value["adt_change_count"],
        treatment_change_count=value["treatment_change_count"],
        coordinate_change_count=value["coordinate_change_count"],
        current_source_checksum=value["current_source_checksum"],
        candidate_source_checksum=value["candidate_source_checksum"],
        current_data_status=value["current_data_status"],
        candidate_data_status=value["candidate_data_status"],
        issues=tuple(RegistrationIssue(**item) for item in value.get("issues", [])),
    )


def _candidate_fingerprint(workspace: Path) -> str:
    manifest = _read_json(workspace / "manifest.json", "Candidate manifest")
    comparison_checksum = compute_source_checksum(workspace / COMPARISON_NAME)
    update = _update_metadata(workspace)
    payload = {
        "readiness_fingerprint": manifest.get("readiness_fingerprint"),
        "comparison_checksum": comparison_checksum,
        "slug": update["slug"],
        "candidate_data_version": update["candidate_data_version"],
        "active_version_at_creation": update["active_version_at_creation"],
        "provenance_confirmed": update["provenance_confirmed"],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def inspect_update_workspace(
    workspace_path: str | Path,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> UpdateInspection:
    workspace = Path(workspace_path).resolve()
    update = _update_metadata(workspace)
    state = UpdateLifecycleState(update["state"])
    issues: list[RegistrationIssue] = []
    comparison = _comparison_from_disk(workspace)
    try:
        registered = get_persistent_registration(update["slug"], registration_root)
        if registered.active_data_version != update["active_version_at_creation"] and state not in {
            UpdateLifecycleState.ACTIVE, UpdateLifecycleState.SUPERSEDED,
            UpdateLifecycleState.ROLLED_BACK,
        }:
            issues.append(RegistrationIssue(
                "blocking", "active_data_version",
                "Active version changed after this candidate was created; create/review a new comparison."
            ))
        if update["candidate_data_version"] in _registration_metadata(
            registered.registration_path
        )["available_data_versions"] and state != UpdateLifecycleState.ACTIVE:
            issues.append(RegistrationIssue(
                "blocking", "candidate_data_version", "Candidate version already exists permanently."
            ))
    except ValueError as exc:
        issues.append(RegistrationIssue("blocking", "parent_registration", str(exc)))
    if state == UpdateLifecycleState.READY_FOR_ACTIVATION:
        inspection = refresh_real_import_readiness(workspace)
        manifest = _read_json(workspace / "manifest.json", "Candidate manifest")
        if inspection.lifecycle_state != PackageLifecycleState.READY_FOR_REGISTRATION:
            issues.append(RegistrationIssue(
                "blocking", "canonical_validation", "Candidate canonical readiness is stale."
            ))
            update["state"] = UpdateLifecycleState.VALIDATION_REQUIRED.value
            update.pop("candidate_fingerprint", None)
            _write_json_atomic(workspace / UPDATE_METADATA_NAME, update)
            _append_update_event(
                workspace,
                "activation readiness invalidated",
                UpdateLifecycleState.VALIDATION_REQUIRED,
                "Candidate source or readiness-sensitive content changed after review.",
            )
            state = UpdateLifecycleState.VALIDATION_REQUIRED
        if comparison is None:
            issues.append(RegistrationIssue("blocking", "comparison", "Version comparison is missing."))
        elif comparison.active_version != update["active_version_at_creation"]:
            issues.append(RegistrationIssue("blocking", "comparison", "Version comparison is stale."))
        try:
            current = _candidate_fingerprint(workspace)
        except (OSError, TypeError, ValueError) as exc:
            issues.append(RegistrationIssue("blocking", "candidate_fingerprint", str(exc)))
        else:
            if update.get("candidate_fingerprint") != current:
                issues.append(RegistrationIssue(
                    "blocking", "candidate_fingerprint", "Candidate readiness fingerprint is stale."
                ))
        if manifest.get("readiness_fingerprint") != inspection.current_fingerprint:
            issues.append(RegistrationIssue(
                "blocking", "readiness_fingerprint", "Canonical readiness fingerprint is stale."
            ))
    return UpdateInspection(
        workspace_path=workspace,
        slug=update["slug"],
        candidate_version=update["candidate_data_version"],
        state=state,
        active_version_at_creation=update["active_version_at_creation"],
        mapping_reused=bool(update["mapping_reused"]),
        defaults_reused=bool(update["defaults_reused"]),
        comparison=comparison,
        issues=tuple(issues),
    )


def validate_update_workspace(
    workspace_path: str | Path,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> UpdateInspection:
    workspace = Path(workspace_path).resolve()
    result = validate_real_import_package(workspace)
    update = _update_metadata(workspace)
    if result.blocking_issues:
        update["state"] = UpdateLifecycleState.VALIDATION_REQUIRED.value
        update.pop("candidate_fingerprint", None)
        _write_json_atomic(workspace / UPDATE_METADATA_NAME, update)
        _append_update_event(
            workspace, "update validation failed", UpdateLifecycleState.VALIDATION_REQUIRED,
            f"{len(result.blocking_issues)} blocking canonical issue(s)."
        )
        return inspect_update_workspace(workspace, registration_root=registration_root)
    comparison = compare_candidate_to_active(workspace, registration_root=registration_root)
    update["state"] = UpdateLifecycleState.VALIDATED.value
    update["comparison_active_version"] = comparison.active_version
    update.pop("candidate_fingerprint", None)
    _write_json_atomic(workspace / UPDATE_METADATA_NAME, update)
    _append_update_event(
        workspace, "update validated", UpdateLifecycleState.VALIDATED,
        "Candidate source, mappings, provenance, canonical export, and comparison passed."
    )
    return inspect_update_workspace(workspace, registration_root=registration_root)


def begin_update_review(
    workspace_path: str | Path,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> UpdateInspection:
    workspace = Path(workspace_path).resolve()
    update = _update_metadata(workspace)
    if UpdateLifecycleState(update["state"]) != UpdateLifecycleState.VALIDATED:
        raise ValueError("Municipality update must be Validated before review begins.")
    begin_real_import_review(workspace)
    update["state"] = UpdateLifecycleState.REVIEW_REQUIRED.value
    _write_json_atomic(workspace / UPDATE_METADATA_NAME, update)
    _append_update_event(
        workspace, "update reviewed", UpdateLifecycleState.REVIEW_REQUIRED,
        "Operator opened explicit version comparison and candidate review."
    )
    return inspect_update_workspace(workspace, registration_root=registration_root)


def mark_update_ready(
    workspace_path: str | Path,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> UpdateInspection:
    workspace = Path(workspace_path).resolve()
    update = _update_metadata(workspace)
    if UpdateLifecycleState(update["state"]) != UpdateLifecycleState.REVIEW_REQUIRED:
        raise ValueError("Municipality update must be in Review Required before activation readiness.")
    if _comparison_from_disk(workspace) is None:
        raise ValueError("Version comparison must be completed before activation readiness.")
    mark_real_import_ready(workspace)
    update["state"] = UpdateLifecycleState.READY_FOR_ACTIVATION.value
    _write_json_atomic(workspace / UPDATE_METADATA_NAME, update)
    update["candidate_fingerprint"] = _candidate_fingerprint(workspace)
    _write_json_atomic(workspace / UPDATE_METADATA_NAME, update)
    _append_update_event(
        workspace, "marked ready for activation", UpdateLifecycleState.READY_FOR_ACTIVATION,
        "All current candidate, provenance, comparison, and review gates passed."
    )
    return inspect_update_workspace(workspace, registration_root=registration_root)


def activation_preview(
    workspace_path: str | Path,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    record_event: bool = True,
) -> ActivationPreview:
    workspace = Path(workspace_path).resolve()
    inspection = inspect_update_workspace(workspace, registration_root=registration_root)
    update = _update_metadata(workspace)
    issues = list(inspection.issues)
    if inspection.state != UpdateLifecycleState.READY_FOR_ACTIVATION:
        issues.append(RegistrationIssue(
            "blocking", "update_state",
            f"Candidate must be exactly Ready for Activation; current state is '{inspection.state.value}'."
        ))
    registered = get_persistent_registration(update["slug"], registration_root)
    registration_metadata = _registration_metadata(registered.registration_path)
    candidate_manifest = _read_json(workspace / "manifest.json", "Candidate manifest")
    comparison = inspection.comparison
    destination = registered.registration_path / "versions" / str(update["candidate_data_version"])
    if destination.exists():
        issues.append(RegistrationIssue(
            "blocking", "activation_destination", f"Permanent data version already exists: '{destination}'."
        ))
    expected_next = max(registration_metadata["available_data_versions"]) + 1
    if update["candidate_data_version"] != expected_next:
        issues.append(RegistrationIssue(
            "blocking", "candidate_data_version",
            f"Candidate version must be the deterministic next version {expected_next}."
        ))
    preview = ActivationPreview(
        slug=registered.config.slug,
        formal_name=registered.config.formal_name,
        current_active_version=registered.active_data_version,
        candidate_version=update["candidate_data_version"],
        current_source_checksum=registration_metadata["source_checksum"],
        candidate_source_checksum=str(candidate_manifest.get("source_checksum", "")),
        current_canonical_checksum=registration_metadata["canonical_checksum"],
        candidate_canonical_checksum=str(candidate_manifest.get("canonical_checksum", "")),
        old_row_count=comparison.old_row_count if comparison else None,
        new_row_count=comparison.new_row_count if comparison else None,
        row_count_change=(comparison.new_row_count - comparison.old_row_count if comparison else None),
        current_data_status=registered.config.normalized_data_status,
        candidate_data_status=str(candidate_manifest.get("data_status", "")),
        source_owner=str(candidate_manifest.get("source_owner", "")),
        source_date=str(candidate_manifest.get("source_acquired_date", "")),
        source_reference=str(candidate_manifest.get("source_reference", "")),
        activation_destination=destination,
        issues=tuple(issues),
    )
    if record_event:
        _append_update_event(
            workspace,
            "activation previewed" if preview.result == "PASS" else "activation blocked",
            inspection.state,
            f"Activation preview result: {preview.result}; {len(preview.blocking_issues)} blocking issue(s).",
        )
    return preview


def _configuration_snapshot(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: manifest.get(field)
        for field in (
            "municipality_id", "slug", "state", "entity_type", "formal_name",
            "short_name", "map_center", "map_zoom", "inventory_adapter",
            "scenario_catalog_id", "pilot_mode", "pilot_label", "leadership_label",
            "official_action_label", "data_status",
        )
    }


def _record_from_manifest(
    manifest: Mapping[str, Any], version: int, *, canonical_checksum: str,
    activated_at: str, row_count: int | None,
) -> dict[str, Any]:
    return {
        "data_version": version,
        "manifest_path": f"versions/{version}/manifest.json",
        "canonical_inventory_path": f"versions/{version}/canonical_inventory.csv",
        "source_checksum": manifest["source_checksum"],
        "canonical_checksum": canonical_checksum,
        "readiness_fingerprint": manifest["readiness_fingerprint"],
        "configuration_snapshot": _configuration_snapshot(manifest),
        "mapping_snapshot": manifest.get("column_mapping", {}),
        "defaults_snapshot": manifest.get("canonical_defaults", {}),
        "source_provenance": {
            "owner": manifest.get("source_owner"),
            "acquired_date": manifest.get("source_acquired_date"),
            "reference": manifest.get("source_reference"),
            "checksum": manifest.get("source_checksum"),
        },
        "data_status": manifest.get("data_status"),
        "row_count": row_count,
        "activated_at_utc": activated_at,
    }


def _active_record(metadata: Mapping[str, Any]) -> dict[str, Any]:
    version = metadata["active_data_version"]
    records = metadata.get("version_records", {})
    if str(version) in records:
        return dict(records[str(version)])
    return {
        "data_version": version,
        "manifest_path": metadata["active_manifest_path"],
        "canonical_inventory_path": metadata["canonical_inventory_path"],
        "source_checksum": metadata["source_checksum"],
        "canonical_checksum": metadata["canonical_checksum"],
        "readiness_fingerprint": metadata["readiness_fingerprint"],
        "configuration_snapshot": metadata["configuration_snapshot"],
        "mapping_snapshot": metadata["mapping_snapshot"],
        "defaults_snapshot": metadata["defaults_snapshot"],
        "source_provenance": metadata["source_provenance"],
        "data_status": metadata["configuration_snapshot"].get("data_status"),
        "row_count": None,
        "activated_at_utc": metadata.get(
            "active_version_activated_at_utc", metadata["registered_at_utc"]
        ),
    }


def _metadata_for_record(metadata: Mapping[str, Any], record: Mapping[str, Any]) -> dict[str, Any]:
    updated = dict(metadata)
    previous = metadata["active_data_version"]
    updated.update({
        "previous_active_data_version": previous,
        "active_data_version": record["data_version"],
        "active_manifest_path": record["manifest_path"],
        "canonical_inventory_path": record["canonical_inventory_path"],
        "source_checksum": record["source_checksum"],
        "canonical_checksum": record["canonical_checksum"],
        "readiness_fingerprint": record["readiness_fingerprint"],
        "configuration_snapshot": record["configuration_snapshot"],
        "mapping_snapshot": record["mapping_snapshot"],
        "defaults_snapshot": record["defaults_snapshot"],
        "source_provenance": record["source_provenance"],
        "active_version_activated_at_utc": _utc_timestamp(),
    })
    return updated


def _copy_candidate_version(workspace: Path, staging: Path, preview: ActivationPreview) -> dict[str, Any]:
    staging.mkdir(parents=False, exist_ok=False)
    manifest = _read_json(workspace / "manifest.json", "Candidate manifest")
    source_path = (workspace / str(manifest["source_csv_path"])).resolve()
    if source_path.parent != workspace:
        raise ValueError("Candidate source path escapes its update workspace.")
    copies = {
        source_path: staging / "source_roads.csv",
        workspace / "source_roads.raw.csv": staging / "source_roads.raw.csv",
        workspace / CANONICAL_REVIEW_NAME: staging / "canonical_inventory.csv",
        workspace / MAPPING_REVIEW_NAME: staging / MAPPING_REVIEW_NAME,
        workspace / VALIDATION_SUMMARY_NAME: staging / VALIDATION_SUMMARY_NAME,
        workspace / REVIEW_SUMMARY_NAME: staging / REVIEW_SUMMARY_NAME,
        workspace / REGISTRATION_PACKET_NAME: staging / REGISTRATION_PACKET_NAME,
        workspace / COMPARISON_NAME: staging / COMPARISON_NAME,
        workspace / UPDATE_HISTORY_NAME: staging / UPDATE_HISTORY_NAME,
    }
    for source, destination in copies.items():
        if not source.is_file():
            raise ValueError(f"Required candidate version artifact is missing: '{source}'.")
        shutil.copy2(source, destination)
    runtime_manifest = dict(manifest)
    runtime_manifest["source_csv_path"] = "source_roads.csv"
    runtime_manifest["lifecycle_state"] = PackageLifecycleState.REGISTERED.value
    _write_json_atomic(staging / "manifest.json", runtime_manifest)
    canonical_checksum = compute_source_checksum(staging / "canonical_inventory.csv")
    config = load_onboarding_manifest(staging / "manifest.json")
    if compute_source_checksum(config.data_path) != preview.candidate_source_checksum:
        raise ValueError("Staged candidate source checksum changed during copy.")
    canonical = pd.read_csv(staging / "canonical_inventory.csv")
    validate_canonical_schema(
        canonical,
        expected_data_status=config.normalized_data_status,
        municipality_slug=config.slug,
    )
    if canonical_checksum != preview.candidate_canonical_checksum:
        raise ValueError("Staged candidate canonical checksum changed during copy.")
    record = _record_from_manifest(
        runtime_manifest,
        preview.candidate_version,
        canonical_checksum=canonical_checksum,
        activated_at=_utc_timestamp(),
        row_count=len(canonical),
    )
    _write_json_atomic(staging / "version.json", record)
    return record


def activate_update(
    workspace_path: str | Path,
    *,
    confirmation: str,
    confirmed: bool,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    verifier: Callable[[Path], Any] = verify_registered_municipality,
) -> RegisteredMunicipality:
    workspace = Path(workspace_path).resolve()
    preview = activation_preview(
        workspace, registration_root=registration_root, record_event=False
    )
    expected_confirmation = f"{preview.slug} version {preview.candidate_version}"
    if not confirmed or confirmation.strip() != expected_confirmation:
        raise ValueError(f"Type '{expected_confirmation}' and confirm activation.")
    if preview.blocking_issues:
        _append_update_event(
            workspace, "activation blocked", UpdateLifecycleState.READY_FOR_ACTIVATION,
            "; ".join(issue.message for issue in preview.blocking_issues)
        )
        raise ValueError("Activation is blocked: " + "; ".join(
            issue.message for issue in preview.blocking_issues
        ))
    registration = _safe_registration_path(preview.slug, registration_root)
    metadata_path = registration / REGISTRATION_METADATA_NAME
    original = _registration_metadata(registration)
    versions_root = registration / "versions"
    destination = versions_root / str(preview.candidate_version)
    staging = versions_root / f".{preview.candidate_version}.staging-{uuid4().hex}"
    if staging.parent.resolve() != versions_root.resolve() or destination.parent.resolve() != versions_root.resolve():
        raise ValueError("Candidate activation path escaped the registered versions root.")
    _append_update_event(
        workspace, "activation attempted", UpdateLifecycleState.READY_FOR_ACTIVATION,
        f"Atomic activation attempted for data version {preview.candidate_version}."
    )
    original_update = _update_metadata(workspace)
    promoted = False
    switched = False
    try:
        record = _copy_candidate_version(workspace, staging, preview)
        if destination.exists():
            raise ValueError(f"Permanent version collision at '{destination}'.")
        staging.replace(destination)
        promoted = True
        records = dict(original.get("version_records", {}))
        records[str(original["active_data_version"])] = _record_for_version(
            registration, original, original["active_data_version"]
        )
        records[str(preview.candidate_version)] = record
        updated = _metadata_for_record(original, record)
        updated["available_data_versions"] = sorted(
            [*original["available_data_versions"], preview.candidate_version]
        )
        updated["version_records"] = records
        _write_json_atomic(metadata_path, updated)
        switched = True
        verifier(registration)
        registered = get_persistent_registration(preview.slug, registration_root)
        update = dict(original_update)
        update["state"] = UpdateLifecycleState.ACTIVE.value
        update["activated_at_utc"] = _utc_timestamp()
        _write_json_atomic(workspace / UPDATE_METADATA_NAME, update)
        _append_version_event(
            registration, "activation succeeded",
            f"Activated version {preview.candidate_version}; previous active version was "
            f"{preview.current_active_version}.",
            active_version=preview.candidate_version,
            previous_active_version=preview.current_active_version,
        )
        _append_update_event(
            workspace, "activation succeeded", UpdateLifecycleState.ACTIVE,
            f"Data version {preview.candidate_version} is active; version "
            f"{preview.current_active_version} remains immutable and available."
        )
        _set_workspace_state_if_present(
            preview.slug,
            preview.current_active_version,
            UpdateLifecycleState.SUPERSEDED,
            workspace_root=workspace.parent.parent,
            event="update superseded",
            summary=f"Data version {preview.candidate_version} replaced this version as active.",
        )
    except Exception as exc:
        if switched:
            _write_json_atomic(metadata_path, original)
        _write_json_atomic(workspace / UPDATE_METADATA_NAME, original_update)
        cleanup = destination if promoted else staging
        if cleanup.exists():
            shutil.rmtree(cleanup)
        _append_update_event(
            workspace, "activation verification failed", UpdateLifecycleState.READY_FOR_ACTIVATION,
            f"Candidate activation failed and active version {original['active_data_version']} was preserved: {exc}"
        )
        _append_version_event(
            registration, "activation verification failed",
            f"Version {preview.candidate_version} failed; active version remained {original['active_data_version']}.",
            candidate_version=preview.candidate_version,
            active_version=original["active_data_version"],
        )
        raise ValueError(f"Activation failed; previous active version was restored: {exc}") from exc
    return registered


def _record_for_version(registration: Path, metadata: Mapping[str, Any], version: int) -> dict[str, Any]:
    records = metadata.get("version_records", {})
    if str(version) in records:
        return dict(records[str(version)])
    version_path = registration / "versions" / str(version)
    record_path = version_path / "version.json"
    if record_path.is_file():
        return _read_json(record_path, "Immutable data-version metadata")
    if version == metadata["active_data_version"]:
        # Phase 21 compatibility: registrations created before version.json
        # materialization remain active and can be captured before v2 activation.
        return _active_record(metadata)
    raise ValueError(f"Immutable metadata for data version {version} is unavailable.")


def rollback_active_version(
    slug: str,
    target_version: int,
    *,
    confirmation: str,
    confirmed: bool,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    workspace_root: str | Path = UPDATE_WORKSPACES_ROOT,
    verifier: Callable[[Path], Any] = verify_registered_municipality,
) -> RegisteredMunicipality:
    safe_slug = _normalized_slug(slug)
    target = _version_number(target_version, "target_version")
    expected = f"{safe_slug} version {target}"
    if not confirmed or confirmation.strip() != expected:
        raise ValueError(f"Type '{expected}' and confirm rollback.")
    registration = _safe_registration_path(safe_slug, registration_root)
    metadata_path = registration / REGISTRATION_METADATA_NAME
    original = _registration_metadata(registration)
    if target == original["active_data_version"]:
        raise ValueError(f"Data version {target} is already active.")
    if target not in original["available_data_versions"]:
        raise ValueError(f"Data version {target} is not available for '{safe_slug}'.")
    record = _record_for_version(registration, original, target)
    prospective = _metadata_for_record(original, record)
    _write_json_atomic(metadata_path, prospective)
    try:
        verifier(registration)
        registered = get_persistent_registration(safe_slug, registration_root)
        _append_version_event(
            registration, "rollback performed",
            f"Activated prior immutable version {target}; version {original['active_data_version']} remains available.",
            active_version=target,
            previous_active_version=original["active_data_version"],
        )
        previous_state = (
            UpdateLifecycleState.ROLLED_BACK
            if target < original["active_data_version"]
            else UpdateLifecycleState.SUPERSEDED
        )
        _set_workspace_state_if_present(
            safe_slug,
            original["active_data_version"],
            previous_state,
            workspace_root=workspace_root,
            event=("update rolled back" if previous_state == UpdateLifecycleState.ROLLED_BACK
                   else "update superseded"),
            summary=f"Active pointer changed to immutable data version {target}.",
        )
        _set_workspace_state_if_present(
            safe_slug,
            target,
            UpdateLifecycleState.ACTIVE,
            workspace_root=workspace_root,
            event="version reactivated",
            summary=f"Immutable data version {target} became active through controlled rollback.",
        )
    except Exception as exc:
        _write_json_atomic(metadata_path, original)
        _append_version_event(
            registration, "rollback verification failed",
            f"Rollback to version {target} failed; version {original['active_data_version']} remained active.",
            target_version=target,
            active_version=original["active_data_version"],
        )
        raise ValueError(f"Rollback verification failed; prior active version was restored: {exc}") from exc
    return registered


def version_history(
    slug: str,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> tuple[dict[str, Any], ...]:
    registered = get_persistent_registration(slug, registration_root)
    metadata = _registration_metadata(registered.registration_path)
    rows: list[dict[str, Any]] = []
    for version in metadata["available_data_versions"]:
        record = _record_for_version(registered.registration_path, metadata, version)
        rows.append({
            "data_version": version,
            "state": "Active" if version == metadata["active_data_version"] else "Superseded",
            "activated_at_utc": record.get("activated_at_utc"),
            "data_status": record.get("data_status"),
            "source_owner": record.get("source_provenance", {}).get("owner"),
            "source_date": record.get("source_provenance", {}).get("acquired_date"),
            "source_reference": record.get("source_provenance", {}).get("reference"),
            "source_checksum": record.get("source_checksum"),
            "canonical_checksum": record.get("canonical_checksum"),
            "row_count": record.get("row_count"),
        })
    return tuple(rows)
