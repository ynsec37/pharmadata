"""Dataset registry and loading: which datasets exist, their metadata, and I/O."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, NotRequired, TypedDict, cast

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from pharmadata._core.output_format import OutputFormat, get_output_format

if TYPE_CHECKING:
    # pandas is an optional extra; only named by the annotations below.
    import pandas as pd


@dataclass(frozen=True, slots=True)
class Collection:
    """One named group of datasets: module, title, and where it comes from.

    ``url`` and ``example`` are optional: a bare new collection needs only a
    ``title`` and ``source``. ``example`` falls back to the first dataset.
    """

    name: str  # the submodule and the _data directory name
    title: str  # for the generated docs and the nav
    source: str  # the upstream source, named on its index page
    url: str = ""  # where that source is published
    example: str = ""  # a representative dataset, used in docstring examples


# The _meta.json contract: one entry per dataset, one spec per column.
class ColumnSpec(TypedDict):
    """One column's entry in a collection's ``_meta.json``."""

    label: str | None
    type: str
    mandatory: str | None
    role: str | None


class DatasetMetaEntry(TypedDict):
    """One dataset's entry in a collection's ``_meta.json``.

    ``parquet_hash`` and friends are written by the build pipeline to enable
    incremental refresh and integrity checks; they are absent in hand-authored
    or legacy entries. ``hash_alg`` names the algorithm used for
    ``parquet_hash`` (currently ``"sha256"``).
    """

    label: str | None
    structure: str | None
    n_rows: int
    columns: dict[str, ColumnSpec]
    parquet_hash: NotRequired[str]
    parquet_size_bytes: NotRequired[int]
    hash_alg: NotRequired[str]


# The directory the shipped data lives in, a sibling of this ``_core`` package.
_DATA_ROOT = Path(__file__).resolve().parent.parent / "_data"


def _resolve_example(child: Path, example: str) -> str:
    """Return *example*, else the first dataset declared in ``_meta.json``."""
    if example:
        return example
    meta_path = child / "_meta.json"
    if not meta_path.is_file():
        return ""
    datasets = json.loads(meta_path.read_text(encoding="utf-8"))
    return next(iter(sorted(datasets)), "")


def _discover_collections() -> dict[str, Collection]:
    """Every collection declared by a ``_collection.json`` under ``_data``.

    A directory becomes a collection by dropping a ``_collection.json`` beside
    its ``_meta.json``. Only ``title`` and ``source`` are required; ``url`` and
    ``example`` are optional, and an omitted ``example`` falls back to the first
    dataset. Nothing is hardcoded, so a new dataset group is picked up without
    editing Python.
    """
    found: dict[str, Collection] = {}
    if not _DATA_ROOT.is_dir():  # pragma: no cover - the data ships with the package
        return found
    for child in sorted(_DATA_ROOT.iterdir()):
        config = child / "_collection.json"
        if child.is_dir() and config.is_file():
            raw = json.loads(config.read_text(encoding="utf-8"))
            found[child.name] = Collection(
                name=child.name,
                title=str(raw["title"]),
                source=str(raw["source"]),
                url=str(raw.get("url", "")),
                example=_resolve_example(child, str(raw.get("example", ""))),
            )
    return found


# The single source of truth for which collections exist: read from the data.
COLLECTIONS: dict[str, Collection] = _discover_collections()


@cache
def data_dir(collection: str) -> Path:
    """Directory holding the parquet files and metadata of a collection."""
    if collection not in COLLECTIONS:
        msg = (
            f"unknown collection {collection!r}; expected one of {sorted(COLLECTIONS)}"
        )
        raise ValueError(msg)
    return _DATA_ROOT / collection


@cache
def raw_meta(collection: str) -> dict[str, DatasetMetaEntry]:
    """Raw metadata of a collection: dataset -> label/structure/columns."""
    path = data_dir(collection) / "_meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


@cache
def dataset_names(collection: str) -> frozenset[str]:
    """Names of the datasets available in a collection."""
    return frozenset(raw_meta(collection))


def check_dataset(collection: str, name: str) -> None:
    """Raise a helpful error when *name* is not a dataset in *collection*."""
    if name not in dataset_names(collection):
        msg = (
            f"no dataset {name!r} in collection {collection!r}; "
            f"available: {', '.join(list_datasets(collection))}"
        )
        raise ValueError(msg)


def _meta_entry(collection: str, name: str) -> DatasetMetaEntry:
    """The raw metadata dict of one dataset, after validating it exists."""
    check_dataset(collection, name)
    return raw_meta(collection)[name]


def list_datasets(collection: str) -> list[str]:
    """Names of the datasets available in a collection, sorted alphabetically."""
    return sorted(dataset_names(collection))


@cache
def load_dataset(collection: str, name: str) -> pa.Table:
    """Load a dataset as an immutable pyarrow Table, the internal base.

    pyarrow reads the parquet on every platform, including the browser, where
    polars' own parquet reader is unavailable; the served frame is the arrow
    table converted on demand by :func:`to_output`.
    """
    check_dataset(collection, name)
    return pq.read_table(data_dir(collection) / f"{name}.parquet")


# The one pandas-missing message, raised wherever "pandas" output is asked for.
PANDAS_REQUIRED_MSG = (
    'pandas is required for output_format="pandas"; '
    'install with: pip install "pharmadata[pandas]"'
)


def require_pandas() -> None:
    """Raise ImportError unless pandas can be imported.

    ``sys.modules["pandas"] = None`` (the test fixture for a missing pandas)
    makes ``import pandas`` return None without raising, so check the bound
    name. Readers of parquet must call this first: pyarrow's reader
    initialises the pandas shim and crashes on it when pandas is absent.
    """
    try:
        import pandas as pd
    except ImportError:
        pd = None  # type: ignore[assignment]
    if pd is None:
        msg = PANDAS_REQUIRED_MSG
        raise ImportError(msg)


def to_output(
    table: pa.Table, fmt: OutputFormat
) -> pa.Table | pl.DataFrame | pd.DataFrame:
    """Convert the arrow base into the requested output format.

    ``"arrow"`` hands the table back untouched; polars crosses the Arrow C data
    interface with ``pl.from_arrow``; pandas converts through ``to_pandas``,
    naming the extra to install when pandas is absent.
    """
    if fmt == "arrow":
        return table
    if fmt == "pandas":
        require_pandas()
        return table.to_pandas()
    if fmt == "polars":
        # a Table converts to a DataFrame; from_arrow's stub returns the wider union.
        return cast("pl.DataFrame", pl.from_arrow(table))
    msg = f"unknown output format: {fmt!r}"  # pragma: no cover
    raise ValueError(msg)  # pragma: no cover


@cache
def dataset_doc(collection: str, name: str) -> str:
    """The docstring of a dataset, generated from its CDISC metadata."""
    entry = _meta_entry(collection, name)
    spec = COLLECTIONS[collection]
    rows, cols = shape(collection, name)
    lines = [
        f"{name} - {entry['label'] or name}",
        "",
        f"{spec.title}, from {spec.source} (<{spec.url}>).",
        f"{rows} rows x {cols} columns.",
    ]
    if entry["structure"]:
        lines.append(f"Structure: {entry['structure']}.")
    lines += ["", "Variables", "---------"]
    lines += [
        f"{column} ({info['type']}): {info['label'] or ''}".rstrip()
        for column, info in entry["columns"].items()
    ]
    return "\n".join(lines) + "\n"


@cache
def shape(collection: str, name: str) -> tuple[int, int]:
    """Row and column counts of a dataset, without loading any data."""
    entry = _meta_entry(collection, name)
    return entry["n_rows"], len(entry["columns"])


@cache
def _meta_tables_table(collection: str) -> pa.Table:
    """Arrow base of the dataset-level metadata: one row per dataset."""
    meta = raw_meta(collection)
    names = list_datasets(collection)
    return pa.table(
        {
            "dataset": names,
            "label": [meta[n]["label"] for n in names],
            "n_rows": [meta[n]["n_rows"] for n in names],
            "n_cols": [len(meta[n]["columns"]) for n in names],
        }
    )


@cache
def _meta_specs_table(collection: str) -> pa.Table:
    """Arrow base of the column-level specifications of every dataset."""
    meta = raw_meta(collection)
    dataset: list[str] = []
    variable: list[str] = []
    label: list[str | None] = []
    column_type: list[str] = []
    mandatory: list[str | None] = []
    role: list[str | None] = []
    for name in list_datasets(collection):
        for col, info in meta[name]["columns"].items():
            dataset.append(name)
            variable.append(col)
            label.append(info["label"])
            column_type.append(info["type"])
            mandatory.append(info.get("mandatory"))
            role.append(info.get("role"))
    return pa.table(
        {
            "dataset": dataset,
            "variable": variable,
            "label": label,
            "type": column_type,
            "mandatory": mandatory,
            "role": role,
        }
    )


def meta_tables(collection: str) -> pa.Table | pl.DataFrame | pd.DataFrame:
    """Dataset-level metadata: one row per dataset, in the active format."""
    return to_output(_meta_tables_table(collection), get_output_format())


def meta_columns(collection: str) -> pa.Table | pl.DataFrame | pd.DataFrame:
    """Column-level metadata of every dataset (long format), in the active format.

    The specifications minus the ``mandatory`` and ``role`` columns.
    """
    table = _meta_specs_table(collection).select(
        ["dataset", "variable", "label", "type"]
    )
    return to_output(table, get_output_format())


def meta_specs(collection: str) -> pa.Table | pl.DataFrame | pd.DataFrame:
    """Column-level specifications of every dataset (long format), active format."""
    return to_output(_meta_specs_table(collection), get_output_format())
