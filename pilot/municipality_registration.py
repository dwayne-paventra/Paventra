"""Persistent, filesystem-backed promotion of reviewed municipality packages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from pilot.canonical_inventory import validate_canonical_schema
from pilot.municipality_config import MunicipalityConfig
from pilot.municipality_onboarding import load_onboarding_manifest
from pilot.municipality_package_lifecycle import (
    CANONICAL_REVIEW_NAME,
    HISTORY_NAME,
    MAPPING_REVIEW_NAME,
    PackageLifecycleState,
    REGISTRATION_PACKET_NAME,
    REVIEW_SUMMARY_NAME,
    VALIDATION_SUMMARY_NAME,
    append_package_event,
    read_package_history,
    refresh_real_import_readiness,
)
from pilot.source_provenance import compute_source_checksum


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSISTENT_MUNICIPALITIES_ROOT = PROJECT_ROOT / "data" / "municipalities"
REGISTRATION_METADATA_NAME = "registration.json"
REGISTRATION_SCHEMA_VERSION = 1
INITIAL_REGISTRATION_VERSION = 1
INITIAL_DATA_VERSION = 1


class RegistrationState:
    """Bounded operational acceptance states, not municipal certification."""

    PENDING_ACCEPTANCE = "pending_acceptance"
    ACCEPTED = "accepted"
    VALUES = frozenset({PENDING_ACCEPTANCE, ACCEPTED})


@dataclass(frozen=True)
class RegistrationIssue:
    severity: str
    field: str
    message: str

    @property
    def blocking(self) -> bool:
        return self.severity == "blocking"


@dataclass(frozen=True)
class RegistrationPreview:
    package_path: Path
    intended_path: Path
    slug: str
    formal_name: str
    short_name: str
    entity_type: str
    data_status: str
    source_owner: str
    source_date: str
    source_reference: str
    source_checksum: str
    canonical_checksum: str
    segment_count: int | None
    map_center: tuple[float, float] | tuple
    map_zoom: int | None
    scenario_catalog_id: str
    inventory_adapter: str
    leadership_label: str
    official_action_label: str
    registration_version: int
    issues: tuple[RegistrationIssue, ...]

    @property
    def blocking_issues(self) -> tuple[RegistrationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    @property
    def result(self) -> str:
        return "BLOCKED" if self.blocking_issues else "PASS"


@dataclass(frozen=True)
class RegisteredMunicipality:
    config: MunicipalityConfig
    registration_path: Path
    metadata_path: Path
    registration_version: int
    active_data_version: int
    registration_state: str
    registered_at_utc: str
    accepted_at_utc: str | None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{label} was not found at '{path}'.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{label} '{path}' contains invalid JSON at line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}."
        ) from exc
    except OSError as exc:
        raise ValueError(f"{label} '{path}' could not be read: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} '{path}' must contain a JSON object.")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(dict(value), indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _normalized_slug(slug: object) -> str:
    from pilot.municipality_admin import suggest_municipality_slug

    if not isinstance(slug, str) or not slug.strip():
        raise ValueError("Registration field 'slug' must be a non-empty string.")
    normalized = suggest_municipality_slug(slug)
    if normalized != slug:
        raise ValueError(f"Registration slug '{slug}' is invalid; use '{normalized}'.")
    return slug


def _safe_registration_path(slug: str, root: str | Path) -> Path:
    safe_slug = _normalized_slug(slug)
    resolved_root = Path(root).resolve()
    destination = (resolved_root / safe_slug).resolve()
    if destination.parent != resolved_root:
        raise ValueError("Persistent municipality path must remain inside the registration root.")
    return destination


def _safe_relative_path(base: Path, value: object, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Persistent registration field '{field}' must be a non-empty path.")
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"Persistent registration field '{field}' must be relative.")
    resolved = (base / relative).resolve()
    if resolved == base or base not in resolved.parents:
        raise ValueError(f"Persistent registration field '{field}' escapes its registration directory.")
    return resolved


def _registration_metadata(directory: Path) -> dict[str, Any]:
    metadata_path = directory / REGISTRATION_METADATA_NAME
    metadata = _read_json(metadata_path, "Persistent registration metadata")
    required = (
        "registration_schema_version",
        "slug",
        "registration_version",
        "active_data_version",
        "registration_state",
        "registered_at_utc",
        "active_manifest_path",
        "canonical_inventory_path",
        "source_checksum",
        "canonical_checksum",
        "readiness_fingerprint",
        "configuration_snapshot",
        "mapping_snapshot",
        "defaults_snapshot",
        "source_provenance",
        "validation_result",
    )
    missing = [field for field in required if field not in metadata]
    if missing:
        raise ValueError(
            f"Persistent registration '{metadata_path}' is missing fields: {', '.join(missing)}."
        )
    if metadata["registration_schema_version"] != REGISTRATION_SCHEMA_VERSION:
        raise ValueError(
            f"Persistent registration '{metadata_path}' has unsupported schema version "
            f"'{metadata['registration_schema_version']}'."
        )
    slug = _normalized_slug(metadata["slug"])
    if directory.name != slug and not directory.name.startswith(f".{slug}.staging-"):
        raise ValueError(
            f"Persistent registration slug '{slug}' does not match directory '{directory.name}'."
        )
    for field in ("registration_version", "active_data_version"):
        value = metadata[field]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"Persistent registration field '{field}' must be a positive integer.")
    if metadata["registration_state"] not in RegistrationState.VALUES:
        raise ValueError(
            f"Persistent registration field 'registration_state' has unsupported value "
            f"'{metadata['registration_state']}'."
        )
    if metadata["validation_result"] != "PASS":
        raise ValueError("Persistent registration validation_result must be 'PASS'.")
    available = metadata.get("available_data_versions", [metadata["active_data_version"]])
    if (
        not isinstance(available, list)
        or not available
        or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in available)
        or len(set(available)) != len(available)
        or available != sorted(available)
    ):
        raise ValueError(
            "Persistent registration field 'available_data_versions' must be a sorted "
            "list of unique positive integers."
        )
    if metadata["active_data_version"] not in available:
        raise ValueError("Persistent registration active_data_version is not available.")
    metadata["available_data_versions"] = available
    metadata.setdefault("previous_active_data_version", None)
    metadata.setdefault("active_version_activated_at_utc", metadata["registered_at_utc"])
    return metadata


def load_persistent_registration_directory(directory: str | Path) -> RegisteredMunicipality:
    """Load and validate one immutable persistent registration snapshot."""

    registration_path = Path(directory).resolve()
    metadata = _registration_metadata(registration_path)
    metadata_path = registration_path / REGISTRATION_METADATA_NAME
    manifest_path = _safe_relative_path(
        registration_path, metadata["active_manifest_path"], "active_manifest_path"
    )
    canonical_path = _safe_relative_path(
        registration_path,
        metadata["canonical_inventory_path"],
        "canonical_inventory_path",
    )
    config = replace(
        load_onboarding_manifest(manifest_path),
        data_version=metadata["active_data_version"],
    )
    if config.slug != metadata["slug"]:
        raise ValueError(
            f"Persistent registration '{metadata_path}' slug does not match its manifest."
        )
    version_root = registration_path / "versions" / str(metadata["active_data_version"])
    if version_root.resolve() not in manifest_path.parents:
        raise ValueError("Active manifest is not inside its declared version directory.")
    if version_root.resolve() not in config.data_path.resolve().parents:
        raise ValueError("Registered source path is not inside its active version directory.")
    actual_versions = sorted(
        int(item.name)
        for item in (registration_path / "versions").iterdir()
        if item.is_dir() and item.name.isdigit() and int(item.name) > 0
    )
    if actual_versions != metadata["available_data_versions"]:
        raise ValueError(
            f"Persistent registration '{config.slug}' available versions do not match "
            "its immutable version directories."
        )
    if compute_source_checksum(config.data_path) != metadata["source_checksum"]:
        raise ValueError(f"Persistent registration '{config.slug}' source checksum does not match.")
    if compute_source_checksum(canonical_path) != metadata["canonical_checksum"]:
        raise ValueError(f"Persistent registration '{config.slug}' canonical checksum does not match.")

    manifest_document = _read_json(manifest_path, "Registered manifest snapshot")
    expected_config = {
        field: manifest_document.get(field)
        for field in metadata["configuration_snapshot"]
    }
    if metadata["configuration_snapshot"] != expected_config:
        raise ValueError(
            f"Persistent registration '{config.slug}' configuration snapshot does not match its manifest."
        )
    if metadata["mapping_snapshot"] != manifest_document.get("column_mapping", {}):
        raise ValueError(f"Persistent registration '{config.slug}' mapping snapshot does not match.")
    if metadata["defaults_snapshot"] != manifest_document.get("canonical_defaults", {}):
        raise ValueError(f"Persistent registration '{config.slug}' defaults snapshot does not match.")
    expected_provenance = {
        "owner": manifest_document.get("source_owner"),
        "acquired_date": manifest_document.get("source_acquired_date"),
        "reference": manifest_document.get("source_reference"),
        "checksum": manifest_document.get("source_checksum"),
    }
    if metadata["source_provenance"] != expected_provenance:
        raise ValueError(f"Persistent registration '{config.slug}' provenance snapshot does not match.")

    import pandas as pd

    canonical = pd.read_csv(canonical_path)
    validate_canonical_schema(
        canonical,
        expected_data_status=config.normalized_data_status,
        municipality_slug=config.slug,
    )
    from pilot.municipality_onboarding import validate_onboarding_configuration

    validate_onboarding_configuration(config)
    return RegisteredMunicipality(
        config=config,
        registration_path=registration_path,
        metadata_path=metadata_path,
        registration_version=metadata["registration_version"],
        active_data_version=metadata["active_data_version"],
        registration_state=metadata["registration_state"],
        registered_at_utc=metadata["registered_at_utc"],
        accepted_at_utc=metadata.get("accepted_at_utc"),
    )


def load_persistent_municipalities(
    root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    *,
    built_in_slugs: Mapping[str, MunicipalityConfig] | set[str] | frozenset[str] = frozenset(),
) -> dict[str, MunicipalityConfig]:
    """Discover all persistent registrations or fail clearly on any malformed entry."""

    registration_root = Path(root).resolve()
    if not registration_root.exists():
        return {}
    if not registration_root.is_dir():
        raise ValueError(f"Persistent municipality root '{registration_root}' must be a directory.")
    protected = set(built_in_slugs)
    registrations: dict[str, MunicipalityConfig] = {}
    for directory in sorted(registration_root.iterdir()):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        registered = load_persistent_registration_directory(directory)
        slug = registered.config.slug
        if slug in protected:
            raise ValueError(
                f"Persistent municipality slug '{slug}' collides with a built-in registration."
            )
        if slug in registrations:
            raise ValueError(f"Duplicate persistent municipality slug '{slug}'.")
        registrations[slug] = registered.config
    return registrations


def get_persistent_registration(
    slug: str,
    root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> RegisteredMunicipality:
    return load_persistent_registration_directory(_safe_registration_path(slug, root))


def preview_registration(
    package_path: str | Path,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    protected_slugs: Mapping[str, MunicipalityConfig] | set[str] | frozenset[str] = frozenset(),
    generated_root: str | Path | None = None,
    archived_root: str | Path | None = None,
    record_event: bool = True,
) -> RegistrationPreview:
    """Recheck every readiness gate without promoting any registration files."""

    package = Path(package_path).resolve()
    issues: list[RegistrationIssue] = []
    try:
        manifest = _read_json(package / "manifest.json", "Real-import manifest")
    except ValueError as exc:
        manifest = {}
        issues.append(RegistrationIssue("blocking", "manifest", str(exc)))
    slug_value = manifest.get("slug", package.name)
    slug_is_valid = True
    try:
        slug = _normalized_slug(slug_value)
        intended = _safe_registration_path(slug, registration_root)
    except ValueError as exc:
        slug_is_valid = False
        slug = str(slug_value)
        intended = Path(registration_root).resolve() / "<invalid>"
        issues.append(RegistrationIssue("blocking", "slug", str(exc)))

    if manifest.get("package_type") != "real_import":
        issues.append(RegistrationIssue(
            "blocking",
            "package_type",
            "Only a real_import package may be permanently registered; illustrative demos are rejected.",
        ))
    inspection = None
    try:
        inspection = refresh_real_import_readiness(package)
        if inspection.lifecycle_state != PackageLifecycleState.READY_FOR_REGISTRATION:
            issues.append(RegistrationIssue(
                "blocking",
                "lifecycle_state",
                f"Package must be exactly Ready for Registration; current state is "
                f"'{inspection.lifecycle_state.value}'.",
            ))
        for issue in inspection.blocking_issues:
            issues.append(RegistrationIssue("blocking", issue.field, issue.message))
        if manifest.get("readiness_fingerprint") != inspection.current_fingerprint:
            issues.append(RegistrationIssue(
                "blocking", "readiness_fingerprint", "Readiness fingerprint is stale or missing."
            ))
    except (OSError, TypeError, ValueError) as exc:
        issues.append(RegistrationIssue("blocking", "readiness", str(exc)))

    protected = set(protected_slugs)
    if slug in protected:
        issues.append(RegistrationIssue(
            "blocking", "slug", f"Municipality slug '{slug}' is already permanently registered."
        ))
    if intended.exists():
        issues.append(RegistrationIssue(
            "blocking", "registration_path", f"Durable registration path already exists: '{intended}'."
        ))
    if generated_root is None or archived_root is None:
        from pilot.municipality_admin import (
            ARCHIVED_MUNICIPALITIES_ROOT,
            GENERATED_MUNICIPALITIES_ROOT,
        )

        generated_root = GENERATED_MUNICIPALITIES_ROOT if generated_root is None else generated_root
        archived_root = ARCHIVED_MUNICIPALITIES_ROOT if archived_root is None else archived_root
    if slug_is_valid:
        generated_collision = _safe_registration_path(slug, generated_root)
        archived_collision = _safe_registration_path(slug, archived_root)
        if generated_collision.exists() and generated_collision.resolve() != package:
            issues.append(RegistrationIssue(
                "blocking", "slug", f"Generated municipality package already uses slug '{slug}'."
            ))
        if archived_collision.exists():
            issues.append(RegistrationIssue(
                "blocking", "slug", f"Archived illustrative demo already uses slug '{slug}'."
            ))

    try:
        events = read_package_history(package)
        event_names = {str(event.get("event", "")) for event in events}
        if "review opened" not in event_names or "marked ready for registration" not in event_names:
            issues.append(RegistrationIssue(
                "blocking",
                "operator_review",
                "Package history does not show completed operator review and readiness events.",
            ))
    except ValueError as exc:
        issues.append(RegistrationIssue("blocking", "operator_review", str(exc)))
    canonical_path = package / CANONICAL_REVIEW_NAME
    canonical_checksum = str(manifest.get("canonical_checksum", ""))
    segment_count = None
    try:
        actual_canonical = compute_source_checksum(canonical_path)
        if actual_canonical != canonical_checksum:
            issues.append(RegistrationIssue(
                "blocking", "canonical_checksum", "Canonical artifact checksum does not match readiness snapshot."
            ))
        import pandas as pd

        canonical = pd.read_csv(canonical_path)
        segment_count = len(canonical)
        if inspection is not None and inspection.config is not None:
            validate_canonical_schema(
                canonical,
                expected_data_status=inspection.config.normalized_data_status,
                municipality_slug=inspection.config.slug,
            )
    except (OSError, TypeError, ValueError) as exc:
        issues.append(RegistrationIssue("blocking", "canonical_inventory", str(exc)))

    preview = RegistrationPreview(
        package_path=package,
        intended_path=intended,
        slug=slug,
        formal_name=str(manifest.get("formal_name", "")),
        short_name=str(manifest.get("short_name", "")),
        entity_type=str(manifest.get("entity_type", "")),
        data_status=str(manifest.get("data_status", "")),
        source_owner=str(manifest.get("source_owner", "")),
        source_date=str(manifest.get("source_acquired_date", "")),
        source_reference=str(manifest.get("source_reference", "")),
        source_checksum=str(manifest.get("source_checksum", "")),
        canonical_checksum=canonical_checksum,
        segment_count=segment_count,
        map_center=tuple(manifest.get("map_center", ())),
        map_zoom=manifest.get("map_zoom"),
        scenario_catalog_id=str(manifest.get("scenario_catalog_id", "")),
        inventory_adapter=str(manifest.get("inventory_adapter", "")),
        leadership_label=str(manifest.get("leadership_label", "")),
        official_action_label=str(manifest.get("official_action_label", "")),
        registration_version=INITIAL_REGISTRATION_VERSION,
        issues=tuple(issues),
    )
    if record_event and (package / HISTORY_NAME).exists():
        append_package_event(
            package,
            "registration previewed" if preview.result == "PASS" else "registration blocked",
            inspection.lifecycle_state if inspection is not None else PackageLifecycleState.VALIDATION_REQUIRED,
            f"Registration preview result: {preview.result}; {len(preview.blocking_issues)} blocking issue(s).",
        )
    return preview


def _copy_registration_snapshot(package: Path, staging: Path, preview: RegistrationPreview) -> None:
    version_root = staging / "versions" / str(INITIAL_DATA_VERSION)
    version_root.mkdir(parents=True, exist_ok=False)
    source_manifest = _read_json(package / "manifest.json", "Real-import manifest")
    source_name = str(source_manifest["source_csv_path"])
    source_path = (package / source_name).resolve()
    if source_path.parent != package:
        raise ValueError("Real-import source path escapes its package workspace.")

    copies = {
        source_path: version_root / "source_roads.csv",
        package / "source_roads.raw.csv": version_root / "source_roads.raw.csv",
        package / CANONICAL_REVIEW_NAME: version_root / "canonical_inventory.csv",
        package / MAPPING_REVIEW_NAME: version_root / MAPPING_REVIEW_NAME,
        package / VALIDATION_SUMMARY_NAME: version_root / VALIDATION_SUMMARY_NAME,
        package / REVIEW_SUMMARY_NAME: version_root / REVIEW_SUMMARY_NAME,
        package / REGISTRATION_PACKET_NAME: version_root / REGISTRATION_PACKET_NAME,
    }
    for source, destination in copies.items():
        if not source.is_file():
            raise ValueError(f"Required registration artifact is missing: '{source}'.")
        shutil.copy2(source, destination)

    runtime_manifest = dict(source_manifest)
    runtime_manifest["source_csv_path"] = "source_roads.csv"
    runtime_manifest["lifecycle_state"] = PackageLifecycleState.REGISTERED.value
    runtime_manifest_path = version_root / "manifest.json"
    _write_json_atomic(runtime_manifest_path, runtime_manifest)
    metadata = {
        "registration_schema_version": REGISTRATION_SCHEMA_VERSION,
        "slug": preview.slug,
        "registration_version": INITIAL_REGISTRATION_VERSION,
        "active_data_version": INITIAL_DATA_VERSION,
        "available_data_versions": [INITIAL_DATA_VERSION],
        "previous_active_data_version": None,
        "active_version_activated_at_utc": _utc_timestamp(),
        "registration_state": RegistrationState.PENDING_ACCEPTANCE,
        "registered_at_utc": _utc_timestamp(),
        "accepted_at_utc": None,
        "active_manifest_path": f"versions/{INITIAL_DATA_VERSION}/manifest.json",
        "canonical_inventory_path": f"versions/{INITIAL_DATA_VERSION}/canonical_inventory.csv",
        "source_checksum": preview.source_checksum,
        "canonical_checksum": preview.canonical_checksum,
        "readiness_fingerprint": source_manifest["readiness_fingerprint"],
        "configuration_snapshot": {
            field: source_manifest.get(field)
            for field in (
                "municipality_id", "slug", "state", "entity_type", "formal_name",
                "short_name", "map_center", "map_zoom", "inventory_adapter",
                "scenario_catalog_id", "pilot_mode", "pilot_label",
                "leadership_label", "official_action_label", "data_status",
            )
        },
        "mapping_snapshot": source_manifest.get("column_mapping", {}),
        "defaults_snapshot": source_manifest.get("canonical_defaults", {}),
        "source_provenance": {
            "owner": source_manifest.get("source_owner"),
            "acquired_date": source_manifest.get("source_acquired_date"),
            "reference": source_manifest.get("source_reference"),
            "checksum": source_manifest.get("source_checksum"),
        },
        "validation_result": "PASS",
        "source_package_path": str(package),
    }
    version_record = {
        "data_version": INITIAL_DATA_VERSION,
        "manifest_path": metadata["active_manifest_path"],
        "canonical_inventory_path": metadata["canonical_inventory_path"],
        "created_at_utc": metadata["registered_at_utc"],
        "activated_at_utc": metadata["active_version_activated_at_utc"],
        "source_checksum": preview.source_checksum,
        "canonical_checksum": preview.canonical_checksum,
        "readiness_fingerprint": source_manifest["readiness_fingerprint"],
        "configuration_snapshot": metadata["configuration_snapshot"],
        "mapping_snapshot": metadata["mapping_snapshot"],
        "defaults_snapshot": metadata["defaults_snapshot"],
        "data_status": preview.data_status,
        "source_provenance": metadata["source_provenance"],
        "row_count": preview.segment_count,
    }
    metadata["version_records"] = {str(INITIAL_DATA_VERSION): version_record}
    _write_json_atomic(staging / REGISTRATION_METADATA_NAME, metadata)
    _write_json_atomic(version_root / "version.json", version_record)


def verify_registered_municipality(directory: str | Path) -> RegisteredMunicipality:
    """Exercise config, inventory, scenario, map, and report against the staged snapshot."""

    registered = load_persistent_registration_directory(directory)
    from pilot.municipality_data import load_municipality_inventory
    from pilot.municipality_scenarios import (
        build_municipality_scenario_results,
        get_scenario_catalog,
    )

    roads = load_municipality_inventory(registered.config)
    if roads.empty:
        raise ValueError(f"Registered municipality '{registered.config.slug}' inventory is empty.")
    catalog = get_scenario_catalog(registered.config.scenario_catalog_id)
    scenario_name = next(iter(catalog))
    results = build_municipality_scenario_results(
        roads, scenario_name, registered.config.scenario_catalog_id
    )
    from gis.engine import create_network_map

    road_map = create_network_map(
        roads,
        selected_ids=results["selected_ids"],
        map_center=registered.config.map_center,
        zoom_start=registered.config.map_zoom,
    )
    if road_map is None:
        raise ValueError("Registered municipality map initialization failed.")
    from components.municipality_report import build_municipality_report

    report = build_municipality_report(registered.config, roads, results)
    if not report.startswith(b"%PDF"):
        raise ValueError("Registered municipality report generation failed.")
    return registered


def promote_registration(
    package_path: str | Path,
    *,
    confirmation_slug: str,
    confirmed: bool,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    protected_slugs: Mapping[str, MunicipalityConfig] | set[str] | frozenset[str] = frozenset(),
    generated_root: str | Path | None = None,
    archived_root: str | Path | None = None,
    verifier: Callable[[Path], Any] = verify_registered_municipality,
) -> RegisteredMunicipality:
    """Atomically promote one ready package, then verify or roll back the new snapshot."""

    package = Path(package_path).resolve()
    if not confirmed:
        raise ValueError("Registration requires the explicit confirmation checkbox.")
    preview = preview_registration(
        package,
        registration_root=registration_root,
        protected_slugs=protected_slugs,
        generated_root=generated_root,
        archived_root=archived_root,
        record_event=False,
    )
    if confirmation_slug.strip() != preview.slug:
        raise ValueError(f"Type the exact municipality slug '{preview.slug}' to confirm registration.")
    if preview.blocking_issues:
        append_package_event(
            package,
            "registration blocked",
            PackageLifecycleState.READY_FOR_REGISTRATION,
            "; ".join(issue.message for issue in preview.blocking_issues),
        )
        raise ValueError(
            "Registration is blocked: "
            + "; ".join(issue.message for issue in preview.blocking_issues)
        )
    root = Path(registration_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = _safe_registration_path(preview.slug, root)
    staging = (root / f".{preview.slug}.staging-{uuid4().hex}").resolve()
    if staging.parent != root:
        raise ValueError("Registration staging path escaped the persistent root.")
    append_package_event(
        package,
        "registration attempted",
        PackageLifecycleState.READY_FOR_REGISTRATION,
        f"Atomic promotion attempted for registration version {INITIAL_REGISTRATION_VERSION}.",
    )
    promoted = False
    try:
        staging.mkdir(parents=False, exist_ok=False)
        _copy_registration_snapshot(package, staging, preview)
        load_persistent_registration_directory(staging)
        if destination.exists():
            raise ValueError(f"Durable registration path already exists: '{destination}'.")
        staging.replace(destination)
        promoted = True
        verifier(destination)
        registered = load_persistent_registration_directory(destination)
    except Exception as exc:
        cleanup = destination if promoted else staging
        if cleanup.exists():
            shutil.rmtree(cleanup)
        append_package_event(
            package,
            "post-registration verification failed" if promoted else "registration blocked",
            PackageLifecycleState.READY_FOR_REGISTRATION,
            f"Registration promotion rolled back: {exc}",
        )
        raise ValueError(f"Registration failed and was rolled back: {exc}") from exc

    manifest_path = package / "manifest.json"
    manifest = _read_json(manifest_path, "Real-import manifest")
    manifest["lifecycle_state"] = PackageLifecycleState.REGISTERED.value
    _write_json_atomic(manifest_path, manifest)
    package_metadata_path = package / "package_metadata.json"
    package_metadata = _read_json(package_metadata_path, "Package metadata")
    package_metadata.update({
        "registration_version": registered.registration_version,
        "registration_date": registered.registered_at_utc,
        "registration_state": registered.registration_state,
        "registered_data_path": str(destination),
    })
    _write_json_atomic(package_metadata_path, package_metadata)
    append_package_event(
        package,
        "registration succeeded",
        PackageLifecycleState.REGISTERED,
        f"Registered version 1 at '{destination}' pending operational acceptance.",
    )
    return registered


def accept_registration(
    slug: str,
    *,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
) -> RegisteredMunicipality:
    """Finalize operational verification; this is not municipal or legal approval."""

    registered = get_persistent_registration(slug, registration_root)
    metadata = _registration_metadata(registered.registration_path)
    if metadata["registration_state"] == RegistrationState.ACCEPTED:
        return registered
    metadata["registration_state"] = RegistrationState.ACCEPTED
    metadata["accepted_at_utc"] = _utc_timestamp()
    _write_json_atomic(registered.metadata_path, metadata)
    source_package = Path(str(metadata.get("source_package_path", "")))
    if source_package.is_dir() and (source_package / HISTORY_NAME).is_file():
        package_metadata_path = source_package / "package_metadata.json"
        if package_metadata_path.is_file():
            package_metadata = _read_json(package_metadata_path, "Package metadata")
            package_metadata["registration_state"] = RegistrationState.ACCEPTED
            package_metadata["registration_accepted_at"] = metadata["accepted_at_utc"]
            _write_json_atomic(package_metadata_path, package_metadata)
        append_package_event(
            source_package,
            "registration accepted",
            PackageLifecycleState.REGISTERED,
            "Operational registration verification accepted; no municipal/legal approval is implied.",
        )
    return get_persistent_registration(slug, registration_root)


def rollback_registration(
    slug: str,
    *,
    confirmation_slug: str,
    registration_root: str | Path = PERSISTENT_MUNICIPALITIES_ROOT,
    protected_slugs: Mapping[str, MunicipalityConfig] | set[str] | frozenset[str] = frozenset(),
) -> Path:
    """Remove only a pending persistent registration while preserving onboarding history."""

    safe_slug = _normalized_slug(slug)
    if safe_slug in set(protected_slugs):
        raise ValueError(f"Built-in municipality '{safe_slug}' cannot be rolled back.")
    if confirmation_slug.strip() != safe_slug:
        raise ValueError(f"Type the exact municipality slug '{safe_slug}' to confirm rollback.")
    registered = get_persistent_registration(safe_slug, registration_root)
    if registered.registration_state == RegistrationState.ACCEPTED:
        raise ValueError(
            f"Accepted registration '{safe_slug}' requires developer-controlled removal and cannot be rolled back here."
        )
    metadata = _registration_metadata(registered.registration_path)
    source_package = Path(str(metadata.get("source_package_path", "")))
    root = Path(registration_root).resolve()
    destination = _safe_registration_path(safe_slug, root)
    quarantine = (root / f".{safe_slug}.rollback-{uuid4().hex}").resolve()
    if destination != registered.registration_path or quarantine.parent != root:
        raise ValueError("Rollback path safety validation failed.")
    destination.replace(quarantine)
    try:
        shutil.rmtree(quarantine)
    except Exception:
        if quarantine.exists() and not destination.exists():
            quarantine.replace(destination)
        raise
    if source_package.is_dir() and (source_package / HISTORY_NAME).is_file():
        package_metadata_path = source_package / "package_metadata.json"
        if package_metadata_path.is_file():
            package_metadata = _read_json(package_metadata_path, "Package metadata")
            package_metadata["registration_state"] = "rolled_back"
            package_metadata["registration_rolled_back_at"] = _utc_timestamp()
            _write_json_atomic(package_metadata_path, package_metadata)
        source_manifest_path = source_package / "manifest.json"
        if source_manifest_path.is_file():
            source_manifest = _read_json(source_manifest_path, "Real-import manifest")
            source_manifest["lifecycle_state"] = (
                PackageLifecycleState.READY_FOR_REGISTRATION.value
            )
            _write_json_atomic(source_manifest_path, source_manifest)
            refreshed = refresh_real_import_readiness(source_package)
        else:
            refreshed = None
        append_package_event(
            source_package,
            "registration rolled back",
            (
                refreshed.lifecycle_state
                if refreshed is not None
                else PackageLifecycleState.VALIDATION_REQUIRED
            ),
            f"Pending persistent registration '{safe_slug}' was removed; onboarding package preserved.",
        )
    return destination
