"""The generated collection modules, stubs and shipped parquet match _meta.json."""

import importlib
import keyword
import re
from importlib import resources

import pyarrow.parquet as pq
import pytest

from tests._helpers import COLLECTIONS, meta_json


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_stub_matches_meta(collection: str) -> None:
    """The stub declares each _meta.json dataset and its DatasetMeta partner."""
    stub_path = resources.files("pharmadata") / collection / "__init__.pyi"
    text = stub_path.read_text(encoding="utf-8")
    declared = re.findall(r"^(\w+): Final\[DataFrame\]$", text, re.M)
    assert sorted(declared) == sorted(meta_json(collection))
    # every dataset line is paired with its pyreadstat-style metadata line
    declared_meta = re.findall(r"^(\w+)_meta: Final\[DatasetMeta\]$", text, re.M)
    assert sorted(declared_meta) == sorted(declared)
    # Final tells a static checker what the descriptor's __set__ already enforces
    assert "Final[DataFrame]" in text


def test_package_declares_itself_typed() -> None:
    """PEP 561: without the marker a checker skips the stubs and sees Any."""
    assert (resources.files("pharmadata") / "py.typed").is_file()


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_dataset_names_are_valid_identifiers(collection: str) -> None:
    """A dataset name becomes an attribute and a stub line, so it must be one."""
    for name in meta_json(collection):
        assert name.isidentifier(), (
            f"{collection}.{name} is not a valid Python identifier"
        )
        assert not keyword.iskeyword(name), f"{collection}.{name} is a Python keyword"


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_module_and_stub_carry_the_do_not_edit_marker(collection: str) -> None:
    """Both faces of a collection module say the codegen in data-raw writes them."""
    directory = resources.files("pharmadata") / collection
    for name in ("__init__.py", "__init__.pyi"):
        text = (directory / name).read_text(encoding="utf-8")
        assert "data-raw/04_build_modules.py - do not edit." in text, (
            f"{collection}/{name}"
        )
    # a comment before the string would stop it being the module docstring
    doc = importlib.import_module(f"pharmadata.{collection}").__doc__
    assert doc is not None
    assert "datasets from" in doc


@pytest.mark.parametrize("collection", COLLECTIONS)
def test_parquet_files_are_self_describing(collection: str) -> None:
    """The shipped data files carry their labels, not only _meta.json."""
    directory = resources.files("pharmadata") / "_data" / collection
    module = COLLECTIONS[collection]
    for name in module.list_datasets():
        schema = pq.ParquetFile(directory / f"{name}.parquet").schema_arrow
        labels = module.meta(name).column_names_to_labels
        # the file itself names the program that wrote it
        assert schema.metadata is not None
        assert schema.metadata[b"pharmadata:generator"] == b"data-raw/build_data.py"
        # the dataset label lives at the schema level, the column labels per field
        assert schema.metadata[b"label"].decode() == module.meta(name).file_label or ""
        for i in range(len(schema)):
            field = schema.field(i)
            assert field.metadata is not None, f"{name}.{field.name}: no metadata"
            assert field.metadata[b"label"].decode() == labels[field.name], (
                f"{name}.{field.name}: parquet label differs from the API"
            )
            # role/type/mandatory live only in _meta.json, not in the parquet
            assert b"role" not in field.metadata, f"{name}.{field.name}: role leaked"
