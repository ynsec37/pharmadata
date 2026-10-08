"""The lockfile of the build's R stage: what it pins, and whether it still covers."""

import json
import re
from pathlib import Path

import pytest

from tests._helpers import ROOT

pytestmark = pytest.mark.build

LOCKFILE = ROOT / "renv.lock"

# renv reads the lockfile but is not a dependency of it, as uv is not of uv.lock
TOOL = "renv"

# Base R packages ship with R itself; renv.lock only pins CRAN packages, so these
# are never records a restore has to install.
BASE = {
    "base",
    "compiler",
    "datasets",
    "grDevices",
    "graphics",
    "grid",
    "methods",
    "parallel",
    "splines",
    "stats",
    "stats4",
    "tcltk",
    "tools",
    "utils",
}

# Quarto starts these to run the R of a .qmd; no library() call names them
RENDER_ENGINES = {"knitr", "reticulate", "rmarkdown"}

# Posit's CRAN mirror: it serves Linux binaries, so a restore installs
REPOSITORY = re.compile(
    r"https://packagemanager\.posit\.co/cran/(latest|\d{4}-\d{2}-\d{2})$"
)

ATTACH = re.compile(r"(?:library|require)\(\s*([A-Za-z][A-Za-z0-9._]*)")
NAMESPACE = re.compile(r"([A-Za-z][A-Za-z0-9._]*)::")
CHUNK = re.compile(r"^```\{r[^\n]*\n(.*?)^```", re.DOTALL | re.MULTILINE)
COMMENT = re.compile("#.*")


def _sources() -> list[Path]:
    """The files whose R the lockfile has to account for."""
    programs = sorted((ROOT / "data-raw").glob("*.R"))
    pages = [
        page
        for page in sorted((ROOT / "docs").rglob("*.qmd"))
        if not page.name.startswith("_")  # a probe is not a page
    ]
    return [*programs, *pages]


def _r_code(path: Path) -> str:
    """The R code of one source: the chunks of a `.qmd`, the whole of an `.R`."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".qmd":
        text = "\n".join(CHUNK.findall(text))
    # a comment is not a use of a package
    return COMMENT.sub("", text)


def _used() -> set[str]:
    """Every package a source attaches or reaches through ``::``."""
    found: set[str] = set()
    for path in _sources():
        code = _r_code(path)
        found.update(ATTACH.findall(code))
        found.update(NAMESPACE.findall(code))
    return found - {TOOL} - BASE


@pytest.fixture(scope="module")
def lock() -> dict:
    """The committed lockfile, parsed once for the module."""
    return json.loads(LOCKFILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def records(lock: dict) -> dict:
    """The packages the lockfile names, as it names them."""
    return lock["Packages"]


@pytest.mark.parametrize("package", sorted(_used()))
def test_one_package_the_sources_use_is_locked(package: str, records: dict) -> None:
    """A package a source reaches for is a version a restore has to install."""
    assert package in records, (
        f"renv.lock names no version of {package}; run make r-lock"
    )


def test_the_render_engines_are_locked(records: dict) -> None:
    """The comparison pages render because those packages are in the library."""
    missing = sorted(RENDER_ENGINES - set(records))
    assert not missing, f"the Quarto render needs {missing}, which renv.lock lacks"


def test_the_tool_that_reads_the_lockfile_is_not_locked(records: dict) -> None:
    """The renv tool is installed as a tool, not restored as a dependency."""
    assert TOOL not in records, "renv belongs to the runner, not to renv.lock"


def test_the_lockfile_names_one_posit_repository(lock: dict) -> None:
    """More than one repository would leave a restore guessing where a version is."""
    repositories = lock["R"]["Repositories"]
    assert len(repositories) == 1, "the R stage is locked to CRAN alone"
    assert REPOSITORY.match(repositories[0]["URL"]), repositories[0]["URL"]


def test_every_record_names_a_version_and_where_to_get_it(records: dict) -> None:
    """A record a restore could not download is a record that ends a rebuild."""
    for name, record in records.items():
        assert record["Package"] == name, f"{name} is keyed under another name"
        assert record.get("Version"), f"{name} is locked without a version"
        downloadable = record.get("Repository") or any(
            key.startswith("Remote") for key in record
        )
        assert downloadable, f"{name} has no repository and no remote to restore from"


def test_the_lockfile_records_the_r_it_was_written_with(lock: dict) -> None:
    """The R version is part of the contract: a package is built against it."""
    version = lock["R"]["Version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
