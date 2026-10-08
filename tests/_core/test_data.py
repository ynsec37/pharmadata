"""data.py: loading, output conversion and mutation safety across backends."""

import sys

import polars as pl
import pyarrow as pa
import pytest

from pharmadata import (
    cdiscpilotadam,
    output_format,
    set_output_pandas,
    set_output_polars,
)
from pharmadata import pharmaverseadam as adam
from pharmadata import pharmaversesdtm as sdtm


def test_pandas_output_changes_dataset_output() -> None:
    """Switching to pandas serves the same dataset as a pandas frame."""
    pd = pytest.importorskip("pandas")

    set_output_pandas()
    frame = adam.adsl

    assert isinstance(frame, pd.DataFrame)
    assert frame.shape == (306, 55)


def test_output_frames_are_mutation_safe() -> None:
    """A mutation through a served frame never leaks into the next read, on either backend."""
    pd = pytest.importorskip("pandas")

    set_output_polars()
    polars_frame = adam.adsl
    dropped = polars_frame.columns[0]
    polars_frame.drop_in_place(dropped)
    assert dropped in adam.adsl.columns

    set_output_pandas()
    pandas_frame = adam.adsl
    assert isinstance(pandas_frame, pd.DataFrame)
    pandas_frame.loc[0, "STUDYID"] = "MUTATED"
    assert adam.adsl.loc[0, "STUDYID"] != "MUTATED"


def test_pandas_output_without_pandas_has_helpful_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pandas missing altogether names the extra to install, not a bare ImportError."""
    monkeypatch.setitem(sys.modules, "pandas", None)
    set_output_pandas()

    with pytest.raises(ImportError, match=r"pharmadata\[pandas\]"):
        _ = sdtm.dm


def test_arrow_output_serves_pyarrow_table() -> None:
    """The arrow format hands back the immutable pyarrow table the data is read into."""
    with output_format("arrow"):
        table = adam.adsl
    assert isinstance(table, pa.Table)
    assert table.num_rows == 306
    assert table.num_columns == 55


def test_metadata_follows_output_format() -> None:
    """The metadata helpers and specs serve the active format, like the datasets."""
    pd = pytest.importorskip("pandas")

    with output_format("arrow"):
        assert isinstance(adam.meta_tables(), pa.Table)
        assert isinstance(adam.meta("adsl").specs, pa.Table)
    with output_format("pandas"):
        assert isinstance(adam.meta_tables(), pd.DataFrame)
        assert isinstance(adam.meta("adsl").specs, pd.DataFrame)
    assert isinstance(adam.meta_tables(), pl.DataFrame)


def test_pandas_output_serves_to_dict_as_pandas() -> None:
    """to_dict() follows the active backend, like the lazy attributes do."""
    pd = pytest.importorskip("pandas")

    with output_format("pandas"):
        frames = cdiscpilotadam.to_dict()

    assert set(frames) == set(cdiscpilotadam.list_datasets())
    assert all(isinstance(frame, pd.DataFrame) for frame in frames.values())
