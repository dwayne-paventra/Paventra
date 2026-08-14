"""Backward-compatible Jackson wrappers around the canonical inventory pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pilot.canonical_inventory import (
    CANONICAL_COLUMNS,
    load_canonical_inventory,
    load_streamlit_inventory,
    normalize_treatment,
    to_streamlit_inventory as _to_streamlit_inventory,
    validate_canonical_schema,
)
from pilot.jackson_config import JACKSON_MUNICIPALITY


JACKSON_CANONICAL_COLUMNS = CANONICAL_COLUMNS


def validate_jackson_schema(roads: pd.DataFrame) -> None:
    """Compatibility wrapper for canonical schema validation."""

    validate_canonical_schema(roads)


def load_jackson_canonical_data(
    path: str | Path = JACKSON_MUNICIPALITY.data_path,
) -> pd.DataFrame:
    """Compatibility wrapper for canonical inventory loading."""

    return load_canonical_inventory(path)


def to_streamlit_inventory(
    roads: pd.DataFrame,
    municipality_name: str = JACKSON_MUNICIPALITY.name,
) -> pd.DataFrame:
    """Compatibility wrapper for the shared Streamlit inventory adapter."""

    return _to_streamlit_inventory(roads, municipality_name)


def load_jackson_streamlit_inventory(
    path: str | Path = JACKSON_MUNICIPALITY.data_path,
    municipality_name: str = JACKSON_MUNICIPALITY.name,
) -> pd.DataFrame:
    """Compatibility wrapper preserving the existing Jackson entry point."""

    return load_streamlit_inventory(path, municipality_name)
