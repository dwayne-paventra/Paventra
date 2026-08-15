"""Operator helpers for generated demo and municipality import packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import csv
import io
import json
from pathlib import Path
import re
import shutil
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from pilot.canonical_inventory import (
    CANONICAL_COLUMNS,
    enrich_canonical_inventory,
    normalize_treatment,
    validate_canonical_schema,
)
from pilot.municipality_config import MunicipalityConfig
from pilot.municipality_config import validate_municipality_config
from pilot.municipality_onboarding import (
    export_canonical_inventory,
    load_onboarding_manifest,
    map_source_to_canonical,
)
from pilot.source_provenance import (
    SourceProvenance,
    compute_content_checksum,
    compute_source_checksum,
)
from pilot.municipality_package_lifecycle import (
    CANONICAL_REVIEW_NAME,
    HISTORY_NAME,
    MAPPING_REVIEW_NAME,
    PackageLifecycleState,
    REGISTRATION_PACKET_NAME,
    REVIEW_SUMMARY_NAME,
    VALIDATION_SUMMARY_NAME,
    append_package_event,
    initialize_real_import_workspace_artifacts,
    validate_real_import_package,
)
from pilot.onboarding_manifest_contract import REAL_IMPORT_WORKSPACE_MANIFEST_VERSION


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATED_MUNICIPALITIES_ROOT = PROJECT_ROOT / "generated" / "municipalities"
ARCHIVED_MUNICIPALITIES_ROOT = PROJECT_ROOT / "generated" / "archived_municipalities"
GENERATED_MANIFEST_NAME = "manifest.json"
GENERATED_METADATA_NAME = "package_metadata.json"

KNOWN_TREATMENTS = frozenset({
    "Not Assigned",
    "Crack Seal",
    "Mill & Fill",
    "Overlay",
    "Reconstruction",
})


@dataclass(frozen=True)
class MunicipalityIdentity:
    formal_name: str
    short_name: str
    entity_type: str
    state: str
    slug: str
    leadership_label: str
    official_action_label: str
    map_center: tuple[float, float]
    map_zoom: int
    scenario_catalog_id: str
    pilot_label: str = "Municipal Pilot"


@dataclass(frozen=True)
class OnboardingReview:
    config: MunicipalityConfig
    source_rows: int
    canonical: pd.DataFrame
    mapping: Mapping[str, str]
    defaults: Mapping[str, Any]
    checksum: str
    treatment_normalizations: Mapping[str, str]
    unknown_treatments: tuple[str, ...]


@dataclass(frozen=True)
class GeneratedMunicipalityPackage:
    config: MunicipalityConfig
    manifest_path: Path
    source_path: Path
    canonical_review_path: Path
    review: OnboardingReview
    runtime_launchable: bool


@dataclass(frozen=True)
class MunicipalityPortfolioEntry:
    """Cheap, display-ready metadata for one permanent or generated municipality."""

    slug: str
    formal_name: str
    short_name: str
    entity_type: str
    data_status: str
    source_type: str
    package_type: str
    scenario_catalog_id: str
    road_count: int | None
    generated_date: str | None
    permanent: bool
    archived: bool
    readiness_state: str
    validation_summary: str
    package_path: Path
    manifest_path: Path | None
    manifest_version: int | None
    config: MunicipalityConfig | None

    @property
    def dashboard_launchable(self) -> bool:
        return not self.archived and (
            self.permanent
            or (
                self.config is not None
                and self.config.inventory_adapter == "canonical_demo"
                and self.config.normalized_data_status == "illustrative"
            )
        )


def suggest_municipality_slug(value: str) -> str:
    """Return a stable lowercase slug suitable for configuration and paths."""

    if not isinstance(value, str):
        raise ValueError("Municipality name must be text before a slug can be suggested.")
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    if not slug:
        raise ValueError("Municipality name must contain letters or numbers.")
    return slug


def _normalized_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


_HEADER_ALIASES = {
    "road_id": {"roadid", "assetid", "assetno", "roadnumber"},
    "segment_id": {"segmentid", "segmentcode", "segmentref"},
    "road_name": {"roadname", "streetname", "street", "road"},
    "from_street": {"fromstreet", "streetfrom", "beginat", "fromloc"},
    "to_street": {"tostreet", "streetto", "endat", "toloc"},
    "jurisdiction": {"jurisdiction", "owner", "agency"},
    "latitude": {"latitude", "lat", "latvalue", "latitudedd"},
    "longitude": {"longitude", "lon", "lng", "long", "lonvalue", "longitudedd"},
    "road_length_miles": {"roadlengthmiles", "lengthmiles", "lengthmi", "length"},
    "lanes": {"lanes", "lanecount", "numberoflanes"},
    "surface_type": {"surfacetype", "surface", "pavement"},
    "functional_class": {"functionalclass", "roadclass", "routeclass", "classdesc"},
    "pci": {"pci", "pciscore", "pcirating", "conditionscore"},
    "condition_date": {"conditiondate", "inspectiondate", "inspectedon"},
    "traffic_level": {"trafficlevel", "trafficband", "traffic"},
    "adt": {"adt", "aadt", "averagedailytraffic", "dailytraffic"},
    "age_years": {"ageyears", "assetageyears", "assetage", "pavementage"},
    "freeze_thaw": {"freezethaw", "freezeexposure", "freezerisk"},
    "recommended_treatment": {"recommendedtreatment", "proposedtreatment", "actionrec"},
    "treatment_cost_per_lane_mile": {
        "treatmentcostperlanemile", "costperlanemile", "unitcost", "costlm"
    },
    "data_status": {"datastatus", "sourcestatus"},
    "data_source": {"datasource", "sourcelabel"},
    "data_updated_at": {"dataupdatedat", "lastupdated", "lastrefresh", "sourceupdateddate"},
}


def suggest_column_mappings(headers: Sequence[str]) -> dict[str, str | None]:
    """Suggest unambiguous source-to-canonical mappings without finalizing them."""

    suggestions: dict[str, str | None] = {}
    claimed: set[str] = set()
    for header in headers:
        normalized = _normalized_header(str(header))
        matches = [
            canonical
            for canonical, aliases in _HEADER_ALIASES.items()
            if normalized in aliases
        ]
        suggestion = matches[0] if len(matches) == 1 and matches[0] not in claimed else None
        suggestions[str(header)] = suggestion
        if suggestion:
            claimed.add(suggestion)
    return suggestions


def _package_directory(slug: str, root: Path = GENERATED_MUNICIPALITIES_ROOT) -> Path:
    safe_slug = suggest_municipality_slug(slug)
    if safe_slug != slug:
        raise ValueError(
            f"Municipality slug '{slug}' is not normalized; use '{safe_slug}'."
        )
    resolved_root = root.resolve()
    destination = (resolved_root / safe_slug).resolve()
    if destination.parent != resolved_root:
        raise ValueError("Generated municipality path must remain inside the generated area.")
    return destination


def assert_slug_available(
    slug: str,
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
    archived_root: Path | None = None,
) -> Path:
    """Reject permanent or generated slug collisions before any write."""

    from pilot.municipality_registry import MUNICIPALITIES

    destination = _package_directory(slug, generated_root)
    if slug in MUNICIPALITIES:
        raise ValueError(f"Municipality slug '{slug}' is already permanently registered.")
    if destination.exists():
        raise ValueError(
            f"Generated municipality slug '{slug}' already exists at '{destination}'."
        )
    archive = archived_root
    if archive is None and generated_root.resolve() == GENERATED_MUNICIPALITIES_ROOT.resolve():
        archive = ARCHIVED_MUNICIPALITIES_ROOT
    if archive is not None and _package_directory(slug, archive).exists():
        raise ValueError(
            f"Generated municipality slug '{slug}' is archived and must be restored or "
            "intentionally renamed before reuse."
        )
    return destination


def _csv_record_count(path: Path) -> int | None:
    """Count CSV data records without loading the municipality inventory pipeline."""

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            rows = csv.reader(source)
            next(rows)
            return sum(1 for _ in rows)
    except (OSError, StopIteration, UnicodeError, csv.Error):
        return None


def _generated_date(path: Path, metadata: Mapping[str, Any]) -> str | None:
    value = metadata.get("created_at")
    if isinstance(value, str) and value.strip():
        return value.strip()
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
    except OSError:
        return None


def _read_package_metadata(directory: Path) -> dict[str, Any]:
    path = directory / GENERATED_METADATA_NAME
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def generate_synthetic_canonical_inventory(
    identity: MunicipalityIdentity,
    *,
    road_count: int = 10,
) -> pd.DataFrame:
    """Create an explicitly synthetic canonical inventory near the configured map center."""

    if isinstance(road_count, bool) or not isinstance(road_count, int) or not 5 <= road_count <= 50:
        raise ValueError("Synthetic road count must be an integer from 5 through 50.")
    latitude, longitude = identity.map_center
    classes = ("Local", "Collector", "Arterial")
    traffic = (("Low", 900), ("Medium", 4800), ("High", 13200))
    pci_values = (88, 74, 63, 51, 39, 27)
    treatments = (
        ("Crack Seal", 85_000),
        ("Overlay", 250_000),
        ("Mill and Overlay", 400_000),
        ("Reconstruction", 650_000),
        ("No Treatment", 0),
    )
    today = date.today().isoformat()
    rows = []
    for index in range(road_count):
        number = index + 1
        traffic_level, adt = traffic[index % len(traffic)]
        treatment, treatment_cost = treatments[index % len(treatments)]
        rows.append({
            "road_id": f"SYN-{number:03d}",
            "segment_id": f"SYN-SEG-{number:03d}",
            "road_name": f"Synthetic Demonstration Corridor {number}",
            "from_street": f"Demo Limit {number}A",
            "to_street": f"Demo Limit {number}B",
            "jurisdiction": identity.formal_name,
            "latitude": min(90.0, max(-90.0, latitude + ((index % 4) - 1.5) * 0.002)),
            "longitude": min(180.0, max(-180.0, longitude + ((index % 5) - 2) * 0.002)),
            "road_length_miles": round(0.35 + (index % 6) * 0.18, 2),
            "lanes": 4 if index % 5 == 2 else 2,
            "surface_type": "Asphalt",
            "functional_class": classes[index % len(classes)],
            "pci": pci_values[index % len(pci_values)],
            "condition_date": today,
            "traffic_level": traffic_level,
            "adt": adt + index * 110,
            "age_years": 4 + (index * 3) % 28,
            "freeze_thaw": ("Low", "Medium", "High")[index % 3],
            "recommended_treatment": treatment,
            "treatment_cost_per_lane_mile": treatment_cost,
            "data_status": "illustrative",
            "data_source": "Paventra synthetic demonstration inventory",
            "data_updated_at": today,
        })
    canonical = pd.DataFrame(rows, columns=CANONICAL_COLUMNS)
    validate_canonical_schema(
        canonical,
        expected_data_status="illustrative",
        municipality_slug=identity.slug,
    )
    return canonical


def _build_config(
    identity: MunicipalityIdentity,
    *,
    data_path: Path,
    inventory_adapter: str,
    data_status: str,
    mapping: Mapping[str, str],
    defaults: Mapping[str, Any],
    provenance: SourceProvenance,
    manifest_version: int = 3,
) -> MunicipalityConfig:
    return MunicipalityConfig(
        municipality_id=f"{identity.slug}-{suggest_municipality_slug(identity.state)}",
        slug=identity.slug,
        state=identity.state,
        data_directory=data_path.parent,
        data_path=data_path,
        map_center=identity.map_center,
        map_zoom=identity.map_zoom,
        pilot_mode=f"{identity.slug}_pilot",
        inventory_adapter=inventory_adapter,
        entity_type=identity.entity_type,
        formal_name=identity.formal_name,
        short_name=identity.short_name,
        pilot_label=identity.pilot_label,
        leadership_label=identity.leadership_label,
        official_action_label=identity.official_action_label,
        scenario_catalog_id=identity.scenario_catalog_id,
        data_status=data_status,
        source_column_mapping=dict(mapping),
        canonical_defaults=dict(defaults),
        source_provenance=provenance,
        onboarding_manifest_version=manifest_version,
    )


def _treatment_review(canonical: pd.DataFrame) -> tuple[dict[str, str], tuple[str, ...]]:
    supplied = sorted({str(value).strip() for value in canonical["recommended_treatment"]})
    normalizations = {
        value: normalize_treatment(value)
        for value in supplied
        if normalize_treatment(value) != value
    }
    unknown = tuple(
        value for value in supplied if normalize_treatment(value) not in KNOWN_TREATMENTS
    )
    return normalizations, unknown


def review_real_import(
    identity: MunicipalityIdentity,
    source_content: bytes,
    *,
    mapping: Mapping[str, str],
    defaults: Mapping[str, Any],
    data_status: str,
    source_owner: str,
    acquired_date: str,
    source_reference: str,
    declared_checksum: str | None = None,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> OnboardingReview:
    """Validate uploaded bytes through the existing mapped canonical pipeline."""

    if not source_content:
        raise ValueError("Uploaded source CSV must not be empty.")
    try:
        source = pd.read_csv(io.BytesIO(source_content))
    except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError(f"Uploaded source CSV could not be read: {exc}") from exc
    checksum = compute_content_checksum(source_content)
    declared = (declared_checksum or "").strip().lower()
    if declared and declared != checksum:
        raise ValueError(
            f"Declared source checksum does not match upload: declared {declared}, actual {checksum}."
        )
    destination = _package_directory(identity.slug, generated_root)
    filtered_mapping = {source_name: target for source_name, target in mapping.items() if target}
    provenance = SourceProvenance(
        owner=source_owner,
        acquired_date=acquired_date,
        reference=source_reference,
        checksum=checksum,
    )
    config = _build_config(
        identity,
        data_path=destination / "source_roads.csv",
        inventory_adapter="mapped_csv",
        data_status=data_status,
        mapping=filtered_mapping,
        defaults=defaults,
        provenance=provenance,
    )
    canonical = map_source_to_canonical(config, source)
    normalizations, unknown = _treatment_review(canonical)
    return OnboardingReview(
        config=config,
        source_rows=len(source),
        canonical=enrich_canonical_inventory(canonical),
        mapping=filtered_mapping,
        defaults=dict(defaults),
        checksum=checksum,
        treatment_normalizations=normalizations,
        unknown_treatments=unknown,
    )


def review_illustrative_demo(
    identity: MunicipalityIdentity,
    *,
    road_count: int = 10,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> OnboardingReview:
    """Build and validate an illustrative-only demo review without writing files."""

    destination = _package_directory(identity.slug, generated_root)
    canonical = enrich_canonical_inventory(
        generate_synthetic_canonical_inventory(identity, road_count=road_count)
    )
    csv_content = canonical.loc[:, CANONICAL_COLUMNS].to_csv(
        index=False, lineterminator="\n"
    ).encode("utf-8")
    checksum = compute_content_checksum(csv_content)
    mapping = {column: column for column in CANONICAL_COLUMNS}
    config = _build_config(
        identity,
        data_path=destination / "synthetic_roads.csv",
        inventory_adapter="canonical_demo",
        data_status="illustrative",
        mapping=mapping,
        defaults={},
        provenance=SourceProvenance(
            owner="Paventra synthetic demo generator",
            acquired_date=date.today().isoformat(),
            reference=f"Runtime illustrative demo package for {identity.formal_name}",
            checksum=checksum,
        ),
    )
    from pilot.municipality_registry import validate_municipality_registry

    validate_municipality_registry(
        {config.slug: config},
        default_slug=config.slug,
    )
    normalizations, unknown = _treatment_review(canonical)
    return OnboardingReview(
        config=config,
        source_rows=len(canonical),
        canonical=canonical,
        mapping=mapping,
        defaults={},
        checksum=checksum,
        treatment_normalizations=normalizations,
        unknown_treatments=unknown,
    )


def _manifest_document(
    review: OnboardingReview,
    source_filename: str,
    *,
    real_import: bool = False,
) -> dict[str, Any]:
    config = review.config
    provenance = config.source_provenance
    document = {
        "manifest_version": REAL_IMPORT_WORKSPACE_MANIFEST_VERSION if real_import else 3,
        "municipality_id": config.municipality_id,
        "slug": config.slug,
        "state": config.state,
        "entity_type": config.entity_type,
        "formal_name": config.formal_name,
        "short_name": config.short_name,
        "data_status": config.normalized_data_status,
        "source_owner": provenance.owner,
        "source_acquired_date": provenance.acquired_date,
        "source_reference": provenance.reference,
        "source_checksum": review.checksum,
        "source_csv_path": source_filename,
        "column_mapping": dict(review.mapping),
        "canonical_defaults": dict(review.defaults),
        "map_center": list(config.map_center),
        "map_zoom": config.map_zoom,
        "inventory_adapter": config.inventory_adapter,
        "scenario_catalog_id": config.scenario_catalog_id,
        "pilot_mode": config.pilot_mode,
        "pilot_label": config.pilot_label,
        "leadership_label": config.leadership_label,
        "official_action_label": config.official_action_label,
    }
    if real_import:
        document.update({
            "package_type": "real_import",
            "lifecycle_state": PackageLifecycleState.DRAFT.value,
            "source_field_meanings": {},
            "canonical_review_path": CANONICAL_REVIEW_NAME,
            "mapping_review_path": MAPPING_REVIEW_NAME,
            "validation_summary_path": VALIDATION_SUMMARY_NAME,
            "review_summary_path": REVIEW_SUMMARY_NAME,
            "registration_packet_path": REGISTRATION_PACKET_NAME,
            "history_path": HISTORY_NAME,
        })
    return document


def _write_package(
    review: OnboardingReview,
    source_content: bytes,
    source_filename: str,
    *,
    runtime_launchable: bool,
    generated_root: Path,
) -> GeneratedMunicipalityPackage:
    destination = assert_slug_available(review.config.slug, generated_root=generated_root)
    try:
        destination.mkdir(parents=True, exist_ok=False)
        raw_path = destination / "source_roads.raw.csv"
        source_path = destination / source_filename
        raw_path.write_bytes(source_content)
        source_path.write_bytes(source_content)
        if compute_source_checksum(raw_path) != review.checksum:
            raise ValueError("Preserved raw source checksum changed during package creation.")
        manifest_path = destination / GENERATED_MANIFEST_NAME
        real_import = review.config.inventory_adapter != "canonical_demo"
        manifest_path.write_text(
            json.dumps(
                _manifest_document(review, source_filename, real_import=real_import),
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        config = load_onboarding_manifest(manifest_path)
        canonical_review_path = destination / "canonical_review.csv"
        export_canonical_inventory(
            review.canonical,
            canonical_review_path,
            expected_data_status=config.normalized_data_status,
            municipality_slug=config.slug,
        )
        metadata_path = destination / GENERATED_METADATA_NAME
        metadata_path.write_text(
            json.dumps(
                {
                    "metadata_version": 1,
                    "slug": config.slug,
                    "package_type": (
                        "illustrative_demo"
                        if config.inventory_adapter == "canonical_demo"
                        else "real_import"
                    ),
                    "road_count": len(review.canonical),
                    "validation_result": "PASS",
                    "created_at": date.today().isoformat(),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        if real_import:
            append_package_event(
                destination,
                "created",
                PackageLifecycleState.DRAFT,
                "Real-import workspace created from operator-reviewed source inputs.",
            )
            inspection = validate_real_import_package(destination)
            if inspection.blocking_issues:
                raise ValueError(
                    "Created real-import workspace did not pass validation: "
                    + "; ".join(issue.message for issue in inspection.blocking_issues)
                )
            config = load_onboarding_manifest(manifest_path)
        return GeneratedMunicipalityPackage(
            config=config,
            manifest_path=manifest_path,
            source_path=source_path,
            canonical_review_path=canonical_review_path,
            review=review,
            runtime_launchable=runtime_launchable,
        )
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise


def create_illustrative_demo_package(
    review: OnboardingReview,
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> GeneratedMunicipalityPackage:
    """Persist a validated illustrative package in the isolated generated area."""

    if review.config.normalized_data_status != "illustrative":
        raise ValueError("Generated demo packages must use illustrative data status.")
    canonical = review.canonical.loc[:, CANONICAL_COLUMNS]
    content = canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
    if compute_content_checksum(content) != review.checksum:
        raise ValueError("Synthetic review content changed before package creation.")
    return _write_package(
        review,
        content,
        "synthetic_roads.csv",
        runtime_launchable=True,
        generated_root=generated_root,
    )


def create_real_import_package(
    review: OnboardingReview,
    source_content: bytes,
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> GeneratedMunicipalityPackage:
    """Persist a validated real-import package without permanent registration."""

    if compute_content_checksum(source_content) != review.checksum:
        raise ValueError("Uploaded source changed after validation; validate it again.")
    return _write_package(
        review,
        source_content,
        "source_roads.csv",
        runtime_launchable=False,
        generated_root=generated_root,
    )


def save_real_import_draft(
    identity: MunicipalityIdentity,
    source_content: bytes,
    *,
    mapping: Mapping[str, str],
    defaults: Mapping[str, Any],
    data_status: str,
    source_owner: str,
    acquired_date: str,
    source_reference: str,
    declared_checksum: str | None = None,
    source_field_meanings: Mapping[str, str] | None = None,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> Path:
    """Create or update a resumable real-import workspace without claiming validation."""

    if not source_content:
        raise ValueError("Uploaded source CSV must not be empty before saving a draft.")
    checksum = compute_content_checksum(source_content)
    declared = (declared_checksum or "").strip().lower()
    if declared and declared != checksum:
        raise ValueError(
            f"Declared source checksum does not match upload: declared {declared}, actual {checksum}."
        )
    destination = _package_directory(identity.slug, generated_root)
    exists = destination.exists()
    previous_state = PackageLifecycleState.DRAFT
    if exists:
        manifest_path = destination / GENERATED_MANIFEST_NAME
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Existing real-import workspace could not be reopened: {exc}") from exc
        if existing.get("package_type") != "real_import":
            raise ValueError(
                f"Generated municipality slug '{identity.slug}' is not a real-import workspace."
            )
        try:
            previous_state = PackageLifecycleState(existing.get("lifecycle_state"))
        except ValueError:
            previous_state = PackageLifecycleState.VALIDATION_REQUIRED
    else:
        destination = assert_slug_available(identity.slug, generated_root=generated_root)
        destination.mkdir(parents=True, exist_ok=False)

    filtered_mapping = {
        str(source): str(target)
        for source, target in mapping.items()
        if str(target).strip()
    }
    provenance = SourceProvenance(
        owner=source_owner,
        acquired_date=acquired_date,
        reference=source_reference,
        checksum=checksum,
    )
    config = _build_config(
        identity,
        data_path=destination / "source_roads.csv",
        inventory_adapter="mapped_csv",
        data_status=data_status,
        mapping=filtered_mapping,
        defaults=defaults,
        provenance=provenance,
        manifest_version=REAL_IMPORT_WORKSPACE_MANIFEST_VERSION,
    )
    validate_municipality_config(config)
    from pilot.municipality_data import INVENTORY_ADAPTERS
    from pilot.municipality_scenarios import SCENARIO_CATALOGS
    if config.inventory_adapter not in INVENTORY_ADAPTERS:
        raise ValueError(
            f"Municipality '{config.slug}' field 'inventory_adapter' references unknown "
            f"adapter '{config.inventory_adapter}'."
        )
    if config.scenario_catalog_id not in SCENARIO_CATALOGS:
        raise ValueError(
            f"Municipality '{config.slug}' field 'scenario_catalog_id' references unknown "
            f"catalog '{config.scenario_catalog_id}'."
        )

    review = OnboardingReview(
        config=config,
        source_rows=0,
        canonical=pd.DataFrame(),
        mapping=filtered_mapping,
        defaults=dict(defaults),
        checksum=checksum,
        treatment_normalizations={},
        unknown_treatments=(),
    )
    document = _manifest_document(review, "source_roads.csv", real_import=True)
    document["source_field_meanings"] = {
        str(field): str(meaning).strip()
        for field, meaning in (source_field_meanings or {}).items()
        if str(meaning).strip()
    }
    if exists and previous_state != PackageLifecycleState.DRAFT:
        document["lifecycle_state"] = PackageLifecycleState.VALIDATION_REQUIRED.value
    manifest_path = destination / GENERATED_MANIFEST_NAME
    temporary = manifest_path.with_suffix(".json.tmp")
    try:
        (destination / "source_roads.raw.csv").write_bytes(source_content)
        (destination / "source_roads.csv").write_bytes(source_content)
        temporary.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        temporary.replace(manifest_path)
        (destination / GENERATED_METADATA_NAME).write_text(
            json.dumps({
                "metadata_version": 2,
                "slug": config.slug,
                "package_type": "real_import",
                "road_count": _csv_record_count(destination / "source_roads.csv"),
                "validation_result": "NOT RUN",
                "created_at": _read_package_metadata(destination).get("created_at")
                or date.today().isoformat(),
            }, indent=2) + "\n",
            encoding="utf-8",
        )
        inspection = initialize_real_import_workspace_artifacts(destination)
        append_package_event(
            destination,
            "review updated" if exists else "created",
            inspection.lifecycle_state,
            "Operator saved real-import identity, provenance, mappings, defaults, and source reference.",
        )
        return destination
    except Exception:
        if not exists and destination.exists():
            shutil.rmtree(destination)
        raise


def load_generated_municipality(
    slug: str,
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> MunicipalityConfig:
    """Load one explicitly selected generated manifest without registering it."""

    manifest = _package_directory(slug, generated_root) / GENERATED_MANIFEST_NAME
    if not manifest.is_file():
        raise ValueError(f"Generated municipality '{slug}' is not available.")
    return load_onboarding_manifest(manifest)


def list_generated_municipalities(
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> tuple[MunicipalityConfig, ...]:
    """List valid operator-generated packages; this is not permanent registry discovery."""

    if not generated_root.is_dir():
        return ()
    configs = []
    for directory in sorted(generated_root.iterdir()):
        manifest = directory / GENERATED_MANIFEST_NAME
        if directory.is_dir() and manifest.is_file():
            try:
                configs.append(load_onboarding_manifest(manifest))
            except ValueError:
                # Draft real imports are discoverable through the Portfolio but
                # are intentionally not runtime-loadable configurations.
                continue
    return tuple(configs)


def _permanent_portfolio_entries() -> list[MunicipalityPortfolioEntry]:
    from pilot.municipality_registry import MUNICIPALITIES

    entries = []
    for slug, config in MUNICIPALITIES.items():
        entries.append(MunicipalityPortfolioEntry(
            slug=slug,
            formal_name=config.formal_name,
            short_name=config.short_name,
            entity_type=config.entity_type,
            data_status=config.normalized_data_status,
            source_type="Permanent registry",
            package_type="registered",
            scenario_catalog_id=config.scenario_catalog_id,
            road_count=_csv_record_count(config.data_path),
            generated_date=None,
            permanent=True,
            archived=False,
            readiness_state="Permanent / Registered",
            validation_summary="Registered configuration",
            package_path=config.data_directory,
            manifest_path=(
                config.data_directory / GENERATED_MANIFEST_NAME
                if config.onboarding_manifest_version is not None
                else None
            ),
            manifest_version=config.onboarding_manifest_version,
            config=config,
        ))
    return entries


def _generated_portfolio_entry(
    directory: Path,
    *,
    archived: bool,
) -> MunicipalityPortfolioEntry:
    manifest = directory / GENERATED_MANIFEST_NAME
    metadata = _read_package_metadata(directory)
    try:
        raw_document = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(raw_document, dict):
            raise ValueError("Generated manifest must contain a JSON object.")
        if raw_document.get("package_type") == "real_import":
            from pilot.municipality_package_lifecycle import refresh_real_import_readiness

            inspection = refresh_real_import_readiness(directory)
            config = inspection.config
            validation = (
                "; ".join(issue.message for issue in inspection.issues)
                if inspection.issues
                else "All current package gates pass"
            )
            return MunicipalityPortfolioEntry(
                slug=str(raw_document.get("slug") or directory.name),
                formal_name=str(raw_document.get("formal_name") or directory.name),
                short_name=str(
                    raw_document.get("short_name")
                    or raw_document.get("formal_name")
                    or directory.name
                ),
                entity_type=str(raw_document.get("entity_type") or "unknown"),
                data_status=str(raw_document.get("data_status") or "unknown"),
                source_type="Municipality import",
                package_type="real_import",
                scenario_catalog_id=str(
                    raw_document.get("scenario_catalog_id") or "unknown"
                ),
                road_count=inspection.source_rows,
                generated_date=_generated_date(manifest, metadata),
                permanent=False,
                archived=False,
                readiness_state=f"Real Import — {inspection.lifecycle_state.value}",
                validation_summary=validation,
                package_path=directory,
                manifest_path=manifest,
                manifest_version=raw_document.get("manifest_version"),
                config=config,
            )
        config = load_onboarding_manifest(manifest)
        if config.slug != directory.name:
            raise ValueError(
                f"Manifest slug '{config.slug}' does not match package directory "
                f"'{directory.name}'."
            )
        illustrative_demo = config.inventory_adapter == "canonical_demo"
        if archived and not (
            illustrative_demo and config.normalized_data_status == "illustrative"
        ):
            raise ValueError("Only illustrative demo packages may be archived.")
        if archived:
            readiness = "Archived Generated Demo"
        elif illustrative_demo and config.normalized_data_status == "illustrative":
            readiness = "Generated Illustrative Demo"
        else:
            readiness = "Real Import — Validation Required"
        cached_count = metadata.get("road_count")
        road_count = (
            cached_count
            if isinstance(cached_count, int) and not isinstance(cached_count, bool)
            and cached_count >= 0
            else _csv_record_count(config.data_path)
        )
        return MunicipalityPortfolioEntry(
            slug=config.slug,
            formal_name=config.formal_name,
            short_name=config.short_name,
            entity_type=config.entity_type,
            data_status=config.normalized_data_status,
            source_type=(
                "Synthetic demo generator" if illustrative_demo else "Municipality import"
            ),
            package_type="illustrative_demo" if illustrative_demo else "real_import",
            scenario_catalog_id=config.scenario_catalog_id,
            road_count=road_count,
            generated_date=_generated_date(manifest, metadata),
            permanent=False,
            archived=archived,
            readiness_state=readiness,
            validation_summary=str(metadata.get("validation_result", "Manifest valid")),
            package_path=directory,
            manifest_path=manifest,
            manifest_version=config.onboarding_manifest_version,
            config=config,
        )
    except (
        AttributeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raw: dict[str, Any] = {}
        try:
            candidate = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                raw = candidate
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
        return MunicipalityPortfolioEntry(
            slug=directory.name,
            formal_name=str(raw.get("formal_name") or directory.name),
            short_name=str(raw.get("short_name") or raw.get("formal_name") or directory.name),
            entity_type=str(raw.get("entity_type") or "unknown"),
            data_status=str(raw.get("data_status") or "unknown"),
            source_type="Generated package",
            package_type=str(metadata.get("package_type") or "unknown"),
            scenario_catalog_id=str(raw.get("scenario_catalog_id") or "unknown"),
            road_count=(
                metadata.get("road_count")
                if isinstance(metadata.get("road_count"), int)
                else None
            ),
            generated_date=_generated_date(manifest, metadata),
            permanent=False,
            archived=archived,
            readiness_state="Validation Required",
            validation_summary=str(exc),
            package_path=directory,
            manifest_path=manifest if manifest.exists() else None,
            manifest_version=(
                raw.get("manifest_version")
                if isinstance(raw.get("manifest_version"), int)
                else None
            ),
            config=None,
        )


def build_municipality_portfolio(
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
    archived_root: Path = ARCHIVED_MUNICIPALITIES_ROOT,
    include_archived: bool = False,
) -> tuple[MunicipalityPortfolioEntry, ...]:
    """Build portfolio metadata without loading or enriching every inventory."""

    entries = _permanent_portfolio_entries()
    roots = [(generated_root, False)]
    if include_archived:
        roots.append((archived_root, True))
    for root, archived in roots:
        if not root.is_dir():
            continue
        for directory in sorted(root.iterdir()):
            if directory.is_dir():
                entries.append(_generated_portfolio_entry(directory, archived=archived))
    return tuple(sorted(entries, key=lambda item: (item.formal_name.lower(), item.slug)))


def filter_municipality_portfolio(
    entries: Sequence[MunicipalityPortfolioEntry],
    *,
    search: str = "",
    entity_types: Sequence[str] = (),
    data_statuses: Sequence[str] = (),
    source_scopes: Sequence[str] = (),
    readiness_states: Sequence[str] = (),
) -> tuple[MunicipalityPortfolioEntry, ...]:
    """Apply cheap in-memory portfolio search and filters."""

    query = search.strip().lower()
    entity_filter = set(entity_types)
    status_filter = set(data_statuses)
    source_filter = set(source_scopes)
    readiness_filter = set(readiness_states)
    filtered = []
    for entry in entries:
        scope = "Permanent" if entry.permanent else (
            "Archived" if entry.archived else "Generated"
        )
        if query and query not in f"{entry.formal_name} {entry.short_name} {entry.slug}".lower():
            continue
        if entity_filter and entry.entity_type not in entity_filter:
            continue
        if status_filter and entry.data_status not in status_filter:
            continue
        if source_filter and scope not in source_filter:
            continue
        if readiness_filter and entry.readiness_state not in readiness_filter:
            continue
        filtered.append(entry)
    return tuple(filtered)


def archive_generated_demo(
    slug: str,
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
    archived_root: Path = ARCHIVED_MUNICIPALITIES_ROOT,
) -> Path:
    """Move one validated illustrative demo into recoverable archive storage."""

    from pilot.municipality_registry import MUNICIPALITIES

    if slug in MUNICIPALITIES:
        raise ValueError(f"Permanent municipality '{slug}' cannot be archived.")
    source = _package_directory(slug, generated_root)
    destination = _package_directory(slug, archived_root)
    if not source.is_dir():
        raise ValueError(f"Generated municipality '{slug}' is not available to archive.")
    if destination.exists():
        raise ValueError(f"Archived municipality slug '{slug}' already exists.")
    config = load_onboarding_manifest(source / GENERATED_MANIFEST_NAME)
    if config.slug != slug:
        raise ValueError(f"Generated package manifest does not match slug '{slug}'.")
    if not (
        config.inventory_adapter == "canonical_demo"
        and config.normalized_data_status == "illustrative"
    ):
        raise ValueError("Only generated illustrative demo packages may be archived.")
    archived_root.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return destination


def restore_archived_demo(
    slug: str,
    *,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
    archived_root: Path = ARCHIVED_MUNICIPALITIES_ROOT,
) -> Path:
    """Restore one archived illustrative demo to the active generated area."""

    from pilot.municipality_registry import MUNICIPALITIES

    if slug in MUNICIPALITIES:
        raise ValueError(f"Permanent municipality slug '{slug}' cannot be restored.")
    source = _package_directory(slug, archived_root)
    destination = _package_directory(slug, generated_root)
    if not source.is_dir():
        raise ValueError(f"Archived municipality '{slug}' is not available to restore.")
    if destination.exists():
        raise ValueError(f"Generated municipality slug '{slug}' already exists.")
    config = load_onboarding_manifest(source / GENERATED_MANIFEST_NAME)
    if config.slug != slug or config.inventory_adapter != "canonical_demo" or (
        config.normalized_data_status != "illustrative"
    ):
        raise ValueError("Only archived illustrative demo packages may be restored.")
    generated_root.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return destination


def clone_illustrative_demo(
    source_slug: str,
    identity: MunicipalityIdentity,
    *,
    road_count: int | None = None,
    generated_root: Path = GENERATED_MUNICIPALITIES_ROOT,
) -> GeneratedMunicipalityPackage:
    """Regenerate an illustrative demo under a new identity and slug."""

    source = load_generated_municipality(source_slug, generated_root=generated_root)
    if not (
        source.inventory_adapter == "canonical_demo"
        and source.normalized_data_status == "illustrative"
    ):
        raise ValueError("Only generated illustrative demo packages may be cloned.")
    count = road_count
    if count is None:
        metadata = _read_package_metadata(_package_directory(source_slug, generated_root))
        cached_count = metadata.get("road_count")
        count = cached_count if isinstance(cached_count, int) else _csv_record_count(source.data_path)
    if count is None:
        raise ValueError(f"Could not determine road count for generated demo '{source_slug}'.")
    review = review_illustrative_demo(
        identity,
        road_count=count,
        generated_root=generated_root,
    )
    return create_illustrative_demo_package(review, generated_root=generated_root)
