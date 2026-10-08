"""The 04_build_modules.py generator: template, stub and file writing."""

from pathlib import Path

import pytest

from pharmadata._core import data
from tests._helpers import source_script

pytestmark = pytest.mark.build

gen = source_script("04_build_modules")

# A minimal collection spec: enough to drive module_source's template.
_SPEC = data.Collection(
    name="testcoll",
    title="Test Datasets (ADaM)",
    source="The Test Source",
    url="https://example.com/test",
    example="dm",
)

# A minimal _meta.json entry, the shape _stub_docstring reads.
_META_ENTRY: data.DatasetMetaEntry = {
    "label": "Demographics",
    "structure": "one record per subject",
    "n_rows": 306,
    "columns": {
        "USUBJID": {
            "label": "Unique Subject Identifier",
            "type": "String",
            "mandatory": "Y",
            "role": "ID",
        },
        "AGE": {"label": "Age", "type": "Int64", "mandatory": "Y", "role": "Analysis"},
    },
}


def test_module_source_substitutes_every_template_variable() -> None:
    """The module template is filled from the collection spec, no placeholders left."""
    source = gen.module_source(_SPEC)

    assert gen.GENERATED_BY in source
    assert "Test Datasets" in source  # kind = title split at " ("
    assert "The Test Source" in source
    assert "testcoll" in source
    assert "dm" in source
    # no unresolved template variable survives
    assert "${" not in source
    # the install call wires the right collection
    assert 'collection.install(__name__, data.COLLECTIONS["testcoll"])' in source
    # every helper delegates back to the package, not a copy
    assert 'return data.list_datasets("testcoll")' in source
    assert 'return build("testcoll", name)' in source
    assert 'return data.meta_tables("testcoll")' in source
    assert 'return collection.load_all("testcoll")' in source


def test_docstring_literal_escapes_backslashes_and_quotes() -> None:
    """A stub docstring must be valid Python: backslashes and triple quotes escaped."""
    literal = gen._docstring_literal('a\\b and """quoted"""')
    assert literal == '"""a\\\\b and \\"\\"\\"quoted\\"\\"\\"\n"""'
    # the result is a well-formed triple-quoted string literal
    assert literal.startswith('"""')
    assert literal.endswith('"""')


def test_stub_docstring_reports_label_shape_and_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dataset docstring carries the label, row/col count, structure and variables."""
    monkeypatch.setattr(data, "_meta_entry", lambda *_: _META_ENTRY)
    monkeypatch.setattr(data, "shape", lambda *_: (306, 2))

    doc = gen._stub_docstring("testcoll", "dm")

    assert doc.startswith("Demographics")
    assert "306 rows x 2 columns." in doc
    assert "Structure: one record per subject." in doc
    assert "Variables:" in doc
    assert "- `USUBJID` (String): Unique Subject Identifier" in doc
    assert "- `AGE` (Int64): Age" in doc


def test_stub_source_lists_helpers_and_datasets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The .pyi stub declares the six helpers and every dataset as Final attributes."""
    monkeypatch.setattr(data, "_meta_entry", lambda *_: _META_ENTRY)
    monkeypatch.setattr(data, "shape", lambda *_: (306, 2))

    stub = gen.stub_source("testcoll", ["ae", "dm"])

    # header and the do-not-edit marker
    assert stub.startswith(f"# {gen.GENERATED_BY}")
    # the six helper signatures
    for fn in (
        "list_datasets",
        "meta",
        "meta_tables",
        "meta_columns",
        "meta_specs",
        "to_dict",
    ):
        assert f"def {fn}(" in stub
    # datasets are Final attributes, each paired with its _meta
    assert "ae: Final[DataFrame]" in stub
    assert "ae_meta: Final[DatasetMeta]" in stub
    assert "dm: Final[DataFrame]" in stub
    assert "dm_meta: Final[DatasetMeta]" in stub
    # a dataset attribute carries a docstring; its _meta partner does not
    dm_block = stub[stub.index("dm: Final[DataFrame]") :]
    assert '"""' in dm_block  # the dataset docstring literal
    meta_block = stub[stub.index("dm_meta: Final[DatasetMeta]") :]
    assert not meta_block.startswith('dm_meta: Final[DatasetMeta]\n"""')


def test_write_collection_writes_module_and_stub(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """write_collection() writes __init__.py and __init__.pyi under <collection>/."""
    monkeypatch.setattr(data, "_meta_entry", lambda *_: _META_ENTRY)
    monkeypatch.setattr(data, "shape", lambda *_: (306, 2))
    monkeypatch.setattr(data, "list_datasets", lambda *_: ["dm"])

    paths = gen.write_collection(_SPEC, src=tmp_path)

    assert sorted(p.name for p in paths) == ["__init__.py", "__init__.pyi"]
    assert (tmp_path / "testcoll" / "__init__.py").is_file()
    assert (tmp_path / "testcoll" / "__init__.pyi").is_file()


def test_main_filters_by_collection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--collection regenerates only that collection, not every discovered one."""
    written: list[str] = []

    def fake_write(spec: data.Collection, src: Path = gen.SRC) -> list[Path]:
        written.append(spec.name)
        return [tmp_path / spec.name / "__init__.py"]

    other = data.Collection("other", "Other", "src", example="dm")
    monkeypatch.setattr(gen, "write_collection", fake_write)

    gen.main(["--collection", "testcoll"], collections=[_SPEC, other])

    assert written == ["testcoll"]
    assert "1 collection" in capsys.readouterr().out


def test_main_without_args_generates_every_collection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No --collection means every discovered collection is regenerated."""
    written: list[str] = []

    def fake_write(spec: data.Collection, src: Path = gen.SRC) -> list[Path]:
        written.append(spec.name)
        return [tmp_path / spec.name / "__init__.py"]

    specs = [
        data.Collection("coll_a", "A", "srcA", example="dm"),
        data.Collection("coll_b", "B", "srcB", example="ae"),
    ]
    monkeypatch.setattr(gen, "write_collection", fake_write)

    gen.main([], collections=specs)

    assert sorted(written) == ["coll_a", "coll_b"]
    assert "2 collection" in capsys.readouterr().out
