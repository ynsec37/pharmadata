"""The source behind each collection: one export program, one fetched bundle."""

import dataclasses
import io
import zipfile
from pathlib import Path

import pytest

from pharmadata._core import data
from tests._helpers import source_script

pytestmark = pytest.mark.build

fetch = source_script("01_fetch_sources")

# The collections that come from a pharmaverse R package rather than from a
# submission package published inside phuse-scripts.
REPO_KEYS = ("pharmaverseadam", "pharmaversesdtm")


def _source(key: str) -> fetch.Source:
    """The one registered source of a collection, by key."""
    return next(source for source in fetch.SOURCES if source.key == key)


def _bundle(members: dict[str, bytes]) -> bytes:
    """An in-memory zip of these members, as a source's bundle."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture
def sources_dir(tmp_path: Path) -> Path:
    """A temporary directory a fetch writes into, passed explicitly as source_dir."""
    return tmp_path


def test_sources_cover_exactly_the_registered_collections() -> None:
    """Every collection has one fetched source, and no source feeds nothing."""
    keys = [source.key for source in fetch.SOURCES]
    assert set(keys) == set(data.COLLECTIONS)
    assert len(keys) == len(set(keys)), "a collection is fetched twice"
    assert {source.key for source in fetch.REPOS} == set(REPO_KEYS)
    piloted = set(data.COLLECTIONS) - set(REPO_KEYS)
    assert {source.key for source in fetch.ARCHIVES} == piloted


def test_everything_fetched_lands_inside_data_raw() -> None:
    """A refresh writes no file outside data-raw/."""
    assert fetch.SOURCE_DIR.is_relative_to(fetch.PKG / "data-raw")
    for source in fetch.SOURCES:
        assert fetch.out_dir(source).is_relative_to(fetch.SOURCE_DIR)


def test_sources_are_fetched_as_files_not_as_repositories() -> None:
    """No git history is downloaded: a source is the files at a ref, as a zip."""
    for source in fetch.SOURCES:
        url = fetch.url_for(source)
        assert url.startswith("https://github.com/")
        assert ".git" not in url
        assert url.endswith(".zip")
    # a repository's own tree and one file inside a repository are the two kinds
    assert fetch.url_for(_source("pharmaverseadam")) == (
        "https://github.com/pharmaverse/pharmaverseadam/archive/main.zip"
    )
    assert fetch.url_for(_source("cdiscpilotadam")).startswith(
        "https://github.com/phuse-org/phuse-scripts/raw/master/"
    )


def test_a_source_is_fetched_at_the_ref_it_records() -> None:
    """Pinning a release is changing that ref, to a tag or a commit SHA alike."""
    adam = _source("pharmaverseadam")
    pinned = dataclasses.replace(adam, ref="v1.2.0")
    assert fetch.url_for(pinned) == (
        "https://github.com/pharmaverse/pharmaverseadam/archive/v1.2.0.zip"
    )


def test_every_required_file_is_one_the_source_keeps() -> None:
    """A requirement a keep pattern cannot match would fail every fetch."""
    for source in fetch.SOURCES:
        for need in source.require:
            assert fetch.member_path(source, f"top/{need}") == need


def test_a_bundle_is_kept_only_down_to_what_is_data() -> None:
    """A tree keeps the package's own paths, with the ref-named directory dropped."""
    adam = _source("pharmaverseadam")
    # GitHub nests a repository's files under a directory named after the ref
    assert fetch.member_path(adam, "pharmaverseadam-main/data/adsl.rda") == (
        "data/adsl.rda"
    )
    assert fetch.member_path(adam, "pharmaverseadam-main/man/adsl.Rd") == (
        "man/adsl.Rd"
    )
    assert fetch.member_path(adam, "pharmaverseadam-main/DESCRIPTION") == "DESCRIPTION"
    assert fetch.member_path(adam, "pharmaverseadam-main/LICENSE.md") == "LICENSE.md"
    # whatever else a package holds is not data
    assert fetch.member_path(adam, "pharmaverseadam-main/NAMESPACE") == ""
    assert fetch.member_path(adam, "pharmaverseadam-main/README.md") == ""
    assert fetch.member_path(adam, "pharmaverseadam-main/R/utils.R") == ""
    assert fetch.member_path(adam, "pharmaverseadam-main/tests/testthat.R") == ""
    assert fetch.member_path(adam, "pharmaverseadam-main/vignettes/intro.qmd") == ""
    # uncompressed CSV copies of the datasets, kept beside the specification
    assert fetch.member_path(adam, "x/inst/extdata/adams-specs.json") == (
        "inst/extdata/adams-specs.json"
    )
    assert fetch.member_path(adam, "x/inst/extdata/adlb.csv") == ""


def test_a_submission_archive_is_kept_down_to_its_datasets() -> None:
    """The documents beside the transport files are not part of a collection."""
    sdtm = _source("cdiscpilotsdtm")
    # the folder a submission nests its datasets in is not part of the path either
    assert fetch.member_path(sdtm, "SDTM/dm.xpt") == "dm.xpt"
    assert fetch.member_path(sdtm, "SDTM/define.xml") == "define.xml"
    assert fetch.member_path(sdtm, "SDTM/define2-0-0.xsl") == ""
    assert fetch.member_path(sdtm, "SDTM/Readme.md") == ""
    assert fetch.member_path(sdtm, "SDRG_CDISCPILOT03_SDTMIG_3.2.docx") == ""


def test_no_member_can_escape_its_directory() -> None:
    """A directory entry and a parent traversal are both refused."""
    adam = _source("pharmaverseadam")
    assert fetch.member_path(adam, "pharmaverseadam-main/data/") == ""
    assert fetch.member_path(adam, "pharmaverseadam-main/data/../../evil.rda") == ""
    sdtm = _source("cdiscpilotsdtm")
    assert fetch.member_path(sdtm, "SDTM/../../evil.xpt") == ""
    assert fetch.member_path(sdtm, "SDTM/") == ""


def test_extraction_writes_the_kept_paths_and_reports_them(sources_dir: Path) -> None:
    """Only what a source keeps is written, under its own directory."""
    adam = _source("pharmaverseadam")
    bundle = _bundle(
        {
            "pharmaverseadam-main/data/adsl.rda": b"adsl",
            "pharmaverseadam-main/man/adsl.Rd": b"title",
            "pharmaverseadam-main/DESCRIPTION": b"Apache-2.0",
            "pharmaverseadam-main/inst/extdata/adams-specs.json": b"{}",
            "pharmaverseadam-main/inst/extdata/adlb.csv": b"noise",
            "pharmaverseadam-main/R/noise.R": b"noise",
            "pharmaverseadam-main/data/": b"",
        }
    )
    written = fetch.extract(adam, bundle, source_dir=sources_dir)
    assert written == sorted(
        ["DESCRIPTION", "data/adsl.rda", "inst/extdata/adams-specs.json", "man/adsl.Rd"]
    )
    destination = sources_dir / "pharmaverseadam"
    assert (destination / "data/adsl.rda").read_bytes() == b"adsl"
    assert not (destination / "inst/extdata/adlb.csv").exists()


def _deletion_works(path: Path) -> bool:
    """Whether the filesystem actually removes a file after unlink.

    Some sandboxes let ``unlink`` return success without deleting the file,
    which makes stale-entry tests meaningless there.
    """
    probe = path / "_probe"
    probe.write_bytes(b"")
    probe.unlink()
    return not probe.exists()


def test_extraction_writes_fresh(sources_dir: Path) -> None:
    """A dataset withdrawn upstream does not survive as a stale copy."""
    if not _deletion_works(sources_dir):
        pytest.skip("filesystem does not support file deletion")
    sdtm = _source("cdiscpilotsdtm")
    stale = fetch.out_dir(sdtm, source_dir=sources_dir) / "gone.xpt"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")
    fetch.extract(
        sdtm,
        _bundle({"SDTM/dm.xpt": b"dm", "SDTM/define.xml": b"define"}),
        source_dir=sources_dir,
    )
    assert not stale.exists()
    assert (fetch.out_dir(sdtm, source_dir=sources_dir) / "dm.xpt").is_file()


def test_extraction_refuses_a_bundle_that_is_not_the_expected_one(
    sources_dir: Path,
) -> None:
    """No data, or a missing file an export cannot do without, stops the fetch."""
    sdtm = _source("cdiscpilotsdtm")
    with pytest.raises(SystemExit, match=r"holds none of \*\.xpt"):
        fetch.extract(
            sdtm, _bundle({"SDTM/notes.md": b"prose"}), source_dir=sources_dir
        )
    # datasets without the Define-XML their labels, structures and roles come from
    with pytest.raises(SystemExit, match=r"holds no define\.xml"):
        fetch.extract(sdtm, _bundle({"SDTM/dm.xpt": b"dm"}), source_dir=sources_dir)
    adam = _source("pharmaverseadam")
    good = _bundle(
        {
            "x/data/adsl.rda": b"adsl",
            "x/inst/extdata/adams-specs.json": b"{}",
        }
    )
    fetch.extract(adam, good, source_dir=sources_dir)
    with pytest.raises(SystemExit, match=r"holds no inst/extdata/adams-specs"):
        fetch.extract(
            adam, _bundle({"x/data/adsl.rda": b"adsl"}), source_dir=sources_dir
        )
    # a bundle that fails a check leaves the files of the last good fetch alone
    target = sources_dir / "pharmaverseadam" / "data" / "adsl.rda"
    assert target.read_bytes() == b"adsl"
