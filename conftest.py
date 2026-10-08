"""Fixtures for every collected item: the tests/ suite and the src/ doctests.

Sits at the root - the common ancestor of the two trees - so the docstring
examples collected from src/ (``--doctest-modules``) run with the same fixtures
as the tests.
"""

from collections.abc import Iterator, MutableMapping

import pytest

import pharmadata
from pharmadata import (
    cdiscpilotadam,
    cdiscpilotsdtm,
    pharmaverseadam,
    pharmaversesdtm,
    set_output_polars,
)
from pharmadata._core import collection, data, meta

_FACADES = (cdiscpilotadam, cdiscpilotsdtm, pharmaverseadam, pharmaversesdtm)

# Every @cache in _core: file-reading functions cache parsed parquet/JSON, so a
# test patching the data source must start from a cold cache.
_CACHED = (
    data.data_dir,
    data.raw_meta,
    data.dataset_names,
    data.load_dataset,
    data.dataset_doc,
    data.shape,
    data._meta_tables_table,
    data._meta_specs_table,
    collection._load_polars,
    collection._load_pandas,
    meta.build,
)


@pytest.fixture(autouse=True)
def _reset_output_format() -> Iterator[None]:
    """Leave the output format on polars around every item, doctests included."""
    set_output_polars()
    yield
    set_output_polars()


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterator[None]:
    """Drop every @cache so no test reads another test's parsed data or metadata."""
    for fn in _CACHED:
        fn.cache_clear()
    yield
    for fn in _CACHED:
        fn.cache_clear()


@pytest.fixture(autouse=True)
def _doctest_namespace(doctest_namespace: MutableMapping[str, object]) -> None:
    """Give the src/ docstring examples the package-level names they call."""
    doctest_namespace["pharmadata"] = pharmadata
    for facade in _FACADES:
        doctest_namespace[facade.__name__.rsplit(".", 1)[-1]] = facade
