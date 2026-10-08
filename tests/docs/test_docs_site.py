"""The great-docs site: dataset pages, source links, theme colours, changelog."""

import re
from importlib import resources
from types import ModuleType

import pyarrow.parquet as pq
import pytest

import pharmadata
from pharmadata import pharmaverseadam as adam
from pharmadata._core import data
from tests._helpers import COLLECTIONS, DATASETS, DOCS, GUIDES, RESOURCES, ROOT, dataset_page

pytestmark = pytest.mark.docs


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_every_dataset_has_a_doc_page(collection: str, module: ModuleType) -> None:
    """One page per dataset under docs/datasets/, linked from the datasets index."""
    nav = (DATASETS / "index.qmd").read_text(encoding="utf-8")
    for name in module.list_datasets():
        page = dataset_page(collection, name)
        assert page.is_file(), f"missing doc page for {collection}.{name}"
        assert f"[{name}]({collection}/{name}.html)" in nav, (
            f"{name} not linked from the datasets index"
        )
        text = page.read_text(encoding="utf-8")
        # every page previews its first rows with the great-docs table explorer,
        # so the full frame is never embedded
        assert "from great_docs import tbl_explorer" in text, (
            f"{name} page does not preview its data with tbl_explorer"
        )
        assert f"tbl_explorer({collection}.{name}.head(10))" in text
        example = f"{collection}.meta({name!r})"
        assert example in text, f"{name} page lacks the meta example"
        assert "schema_arrow" not in text, f"{name} repeats the parquet lesson"


def test_the_datasets_index_links_every_collection_source() -> None:
    """The one datasets index names the publisher each collection points at."""
    index = (DATASETS / "index.qmd").read_text(encoding="utf-8")
    for name, spec in data.COLLECTIONS.items():
        assert f"[{spec.source}]({spec.url})" in index, f"{name} source not named"


def test_the_registry_names_exactly_the_four_documented_sources() -> None:
    """The source links are the ones the collection table in the docs promises."""
    expected = {
        "pharmaverseadam": (
            "pharmaverseadam",
            "https://github.com/pharmaverse/pharmaverseadam",
        ),
        "pharmaversesdtm": (
            "pharmaversesdtm",
            "https://github.com/pharmaverse/pharmaversesdtm",
        ),
        "cdiscpilotadam": (
            "the CDISC SDTM/ADaM Pilot Project",
            "https://github.com/phuse-org/phuse-scripts/tree/master/data/adam",
        ),
        "cdiscpilotsdtm": (
            "the CDISC SDTM/ADaM Pilot Project",
            "https://github.com/phuse-org/phuse-scripts/tree/master/data/sdtm",
        ),
    }
    actual = {name: (spec.source, spec.url) for name, spec in data.COLLECTIONS.items()}
    assert actual == expected


def test_the_parquet_read_is_explained_once() -> None:
    """The landing page holds the direct-read example; no reference page repeats it."""
    index = (GUIDES / "index.qmd").read_text(encoding="utf-8")
    assert "pq.ParquetFile(path).schema_arrow" in index
    assert "pq.read_table(path, columns=" in index
    # the dataset label comes from the schema metadata, bytes decoded to str
    assert '.get(b"label", b"").decode()' in index
    decoded = {
        key.decode(): value.decode()
        for key, value in pq.read_schema(
            resources.files("pharmadata") / "_data" / "pharmaverseadam" / "adsl.parquet"
        )
        .field("AGE")
        .metadata.items()
    }
    assert decoded["label"] == adam.adsl_meta.column_names_to_labels["AGE"]
    repeated = [
        page.name
        for collection in COLLECTIONS
        for page in dataset_page(collection, "x").parent.glob("*.qmd")
        if "schema_arrow" in page.read_text(encoding="utf-8")
    ]
    assert not repeated, f"the parquet lesson is repeated on {repeated}"


def test_every_generated_page_says_do_not_edit() -> None:
    """Each build-written dataset page names its producer at the top."""
    pages = [
        page
        for collection in COLLECTIONS
        for page in dataset_page(collection, "x").parent.glob("*.qmd")
    ]
    assert pages, "no generated dataset pages found"
    for page in pages:
        head = page.read_text(encoding="utf-8")[:400]
        assert "do not edit." in head, f"{page.relative_to(ROOT)} has no marker"


def test_the_changelog_is_a_hand_written_page() -> None:
    """docs/changelog.md is the release record itself: hand-written, filled."""
    assert not (DOCS.parent / "CHANGELOG.md").exists(), "the root changelog is back"
    page = (DOCS / "changelog.md").read_text(encoding="utf-8")
    assert "do not edit." not in page, "the changelog carries a generation marker"
    # the entry for the version the package reports, spelled as the file declares it
    assert f"## {pharmadata.__version__}" in page, "no entry for the shipped version"
    # a record reduced to a stub would still pass the checks above
    entry = page.split(f"## {pharmadata.__version__}", 1)[1]
    assert entry.strip(), "the release record has been emptied"


def test_the_navbar_and_accent_colours_match_the_brand() -> None:
    """White/black navbar and the polars-teal accent, declared in docs config."""
    cfg = (DOCS / "great-docs.yml").read_text(encoding="utf-8")
    assert "navbar_color:" in cfg
    assert 'light: "#ffffff"' in cfg
    assert 'dark: "#000000"' in cfg
    assert 'accent_color: "#0a7d91"' in cfg


def test_the_constants_sidebar_group_is_renamed_via_a_shipped_js() -> None:
    """Rename the hardcoded Reference "Constants" group via a shipped JS file.

    great-docs hardcodes the group label; a standalone script under docs/assets/
    (great-docs' convention: source paths are relative to docs/) rewrites it to
    "Datasets" at load time.
    """
    js = DOCS / "assets" / "gd-rename-labels.js"
    assert js.is_file(), "the sidebar rename script is missing from docs/assets/"
    source = js.read_text(encoding="utf-8")
    # the code stays out of the yml and targets the category title by its text
    assert ".menu-text" in source
    assert 'Constants: "Datasets"' in source
    cfg = (DOCS / "great-docs.yml").read_text(encoding="utf-8")
    # wired site-wide through include_in_header, resolved by the quarto:offset
    # meta so the path also works on nested pages under the /pharmadata/ base
    assert "include_in_header:" in cfg
    assert "quarto:offset" in cfg
    assert "assets/gd-rename-labels.js" in cfg


def test_the_navbar_orders_the_six_top_level_sections() -> None:
    """The site config drives the requested navbar and the marimo notebook."""
    cfg = (DOCS / "great-docs.yml").read_text(encoding="utf-8")
    # the six top-level items, in the order the reader should meet them
    order = re.search(r"navbar_order:\n((?:  - .+\n)+)", cfg)
    assert order is not None, "no navbar_order block"
    items = re.findall(r"^  - (.+)$", order.group(1), re.M)
    assert items == [
        "User Guide",
        "Datasets",
        "Examples",
        "Notebook",
        "Reference",
        "Resources",
    ]
    # each content section is backed by its own directory under docs/
    # (great-docs resolves section dirs relative to docs/)
    for section in ("Datasets", "Examples", "Notebook", "Resources"):
        assert re.search(rf"- title: {section}\n    dir: \w+", cfg), (
            f"{section} section missing"
        )
    # the interactive viewer is a marimo notebook great-docs renders natively
    assert re.search(r"^marimo: true$", cfg, re.M), "marimo is not enabled"
    notebook_src = (DOCS / "notebooks" / "index.qmd").read_text(encoding="utf-8")
    assert (DOCS / "notebooks" / "index.qmd").is_file(), "no Notebook page"
    assert "{{< marimo" in notebook_src, "the Notebook page drops the marimo embed"
    # the island renders inline, so it works at any page depth; the iframe mode
    # resolves a page-relative src that 404s on the nested /docs/notebooks/ page
    assert 'mode="iframe"' not in notebook_src, (
        "the Notebook page still uses the iframe mode that 404s when nested"
    )


def test_the_resources_section_lists_the_directory_and_the_comparison() -> None:
    """The Resources page pair: the directory and the polars-vs-tidyverse grid."""
    index = (RESOURCES / "01-python-resources.qmd").read_text(encoding="utf-8")
    for name in ("pyreadstat", "datacompy", "pycsr.org", "pharmaverse.org"):
        assert name in index, f"the directory page does not mention {name}"
    comparison = (RESOURCES / "02-polars-vs-tidyverse.qmd").read_text(encoding="utf-8")
    # the comparison grid holds two columns per section
    assert "{.compare " in comparison
    assert comparison.count("{.compare-col ") >= 2
    # each section pairs one Python and one R chunk
    py_fences = len(re.findall(r"^```\{python\}", comparison, re.M))
    r_fences = len(re.findall(r"^```\{r\}", comparison, re.M))
    assert py_fences == r_fences > 0, "each section needs one Python and one R chunk"
