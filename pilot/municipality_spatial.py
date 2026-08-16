"""Municipality road-geometry ingestion and immutable runtime artifacts.

GeoJSON is the Phase 23 exchange format.  Source CRS must be declared either
in the GeoJSON ``crs`` member or explicitly by the operator; the importer never
guesses a CRS.  Valid input is normalized to EPSG:4326 and joined to the shared
canonical inventory by an operator-selected identifier.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import geopandas as gpd
import pandas as pd
from pyproj import CRS


SPATIAL_SOURCE_NAME = "source_roads.raw.geojson"
SPATIAL_INPUT_NAME = "spatial_input.json"
SPATIAL_ARTIFACT_NAME = "roads.geojson"
SPATIAL_REVIEW_NAME = "spatial_review.json"
SPATIAL_METADATA_NAME = "spatial_metadata.json"
TARGET_CRS = "EPSG:4326"
JOIN_FIELDS = frozenset({"segment_id", "road_id"})


@dataclass(frozen=True)
class SpatialIssue:
    severity: str
    field: str
    message: str

    @property
    def blocking(self) -> bool:
        return self.severity == "blocking"


@dataclass(frozen=True)
class SpatialReview:
    feature_count: int
    canonical_row_count: int
    matched_count: int
    source_crs: str
    target_crs: str
    join_source_field: str
    join_canonical_field: str
    unmatched_source_ids: tuple[str, ...]
    unmatched_canonical_ids: tuple[str, ...]
    duplicate_source_ids: tuple[str, ...]
    issues: tuple[SpatialIssue, ...]

    @property
    def blocking_issues(self) -> tuple[SpatialIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["result"] = "FAIL" if self.blocking_issues else "PASS"
        return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_spatial_source(
    package_path: str | Path,
    content: bytes,
    *,
    source_id_field: str,
    canonical_id_field: str = "segment_id",
    source_crs: str = "",
    source_owner: str,
    acquired_date: str,
    source_reference: str,
    provenance_confirmed: bool,
) -> Path:
    """Preserve a GeoJSON source and its explicit, reviewable ingestion settings."""

    package = Path(package_path).resolve()
    if not package.is_dir():
        raise ValueError(f"Spatial package workspace does not exist: '{package}'.")
    required = {
        "source_id_field": source_id_field,
        "canonical_id_field": canonical_id_field,
        "source_owner": source_owner,
        "acquired_date": acquired_date,
        "source_reference": source_reference,
    }
    for field, value in required.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Spatial field '{field}' must be a non-empty string.")
    if canonical_id_field not in JOIN_FIELDS:
        raise ValueError("Spatial field 'canonical_id_field' must be 'segment_id' or 'road_id'.")
    if not provenance_confirmed:
        raise ValueError("Spatial provenance and CRS declarations require operator confirmation.")
    try:
        document = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Spatial source is not valid UTF-8 GeoJSON: {exc}.") from exc
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("Spatial source must be a GeoJSON FeatureCollection.")
    source_path = package / SPATIAL_SOURCE_NAME
    source_path.write_bytes(content)
    for derived_name in (SPATIAL_ARTIFACT_NAME, SPATIAL_REVIEW_NAME, SPATIAL_METADATA_NAME):
        (package / derived_name).unlink(missing_ok=True)
    _write_json(package / SPATIAL_INPUT_NAME, {
        "format": "GeoJSON",
        "source_path": SPATIAL_SOURCE_NAME,
        "source_checksum": _checksum(source_path),
        "source_id_field": source_id_field.strip(),
        "canonical_id_field": canonical_id_field,
        "declared_source_crs": source_crs.strip(),
        "target_crs": TARGET_CRS,
        "source_owner": source_owner.strip(),
        "acquired_date": acquired_date.strip(),
        "source_reference": source_reference.strip(),
        "provenance_confirmed": True,
    })
    return source_path


def _geojson_crs(document: Mapping[str, Any]) -> str:
    value = document.get("crs")
    if not value:
        return ""
    if not isinstance(value, Mapping):
        raise ValueError("GeoJSON field 'crs' must be an object.")
    properties = value.get("properties")
    if not isinstance(properties, Mapping):
        raise ValueError("GeoJSON field 'crs.properties' must be an object.")
    return str(properties.get("name", "")).strip()


def _review(package: Path, review: SpatialReview) -> SpatialReview:
    _write_json(package / SPATIAL_REVIEW_NAME, review.as_dict())
    return review


def validate_spatial_workspace(
    package_path: str | Path,
    canonical_path: str | Path,
) -> SpatialReview | None:
    """Validate, join, and normalize optional line geometry for one package."""

    package = Path(package_path).resolve()
    input_path = package / SPATIAL_INPUT_NAME
    if not input_path.is_file():
        return None
    settings = json.loads(input_path.read_text(encoding="utf-8"))
    source_path = (package / str(settings.get("source_path", ""))).resolve()
    issues: list[SpatialIssue] = []
    if source_path.parent != package or not source_path.is_file():
        issues.append(SpatialIssue("blocking", "source_path", "Spatial source is missing or escapes its package."))
    elif _checksum(source_path) != settings.get("source_checksum"):
        issues.append(SpatialIssue("blocking", "source_checksum", "Spatial source checksum does not match the preserved source."))
    canonical = pd.read_csv(canonical_path)
    source_id = str(settings.get("source_id_field", "")).strip()
    canonical_id = str(settings.get("canonical_id_field", "")).strip()
    declared_crs = str(settings.get("declared_source_crs", "")).strip()
    embedded_crs = ""
    document: dict[str, Any] = {}
    if not issues:
        try:
            document = json.loads(source_path.read_text(encoding="utf-8-sig"))
            embedded_crs = _geojson_crs(document)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            issues.append(SpatialIssue("blocking", "geojson", str(exc)))
    if declared_crs and embedded_crs:
        try:
            if CRS.from_user_input(declared_crs) != CRS.from_user_input(embedded_crs):
                issues.append(SpatialIssue("blocking", "source_crs", "Declared CRS conflicts with the GeoJSON CRS."))
        except Exception as exc:
            issues.append(SpatialIssue("blocking", "source_crs", f"Invalid CRS: {exc}."))
    resolved_crs = declared_crs or embedded_crs
    if not resolved_crs:
        issues.append(SpatialIssue("blocking", "source_crs", "Source CRS is missing; declare it explicitly. CRS guessing is not allowed."))
    else:
        try:
            CRS.from_user_input(resolved_crs)
        except Exception as exc:
            issues.append(SpatialIssue("blocking", "source_crs", f"Source CRS '{resolved_crs}' is invalid or unsupported: {exc}."))
    frame = None
    if not issues:
        try:
            frame = gpd.GeoDataFrame.from_features(document["features"], crs=resolved_crs)
        except Exception as exc:
            issues.append(SpatialIssue("blocking", "geojson", f"GeoJSON features could not be read: {exc}."))
    if frame is not None:
        if frame.empty:
            issues.append(SpatialIssue("blocking", "geometry", "Spatial source contains no features."))
        if source_id not in frame.columns:
            issues.append(SpatialIssue("blocking", source_id or "source_id_field", f"Spatial identifier column '{source_id}' is missing."))
        if canonical_id not in JOIN_FIELDS or canonical_id not in canonical.columns:
            issues.append(SpatialIssue("blocking", "canonical_id_field", f"Canonical identifier '{canonical_id}' is unavailable."))
        bad_types = sorted(set(frame.geometry.geom_type) - {"LineString", "MultiLineString"})
        if bad_types:
            issues.append(SpatialIssue("blocking", "geometry", "Only LineString/MultiLineString geometry is supported; found " + ", ".join(bad_types) + "."))
        if frame.geometry.isna().any() or frame.geometry.is_empty.any() or (~frame.geometry.is_valid).any():
            issues.append(SpatialIssue("blocking", "geometry", "Geometry must be present, non-empty, and valid for every feature."))
    unmatched_source: tuple[str, ...] = ()
    unmatched_canonical: tuple[str, ...] = ()
    duplicate_source: tuple[str, ...] = ()
    matched = 0
    if frame is not None and not issues:
        frame[source_id] = frame[source_id].astype(str).str.strip()
        canonical[canonical_id] = canonical[canonical_id].astype(str).str.strip()
        duplicate_source = tuple(sorted(set(frame.loc[frame[source_id].duplicated(False), source_id])))
        if frame[source_id].eq("").any() or duplicate_source:
            issues.append(SpatialIssue("blocking", source_id, "Spatial identifiers must be non-empty and unique."))
        if canonical[canonical_id].duplicated().any():
            issues.append(SpatialIssue("blocking", canonical_id, f"Canonical identifier '{canonical_id}' is not unique; the join would be ambiguous."))
        source_ids = set(frame[source_id])
        canonical_ids = set(canonical[canonical_id])
        unmatched_source = tuple(sorted(source_ids - canonical_ids))
        unmatched_canonical = tuple(sorted(canonical_ids - source_ids))
        if unmatched_source:
            issues.append(SpatialIssue("blocking", source_id, f"{len(unmatched_source)} spatial identifier(s) do not match canonical inventory."))
        if unmatched_canonical:
            issues.append(SpatialIssue("blocking", canonical_id, f"{len(unmatched_canonical)} canonical row(s) have no spatial feature."))
        matched = len(source_ids & canonical_ids)
    review = SpatialReview(
        feature_count=0 if frame is None else len(frame), canonical_row_count=len(canonical),
        matched_count=matched, source_crs=resolved_crs, target_crs=TARGET_CRS,
        join_source_field=source_id, join_canonical_field=canonical_id,
        unmatched_source_ids=unmatched_source, unmatched_canonical_ids=unmatched_canonical,
        duplicate_source_ids=duplicate_source,
        issues=tuple(issues),
    )
    if review.blocking_issues or frame is None:
        return _review(package, review)
    canonical_join = pd.DataFrame({
        "_canonical_join_id": canonical[canonical_id],
        "_canonical_road_id": canonical["road_id"],
        "_canonical_segment_id": canonical["segment_id"],
    })
    joined = frame.merge(
        canonical_join, left_on=source_id, right_on="_canonical_join_id", how="left"
    )
    joined["road_id"] = joined["_canonical_road_id"]
    joined["segment_id"] = joined["_canonical_segment_id"]
    try:
        joined = joined[["road_id", "segment_id", "geometry"]].to_crs(TARGET_CRS)
    except Exception as exc:
        review = SpatialReview(**{
            **review.__dict__,
            "issues": (SpatialIssue("blocking", "source_crs", f"Geometry could not be transformed to {TARGET_CRS}: {exc}."),),
        })
        return _review(package, review)
    minx, miny, maxx, maxy = joined.total_bounds
    if not (-180 <= minx <= 180 and -180 <= maxx <= 180 and -90 <= miny <= 90 and -90 <= maxy <= 90):
        review = SpatialReview(**{**review.__dict__, "issues": (SpatialIssue("blocking", "geometry", "Transformed geometry falls outside valid EPSG:4326 longitude/latitude ranges."),)})
        return _review(package, review)
    artifact = package / SPATIAL_ARTIFACT_NAME
    joined.to_file(artifact, driver="GeoJSON")
    metadata = {
        "artifact_path": SPATIAL_ARTIFACT_NAME,
        "artifact_checksum": _checksum(artifact),
        "source_checksum": settings["source_checksum"],
        "feature_count": len(joined),
        "source_crs": resolved_crs,
        "target_crs": TARGET_CRS,
        "join_source_field": source_id,
        "join_canonical_field": canonical_id,
        "provenance": {key: settings[key] for key in ("source_owner", "acquired_date", "source_reference")},
    }
    _write_json(package / SPATIAL_METADATA_NAME, metadata)
    return _review(package, review)


def load_spatial_artifact(data_directory: str | Path) -> dict[str, Any] | None:
    """Load an optional normalized runtime GeoJSON artifact."""

    path = Path(data_directory).resolve() / SPATIAL_ARTIFACT_NAME
    if not path.is_file():
        return None
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("type") != "FeatureCollection":
        raise ValueError(f"Spatial artifact '{path}' is not a GeoJSON FeatureCollection.")
    return document


def validate_runtime_spatial_artifact(
    data_directory: str | Path, canonical: pd.DataFrame
) -> int | None:
    """Verify a normalized artifact still resolves exactly to canonical segments."""

    document = load_spatial_artifact(data_directory)
    if document is None:
        return None
    features = document.get("features", [])
    segment_ids: list[str] = []
    for feature in features:
        properties = feature.get("properties", {})
        segment_id = str(properties.get("segment_id", "")).strip()
        road_id = str(properties.get("road_id", "")).strip()
        geometry = feature.get("geometry", {})
        if not segment_id or not road_id:
            raise ValueError("Runtime spatial feature is missing canonical road_id/segment_id linkage.")
        if geometry.get("type") not in {"LineString", "MultiLineString"}:
            raise ValueError("Runtime spatial artifact contains unsupported geometry type.")
        coordinates = list(_runtime_coordinates(geometry.get("coordinates", [])))
        if not coordinates or any(
            not (-180 <= longitude <= 180 and -90 <= latitude <= 90)
            for longitude, latitude in coordinates
        ):
            raise ValueError("Runtime spatial artifact contains empty or out-of-range coordinates.")
        segment_ids.append(segment_id)
    if len(segment_ids) != len(set(segment_ids)):
        raise ValueError("Runtime spatial artifact contains duplicate segment identifiers.")
    expected = set(canonical["segment_id"].astype(str).str.strip())
    actual = set(segment_ids)
    if actual != expected:
        raise ValueError(
            "Runtime spatial/canonical join mismatch: "
            f"{len(expected - actual)} canonical segment(s) missing geometry and "
            f"{len(actual - expected)} geometry feature(s) unmatched."
        )
    return len(features)


def _runtime_coordinates(value):
    if (
        isinstance(value, list) and len(value) >= 2
        and all(isinstance(item, (int, float)) for item in value[:2])
    ):
        yield float(value[0]), float(value[1])
    elif isinstance(value, list):
        for item in value:
            yield from _runtime_coordinates(item)


def geometry_signatures(data_directory: str | Path) -> dict[str, str]:
    """Return stable per-segment signatures for version comparisons."""

    document = load_spatial_artifact(data_directory)
    if document is None:
        return {}
    signatures: dict[str, str] = {}
    for feature in document.get("features", []):
        segment_id = str(feature.get("properties", {}).get("segment_id", "")).strip()
        if not segment_id or segment_id in signatures:
            raise ValueError("Spatial artifact segment identifiers must be present and unique.")
        geometry = json.dumps(feature.get("geometry"), sort_keys=True, separators=(",", ":"))
        signatures[segment_id] = hashlib.sha256(geometry.encode("utf-8")).hexdigest()
    return signatures
