# Municipal GIS ingestion

Paventra accepts optional municipal road geometry in either of these forms:

- Preferred: one GeoJSON `FeatureCollection` with a unique road or segment ID.
- Also accepted: one shapefile export containing matching `.shp`, `.shx`,
  `.dbf`, and `.prj` files. An optional `.cpg` may be included.

Ask the municipality to deliver every shapefile component from the same
export, without renaming individual files. The `.prj` is mandatory because
Paventra never guesses CRS. A unique stable road/segment ID is equally
important: it is the auditable link between GIS geometry and the canonical
inventory used by analytics and reports.

Each feature must contain valid `LineString` or `MultiLineString` geometry and
a non-empty, unique identifier. The operator confirms whether that field joins
to canonical `segment_id` or `road_id`. Name-based and proximity matching are
not registration evidence; exact identifier equality remains authoritative.

GeoJSON CRS must be embedded or entered by the operator. Shapefile CRS is read
from its `.prj`. Valid geometry is transformed to EPSG:4326 and written as the
same version-specific immutable `roads.geojson`, regardless of source format.
Original source files, individual checksums, a deterministic bundle checksum,
join settings, CRS, provenance, review, and normalized artifact remain in the
package/version directory.

Spatial completeness is intentionally strict: every canonical segment must
have exactly one valid geometry feature before the GIS layer can pass. The
review shows GIS-only IDs, canonical-only IDs, duplicates, geometry quality,
and match coverage so corrections can be requested from the source owner.

When no municipal line file is supplied, the application retains its existing
latitude/longitude marker map. A candidate data version inherits the active
version's geometry unless the operator supplies and validates a replacement,
so an inventory-only update does not silently remove the active road network.
