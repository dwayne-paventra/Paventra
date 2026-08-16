"""Operational lifecycle and developer handoff for real-import packages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from pilot.canonical_inventory import (
    CANONICAL_COLUMNS,
    CANONICAL_NUMERIC_COLUMNS,
    normalize_treatment,
    validate_canonical_schema,
)
from pilot.municipality_onboarding import (
    export_canonical_inventory,
    load_onboarded_canonical_inventory,
    parse_onboarding_manifest,
)
from pilot.onboarding_manifest_contract import (
    REAL_IMPORT_WORKSPACE_MANIFEST_VERSION,
    validate_manifest_contract,
)
from pilot.source_provenance import compute_source_checksum
from pilot.municipality_spatial import (
    SPATIAL_INPUT_NAME,
    SPATIAL_REVIEW_NAME,
    spatial_readiness_snapshot,
    validate_spatial_workspace,
)


MANIFEST_NAME = "manifest.json"
CANONICAL_REVIEW_NAME = "canonical_review.csv"
MAPPING_REVIEW_NAME = "mapping_review.csv"
VALIDATION_SUMMARY_NAME = "validation_summary.json"
REVIEW_SUMMARY_NAME = "operator_review.md"
REGISTRATION_PACKET_NAME = "registration_packet.md"
HISTORY_NAME = "package_history.jsonl"
METADATA_NAME = "package_metadata.json"


class PackageLifecycleState(str, Enum):
    """Stable states for real municipality import workspaces."""

    DRAFT = "Draft"
    VALIDATION_REQUIRED = "Validation Required"
    VALIDATED = "Validated"
    REVIEW_REQUIRED = "Review Required"
    READY_FOR_REGISTRATION = "Ready for Registration"
    REGISTERED = "Registered"
    ARCHIVED = "Archived"


@dataclass(frozen=True)
class PackageIssue:
    """One operator-facing validation issue."""

    severity: str
    field: str
    message: str

    @property
    def blocking(self) -> bool:
        return self.severity == "blocking"


@dataclass(frozen=True)
class RealImportInspection:
    """Read-only operational view of one real-import package."""

    package_path: Path
    manifest_path: Path
    manifest: Mapping[str, Any]
    lifecycle_state: PackageLifecycleState
    issues: tuple[PackageIssue, ...]
    source_rows: int | None
    canonical_rows: int | None
    current_fingerprint: str | None
    config: Any | None

    @property
    def blocking_issues(self) -> tuple[PackageIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    @property
    def warnings(self) -> tuple[PackageIssue, ...]:
        return tuple(issue for issue in self.issues if not issue.blocking)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_manifest(package_path: str | Path) -> tuple[Path, dict[str, Any]]:
    package = Path(package_path).resolve()
    manifest_path = package / MANIFEST_NAME
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Real-import manifest was not found at '{manifest_path}'.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Real-import manifest '{manifest_path}' contains invalid JSON at line "
            f"{exc.lineno}, column {exc.colno}: {exc.msg}."
        ) from exc
    except OSError as exc:
        raise ValueError(f"Real-import manifest '{manifest_path}' could not be read: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError(f"Real-import manifest '{manifest_path}' must contain a JSON object.")
    return manifest_path, document


def _write_manifest(manifest_path: Path, document: Mapping[str, Any]) -> None:
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(dict(document), indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)


def _update_metadata(
    package: Path,
    *,
    state: PackageLifecycleState,
    validation_result: str,
    road_count: int | None,
) -> None:
    """Refresh non-authoritative Portfolio cache values after lifecycle changes."""

    path = package / METADATA_NAME
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    existing.update({
        "metadata_version": 2,
        "package_type": "real_import",
        "lifecycle_state_cache": state.value,
        "validation_result": validation_result,
        "road_count": road_count,
        "updated_at_utc": _utc_timestamp(),
    })
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def append_package_event(
    package_path: str | Path,
    event: str,
    state: PackageLifecycleState,
    summary: str,
) -> None:
    """Append a human-readable operational event; this is not a security audit log."""

    record = {
        "timestamp_utc": _utc_timestamp(),
        "event": str(event),
        "state": state.value,
        "summary": " ".join(str(summary).split()),
    }
    history_path = Path(package_path).resolve() / HISTORY_NAME
    with history_path.open("a", encoding="utf-8", newline="\n") as history:
        history.write(json.dumps(record, sort_keys=True) + "\n")


def read_package_history(package_path: str | Path) -> tuple[Mapping[str, Any], ...]:
    """Read valid append-only history records for operator presentation."""

    path = Path(package_path).resolve() / HISTORY_NAME
    if not path.is_file():
        return ()
    records: list[Mapping[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Package history '{path}' contains invalid JSON on line {line_number}."
            ) from exc
        if not isinstance(record, Mapping):
            raise ValueError(f"Package history '{path}' line {line_number} must be an object.")
        records.append(record)
    return tuple(records)


def _state(document: Mapping[str, Any]) -> PackageLifecycleState:
    value = document.get("lifecycle_state", PackageLifecycleState.VALIDATION_REQUIRED.value)
    try:
        return PackageLifecycleState(value)
    except ValueError as exc:
        supported = ", ".join(state.value for state in PackageLifecycleState)
        raise ValueError(
            f"Real-import manifest field 'lifecycle_state' has unsupported value "
            f"'{value}'. Supported states: {supported}."
        ) from exc


def _source_path(package: Path, document: Mapping[str, Any]) -> Path:
    value = document.get("source_csv_path", "")
    source = Path(value)
    if source.is_absolute():
        resolved = source.resolve()
    else:
        resolved = (package / source).resolve()
    if resolved.parent != package:
        raise ValueError("Real-import source file must remain directly inside its package workspace.")
    return resolved


_READINESS_FIELDS = (
    "municipality_id",
    "slug",
    "state",
    "entity_type",
    "formal_name",
    "short_name",
    "data_status",
    "source_owner",
    "source_acquired_date",
    "source_reference",
    "source_checksum",
    "source_csv_path",
    "column_mapping",
    "canonical_defaults",
    "map_center",
    "map_zoom",
    "inventory_adapter",
    "scenario_catalog_id",
    "pilot_mode",
    "pilot_label",
    "leadership_label",
    "official_action_label",
    "canonical_checksum",
)


def compute_readiness_fingerprint(package_path: str | Path) -> str:
    """Fingerprint every readiness-sensitive manifest value and actual source bytes."""

    package = Path(package_path).resolve()
    _, document = _read_manifest(package)
    source_checksum = compute_source_checksum(_source_path(package, document))
    snapshot = {field: document.get(field) for field in _READINESS_FIELDS}
    snapshot["actual_source_checksum"] = source_checksum
    snapshot["spatial_artifacts"] = spatial_readiness_snapshot(package)
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _csv_row_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            rows = csv.reader(source)
            next(rows)
            return sum(1 for _ in rows)
    except (OSError, StopIteration, UnicodeError, csv.Error):
        return None


def build_mapping_review(document: Mapping[str, Any]) -> pd.DataFrame:
    """Build a canonical-field review showing mapping/default/derived resolution."""

    mappings = document.get("column_mapping")
    defaults = document.get("canonical_defaults")
    meanings = document.get("source_field_meanings")
    mappings = mappings if isinstance(mappings, Mapping) else {}
    defaults = defaults if isinstance(defaults, Mapping) else {}
    meanings = meanings if isinstance(meanings, Mapping) else {}
    source_for = {canonical: source for source, canonical in mappings.items()}
    rows = []
    for canonical in CANONICAL_COLUMNS:
        source = source_for.get(canonical)
        if source is not None:
            resolution = "mapped"
            default = ""
        elif canonical in defaults:
            resolution = "defaulted"
            default = defaults[canonical]
        elif canonical == "data_status":
            resolution = "derived"
            default = document.get("data_status", "")
        else:
            resolution = "unresolved"
            default = ""
        if canonical in CANONICAL_NUMERIC_COLUMNS:
            transformation = "numeric coercion and range validation"
        elif canonical == "recommended_treatment":
            transformation = "shared treatment-label normalization"
        elif canonical == "data_status":
            transformation = "configured package data status"
        else:
            transformation = "trim/validate through canonical pipeline"
        rows.append({
            "source_field": source or "",
            "source_meaning": str(meanings.get(source, "")) if source else "",
            "canonical_field": canonical,
            "transformation": transformation,
            "default_value": default,
            "resolution": resolution,
            "blocking": resolution == "unresolved",
        })
    return pd.DataFrame(rows)


def _evaluate(package: Path, document: Mapping[str, Any]) -> RealImportInspection:
    issues: list[PackageIssue] = []
    config = None
    source_rows = None
    canonical_rows = None
    fingerprint = None
    manifest_path = package / MANIFEST_NAME
    try:
        version = validate_manifest_contract(document, manifest_path)
        if version != REAL_IMPORT_WORKSPACE_MANIFEST_VERSION:
            raise ValueError(
                f"Real-import package requires manifest version "
                f"{REAL_IMPORT_WORKSPACE_MANIFEST_VERSION}; received {version}."
            )
        if document.get("package_type") != "real_import":
            raise ValueError("Real-import manifest field 'package_type' must be 'real_import'.")
        _state(document)
    except (TypeError, ValueError) as exc:
        issues.append(PackageIssue("blocking", "manifest", str(exc)))

    source_path: Path | None = None
    try:
        source_path = _source_path(package, document)
        actual_checksum = compute_source_checksum(source_path)
        source_rows = _csv_row_count(source_path)
        declared = str(document.get("source_checksum", "")).strip().lower()
        if actual_checksum != declared:
            issues.append(PackageIssue(
                "blocking",
                "source_checksum",
                f"Declared checksum {declared or '<missing>'} does not match source {actual_checksum}.",
            ))
        fingerprint = compute_readiness_fingerprint(package)
    except (OSError, TypeError, ValueError) as exc:
        issues.append(PackageIssue("blocking", "source_csv_path", str(exc)))

    mapping_review = build_mapping_review(document)
    for field in mapping_review.loc[mapping_review["blocking"], "canonical_field"]:
        issues.append(PackageIssue(
            "blocking",
            str(field),
            f"Required canonical field '{field}' is unresolved; map it or provide an explicit default.",
        ))
    for coordinate in ("latitude", "longitude"):
        row = mapping_review.loc[mapping_review["canonical_field"] == coordinate].iloc[0]
        if row["resolution"] == "defaulted":
            issues.append(PackageIssue(
                "warning",
                coordinate,
                f"Canonical field '{coordinate}' is defaulted for every row; confirm map usability.",
            ))

    declared_canonical_checksum = document.get("canonical_checksum")
    canonical_path = package / CANONICAL_REVIEW_NAME
    if declared_canonical_checksum:
        try:
            actual_canonical_checksum = compute_source_checksum(canonical_path)
            if actual_canonical_checksum != declared_canonical_checksum:
                issues.append(PackageIssue(
                    "blocking",
                    "canonical_review_path",
                    "Canonical review artifact changed after validation; revalidation is required.",
                ))
        except ValueError as exc:
            issues.append(PackageIssue("blocking", "canonical_review_path", str(exc)))

    spatial_review_path = package / SPATIAL_REVIEW_NAME
    if (package / SPATIAL_INPUT_NAME).is_file() and spatial_review_path.is_file():
        try:
            spatial_review = json.loads(spatial_review_path.read_text(encoding="utf-8"))
            for issue in spatial_review.get("issues", []):
                issues.append(PackageIssue(
                    str(issue.get("severity", "blocking")),
                    f"spatial.{issue.get('field', 'geometry')}",
                    str(issue.get("message", "Spatial validation failed.")),
                ))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            issues.append(PackageIssue("blocking", "spatial_review", str(exc)))

    if not any(issue.blocking for issue in issues):
        try:
            config = parse_onboarding_manifest(document, manifest_path)
            inventory = load_onboarded_canonical_inventory(config)
            canonical_rows = len(inventory)
            unknown_treatments = sorted({
                str(value).strip()
                for value in inventory["recommended_treatment"]
                if normalize_treatment(value) == str(value).strip()
                and str(value).strip() not in {
                    "Not Assigned", "Crack Seal", "Mill & Fill", "Overlay", "Reconstruction"
                }
            })
            if unknown_treatments:
                issues.append(PackageIssue(
                    "warning",
                    "recommended_treatment",
                    "Unrecognized treatment labels are retained: " + ", ".join(unknown_treatments),
                ))
        except (OSError, TypeError, ValueError) as exc:
            issues.append(PackageIssue("blocking", "canonical_inventory", str(exc)))

    declared_state = _state(document) if not any(
        issue.field == "manifest" for issue in issues
    ) else PackageLifecycleState.VALIDATION_REQUIRED
    effective_state = declared_state
    protected_fingerprint = None
    if declared_state in {
        PackageLifecycleState.VALIDATED,
        PackageLifecycleState.REVIEW_REQUIRED,
    }:
        protected_fingerprint = document.get("validated_fingerprint")
    elif declared_state == PackageLifecycleState.READY_FOR_REGISTRATION:
        protected_fingerprint = document.get("readiness_fingerprint")
    if protected_fingerprint is not None or declared_state in {
        PackageLifecycleState.VALIDATED,
        PackageLifecycleState.REVIEW_REQUIRED,
        PackageLifecycleState.READY_FOR_REGISTRATION,
    }:
        if (
            any(issue.blocking for issue in issues)
            or not fingerprint
            or protected_fingerprint != fingerprint
        ):
            effective_state = PackageLifecycleState.VALIDATION_REQUIRED
            issues.append(PackageIssue(
                "blocking",
                "readiness_fingerprint",
                "Readiness-sensitive package content changed after review; revalidation is required.",
            ))
    return RealImportInspection(
        package_path=package,
        manifest_path=manifest_path,
        manifest=document,
        lifecycle_state=effective_state,
        issues=tuple(issues),
        source_rows=source_rows,
        canonical_rows=canonical_rows,
        current_fingerprint=fingerprint,
        config=config,
    )


def inspect_real_import_package(package_path: str | Path) -> RealImportInspection:
    """Inspect a package and calculate its effective state without trusting stale readiness."""

    package = Path(package_path).resolve()
    _, document = _read_manifest(package)
    return _evaluate(package, document)


def initialize_real_import_workspace_artifacts(
    package_path: str | Path,
) -> RealImportInspection:
    """Write draft-safe review artifacts without claiming that validation passed."""

    inspection = inspect_real_import_package(package_path)
    _write_mapping_review(inspection.package_path, inspection.manifest)
    _write_validation_summary(inspection)
    _write_operator_review(inspection)
    _write_invalidated_registration_packet(inspection.package_path, inspection.manifest)
    _update_metadata(
        inspection.package_path,
        state=inspection.lifecycle_state,
        validation_result="NOT RUN",
        road_count=inspection.source_rows,
    )
    return inspection


def _write_validation_summary(inspection: RealImportInspection) -> Path:
    path = inspection.package_path / VALIDATION_SUMMARY_NAME
    payload = {
        "validated_at_utc": _utc_timestamp(),
        "state": inspection.lifecycle_state.value,
        "source_row_count": inspection.source_rows,
        "canonical_row_count": inspection.canonical_rows,
        "blocking_issue_count": len(inspection.blocking_issues),
        "warning_count": len(inspection.warnings),
        "issues": [issue.__dict__ for issue in inspection.issues],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _write_mapping_review(package: Path, document: Mapping[str, Any]) -> Path:
    path = package / MAPPING_REVIEW_NAME
    build_mapping_review(document).to_csv(path, index=False, lineterminator="\n")
    return path


def _invalidate_document(document: dict[str, Any]) -> None:
    document["lifecycle_state"] = PackageLifecycleState.VALIDATION_REQUIRED.value
    document.pop("validated_fingerprint", None)
    document.pop("readiness_fingerprint", None)
    document.pop("canonical_checksum", None)


def refresh_real_import_readiness(package_path: str | Path) -> RealImportInspection:
    """Persist stale-ready invalidation so later sessions cannot display old readiness."""

    package = Path(package_path).resolve()
    manifest_path, document = _read_manifest(package)
    inspection = _evaluate(package, document)
    if (
        document.get("lifecycle_state") in {
            PackageLifecycleState.VALIDATED.value,
            PackageLifecycleState.REVIEW_REQUIRED.value,
            PackageLifecycleState.READY_FOR_REGISTRATION.value,
        }
        and inspection.lifecycle_state == PackageLifecycleState.VALIDATION_REQUIRED
    ):
        _invalidate_document(document)
        _write_manifest(manifest_path, document)
        _write_invalidated_registration_packet(package, document)
        _update_metadata(
            package,
            state=PackageLifecycleState.VALIDATION_REQUIRED,
            validation_result="STALE — REVALIDATION REQUIRED",
            road_count=inspection.source_rows,
        )
        append_package_event(
            package,
            "readiness invalidated",
            PackageLifecycleState.VALIDATION_REQUIRED,
            "Readiness-sensitive source or configuration content changed; revalidation required.",
        )
        inspection = _evaluate(package, document)
        _write_validation_summary(inspection)
    return inspection


def validate_real_import_package(package_path: str | Path) -> RealImportInspection:
    """Run all readiness gates and persist canonical/review artifacts on success."""

    package = Path(package_path).resolve()
    manifest_path, document = _read_manifest(package)
    inspection = _evaluate(package, document)
    _write_mapping_review(package, document)
    if inspection.blocking_issues:
        _invalidate_document(document)
        _write_manifest(manifest_path, document)
        failed = _evaluate(package, document)
        _write_validation_summary(failed)
        _write_invalidated_registration_packet(package, document)
        _update_metadata(
            package,
            state=PackageLifecycleState.VALIDATION_REQUIRED,
            validation_result="FAIL",
            road_count=failed.source_rows,
        )
        append_package_event(
            package,
            "validation failed",
            PackageLifecycleState.VALIDATION_REQUIRED,
            f"{len(failed.blocking_issues)} blocking issue(s); {len(failed.warnings)} warning(s).",
        )
        return failed

    assert inspection.config is not None
    inventory = load_onboarded_canonical_inventory(inspection.config)
    canonical_path = package / CANONICAL_REVIEW_NAME
    export_canonical_inventory(
        inventory,
        canonical_path,
        force=True,
        expected_data_status=inspection.config.normalized_data_status,
        municipality_slug=inspection.config.slug,
    )
    exported = pd.read_csv(canonical_path)
    validate_canonical_schema(
        exported,
        expected_data_status=inspection.config.normalized_data_status,
        municipality_slug=inspection.config.slug,
    )
    spatial_review = validate_spatial_workspace(package, canonical_path)
    if spatial_review is not None and spatial_review.blocking_issues:
        _invalidate_document(document)
        _write_manifest(manifest_path, document)
        failed = _evaluate(package, document)
        _write_validation_summary(failed)
        _write_invalidated_registration_packet(package, document)
        _update_metadata(
            package,
            state=PackageLifecycleState.VALIDATION_REQUIRED,
            validation_result="FAIL",
            road_count=failed.source_rows,
        )
        append_package_event(
            package, "spatial validation failed",
            PackageLifecycleState.VALIDATION_REQUIRED,
            f"{len(spatial_review.blocking_issues)} blocking spatial issue(s).",
        )
        return failed
    document["lifecycle_state"] = PackageLifecycleState.VALIDATED.value
    document["canonical_checksum"] = compute_source_checksum(canonical_path)
    document.pop("validated_fingerprint", None)
    document.pop("readiness_fingerprint", None)
    _write_manifest(manifest_path, document)
    document["validated_fingerprint"] = compute_readiness_fingerprint(package)
    _write_manifest(manifest_path, document)
    validated = _evaluate(package, document)
    _write_validation_summary(validated)
    _write_operator_review(validated)
    _write_invalidated_registration_packet(package, document)
    _update_metadata(
        package,
        state=PackageLifecycleState.VALIDATED,
        validation_result="PASS",
        road_count=validated.canonical_rows,
    )
    append_package_event(
        package,
        "validated",
        PackageLifecycleState.VALIDATED,
        f"Source and canonical exports passed with {len(validated.warnings)} warning(s).",
    )
    return validated


def begin_real_import_review(package_path: str | Path) -> RealImportInspection:
    """Move a currently validated package into explicit operator review."""

    package = Path(package_path).resolve()
    manifest_path, document = _read_manifest(package)
    inspection = refresh_real_import_readiness(package)
    if inspection.blocking_issues or inspection.lifecycle_state != PackageLifecycleState.VALIDATED:
        raise ValueError("Real-import package must be Validated before review can begin.")
    if document.get("validated_fingerprint") != inspection.current_fingerprint:
        raise ValueError("Validated package content changed; validate again before review.")
    document["lifecycle_state"] = PackageLifecycleState.REVIEW_REQUIRED.value
    _write_manifest(manifest_path, document)
    reviewed = _evaluate(package, document)
    _write_operator_review(reviewed)
    _update_metadata(
        package,
        state=PackageLifecycleState.REVIEW_REQUIRED,
        validation_result="PASS",
        road_count=reviewed.canonical_rows,
    )
    append_package_event(
        package,
        "review opened",
        PackageLifecycleState.REVIEW_REQUIRED,
        "Operator review opened; permanent registration remains blocked.",
    )
    return reviewed


def mark_real_import_ready(package_path: str | Path) -> RealImportInspection:
    """Mark a reviewed package ready only when every current readiness gate passes."""

    package = Path(package_path).resolve()
    manifest_path, document = _read_manifest(package)
    inspection = _evaluate(package, document)
    if inspection.lifecycle_state != PackageLifecycleState.REVIEW_REQUIRED:
        raise ValueError("Real-import package must be in Review Required before it can be marked ready.")
    if inspection.blocking_issues:
        raise ValueError(
            "Real-import package has blocking readiness issues: "
            + "; ".join(issue.message for issue in inspection.blocking_issues)
        )
    if document.get("validated_fingerprint") != inspection.current_fingerprint:
        raise ValueError("Package changed after validation; validate it again before registration readiness.")
    canonical_path = package / CANONICAL_REVIEW_NAME
    if not canonical_path.is_file():
        raise ValueError("Canonical review artifact is missing; validate the package again.")
    assert inspection.config is not None
    canonical = pd.read_csv(canonical_path)
    validate_canonical_schema(
        canonical,
        expected_data_status=inspection.config.normalized_data_status,
        municipality_slug=inspection.config.slug,
    )
    document["lifecycle_state"] = PackageLifecycleState.READY_FOR_REGISTRATION.value
    document["readiness_fingerprint"] = inspection.current_fingerprint
    _write_manifest(manifest_path, document)
    ready = _evaluate(package, document)
    _write_operator_review(ready)
    _write_registration_packet(ready)
    _update_metadata(
        package,
        state=PackageLifecycleState.READY_FOR_REGISTRATION,
        validation_result="PASS",
        road_count=ready.canonical_rows,
    )
    append_package_event(
        package,
        "marked ready for registration",
        PackageLifecycleState.READY_FOR_REGISTRATION,
        "All readiness gates passed; developer-reviewed source registration is still required.",
    )
    return ready


def suggested_registry_snippet(slug: str, manifest_path: str | Path) -> str:
    """Return review-only Python text; the helper never writes application source."""

    path = Path(manifest_path).resolve()
    return (
        "# Suggested developer-reviewed registration only; do not paste without review.\n"
        "from pathlib import Path\n"
        "from pilot.municipality_onboarding import load_onboarding_manifest\n\n"
        f"_reviewed_{slug} = load_onboarding_manifest(\n"
        f"    Path(r\"{path}\")\n"
        ")\n"
        f"MUNICIPALITIES[_reviewed_{slug}.slug] = _reviewed_{slug}\n"
    )


def _review_lines(inspection: RealImportInspection) -> list[str]:
    document = inspection.manifest
    checksum = str(document.get("source_checksum", ""))
    return [
        f"# Real Municipality Review — {document.get('formal_name', document.get('slug', 'Unknown'))}",
        "",
        f"- Municipality slug: `{document.get('slug', '')}`",
        f"- Entity type: {document.get('entity_type', '')}",
        f"- Data status: {document.get('data_status', '')}",
        f"- Source owner: {document.get('source_owner', '')}",
        f"- Acquisition date: {document.get('source_acquired_date', '')}",
        f"- Source reference: {document.get('source_reference', '')}",
        f"- Source checksum: `{checksum}`",
        f"- Source rows: {inspection.source_rows if inspection.source_rows is not None else 'Unavailable'}",
        f"- Canonical rows: {inspection.canonical_rows if inspection.canonical_rows is not None else 'Unavailable'}",
        f"- Mappings: {len(document.get('column_mapping', {}))}",
        f"- Defaults: {len(document.get('canonical_defaults', {}))}",
        f"- Scenario catalog: `{document.get('scenario_catalog_id', '')}`",
        f"- Map: {document.get('map_center', '')} at zoom {document.get('map_zoom', '')}",
        f"- Blocking issues: {len(inspection.blocking_issues)}",
        f"- Warnings: {len(inspection.warnings)}",
        f"- Readiness state: **{inspection.lifecycle_state.value}**",
    ]


def _write_operator_review(inspection: RealImportInspection) -> Path:
    path = inspection.package_path / REVIEW_SUMMARY_NAME
    lines = _review_lines(inspection)
    if inspection.issues:
        lines += ["", "## Validation issues"]
        lines += [
            f"- **{issue.severity.upper()}** `{issue.field}` — {issue.message}"
            for issue in inspection.issues
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


_DEVELOPER_CHECKLIST = (
    "Inspect manifest",
    "Inspect mappings and defaults",
    "Confirm source checksum",
    "Add the reviewed registry entry",
    "Run registry and startup validation",
    "Run the complete test suite",
    "Run Streamlit AppTest",
    "Generate and inspect the municipality report",
    "Run the HTTP health check",
    "Inspect the Git diff",
    "Commit only after review",
)


def _write_registration_packet(inspection: RealImportInspection) -> Path:
    document = inspection.manifest
    path = inspection.package_path / REGISTRATION_PACKET_NAME
    lines = [
        f"# Developer Registration Handoff — {document.get('formal_name', '')}",
        "",
        "> Registration is not automatic. This packet is an operator handoff, not code review.",
        "",
        f"- Package path: `{inspection.package_path}`",
        f"- Manifest path: `{inspection.manifest_path}`",
        f"- Municipality slug: `{document.get('slug', '')}`",
        f"- Readiness: **{inspection.lifecycle_state.value}**",
        f"- Source checksum: `{document.get('source_checksum', '')}`",
        f"- Canonical artifact: `{inspection.package_path / CANONICAL_REVIEW_NAME}`",
        f"- Validation summary: `{inspection.package_path / VALIDATION_SUMMARY_NAME}`",
        f"- Mapping review: `{inspection.package_path / MAPPING_REVIEW_NAME}`",
        "",
        "## Suggested registry snippet",
        "",
        "```python",
        suggested_registry_snippet(str(document.get("slug", "municipality")), inspection.manifest_path).rstrip(),
        "```",
        "",
        "## Developer verification checklist",
        "",
        *[f"- [ ] {item}" for item in _DEVELOPER_CHECKLIST],
        "",
        "## Minimal developer instructions",
        "",
        "1. Review every artifact above and choose a durable reviewed data location.",
        "2. Adapt the suggested snippet to the permanent registry source; do not register from an unreviewed working path.",
        "3. Run the checklist and inspect the diff before committing.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_invalidated_registration_packet(package: Path, document: Mapping[str, Any]) -> Path:
    path = package / REGISTRATION_PACKET_NAME
    path.write_text(
        "# Developer Registration Handoff — NOT READY\n\n"
        f"- Municipality slug: `{document.get('slug', '')}`\n"
        f"- Readiness: **{document.get('lifecycle_state', PackageLifecycleState.VALIDATION_REQUIRED.value)}**\n\n"
        "This package is not ready for registration. Revalidate and complete operator review.\n",
        encoding="utf-8",
    )
    return path


def registration_packet_path(package_path: str | Path) -> Path:
    """Return a packet only when effective readiness is current and valid."""

    inspection = refresh_real_import_readiness(package_path)
    if inspection.lifecycle_state != PackageLifecycleState.READY_FOR_REGISTRATION:
        raise ValueError(
            f"Real-import package is '{inspection.lifecycle_state.value}', not Ready for Registration."
        )
    path = inspection.package_path / REGISTRATION_PACKET_NAME
    if not path.is_file():
        _write_registration_packet(inspection)
    return path


def record_package_reopened(package_path: str | Path) -> RealImportInspection:
    """Refresh safety state and record an explicit operator reopen event."""

    inspection = refresh_real_import_readiness(package_path)
    append_package_event(
        inspection.package_path,
        "reopened",
        inspection.lifecycle_state,
        "Operator reopened the persisted real-import workspace.",
    )
    return inspection
