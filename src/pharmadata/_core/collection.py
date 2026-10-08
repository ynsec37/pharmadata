"""Wire a collection onto its module: lazy dataset attributes, ``__all__``, ``__dir__``."""

from __future__ import annotations

import sys
from functools import cache
from typing import TYPE_CHECKING, cast

import polars as pl

from pharmadata._core import data, meta, output_format

if TYPE_CHECKING:
    # pandas is an optional extra; pyarrow is only named by the annotations
    # (both live behind ``data``, which reads and converts the arrow base).
    import pandas as pd
    import pyarrow as pa

# The functions every collection module defines (and that __all__ lists).
HELPER_FUNCTIONS = (
    "list_datasets",
    "meta",
    "meta_tables",
    "meta_columns",
    "meta_specs",
    "to_dict",
)


@cache
def _load_polars(collection: str, name: str) -> pl.DataFrame:
    """The process-wide cached polars frame; callers get a clone via ``load``."""
    # from_arrow of a Table is a DataFrame; the stub returns the wider union.
    return cast("pl.DataFrame", pl.from_arrow(data.load_dataset(collection, name)))


@cache
def _load_pandas(collection: str, name: str) -> pd.DataFrame:
    """The process-wide cached pandas frame; callers get a copy via ``load``."""
    # pyarrow's parquet reader initialises the pandas shim, which crashes when
    # pandas is absent; ``load`` calls ``data.require_pandas`` before this runs.
    return cast(
        "pd.DataFrame", data.to_output(data.load_dataset(collection, name), "pandas")
    )


def load(collection: str, name: str) -> pa.Table | pl.DataFrame | pd.DataFrame:
    """One dataset on the active output format.

    The arrow base is immutable, so ``"arrow"`` shares the cached table; polars
    returns a fresh clone and pandas a deep copy, so a mutation never poisons
    the cache another caller reads.
    """
    fmt = output_format.get_output_format()
    if fmt == "arrow":
        return data.load_dataset(collection, name)
    if fmt == "pandas":
        # before load_dataset: pyarrow would initialise the pandas shim first
        data.require_pandas()
        frame: pa.Table | pl.DataFrame | pd.DataFrame = _load_pandas(
            collection, name
        ).copy()
    else:
        frame = _load_polars(collection, name).clone()
    # a clone/copy does not carry the cached frame's instance docstring
    frame.__doc__ = data.dataset_doc(collection, name)
    return frame


def load_all(
    collection: str,
) -> dict[str, pa.Table | pl.DataFrame | pd.DataFrame]:
    """Every dataset of a collection keyed by name, honoring the active output format.

    The values are polars frames by default, pyarrow Tables when
    ``output_format="arrow"`` is active, and pandas frames when
    ``output_format="pandas"`` is active.
    """
    return {name: load(collection, name) for name in data.list_datasets(collection)}


def install(module_name: str, spec: data.Collection) -> None:
    """Expose *spec*'s datasets as lazy attributes on the module *module_name*."""
    module = sys.modules.get(module_name)
    if module is None:  # pragma: no cover - only under an unusual loader
        msg = f"{module_name} is not in sys.modules; cannot install collection API"
        raise RuntimeError(msg)

    names = data.dataset_names(spec.name)
    sorted_names = data.list_datasets(spec.name)
    module.__dict__["__all__"] = [
        *HELPER_FUNCTIONS,
        *sorted_names,
        *(f"{name}_meta" for name in sorted_names),
    ]

    def __getattr__(
        name: str,
    ) -> pa.Table | pl.DataFrame | pd.DataFrame | meta.DatasetMeta:
        """The dataset named *name*, or its metadata as ``<name>_meta``."""
        if name.startswith("__") and name.endswith("__"):
            # keep introspection (copy, pickle, IPython) on its normal path
            raise AttributeError(name)
        if name in names:
            return load(spec.name, name)
        stem = name.removesuffix("_meta")
        if name.endswith("_meta") and stem in names:
            return meta.build(spec.name, stem)
        msg = (
            f"module {module_name!r} has no dataset {name!r}; "
            f"available: {', '.join(sorted_names)}"
        )
        raise AttributeError(msg)

    def __dir__() -> list[str]:
        return sorted(module.__dict__["__all__"])

    module.__dict__["__getattr__"] = __getattr__
    module.__dict__["__dir__"] = __dir__
