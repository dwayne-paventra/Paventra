"""Operator helpers for generated demo and municipality import packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
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


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATED_MUNICIPALITIES_ROOT = PROJECT_ROOT / "generated" / "municipalities"
GENERATED_MANIFEST_NAME = "manifest.json"

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
    return destination


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
        onboarding_manifest_version=3,
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


def _manifest_document(review: OnboardingReview, source_filename: str) -> dict[str, Any]:
    config = review.config
    provenance = config.source_provenance
    return {
        "manifest_version": 3,
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
        manifest_path.write_text(
            json.dumps(_manifest_document(review, source_filename), indent=2) + "\n",
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
            configs.append(load_onboarding_manifest(manifest))
    return tuple(configs)
