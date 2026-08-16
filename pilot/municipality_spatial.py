"""Municipality road-geometry ingestion and immutable runtime artifacts.

GeoJSON and validated shapefile bundles normalize through one contract. Source
CRS is declared by GeoJSON or read from a shapefile ``.prj``; it is never
guessed. Valid input is normalized to EPSG:4326 and joined to the shared
canonical inventory by an operator-selected identifier.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from pathlib import PurePath
import shutil
import tempfile
from typing import Any, Iterable, Mapping

import geopandas as gpd
import pandas as pd
from pyproj import CRS


SPATIAL_SOURCE_NAME = "source_roads.raw.geojson"
SPATIAL_INPUT_NAME = "spatial_input.json"
SPATIAL_ARTIFACT_NAME = "roads.geojson"
SPATIAL_REVIEW_NAME = "spatial_review.json"
SPATIAL_METADATA_NAME = "spatial_metadata.json"
SHAPEFILE_SOURCE_DIRECTORY = "source_roads_shapefile"
TARGET_CRS = "EPSG:4326"
JOIN_FIELDS = frozenset({"segment_id", "road_id"})
SHAPEFILE_REQUIRED_EXTENSIONS = frozenset({".shp", ".shx", ".dbf", ".prj"})
SHAPEFILE_OPTIONAL_EXTENSIONS = frozenset({".cpg"})
DEFAULT_MAX_BUNDLE_BYTES = 100 * 1024 * 1024
IDENTIFIER_FIELD_NAMES = (
    "segment_id", "segmentid", "seg_id", "road_id", "roadid",
    "asset_id", "assetid", "feature_id", "featureid",
)


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
    duplicate_canonical_ids: tuple[str, ...]
    matched_ids: tuple[str, ...]
    linestring_count: int
    multilinestring_count: int
    empty_geometry_count: int
    invalid_geometry_count: int
    geometry_bounds: tuple[float, float, float, float] | None
    match_percentage: float
    issues: tuple[SpatialIssue, ...]

    @property
    def blocking_issues(self) -> tuple[SpatialIssue, ...]:
        return tuple(issue for issue in self.issues if issue.blocking)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.blocking_issues:
            value["result"] = "BLOCKING"
        elif any(issue.severity == "warning" for issue in self.issues):
            value["result"] = "WARNING"
        else:
            value["result"] = "PASS"
        return value


@dataclass(frozen=True)
class ShapefileBundleSummary:
    basename: str
    filenames: tuple[str, ...]
    checksums: Mapping[str, str]
    total_bytes: int
    bundle_checksum: str


@dataclass(frozen=True)
class SpatialSourcePreview:
    source_format: str
    feature_count: int
    attribute_columns: tuple[str, ...]
    value_examples: Mapping[str, tuple[str, ...]]
    geometry_counts: Mapping[str, int]
    empty_geometry_count: int
    invalid_geometry_count: int
    geometry_bounds: tuple[float, float, float, float] | None
    source_crs: str
    source_checksum: str


@dataclass(frozen=True)
class SpatialMatchPreview:
    source_id_field: str
    canonical_id_field: str
    feature_count: int
    canonical_count: int
    exact_match_count: int
    source_only_ids: tuple[str, ...]
    canonical_only_ids: tuple[str, ...]
    duplicate_source_ids: tuple[str, ...]
    duplicate_canonical_ids: tuple[str, ...]
    matched_ids: tuple[str, ...]

    @property
    def match_percentage(self) -> float:
        return round(100 * self.exact_match_count / self.canonical_count, 1) if self.canonical_count else 0.0


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _content_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_bundle_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Shapefile bundle contains an empty filename.")
    if PurePath(name).name != name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ValueError(f"Shapefile bundle filename '{name}' is unsafe; folders and traversal are not allowed.")
    return name


def validate_shapefile_bundle(
    files: Mapping[str, bytes], *, max_bytes: int = DEFAULT_MAX_BUNDLE_BYTES
) -> ShapefileBundleSummary:
    """Validate one logical shapefile upload before invoking GeoPandas/GDAL."""

    if not isinstance(files, Mapping) or not files:
        raise ValueError("Shapefile bundle is empty.")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise ValueError("Shapefile bundle size limit must be a positive integer.")
    by_extension: dict[str, tuple[str, bytes]] = {}
    basenames: dict[str, str] = {}
    total = 0
    for supplied_name, content in files.items():
        name = _safe_bundle_name(supplied_name)
        if not isinstance(content, bytes):
            raise ValueError(f"Shapefile component '{name}' must contain bytes.")
        extension = Path(name).suffix.casefold()
        if extension not in SHAPEFILE_REQUIRED_EXTENSIONS | SHAPEFILE_OPTIONAL_EXTENSIONS:
            raise ValueError(f"Unsupported shapefile bundle component: '{name}'.")
        if extension in by_extension:
            raise ValueError(f"Duplicate shapefile component: {extension}.")
        if not content:
            raise ValueError(f"Shapefile component '{name}' is empty.")
        stem = Path(name).stem
        basenames[stem.casefold()] = stem
        by_extension[extension] = (name, content)
        total += len(content)
    if len(basenames) != 1:
        names = ", ".join(sorted(name for name, _ in by_extension.values()))
        raise ValueError(f"Shapefile bundle components must share one basename; received: {names}.")
    for extension in sorted(SHAPEFILE_REQUIRED_EXTENSIONS):
        if extension not in by_extension:
            raise ValueError(f"Missing required shapefile component: {extension}.")
    if total > max_bytes:
        raise ValueError(
            f"Shapefile bundle is {total:,} bytes; the operator limit is {max_bytes:,} bytes."
        )
    checksums = {
        name: _content_checksum(content)
        for name, content in sorted(by_extension.values(), key=lambda item: item[0].casefold())
    }
    fingerprint_payload = "\n".join(
        f"{name.casefold()}:{checksums[name]}:{len(by_extension[Path(name).suffix.casefold()][1])}"
        for name in sorted(checksums, key=str.casefold)
    )
    return ShapefileBundleSummary(
        basename=next(iter(basenames.values())),
        filenames=tuple(sorted(checksums, key=str.casefold)),
        checksums=checksums,
        total_bytes=total,
        bundle_checksum=hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
    )


def suggest_spatial_identifier_fields(columns: Iterable[str]) -> tuple[str, ...]:
    """Return deterministic, editable identifier-field suggestions."""

    def normalized(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    priority = {normalized(name): index for index, name in enumerate(IDENTIFIER_FIELD_NAMES)}
    candidates = []
    for position, column in enumerate(columns):
        column_name = str(column)
        key = normalized(column_name)
        if key in priority:
            candidates.append((priority[key], position, column_name))
        elif key.endswith("id"):
            candidates.append((len(priority), position, column_name))
    return tuple(item[2] for item in sorted(candidates))


def build_exact_match_preview(
    source_values: Iterable[Any],
    canonical_values: Iterable[Any],
    *,
    source_id_field: str,
    canonical_id_field: str,
) -> SpatialMatchPreview:
    """Summarize the authoritative exact-string join without changing any IDs."""

    source = pd.Series(list(source_values), dtype="object").astype(str).str.strip()
    canonical = pd.Series(list(canonical_values), dtype="object").astype(str).str.strip()
    duplicate_source = tuple(sorted(set(source[source.duplicated(False)])))
    duplicate_canonical = tuple(sorted(set(canonical[canonical.duplicated(False)])))
    source_ids = set(source)
    canonical_ids = set(canonical)
    return SpatialMatchPreview(
        source_id_field=source_id_field,
        canonical_id_field=canonical_id_field,
        feature_count=len(source),
        canonical_count=len(canonical),
        exact_match_count=len(source_ids & canonical_ids),
        source_only_ids=tuple(sorted(source_ids - canonical_ids)),
        canonical_only_ids=tuple(sorted(canonical_ids - source_ids)),
        duplicate_source_ids=duplicate_source,
        duplicate_canonical_ids=duplicate_canonical,
        matched_ids=tuple(sorted(source_ids & canonical_ids)),
    )


def _frame_preview(
    frame: gpd.GeoDataFrame, *, source_format: str, source_checksum: str
) -> SpatialSourcePreview:
    geometry_counts = {
        str(name): int(count)
        for name, count in frame.geometry.geom_type.value_counts(dropna=False).items()
    }
    columns = tuple(str(column) for column in frame.columns if column != frame.geometry.name)
    examples = {
        column: tuple(
            str(value) for value in frame[column].dropna().astype(str).drop_duplicates().head(3)
        )
        for column in columns
    }
    bounds = None
    if not frame.empty and not frame.geometry.dropna().empty:
        bounds = tuple(float(value) for value in frame.total_bounds)
    return SpatialSourcePreview(
        source_format=source_format,
        feature_count=len(frame),
        attribute_columns=columns,
        value_examples=examples,
        geometry_counts=geometry_counts,
        empty_geometry_count=int(frame.geometry.isna().sum() + frame.geometry.is_empty.sum()),
        invalid_geometry_count=int((~frame.geometry.dropna().is_valid).sum()),
        geometry_bounds=bounds,
        source_crs=frame.crs.to_string() if frame.crs is not None else "",
        source_checksum=source_checksum,
    )


def inspect_geojson_source(content: bytes, *, declared_crs: str = "") -> SpatialSourcePreview:
    """Inspect a GeoJSON upload without preserving or registering it."""

    try:
        document = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Spatial source is not valid UTF-8 GeoJSON: {exc}.") from exc
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("Spatial source must be a GeoJSON FeatureCollection.")
    embedded_crs = _geojson_crs(document)
    if declared_crs.strip() and embedded_crs:
        try:
            if CRS.from_user_input(declared_crs) != CRS.from_user_input(embedded_crs):
                raise ValueError("Declared CRS conflicts with the GeoJSON CRS.")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"GeoJSON CRS is invalid or unsupported: {exc}.") from exc
    source_crs = declared_crs.strip() or embedded_crs
    if not source_crs:
        raise ValueError("Source CRS is missing; declare it explicitly. CRS guessing is not allowed.")
    try:
        CRS.from_user_input(source_crs)
        frame = gpd.GeoDataFrame.from_features(document.get("features", []), crs=source_crs)
    except Exception as exc:
        raise ValueError(f"GeoJSON could not be inspected: {exc}.") from exc
    return _frame_preview(frame, source_format="GeoJSON", source_checksum=_content_checksum(content))


def _write_bundle(directory: Path, files: Mapping[str, bytes]) -> None:
    directory.mkdir(parents=False, exist_ok=False)
    for name, content in files.items():
        (directory / _safe_bundle_name(name)).write_bytes(content)


def _read_shapefile_frame(directory: Path, summary: ShapefileBundleSummary) -> gpd.GeoDataFrame:
    shp_name = next(name for name in summary.filenames if Path(name).suffix.casefold() == ".shp")
    try:
        frame = gpd.read_file(directory / shp_name)
    except Exception as exc:
        raise ValueError(
            "Shapefile bundle could not be read; confirm all components came from the same intact export."
        ) from exc
    if frame.crs is None:
        raise ValueError("Shapefile projection information is missing or unreadable; a valid .prj is required.")
    try:
        CRS.from_user_input(frame.crs)
    except Exception as exc:
        raise ValueError("Shapefile projection information is unreadable or unsupported.") from exc
    return frame


def inspect_shapefile_bundle(
    files: Mapping[str, bytes], *, max_bytes: int = DEFAULT_MAX_BUNDLE_BYTES
) -> SpatialSourcePreview:
    """Validate and inspect a multi-file shapefile upload with friendly errors."""

    summary = validate_shapefile_bundle(files, max_bytes=max_bytes)
    with tempfile.TemporaryDirectory(prefix="paventra-shapefile-preview-") as directory_name:
        directory = Path(directory_name)
        _write_bundle(directory / "bundle", files)
        frame = _read_shapefile_frame(directory / "bundle", summary)
    return _frame_preview(
        frame, source_format="Shapefile", source_checksum=summary.bundle_checksum
    )


def inspect_saved_spatial_source(package_path: str | Path) -> SpatialSourcePreview | None:
    """Reopen a preserved source for operator review without requiring re-upload."""

    package = Path(package_path).resolve()
    input_path = package / SPATIAL_INPUT_NAME
    if not input_path.is_file():
        return None
    settings = json.loads(input_path.read_text(encoding="utf-8"))
    source_path = (package / str(settings.get("source_path", ""))).resolve()
    if source_path.parent != package:
        raise ValueError("Spatial source path escapes its package workspace.")
    if settings.get("format") == "GeoJSON":
        return inspect_geojson_source(
            source_path.read_bytes(), declared_crs=str(settings.get("declared_source_crs", ""))
        )
    if settings.get("format") == "Shapefile":
        return inspect_shapefile_bundle({
            item.name: item.read_bytes() for item in source_path.iterdir() if item.is_file()
        })
    raise ValueError(f"Spatial source format '{settings.get('format')}' is unsupported.")


def update_spatial_identifier_mapping(
    package_path: str | Path, *, source_id_field: str, canonical_id_field: str
) -> None:
    """Update only the editable exact-join selection and invalidate derived output."""

    package = Path(package_path).resolve()
    input_path = package / SPATIAL_INPUT_NAME
    settings = json.loads(input_path.read_text(encoding="utf-8"))
    preview = inspect_saved_spatial_source(package)
    if preview is None or source_id_field not in preview.attribute_columns:
        raise ValueError(f"Spatial identifier column '{source_id_field}' is unavailable.")
    if canonical_id_field not in JOIN_FIELDS:
        raise ValueError("Spatial canonical identifier must be 'segment_id' or 'road_id'.")
    settings["source_id_field"] = source_id_field
    settings["canonical_id_field"] = canonical_id_field
    _write_json(input_path, settings)
    for name in (SPATIAL_ARTIFACT_NAME, SPATIAL_REVIEW_NAME, SPATIAL_METADATA_NAME):
        (package / name).unlink(missing_ok=True)


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
        "source_files": [{
            "name": SPATIAL_SOURCE_NAME,
            "checksum": _checksum(source_path),
            "size": len(content),
        }],
    })
    return source_path


def save_shapefile_source(
    package_path: str | Path,
    files: Mapping[str, bytes],
    *,
    source_id_field: str,
    canonical_id_field: str = "segment_id",
    source_owner: str,
    acquired_date: str,
    source_reference: str,
    provenance_confirmed: bool,
    max_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
) -> Path:
    """Preserve a validated shapefile bundle as one spatial source."""

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
        raise ValueError("Spatial provenance requires operator confirmation.")
    summary = validate_shapefile_bundle(files, max_bytes=max_bytes)
    preview = inspect_shapefile_bundle(files, max_bytes=max_bytes)
    if source_id_field not in preview.attribute_columns:
        raise ValueError(f"Spatial identifier column '{source_id_field}' is missing from the shapefile.")
    destination = package / SHAPEFILE_SOURCE_DIRECTORY
    if destination.exists():
        shutil.rmtree(destination)
    _write_bundle(destination, files)
    (package / SPATIAL_SOURCE_NAME).unlink(missing_ok=True)
    for derived_name in (SPATIAL_ARTIFACT_NAME, SPATIAL_REVIEW_NAME, SPATIAL_METADATA_NAME):
        (package / derived_name).unlink(missing_ok=True)
    _write_json(package / SPATIAL_INPUT_NAME, {
        "format": "Shapefile",
        "source_path": SHAPEFILE_SOURCE_DIRECTORY,
        "source_checksum": summary.bundle_checksum,
        "bundle_checksum": summary.bundle_checksum,
        "source_id_field": source_id_field.strip(),
        "canonical_id_field": canonical_id_field,
        "declared_source_crs": "",
        "detected_source_crs": preview.source_crs,
        "target_crs": TARGET_CRS,
        "source_owner": source_owner.strip(),
        "acquired_date": acquired_date.strip(),
        "source_reference": source_reference.strip(),
        "provenance_confirmed": True,
        "source_files": [
            {"name": name, "checksum": summary.checksums[name], "size": len(files[name])}
            for name in summary.filenames
        ],
        "bundle_bytes": summary.total_bytes,
    })
    return destination


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
    canonical_path: str | Path | pd.DataFrame,
) -> SpatialReview | None:
    """Validate, join, and normalize optional line geometry for one package."""

    package = Path(package_path).resolve()
    input_path = package / SPATIAL_INPUT_NAME
    if not input_path.is_file():
        return None
    settings = json.loads(input_path.read_text(encoding="utf-8"))
    source_path = (package / str(settings.get("source_path", ""))).resolve()
    issues: list[SpatialIssue] = []
    source_format = str(settings.get("format", ""))
    if source_path.parent != package or not source_path.exists():
        issues.append(SpatialIssue("blocking", "source_path", "Spatial source is missing or escapes its package."))
    canonical = (
        canonical_path.copy()
        if isinstance(canonical_path, pd.DataFrame)
        else pd.read_csv(canonical_path)
    )
    source_id = str(settings.get("source_id_field", "")).strip()
    canonical_id = str(settings.get("canonical_id_field", "")).strip()
    declared_crs = str(settings.get("declared_source_crs", "")).strip()
    embedded_crs = ""
    document: dict[str, Any] = {}
    frame = None
    if not issues and source_format == "GeoJSON":
        if not source_path.is_file() or _checksum(source_path) != settings.get("source_checksum"):
            issues.append(SpatialIssue("blocking", "source_checksum", "Spatial source checksum does not match the preserved source."))
    if not issues and source_format == "GeoJSON":
        try:
            document = json.loads(source_path.read_text(encoding="utf-8-sig"))
            embedded_crs = _geojson_crs(document)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            issues.append(SpatialIssue("blocking", "geojson", str(exc)))
    if source_format == "GeoJSON" and declared_crs and embedded_crs:
        try:
            if CRS.from_user_input(declared_crs) != CRS.from_user_input(embedded_crs):
                issues.append(SpatialIssue("blocking", "source_crs", "Declared CRS conflicts with the GeoJSON CRS."))
        except Exception as exc:
            issues.append(SpatialIssue("blocking", "source_crs", f"Invalid CRS: {exc}."))
    resolved_crs = declared_crs or embedded_crs
    if not issues and source_format == "Shapefile":
        try:
            stored_files = {
                item.name: item.read_bytes()
                for item in source_path.iterdir()
                if item.is_file()
            }
            summary = validate_shapefile_bundle(stored_files)
            if summary.bundle_checksum != settings.get("bundle_checksum"):
                issues.append(SpatialIssue("blocking", "source_checksum", "Shapefile bundle checksum does not match the preserved source."))
            else:
                frame = _read_shapefile_frame(source_path, summary)
                resolved_crs = frame.crs.to_string()
        except (OSError, ValueError) as exc:
            issues.append(SpatialIssue("blocking", "shapefile", str(exc)))
    elif source_format not in {"GeoJSON", "Shapefile"}:
        issues.append(SpatialIssue("blocking", "format", f"Spatial source format '{source_format}' is unsupported."))
    if not resolved_crs:
        issues.append(SpatialIssue("blocking", "source_crs", "Source CRS is missing; declare it explicitly. CRS guessing is not allowed."))
    else:
        try:
            CRS.from_user_input(resolved_crs)
        except Exception as exc:
            issues.append(SpatialIssue("blocking", "source_crs", f"Source CRS '{resolved_crs}' is invalid or unsupported: {exc}."))
    if not issues and source_format == "GeoJSON":
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
    duplicate_canonical: tuple[str, ...] = ()
    matched_ids: tuple[str, ...] = ()
    matched = 0
    if frame is not None and not issues:
        frame[source_id] = frame[source_id].astype(str).str.strip()
        canonical[canonical_id] = canonical[canonical_id].astype(str).str.strip()
        match_preview = build_exact_match_preview(
            frame[source_id], canonical[canonical_id],
            source_id_field=source_id, canonical_id_field=canonical_id,
        )
        duplicate_source = match_preview.duplicate_source_ids
        matched_ids = match_preview.matched_ids
        if frame[source_id].eq("").any() or duplicate_source:
            issues.append(SpatialIssue("blocking", source_id, "Spatial identifiers must be non-empty and unique."))
        duplicate_canonical = match_preview.duplicate_canonical_ids
        if duplicate_canonical:
            issues.append(SpatialIssue("blocking", canonical_id, f"Canonical identifier '{canonical_id}' is not unique; the join would be ambiguous."))
        unmatched_source = match_preview.source_only_ids
        unmatched_canonical = match_preview.canonical_only_ids
        if unmatched_source:
            issues.append(SpatialIssue("blocking", source_id, f"{len(unmatched_source)} spatial identifier(s) do not match canonical inventory."))
        if unmatched_canonical:
            issues.append(SpatialIssue("blocking", canonical_id, f"{len(unmatched_canonical)} canonical row(s) have no spatial feature."))
        matched = match_preview.exact_match_count
    geometry_counts = (
        frame.geometry.geom_type.value_counts().to_dict() if frame is not None else {}
    )
    empty_count = (
        int(frame.geometry.isna().sum() + frame.geometry.is_empty.sum())
        if frame is not None else 0
    )
    invalid_count = (
        int((~frame.geometry.dropna().is_valid).sum()) if frame is not None else 0
    )
    bounds = None
    if frame is not None and not frame.empty and not frame.geometry.dropna().empty:
        bounds = tuple(float(value) for value in frame.total_bounds)
    review = SpatialReview(
        feature_count=0 if frame is None else len(frame), canonical_row_count=len(canonical),
        matched_count=matched, source_crs=resolved_crs, target_crs=TARGET_CRS,
        join_source_field=source_id, join_canonical_field=canonical_id,
        unmatched_source_ids=unmatched_source, unmatched_canonical_ids=unmatched_canonical,
        duplicate_source_ids=duplicate_source,
        duplicate_canonical_ids=duplicate_canonical,
        matched_ids=matched_ids,
        linestring_count=int(geometry_counts.get("LineString", 0)),
        multilinestring_count=int(geometry_counts.get("MultiLineString", 0)),
        empty_geometry_count=empty_count,
        invalid_geometry_count=invalid_count,
        geometry_bounds=bounds,
        match_percentage=(round(100 * matched / len(canonical), 1) if len(canonical) else 0.0),
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
        "source_format": source_format,
        "source_files": settings.get("source_files", []),
        "bundle_checksum": settings.get("bundle_checksum"),
        "feature_count": len(joined),
        "source_crs": resolved_crs,
        "target_crs": TARGET_CRS,
        "join_source_field": source_id,
        "join_canonical_field": canonical_id,
        "provenance": {key: settings[key] for key in ("source_owner", "acquired_date", "source_reference")},
        "match_coverage_percent": review.match_percentage,
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


def spatial_readiness_snapshot(package_path: str | Path) -> Mapping[str, str]:
    """Return actual checksums for all readiness-sensitive spatial artifacts."""

    package = Path(package_path).resolve()
    snapshot: dict[str, str] = {}
    for name in (
        SPATIAL_INPUT_NAME, SPATIAL_SOURCE_NAME, SPATIAL_ARTIFACT_NAME,
        SPATIAL_REVIEW_NAME, SPATIAL_METADATA_NAME,
    ):
        path = package / name
        if path.is_file():
            snapshot[name] = _checksum(path)
    bundle = package / SHAPEFILE_SOURCE_DIRECTORY
    if bundle.is_dir():
        for path in sorted(bundle.iterdir(), key=lambda item: item.name.casefold()):
            if path.is_file():
                snapshot[f"{SHAPEFILE_SOURCE_DIRECTORY}/{path.name}"] = _checksum(path)
    return snapshot


def validate_preserved_spatial_source(data_directory: str | Path) -> None:
    """Verify every preserved source component against reviewed checksums."""

    directory = Path(data_directory).resolve()
    input_path = directory / SPATIAL_INPUT_NAME
    if not input_path.is_file():
        return
    settings = json.loads(input_path.read_text(encoding="utf-8"))
    source_path = (directory / str(settings.get("source_path", ""))).resolve()
    if source_path.parent != directory:
        raise ValueError("Preserved spatial source path escapes its version directory.")
    source_files = settings.get("source_files", [])
    expected = {
        str(item.get("name")): str(item.get("checksum"))
        for item in source_files if isinstance(item, Mapping)
    }
    if settings.get("format") == "GeoJSON":
        actual = {source_path.name: _checksum(source_path)} if source_path.is_file() else {}
    elif settings.get("format") == "Shapefile":
        if not source_path.is_dir():
            raise ValueError("Preserved shapefile bundle directory is missing.")
        actual = {
            item.name: _checksum(item) for item in source_path.iterdir() if item.is_file()
        }
        files = {item.name: item.read_bytes() for item in source_path.iterdir() if item.is_file()}
        if validate_shapefile_bundle(files).bundle_checksum != settings.get("bundle_checksum"):
            raise ValueError("Preserved shapefile bundle fingerprint does not match.")
    else:
        raise ValueError(f"Preserved spatial source format '{settings.get('format')}' is unsupported.")
    if actual != expected:
        raise ValueError("Preserved spatial source component checksums do not match reviewed provenance.")


def copy_spatial_package_artifacts(
    source_directory: str | Path, destination_directory: str | Path
) -> None:
    """Copy optional spatial source/review/runtime artifacts without format branching."""

    source = Path(source_directory).resolve()
    destination = Path(destination_directory).resolve()
    for name in (
        SPATIAL_SOURCE_NAME, SPATIAL_INPUT_NAME, SPATIAL_ARTIFACT_NAME,
        SPATIAL_REVIEW_NAME, SPATIAL_METADATA_NAME,
    ):
        path = source / name
        if path.is_file():
            shutil.copy2(path, destination / name)
    bundle = source / SHAPEFILE_SOURCE_DIRECTORY
    if bundle.is_dir():
        shutil.copytree(bundle, destination / SHAPEFILE_SOURCE_DIRECTORY, dirs_exist_ok=True)


def load_spatial_metadata(data_directory: str | Path) -> Mapping[str, Any] | None:
    """Load concise reviewed metadata for operator/version detail surfaces."""

    path = Path(data_directory).resolve() / SPATIAL_METADATA_NAME
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Spatial metadata '{path}' must contain an object.")
    return value
