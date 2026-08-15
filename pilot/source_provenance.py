"""Dataset-level source provenance validation, checksums, and presentation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from pathlib import Path
import re

from pilot.data_provenance import DataProvenanceStatus, normalize_data_status


_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class SourceProvenance:
    """Traceability metadata for one source dataset, not an approval record."""

    owner: str
    acquired_date: str
    reference: str
    checksum: str | None = None

    @property
    def normalized_checksum(self) -> str | None:
        if self.checksum is None:
            return None
        return self.checksum.strip().lower()

    @property
    def cache_key(self) -> str:
        return "|".join((
            self.owner.strip(),
            self.acquired_date.strip(),
            self.reference.strip(),
            self.normalized_checksum or "",
        ))


@dataclass(frozen=True)
class SourceChecksumResult:
    """Actual and optional declared checksum comparison for one source file."""

    actual: str
    declared: str | None
    matched: bool | None


def _identity_label(municipality_slug: str | None) -> str:
    return f"Municipality '{municipality_slug}'" if municipality_slug else "Municipality"


def validate_source_provenance(
    provenance: SourceProvenance | None,
    *,
    data_status: object,
    municipality_slug: str | None = None,
    legacy_manifest_version: int | None = None,
) -> None:
    """Validate source metadata without inferring or changing data status."""

    status = normalize_data_status(data_status)
    identity = _identity_label(municipality_slug)
    legacy_missing_allowed = legacy_manifest_version in (1, 2)

    if provenance is None:
        if status == DataProvenanceStatus.ILLUSTRATIVE.value or legacy_missing_allowed:
            return
        raise ValueError(
            f"{identity} requires source provenance metadata for data_status "
            f"'{status}'; fields 'source_owner', 'source_acquired_date', and "
            "'source_reference' must be configured."
        )
    if not isinstance(provenance, SourceProvenance):
        raise ValueError(f"{identity} field 'source_provenance' must be a SourceProvenance.")

    text_fields = {
        "source_owner": provenance.owner,
        "source_acquired_date": provenance.acquired_date,
        "source_reference": provenance.reference,
    }
    for field_name, value in text_fields.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{identity} field '{field_name}' must be a non-empty string."
            )

    acquired = provenance.acquired_date.strip()
    if not _ISO_DATE_PATTERN.fullmatch(acquired):
        raise ValueError(
            f"{identity} field 'source_acquired_date' must use ISO date YYYY-MM-DD."
        )
    try:
        parsed_date = date.fromisoformat(acquired)
    except ValueError as exc:
        raise ValueError(
            f"{identity} field 'source_acquired_date' is not a valid calendar date: "
            f"'{provenance.acquired_date}'."
        ) from exc
    if parsed_date.isoformat() != acquired:
        raise ValueError(
            f"{identity} field 'source_acquired_date' must use ISO date YYYY-MM-DD."
        )

    if provenance.checksum is not None:
        if not isinstance(provenance.checksum, str) or not _SHA256_PATTERN.fullmatch(
            provenance.checksum.strip()
        ):
            raise ValueError(
                f"{identity} field 'source_checksum' must be a 64-character "
                "hexadecimal SHA-256 value when provided."
            )


def compute_source_checksum(path: str | Path) -> str:
    """Compute a deterministic SHA-256 digest for one source file."""

    source = Path(path)
    digest = hashlib.sha256()
    try:
        with source.open("rb") as source_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise ValueError(f"Source file was not found at '{source}'.") from exc
    except OSError as exc:
        raise ValueError(f"Source file '{source}' could not be read: {exc}") from exc
    return digest.hexdigest()


def compute_content_checksum(content: bytes) -> str:
    """Compute SHA-256 for uploaded source bytes using the provenance contract."""

    if not isinstance(content, bytes):
        raise ValueError("Source content must be bytes before checksum calculation.")
    return hashlib.sha256(content).hexdigest()


def verify_source_checksum(
    path: str | Path,
    provenance: SourceProvenance | None,
    *,
    municipality_slug: str | None = None,
) -> SourceChecksumResult:
    """Compute the actual digest and fail when a declared digest disagrees."""

    actual = compute_source_checksum(path)
    declared = provenance.normalized_checksum if provenance is not None else None
    matched = None if declared is None else actual == declared
    if matched is False:
        identity = _identity_label(municipality_slug)
        raise ValueError(
            f"{identity} field 'source_checksum' does not match source file '{Path(path)}': "
            f"declared {declared}, actual {actual}."
        )
    return SourceChecksumResult(actual=actual, declared=declared, matched=matched)


def source_provenance_summary(
    provenance: SourceProvenance | None,
    *,
    data_status: object,
    legacy_manifest_version: int | None = None,
) -> str:
    """Return concise, status-safe metadata language for UI and reports."""

    status = normalize_data_status(data_status)
    if provenance is None:
        if status == DataProvenanceStatus.ILLUSTRATIVE.value:
            return "Source provenance: synthetic or illustrative demonstration dataset."
        if legacy_manifest_version in (1, 2):
            return (
                "Source provenance metadata: unavailable under legacy manifest "
                f"version {legacy_manifest_version}; data status is unchanged."
            )
        return "Source provenance metadata: not configured."

    checksum_note = ""
    if provenance.normalized_checksum:
        checksum_note = (
            f" SHA-256 recorded: {provenance.normalized_checksum[:12]}… "
            "(integrity comparison only)."
        )
    return (
        f"Source owner: {provenance.owner.strip()}. Acquired: "
        f"{provenance.acquired_date.strip()}. Source reference: "
        f"{provenance.reference.strip()}.{checksum_note}"
    )
