"""The pyreadstat-style DatasetMeta: cached process-wide, frozen, and honest."""

import dataclasses
import subprocess
import sys
from types import ModuleType

import polars as pl
import pytest

import pharmadata
from pharmadata import DatasetMeta, set_output_pandas
from pharmadata import pharmaverseadam as adam
from tests._helpers import COLLECTIONS, meta_json


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_meta_agrees_with_the_frame(collection: str, module: ModuleType) -> None:
    """Names, counts, labels and the dataset label match the frame and the tables."""
    name = module.list_datasets()[0]
    m = module.meta(name)
    df = getattr(module, name)
    assert isinstance(m, DatasetMeta)
    assert m.dataset == name
    assert m.collection == collection
    assert list(m.column_names) == df.columns
    assert m.number_columns == len(m.column_names) == df.width
    # the footer count is the single truth, and it matches a full read
    assert m.number_rows == df.height
    # the parallel tuples stay parallel, and the derived mapping agrees with them
    assert len(m.column_labels) == len(m.column_types) == m.number_columns
    assert m.column_names_to_labels == dict(
        zip(m.column_names, m.column_labels, strict=True)
    )
    entry = meta_json(collection)[name]
    assert m.column_names_to_labels == {
        col: info["label"] for col, info in entry["columns"].items()
    }
    # the dataset label is the one meta_tables reports for the same dataset
    label = module.meta_tables().filter(pl.col("dataset") == name)["label"][0]
    assert m.file_label == label
    # parquet mandates UTF-8 text, whatever the original source file was
    assert m.file_format == "parquet"
    assert m.file_encoding == "utf-8"


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_meta_attribute_and_function_share_one_object(
    collection: str, module: ModuleType
) -> None:
    """adam.adsl_meta is adam.meta("adsl"): one cached object per dataset."""
    name = module.list_datasets()[0]
    assert getattr(module, f"{name}_meta") is module.meta(name)
    assert module.meta(name) is module.meta(name)


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_specs_is_a_fresh_frame_each_time(collection: str, module: ModuleType) -> None:
    """The specs property builds a new frame on every access, so a caller may mutate its own."""
    m = module.meta(module.list_datasets()[0])
    first, second = m.specs, m.specs
    assert first is not second
    assert first.equals(second)
    assert first.columns == ["variable", "label", "type", "mandatory", "role"]
    assert first.height == m.number_columns
    assert first["variable"].to_list() == list(m.column_names)


def test_meta_is_frozen() -> None:
    """A process-wide shared object must refuse to be written to."""
    m = adam.meta("adsl")
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.file_label = "nope"  # type: ignore[misc]


def test_meta_repr_is_a_one_line_summary() -> None:
    """The repr names the dataset and its size, nothing more."""
    expected = "DatasetMeta(pharmaverseadam.adsl, 306 rows x 55 columns)"
    assert repr(adam.adsl_meta) == expected


def test_adsl_meta_baseline() -> None:
    """The ADSL metadata pins the CDISC dimensions the source provides."""
    m = adam.adsl_meta
    assert m.file_label == "Subject Level Analysis"
    assert m.structure == "One record per subject"


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_dir_lists_the_meta_attributes(collection: str, module: ModuleType) -> None:
    """dir() carries every <name>_meta, so IPython completion finds them."""
    listing = dir(module)
    for name in module.list_datasets():
        assert f"{name}_meta" in listing, f"{module.__name__}.{name}_meta not in dir()"


def test_unknown_meta_attribute_raises() -> None:
    """A <name>_meta that names no dataset fails like any unknown dataset."""
    with pytest.raises(AttributeError, match="has no dataset"):
        _ = adam.not_a_dataset_meta


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_no_dataset_name_ends_in_meta(collection: str, module: ModuleType) -> None:
    """The _meta suffix is reserved, so a <name>_meta attribute is never ambiguous."""
    assert all(not name.endswith("_meta") for name in module.list_datasets())


def test_meta_is_backend_independent() -> None:
    """DatasetMeta describes the dataset, not the in-memory backend it loads as."""
    pytest.importorskip("pandas")
    set_output_pandas()
    m = adam.meta("adsl")
    assert m is adam.adsl_meta  # the same cached object, whatever the backend
    df = adam.adsl
    assert list(m.column_names) == list(df.columns)
    assert (m.number_rows, m.number_columns) == df.shape == (306, 55)


def test_importing_pharmadata_loads_pyarrow() -> None:
    """The pyarrow reader is core now: importing the package brings it into the process."""
    probe = (
        "import sys, pharmadata; raise SystemExit(0 if 'pyarrow' in sys.modules else 1)"
    )
    subprocess.run([sys.executable, "-c", probe], check=True)
    assert "DatasetMeta" in pharmadata.__all__


def test_meta_exposes_the_pyreadstat_surface() -> None:
    """DatasetMeta carries the fields a pyreadstat.read_sas7bdat caller expects.

    This is the public metadata contract: renaming or removing any of these
    fields breaks code written against pyreadstat's metadata object.
    """
    m = adam.adsl_meta
    # parallel tuples: column names, labels, and the CDISC type/mandatory/role
    assert isinstance(m.column_names, tuple)
    assert isinstance(m.column_labels, tuple)
    assert len(m.column_names) == len(m.column_labels) == m.number_columns
    # the derived dict agrees with the parallel tuples
    assert m.column_names_to_labels == dict(
        zip(m.column_names, m.column_labels, strict=True)
    )
    # counts: rows from the parquet footer, columns from the schema
    assert isinstance(m.number_rows, int)
    assert isinstance(m.number_columns, int)
    assert m.number_rows == 306
    assert m.number_columns == 55
    # file-level metadata
    assert m.file_label == "Subject Level Analysis"
    assert m.file_format == "parquet"
    assert m.file_encoding == "utf-8"
    # one real label is present and keyed by its column name
    assert m.column_names_to_labels["STUDYID"] == "Study Identifier"
