# Municipal GIS ingestion

Phase 23 accepts optional municipal road geometry as a GeoJSON
`FeatureCollection`. Each feature must contain a valid `LineString` or
`MultiLineString` and a non-empty, unique source identifier. The operator
explicitly chooses whether that property joins to canonical `segment_id` or
`road_id`.

The source CRS must be present in the GeoJSON `crs` member or entered by the
operator. Paventra does not infer or guess CRS. Valid geometry is transformed
to EPSG:4326 and written as the version-specific immutable `roads.geojson`.
The preserved source, checksum, join settings, CRS, provenance, validation
review, and runtime artifact remain together in the package/version directory.

Shapefile upload is intentionally not supported by the operator workflow in
this phase. A shapefile is a multi-file bundle (`.shp`, `.shx`, `.dbf`, and
usually `.prj`); accepting only one part or losing sidecars would undermine
source preservation and CRS validation. Convert the complete municipal
delivery to GeoJSON through a controlled GIS process before onboarding. This
does not affect the legacy internal shapefile reader, which is outside the
municipality ingestion path.

When no municipal line file is supplied, the application retains its existing
latitude/longitude marker map. A candidate data version inherits the active
version's geometry unless the operator supplies and validates a replacement,
so an inventory-only update does not silently remove the active road network.
