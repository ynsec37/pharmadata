"""The 05_build_dataset_qmd.py generator: page, index and markdown rendering."""

from pathlib import Path

import pytest

from pharmadata._core import data
from tests._helpers import source_script

pytestmark = pytest.mark.build

gen = source_script("05_build_dataset_qmd")

_ENTRY: data.DatasetMetaEntry = {
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

_ENTRY_NO_STRUCTURE: data.DatasetMetaEntry = {
    "label": "Adverse Events",
    "structure": None,
    "n_rows": 100,
    "columns": {
        "USUBJID": {
            "label": "Subject",
            "type": "String",
            "mandatory": "Y",
            "role": "ID",
        }
    },
}


def test_md_escapes_pipes_and_collapses_newlines() -> None:
    """A table cell never breaks the table: pipes escaped, newlines to spaces."""
    assert gen.md("a|b") == "a\\|b"
    assert gen.md("line1\nline2") == "line1 line2"
    assert gen.md("  padded  ") == "padded"
    assert gen.md(306) == "306"


def test_structure_block_is_present_only_when_defined() -> None:
    """A dataset with a structure gets the line; one without gets nothing."""
    assert gen._structure_block(_ENTRY) == "\nStructure: `one record per subject`\n"
    assert gen._structure_block(_ENTRY_NO_STRUCTURE) == ""


def test_render_page_fills_every_template_variable() -> None:
    """The page template is fully substituted: title, label, structure, code."""
    page = gen.render_page("pharmaverseadam", "adsl", _ENTRY)

    assert gen.GENERATED_COMMENT in page
    assert "title: adsl" in page
    assert "# adsl" in page
    assert "## Demographics" in page
    assert "Structure: `one record per subject`" in page
    # the python cells import the collection and call meta/specs on the dataset
    assert "from pharmadata import pharmaverseadam" in page
    assert "pharmaverseadam.meta('adsl')" in page
    assert "pharmaverseadam.meta('adsl').specs" in page
    assert "tbl_explorer(pharmaverseadam.adsl.head(10))" in page
    # no unresolved template variable survives
    assert "$" not in page.replace("$widget", "").replace("$name", "").replace(
        "$collection", ""
    ).replace("$label", "").replace("$structure_block", "").replace(
        "$generated_comment", ""
    ).replace("$name_repr", "")


def test_render_page_omits_structure_when_absent() -> None:
    """A dataset without a structure has no Structure line at all."""
    page = gen.render_page("testcoll", "ae", _ENTRY_NO_STRUCTURE)
    assert "Structure:" not in page


def test_collection_rows_are_sorted_and_escaped() -> None:
    """The index table rows are sorted by dataset name and labels are pipe-safe."""
    all_meta = {
        "dm": _ENTRY,
        "ae": {**_ENTRY_NO_STRUCTURE, "n_rows": 1_234},
    }
    rows = gen._collection_rows("testcoll", all_meta)

    lines = rows.split("\n")
    # sorted alphabetically: ae before dm
    assert lines[0].startswith("| [ae](testcoll/ae.html)")
    assert lines[1].startswith("| [dm](testcoll/dm.html)")
    # n_rows is thousands-formatted
    assert "| 1,234 |" in lines[0]
    # column count comes from the columns dict
    assert "| 2 |" in lines[1]  # dm has 2 columns


def test_write_page_writes_under_datasets_collection(tmp_path: Path) -> None:
    """write_page() creates docs/datasets/<NN-collection>/<name>.qmd.

    INDEX_ORDER collections get a numeric prefix so the sidebar follows the
    intended order; great-docs strips the prefix from the published URL.
    """
    gen.write_page("pharmaverseadam", "adsl", _ENTRY, datasets=tmp_path)

    page = tmp_path / "01-pharmaverseadam" / "adsl.qmd"
    assert page.is_file()
    assert "title: adsl" in page.read_text(encoding="utf-8")


def test_write_index_groups_collections_and_totals(tmp_path: Path) -> None:
    """The index lists every collection's datasets with the grand total."""
    specs = {
        "coll_a": data.Collection(
            "coll_a", "Collection A", "Source A", "https://a", "dm"
        ),
        "coll_b": data.Collection(
            "coll_b", "Collection B", "Source B", "https://b", "ae"
        ),
    }

    metas = {
        "coll_a": {"dm": _ENTRY},
        "coll_b": {"ae": _ENTRY_NO_STRUCTURE},
    }
    gen.write_index(metas, collections=specs, datasets=tmp_path)

    index = (tmp_path / "index.qmd").read_text(encoding="utf-8")
    # total datasets and collections
    assert "2 datasets across 2 collections" in index
    # each collection section with its source link
    assert "## Collection A" in index
    assert "[Source A](https://a)" in index
    assert "## Collection B" in index
    assert "[Source B](https://b)" in index
    # every dataset is linked
    assert "[dm](coll_a/dm.html)" in index
    assert "[ae](coll_b/ae.html)" in index


def test_write_index_appends_unknown_collections_alphabetically(tmp_path: Path) -> None:
    """A collection not in INDEX_ORDER still appears, after the known ones."""
    specs = {
        "pharmaverseadam": data.Collection(
            "pharmaverseadam", "Pharmaverse ADaM", "P", "https://p", "adsl"
        ),
        "zz_new": data.Collection("zz_new", "New Collection", "N", "https://n", "x"),
    }

    metas = {
        "zz_new": {"x": _ENTRY_NO_STRUCTURE},
        "pharmaverseadam": {"adsl": _ENTRY},
    }
    gen.write_index(metas, collections=specs, datasets=tmp_path)

    index = (tmp_path / "index.qmd").read_text(encoding="utf-8")
    # the known collection comes first, the new one after
    assert index.index("## Pharmaverse ADaM") < index.index("## New Collection")


def test_main_regenerates_every_page_and_the_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """main() writes a page per dataset across every collection, plus the index."""
    specs = {
        "coll_a": data.Collection("coll_a", "A", "src", "https://a", "dm"),
    }
    monkeypatch.setattr(
        gen, "raw_meta", lambda *_: {"dm": _ENTRY, "ae": _ENTRY_NO_STRUCTURE}
    )

    gen.main(collections=specs, datasets=tmp_path)

    # one page per dataset, plus the index
    assert (tmp_path / "coll_a" / "dm.qmd").is_file()
    assert (tmp_path / "coll_a" / "ae.qmd").is_file()
    assert (tmp_path / "index.qmd").is_file()


def test_filter_datasets_include_pins_to_named_datasets() -> None:
    """Include with a name list keeps only those datasets, sorted."""
    all_meta = {"dm": _ENTRY, "ae": _ENTRY_NO_STRUCTURE, "lb": _ENTRY}
    names = gen._filter_datasets(
        "c", all_meta, include={"c": ["ae", "dm"]}, exclude=None
    )
    assert names == ["ae", "dm"]


def test_filter_datasets_include_none_means_all() -> None:
    """Include with None (bare collection) keeps every dataset."""
    all_meta = {"dm": _ENTRY, "ae": _ENTRY_NO_STRUCTURE}
    names = gen._filter_datasets("c", all_meta, include={"c": None}, exclude=None)
    assert names == ["ae", "dm"]


def test_filter_datasets_exclude_drops_named_datasets() -> None:
    """Exclude with a name list drops those datasets."""
    all_meta = {"dm": _ENTRY, "ae": _ENTRY_NO_STRUCTURE, "lb": _ENTRY}
    names = gen._filter_datasets("c", all_meta, include=None, exclude={"c": ["ae"]})
    assert names == ["dm", "lb"]


def test_filter_datasets_exclude_none_drops_the_collection() -> None:
    """Exclude with None (bare collection) drops every dataset of it."""
    all_meta = {"dm": _ENTRY, "ae": _ENTRY_NO_STRUCTURE}
    names = gen._filter_datasets("c", all_meta, include=None, exclude={"c": None})
    assert names == []


def test_main_include_renders_only_named_datasets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """main(include=...) writes only the requested datasets' pages and index."""
    specs = {"coll_a": data.Collection("coll_a", "A", "src", "https://a", "dm")}
    monkeypatch.setattr(
        gen, "raw_meta", lambda *_: {"dm": _ENTRY, "ae": _ENTRY_NO_STRUCTURE}
    )

    gen.main(collections=specs, datasets=tmp_path, include={"coll_a": ["ae"]})

    assert (tmp_path / "coll_a" / "ae.qmd").is_file()
    assert not (tmp_path / "coll_a" / "dm.qmd").exists()
    index = (tmp_path / "index.qmd").read_text(encoding="utf-8")
    assert "[ae](coll_a/ae.html)" in index
    assert "dm" not in index


def test_main_exclude_skips_requested_datasets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """main(exclude=...) omits the named datasets from pages and the index."""
    specs = {"coll_a": data.Collection("coll_a", "A", "src", "https://a", "dm")}
    monkeypatch.setattr(
        gen, "raw_meta", lambda *_: {"dm": _ENTRY, "ae": _ENTRY_NO_STRUCTURE}
    )

    gen.main(collections=specs, datasets=tmp_path, exclude={"coll_a": ["ae"]})

    assert (tmp_path / "coll_a" / "dm.qmd").is_file()
    assert not (tmp_path / "coll_a" / "ae.qmd").exists()
    index = (tmp_path / "index.qmd").read_text(encoding="utf-8")
    assert "[dm](coll_a/dm.html)" in index
    assert "ae" not in index


def test_main_include_limits_to_listed_collections(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With include set, collections not in it are not rendered at all."""
    specs = {
        "coll_a": data.Collection("coll_a", "A", "src", "https://a", "dm"),
        "coll_b": data.Collection("coll_b", "B", "src", "https://b", "ae"),
    }
    monkeypatch.setattr(gen, "raw_meta", lambda *_: {"dm": _ENTRY})

    gen.main(collections=specs, datasets=tmp_path, include={"coll_a": None})

    assert (tmp_path / "coll_a" / "dm.qmd").is_file()
    assert not (tmp_path / "coll_b").exists()


def test_parse_filter_parses_bare_and_named_specs() -> None:
    """_parse_filter handles ``collection`` and ``collection:a,b`` forms."""
    assert gen._parse_filter(["coll_a"]) == {"coll_a": None}
    assert gen._parse_filter(["coll_a:dm,ae"]) == {"coll_a": ["dm", "ae"]}
    assert gen._parse_filter(["coll_a", "coll_b:x"]) == {
        "coll_a": None,
        "coll_b": ["x"],
    }


def test_main_limit_caps_datasets_per_collection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """main(limit=N) renders at most N datasets per collection, alphabetically."""
    specs = {"coll_a": data.Collection("coll_a", "A", "src", "https://a", "dm")}
    monkeypatch.setattr(
        gen,
        "raw_meta",
        lambda *_: {
            "zz": _ENTRY,
            "aa": _ENTRY_NO_STRUCTURE,
            "mm": _ENTRY,
        },
    )

    gen.main(collections=specs, datasets=tmp_path, limit=2)

    written = {p.stem for p in (tmp_path / "coll_a").glob("*.qmd")}
    # only the first 2 alphabetically: aa and mm
    assert written == {"aa", "mm"}
    assert not (tmp_path / "coll_a" / "zz.qmd").exists()
