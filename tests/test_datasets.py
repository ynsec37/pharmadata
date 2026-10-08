"""Dataset integrity: every shipped dataset loads, and its metadata is coherent."""

from types import ModuleType

import polars as pl
import pytest

from pharmadata import cdiscpilotadam, cdiscpilotsdtm
from pharmadata import pharmaverseadam as adam
from pharmadata import pharmaversesdtm as sdtm
from pharmadata._core import data
from tests._helpers import COLLECTIONS


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_every_dataset_loads_with_labels(collection: str, module: ModuleType) -> None:
    """Every shipped dataset is a non-empty frame and its labels cover all its columns."""
    for name in module.list_datasets():
        df = getattr(module, name)
        assert isinstance(df, pl.DataFrame), f"{collection}.{name} is not a DataFrame"
        assert df.height > 0, f"{collection}.{name} is empty"
        assert set(module.meta(name).column_names_to_labels) == set(df.columns), (
            f"{collection}.{name}: labels do not cover every column"
        )


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_an_unused_text_field_is_null_not_empty(
    collection: str, module: ModuleType
) -> None:
    """No shipped string column holds an empty value: an absent text is a null."""
    for name in module.list_datasets():
        df = getattr(module, name)
        empty = [
            column
            for column in df.select(pl.col(pl.String)).columns
            if (df[column] == "").any()
        ]
        assert not empty, f"{collection}.{name}: empty strings, not nulls: {empty}"


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_every_dataset_documents_itself(collection: str, module: ModuleType) -> None:
    """A loaded frame carries a docstring generated from its CDISC metadata."""
    url = data.COLLECTIONS[collection].url
    for name in module.list_datasets():
        doc = getattr(module, name).__doc__
        assert doc is not None, f"{collection}.{name} has no docstring"
        assert doc.splitlines()[0].startswith(f"{name} - "), collection
        assert url in doc, f"{collection}.{name}: docstring names no source"
        for variable, label in module.meta(name).column_names_to_labels.items():
            assert f"{variable} (" in doc, f"{collection}.{name}: {variable} missing"
            if label:
                assert label in doc, f"{collection}.{name}: {variable} has no label"


def test_the_pandas_backend_keeps_the_dataset_docstring() -> None:
    """Converting a frame does not lose what it documents."""
    pytest.importorskip("pandas")
    import pharmadata

    expected = data.dataset_doc("pharmaverseadam", "adsl")
    with pharmadata.output_format("pandas"):
        assert adam.adsl.__doc__ == expected


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_meta_tables(collection: str, module: ModuleType) -> None:
    """meta_tables lists one non-empty row per dataset with the four documented columns."""
    mt = module.meta_tables()
    names = module.list_datasets()
    assert mt.columns == ["dataset", "label", "n_rows", "n_cols"]
    assert mt.height == len(names)
    assert set(mt["dataset"]) == set(names)
    assert mt["n_rows"].min() > 0
    assert mt["n_cols"].min() > 0


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_meta_columns(collection: str, module: ModuleType) -> None:
    """meta_columns has one row per variable in _meta.json, none dropped and none invented."""
    from tests._helpers import meta_json

    mc = module.meta_columns()
    assert mc.columns[:4] == ["dataset", "variable", "label", "type"]
    expected = sum(
        len(meta_json(collection)[n]["columns"]) for n in module.list_datasets()
    )
    assert mc.height == expected
    assert set(mc["dataset"]) == set(module.list_datasets())


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_meta_specs(collection: str, module: ModuleType) -> None:
    """meta_specs is meta_columns plus the CDISC mandatory and role columns."""
    ms = module.meta_specs()
    assert ms.columns == ["dataset", "variable", "label", "type", "mandatory", "role"]
    mc = module.meta_columns()
    assert ms.select(mc.columns).equals(mc)


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_specs(collection: str, module: ModuleType) -> None:
    """A dataset's specs carry variable, label, type, mandatory and role."""
    spec = module.meta(module.list_datasets()[0]).specs
    assert spec.columns == ["variable", "label", "type", "mandatory", "role"]


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_helpers_reject_unknown_datasets(collection: str, module: ModuleType) -> None:
    """The meta() helper fails loudly with the available list, like load_dataset."""
    with pytest.raises(ValueError, match="no dataset"):
        module.meta("not_a_dataset")


def test_lazy_loading_and_dir() -> None:
    """Datasets answer in dir() but a name that is not one raises rather than returning None."""
    assert "adsl" in dir(adam)
    assert "dm" in dir(sdtm)
    with pytest.raises(AttributeError, match="no dataset"):
        _ = adam.not_a_dataset


def test_adsl_baseline() -> None:
    """The shipped ADSL keeps its 306x55 shape and its CDISC label for STUDYID."""
    df = adam.adsl
    assert df.shape == (306, 55)
    assert adam.adsl_meta.column_names_to_labels["STUDYID"] == "Study Identifier"


def test_cdisc_pilot_labels_come_from_the_define_file() -> None:
    """The pilot datasets keep their own shape, and the Define-XML fills the gaps."""
    assert cdiscpilotadam.adsl.shape == (254, 49)
    assert cdiscpilotsdtm.dm.shape == (306, 25)
    dm_labels = cdiscpilotsdtm.dm_meta.column_names_to_labels
    assert dm_labels["STUDYID"] == "Study Identifier"
    mt = cdiscpilotsdtm.meta_tables()
    label = mt.filter(mt["dataset"] == "dm")["label"][0]
    assert label == "Demographics", "the dataset label is not the Define-XML's"
    # the Define-XML is also where the mandatory flags and roles come from
    assert cdiscpilotsdtm.meta("dm").specs["role"][0] == "IDENTIFIER"
    assert cdiscpilotsdtm.meta("dm").specs["mandatory"][0] == "Yes"
    assert cdiscpilotadam.meta("adsl").specs["role"].is_null().all()


def test_arrow_field_metadata_embedded() -> None:
    """Labels survive in the parquet's Arrow field metadata (self-describing)."""
    from importlib import resources

    import pyarrow.parquet as pq

    path = resources.files("pharmadata") / "_data" / "pharmaverseadam" / "adsl.parquet"
    field = pq.read_schema(path).field("STUDYID")
    assert field.metadata[b"label"] == b"Study Identifier"
    # embedding field metadata must not disturb the polars read path
    assert pl.read_parquet(path).shape == (306, 55)
