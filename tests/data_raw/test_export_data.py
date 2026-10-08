"""The R export stage (02_export_data.R): driver wiring and exporter conventions."""

import re
from pathlib import Path

import pytest

from pharmadata._core import data
from tests._helpers import ROOT

pytestmark = pytest.mark.build

DATA_RAW = ROOT / "data-raw"
DRIVER = (DATA_RAW / "02_export_data.R").read_text(encoding="utf-8")


def _exporter_file(collection: str) -> Path:
    """The single 02_??_export_<collection>.R file for a collection."""
    matches = list(DATA_RAW.glob(f"02_??_export_{collection}.R"))
    assert len(matches) == 1, (
        f"expected one 02_??_export_{collection}.R, found {matches}"
    )
    return matches[0]


@pytest.mark.parametrize("collection", sorted(data.COLLECTIONS))
def test_every_collection_has_an_export_program(collection: str) -> None:
    """One numbered R program per collection, and the driver runs each of them."""
    program = _exporter_file(collection).name
    assert f'"{program}"' in DRIVER, f"02_export_data.R does not run {program}"


@pytest.mark.parametrize("collection", sorted(data.COLLECTIONS))
def test_each_exporter_defines_its_named_function(collection: str) -> None:
    """The driver calls get(paste0('export_', collection))(), so the name must match."""
    source = _exporter_file(collection).read_text(encoding="utf-8")
    pattern = rf"export_{re.escape(collection)}\s*<-\s*function"
    assert re.search(pattern, source), (
        f"{collection} exporter does not define export_{collection}()"
    )


@pytest.mark.parametrize("collection", sorted(data.COLLECTIONS))
def test_each_exporter_has_the_nframe_guard(collection: str) -> None:
    """Sourcing defines functions only; the sys.nframe() guard keeps it from running."""
    source = _exporter_file(collection).read_text(encoding="utf-8")
    assert "if (sys.nframe() == 0L)" in source, (
        f"{collection} exporter lacks the sys.nframe() guard; "
        "sourcing it would execute the export"
    )


def test_driver_programs_cover_every_collection() -> None:
    """The PROGRAMS vector names every collection, so none is skipped at export time."""
    match = re.search(r"PROGRAMS\s*<-\s*c\((.*?)\)", DRIVER, re.S)
    assert match is not None, "02_export_data.R has no PROGRAMS vector"
    body = match.group(1)
    named = re.findall(r'(\w+)\s*=\s*"([^"]+)"', body)
    declared = {key for key, _ in named}
    assert declared == set(data.COLLECTIONS), (
        f"PROGRAMS {sorted(declared)} does not match collections {sorted(data.COLLECTIONS)}"
    )
