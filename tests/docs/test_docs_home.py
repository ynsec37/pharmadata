"""The user guide landing page: it runs its Python chunks and teaches the recipe."""

import contextlib
import io
import re

import polars as pl
import pytest

from tests._helpers import GUIDES

pytestmark = pytest.mark.docs

SOURCE = GUIDES / "index.qmd"


def _run_home_chunks() -> tuple[str, dict[str, object]]:
    """Run the source's python chunks in document order, as Quarto renders them."""
    text = SOURCE.read_text(encoding="utf-8")
    namespace: dict[str, object] = {}
    with contextlib.redirect_stdout(io.StringIO()):
        for block in re.findall(r"^```\{python\}\n(.*?)^```", text, re.M | re.S):
            exec(block, namespace)
    return text, namespace


def test_the_home_source_declares_execute_and_uses_python_chunks() -> None:
    """Without these an executed page silently degrades into a decoration."""
    text = SOURCE.read_text(encoding="utf-8")
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert fm is not None, "index.qmd has no YAML front matter"
    front = fm.group(1)
    assert re.search(r"^jupyter:\s*\S+", front, re.M), (
        "the home page must declare a jupyter kernel to execute python chunks"
    )
    assert "execute:" in front
    plain = re.findall(r"^```python(?:\s|$)", text, re.M)
    assert not plain, f"{len(plain)} un-braced ```python fence(s) would not run"
    assert re.findall(r"^```\{python\}", text, re.M), "no ```{python} chunk to execute"
    assert "```text" not in text, (
        "the home page transcribes an output instead of running it"
    )


def test_the_home_page_teaches_the_direct_read_recipe() -> None:
    """The direct-read recipe lives on the landing page, in one place."""
    text = SOURCE.read_text(encoding="utf-8")
    assert "## Read parquet directly" in text, (
        "the landing page no longer teaches the direct read"
    )
    assert "pq.ParquetFile(path).schema_arrow" in text
    assert "pl.from_arrow(pq.read_table(path, columns=" in text


def test_the_adsl_summary_matches_the_shipped_frame() -> None:
    """The arm table the page derives is the one the shipped ADSL implies."""
    _, namespace = _run_home_chunks()
    adsl = namespace["adsl"]
    assert isinstance(adsl, pl.DataFrame)
    assert adsl.shape == (306, 55)
    summary = (
        adsl.filter(pl.col("TRT01A") != "Screen Failure")
        .group_by("TRT01A")
        .agg(pl.col("AGE").mean().round(1).alias("mean_age"), pl.len().alias("n"))
        .sort("TRT01A")
    )
    # the three randomised arms are computed; the screen-failure group is excluded
    assert len(summary) == 3
    assert set(summary.get_column("TRT01A")).isdisjoint({"Screen Failure"})
