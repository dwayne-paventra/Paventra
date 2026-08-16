"""Reusable operator controls for optional municipality GIS intake."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd
import streamlit as st

from pilot.municipality_spatial import (
    DEFAULT_MAX_BUNDLE_BYTES,
    SpatialSourcePreview,
    inspect_geojson_source,
    inspect_shapefile_bundle,
    suggest_spatial_identifier_fields,
)


@dataclass(frozen=True)
class SpatialUploadSelection:
    source_type: str
    geojson_content: bytes | None = None
    shapefile_files: Mapping[str, bytes] | None = None
    source_id_field: str = ""
    canonical_id_field: str = "segment_id"
    source_crs: str = ""
    preview: SpatialSourcePreview | None = None


def _show_source_preview(preview: SpatialSourcePreview) -> None:
    st.caption(
        f"{preview.source_format} · {preview.feature_count} features · "
        f"detected CRS `{preview.source_crs or 'missing'}` · "
        f"geometry {dict(preview.geometry_counts)}"
    )
    st.dataframe(
        pd.DataFrame([
            {
                "Field": field,
                "Example values": ", ".join(preview.value_examples.get(field, ())),
            }
            for field in preview.attribute_columns
        ]),
        hide_index=True,
        width="stretch",
    )
    st.dataframe(pd.DataFrame([{
        "LineStrings": preview.geometry_counts.get("LineString", 0),
        "MultiLineStrings": preview.geometry_counts.get("MultiLineString", 0),
        "Empty": preview.empty_geometry_count,
        "Invalid": preview.invalid_geometry_count,
        "Bounds": preview.geometry_bounds,
    }]), hide_index=True, width="stretch")


def render_spatial_upload_controls(
    *, key_prefix: str, max_bundle_bytes: int = DEFAULT_MAX_BUNDLE_BYTES,
    no_gis_message: str = "The existing latitude/longitude marker map will remain available.",
) -> SpatialUploadSelection:
    """Render explicit No GIS/GeoJSON/Shapefile intake and return reviewed inputs."""

    source_type = st.radio(
        "GIS geometry source",
        ["No GIS geometry", "GeoJSON", "Shapefile bundle"],
        horizontal=True,
        key=f"{key_prefix}_source_type",
    )
    if source_type == "No GIS geometry":
        st.caption(no_gis_message)
        return SpatialUploadSelection(source_type="none")

    preview = None
    geojson_content = None
    shapefile_files = None
    source_crs = ""
    if source_type == "GeoJSON":
        uploaded = st.file_uploader(
            "Upload road geometry GeoJSON",
            type=["geojson", "json"],
            key=f"{key_prefix}_geojson",
        )
        source_crs = st.text_input(
            "Source CRS (required when GeoJSON has no CRS)",
            value="EPSG:4326",
            key=f"{key_prefix}_crs",
        )
        if uploaded is not None:
            geojson_content = uploaded.getvalue()
            try:
                preview = inspect_geojson_source(geojson_content, declared_crs=source_crs)
            except ValueError as exc:
                st.error(str(exc))
    else:
        st.caption(
            "Select the `.shp`, `.shx`, `.dbf`, and `.prj` from one export together. "
            "An optional `.cpg` is also preserved. The bundle limit is "
            f"{max_bundle_bytes / (1024 * 1024):.0f} MB."
        )
        uploads = st.file_uploader(
            "Upload shapefile bundle",
            type=["shp", "shx", "dbf", "prj", "cpg"],
            accept_multiple_files=True,
            key=f"{key_prefix}_shapefile",
        )
        if uploads:
            names = [upload.name for upload in uploads]
            if len(names) != len(set(name.casefold() for name in names)):
                st.error("Duplicate shapefile filenames were selected.")
            else:
                shapefile_files = {upload.name: upload.getvalue() for upload in uploads}
                try:
                    preview = inspect_shapefile_bundle(
                        shapefile_files, max_bytes=max_bundle_bytes
                    )
                except ValueError as exc:
                    st.error(str(exc))

    source_id_field = ""
    canonical_id_field = "segment_id"
    if preview is not None:
        _show_source_preview(preview)
        suggestions = suggest_spatial_identifier_fields(preview.attribute_columns)
        if suggestions:
            st.info(
                "Suggested identifier field(s): " + ", ".join(suggestions)
                + ". Confirm the selection; suggestions never satisfy registration by themselves."
            )
        else:
            st.warning(
                "No likely identifier field was found. Select a unique road/segment field manually."
            )
        options = list(preview.attribute_columns)
        preferred = suggestions[0] if suggestions else options[0] if options else ""
        if options:
            source_id_field = st.selectbox(
                "GIS identifier field",
                options,
                index=options.index(preferred),
                key=f"{key_prefix}_identifier",
            )
        canonical_id_field = st.selectbox(
            "Exact canonical join target",
            ["segment_id", "road_id"],
            key=f"{key_prefix}_canonical_id",
        )
        st.caption(
            "Exact identifier equality is authoritative. Name or proximity suggestions are not used."
        )
    return SpatialUploadSelection(
        source_type="geojson" if source_type == "GeoJSON" else "shapefile",
        geojson_content=geojson_content,
        shapefile_files=shapefile_files,
        source_id_field=source_id_field,
        canonical_id_field=canonical_id_field,
        source_crs=source_crs,
        preview=preview,
    )
