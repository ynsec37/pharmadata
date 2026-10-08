"""The Examples pages: that each Quarto chunk executes and renders correctly."""

import contextlib
import io
import re

import polars as pl
import pytest

from tests._helpers import ROOT

pytestmark = pytest.mark.docs

EXAMPLES = ROOT / "docs" / "examples"


def _run_example(name: str) -> tuple[str, str, dict[str, object]]:
    """Run a written example source: its text, what it printed, the namespace it
    left.
    """
    text = (EXAMPLES / f"{name}.qmd").read_text(encoding="utf-8")
    namespace: dict[str, object] = {}
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        for block in re.findall(r"^```\{python\}\n(.*?)^```", text, re.M | re.S):
            exec(block, namespace)
    return text, stream.getvalue(), namespace


@pytest.mark.parametrize("slug", ["adsl-from-sdtm", "demographic-table"])
def test_example_qmd_declares_execute_and_uses_python_chunks(slug: str) -> None:
    """Without these invariants an example page becomes a silent decoration."""
    text = (EXAMPLES / f"{slug}.qmd").read_text(encoding="utf-8")
    # front matter names the engine and turns execution on
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert fm is not None, f"{slug}.qmd has no YAML front matter"
    front = fm.group(1)
    assert re.search(r"^jupyter:\s*\S+", front, re.M), (
        f"{slug}.qmd must declare a jupyter kernel (e.g. `jupyter: python3`)"
    )
    assert "engine: markdown" not in front, (
        f"{slug}.qmd uses engine: markdown, which does not execute anything"
    )
    assert "execute:" in front, f"{slug}.qmd has no execute: block"
    # chunks use the pandoc-brace form; a plain fence is copied through unexecuted
    plain = re.findall(r"^```python(?:\s|$)", text, re.M)
    braced = re.findall(r"^```\{python\}", text, re.M)
    assert not plain, f"{slug}.qmd has {len(plain)} un-braced ```python fence(s)"
    assert braced, f"{slug}.qmd has no ```{{python}} chunk"
    assert "```text" not in text, (
        f"{slug}.qmd transcribes an output instead of running it"
    )


def test_the_adsl_example_derives_what_the_package_ships() -> None:
    """Every derived variable the shipped ADSL also carries must agree with it."""
    _, _, namespace = _run_example("adsl-from-sdtm")
    derived, mismatches = namespace["adsl"], namespace["mismatches"]
    assert set(mismatches) == {
        "AGEGR1",
        "RACEGR1",
        "DTHCGR1",
        "DTHDOM",
        "DTHCAUS",
        "EOSSTT",
        "EOSDT",
        "RANDDT",
        "SCRFDT",
        "FRVDT",
        "DTHDT",
        "DTHADY",
        "LDDTHELD",
        "TRTSDT",
        "TRTEDT",
        "TRTDURD",
        "SAFFL",
    }
    assert all(n == 0 for n in mismatches.values())
    # the variables derived on the way must all be present on the frame
    for column in (
        "AGEGR1N",
        "RACEN",
        "TRTSDTM",
        "TRTSTMF",
        "TRTEDTM",
        "TRTETMF",
        "TRTSTM",
        "TRTDURD",
        "SAFFL",
        "TRT01P",
        "TRT01A",
        "TRT01PN",
        "TRT01AN",
        "EOSDT",
        "EOSSTT",
        "DTHDT",
        "RANDDT",
        "SCRFDT",
        "FRVDT",
        "DTHADY",
        "LDDTHELD",
        "RANDFL",
        "DTHCAUS",
        "DTHDOM",
        "REGION1",
        "REGION1N",
        "RACEGR1",
        "RACEGR1N",
        "DTHCGR1",
        "DTHCGR1N",
    ):
        assert column in derived.columns


def test_the_demographic_table_adds_up_to_its_own_columns() -> None:
    """Every cell is checked against the N printed in its column."""
    _, _, namespace = _run_example("demographic-table")
    tlf, arms = namespace["tlf"], namespace["ARMS"]
    adsl = namespace["adsl"]
    assert tlf.columns == ["Characteristic", *arms]
    n = {arm: int(tlf.filter(pl.col("Characteristic") == "N")[0, arm]) for arm in arms}
    for arm, total in n.items():
        assert total == adsl.filter(pl.col("ACTARM") == arm).height
    for row in tlf.iter_rows(named=True):
        for arm in arms:
            cell = re.fullmatch(r"(\d+) \((\d+(?:\.\d+)?)%\)", row[arm] or "")
            if cell:
                counted, percent = int(cell[1]), float(cell[2])
                assert abs(percent - 100 * counted / n[arm]) < 0.05, (
                    f"{row['Characteristic']} in {arm}"
                )
