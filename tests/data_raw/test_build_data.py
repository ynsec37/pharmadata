"""The 03_build_data.py CLI and validation entry points."""

import json
from pathlib import Path

import polars as pl
import pyarrow.parquet as pq
import pytest

from tests._helpers import build_script

pytestmark = pytest.mark.build

# A minimal raw dataset: two columns whose metadata rows the build path must
# carry through to the shipped parquet and _meta.json.
_RAW_META_TEMPLATE = {
    "dataset_label": ["Demographics", "Demographics"],
    "structure": ["one record per subject", "one record per subject"],
    "column_name": ["USUBJID", "AGE"],
    "column_label": ["Unique Subject Identifier", "Age"],
    "mandatory": ["Y", "Y"],
    "role": ["ID", "Analysis"],
}


def _write_raw_collection(raw: Path, collection: str, name: str = "dm") -> None:
    """Drop one dataset's parquet + _meta.parquet into raw/<collection>/."""
    coll_dir = raw / collection
    coll_dir.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"USUBJID": ["01-001", "01-002"], "AGE": [30, 35]}).write_parquet(
        coll_dir / f"{name}.parquet"
    )
    meta = {"dataset_name": [name, name], **_RAW_META_TEMPLATE}
    pl.DataFrame(meta).write_parquet(coll_dir / f"{name}_meta.parquet")


def test_check_passes_on_the_shipped_raw_data(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--check reads every raw dataset and the assets, and succeeds."""
    script = build_script()
    script.main(["--check"])
    assert "ok:" in capsys.readouterr().out


def test_check_refuses_a_collection_without_raw_datasets(tmp_path: Path) -> None:
    """An empty raw directory fails --check rather than crashing a later build."""
    script = build_script()
    with pytest.raises(ValueError, match="no raw datasets"):
        script.validate(collections=["nope"], raw=tmp_path)


def test_check_refuses_data_without_its_metadata(tmp_path: Path) -> None:
    """A parquet without its _meta.parquet fails --check, naming the dataset."""
    script = build_script()
    first = next(iter(script.COLLECTIONS))
    (tmp_path / first).mkdir()
    (tmp_path / first / "dm.parquet").write_bytes(b"")
    with pytest.raises(ValueError, match=r"data without metadata: dm"):
        script.validate(collections=[first], raw=tmp_path)


def test_validate_name_rejects_non_identifiers_and_keywords() -> None:
    """A dataset name becomes an attribute and a stub line, so only identifiers pass."""
    script = build_script()
    for bad in ("foo-bar", "1abc", "class", "for", "with"):
        with pytest.raises(ValueError, match="not a valid Python identifier"):
            script._validate_name(bad, Path(f"{bad}_meta.parquet"))
    script._validate_name("adsl", Path("adsl_meta.parquet"))  # ok


def test_dataset_requires_domain() -> None:
    """--dataset without a domain is refused by argparse rather than guessed."""
    script = build_script()
    with pytest.raises(SystemExit):
        script._parse_args(["--dataset", "adsl"])


def test_domains_are_single_sourced() -> None:
    """03_build_data.py reads the Collection registry from the package, not a copy."""
    from pharmadata._core import data

    assert build_script().COLLECTIONS is data.COLLECTIONS


def test_main_packages_a_collection_into_shipped_data(tmp_path: Path) -> None:
    """main() writes the labelled parquet and _meta.json for a collection."""
    script = build_script()
    raw, data = tmp_path / "raw", tmp_path / "data"
    collection = "testcoll"
    _write_raw_collection(raw, collection)

    script.main([], collections=[collection], raw=raw, data=data)

    # the shipped parquet carries the dataset label in schema metadata and each
    # column label in field metadata; the generator ID is also persisted
    shipped = data / collection / "dm.parquet"
    assert shipped.is_file()
    schema = pq.read_schema(shipped)
    assert schema.metadata[b"label"] == b"Demographics"
    assert schema.metadata[b"pharmadata:generator"] == b"data-raw/build_data.py"
    assert schema.field("AGE").metadata[b"label"] == b"Age"

    # _meta.json holds the full entry, including the row count and the CDISC dtype
    meta = json.loads((data / collection / "_meta.json").read_text(encoding="utf-8"))
    assert set(meta) == {"dm"}
    entry = meta["dm"]
    assert entry["label"] == "Demographics"
    assert entry["structure"] == "one record per subject"
    assert entry["n_rows"] == 2
    assert entry["columns"]["AGE"]["label"] == "Age"
    assert entry["columns"]["AGE"]["type"] == "Int64"
    assert entry["columns"]["AGE"]["mandatory"] == "Y"


def test_main_with_only_rebuilds_one_dataset_and_keeps_full_meta(
    tmp_path: Path,
) -> None:
    """--dataset rewrites one parquet but _meta.json still covers every dataset."""
    script = build_script()
    raw, data = tmp_path / "raw", tmp_path / "data"
    collection = "testcoll"
    _write_raw_collection(raw, collection, name="dm")
    _write_raw_collection(raw, collection, name="ae")

    script.main(
        ["--collection", collection, "--dataset", "ae"],
        collections=[collection],
        raw=raw,
        data=data,
    )

    # only the requested dataset's parquet is written, the other is absent
    assert (data / collection / "ae.parquet").is_file()
    assert not (data / collection / "dm.parquet").exists()
    # but _meta.json carries both, so a partial rebuild never shrinks the catalog
    meta = json.loads((data / collection / "_meta.json").read_text(encoding="utf-8"))
    assert set(meta) == {"ae", "dm"}


def test_main_with_unknown_dataset_names_available_ones(tmp_path: Path) -> None:
    """A --dataset that does not exist fails and lists what is available."""
    script = build_script()
    raw, data = tmp_path / "raw", tmp_path / "data"
    collection = "testcoll"
    _write_raw_collection(raw, collection)

    with pytest.raises(SystemExit, match=r"no dataset 'nope'; available: dm"):
        script.main(
            ["--collection", collection, "--dataset", "nope"],
            collections=[collection],
            raw=raw,
            data=data,
        )
