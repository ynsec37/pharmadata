"""Fetch the upstream files every collection is built from, one HTTPS request per source."""

from __future__ import annotations

import fnmatch
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

# sibling build scripts import each other by name when loaded by path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import _retry, rmtree

PKG = Path(__file__).resolve().parents[1]
# Fetched upstream files, all of it regenerable.
SOURCE_DIR = PKG / "data-raw" / "sources"

# Network timeout per source download, in seconds.
DOWNLOAD_TIMEOUT = 120


@dataclass(frozen=True)
class Source:
    """One upstream source: where its files come from, and which of them are data."""

    key: str  # the directory it fills under data-raw/sources/
    repo: str  # "owner/name" of the upstream repository
    ref: str  # branch, tag or SHA; changing it is the provenance record
    # glob patterns for which members are data, matched after `member_path`
    keep: tuple[str, ...]
    # members an export program cannot run without
    require: tuple[str, ...] = ()
    # archive inside the repository, "" for the repository tree itself
    path: str = ""
    # glob pattern for the actual data files (one per dataset), relative to
    # the source's output directory. Used to hash each dataset's source file.
    data_glob: str = "*.rda"


# The two pharmaverse R packages, read as the files their repository holds.
REPOS = (
    Source(
        key="pharmaverseadam",
        repo="pharmaverse/pharmaverseadam",
        ref="main",
        keep=(
            "DESCRIPTION",
            "LICENSE.md",
            "data/*",
            "man/*",
            "inst/extdata/adams-specs.json",
        ),
        require=("inst/extdata/adams-specs.json",),
        data_glob="data/*.rda",
    ),
    Source(
        key="pharmaversesdtm",
        repo="pharmaverse/pharmaversesdtm",
        ref="main",
        keep=("DESCRIPTION", "LICENSE.md", "data/*", "man/*"),
        data_glob="data/*.rda",
    ),
)

# The CDISC pilot's updated submission packages, published inside phuse-scripts.
ARCHIVES = (
    Source(
        key="cdiscpilotsdtm",
        repo="phuse-org/phuse-scripts",
        ref="master",
        keep=("*.xpt", "define.xml"),
        require=("define.xml",),
        path="data/sdtm/cdiscpilot_update2.zip",
        data_glob="*.xpt",
    ),
    Source(
        key="cdiscpilotadam",
        repo="phuse-org/phuse-scripts",
        ref="master",
        keep=("*.xpt", "define.xml"),
        require=("define.xml",),
        path="data/adam/cdiscpilot_update1.zip",
        data_glob="*.xpt",
    ),
)

# Where every collection's files come from.
SOURCES: tuple[Source, ...] = (*REPOS, *ARCHIVES)


def url_for(source: Source) -> str:
    """Where one source's bundle is downloaded from."""
    if source.path:
        return f"https://github.com/{source.repo}/raw/{source.ref}/{source.path}"
    return f"https://github.com/{source.repo}/archive/{source.ref}.zip"


def out_dir(source: Source, source_dir: Path = SOURCE_DIR) -> Path:
    """The directory a source's files are written to."""
    return source_dir / source.key


def member_path(source: Source, member: str) -> str:
    """Where one bundle member belongs under the source's directory, or ``""``.

    Drops the bundle's top directory; rejects a path that could escape it.
    """
    _, _, rel = member.partition("/")
    if (
        not rel
        or rel.endswith("/")
        or rel.startswith("/")
        or "\\" in rel
        or ".." in rel.split("/")
    ):
        return ""
    name = rel.lower()
    kept = any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in source.keep)
    return rel if kept else ""


def _kept_members(
    source: Source, archive: zipfile.ZipFile
) -> list[tuple[str, zipfile.ZipInfo]]:
    """The (relative path, zip member) pairs a source keeps from *archive*."""
    kept: list[tuple[str, zipfile.ZipInfo]] = []
    for info in archive.infolist():
        rel = member_path(source, info.filename)
        if rel:
            kept.append((rel, info))
    return kept


def _require_present(source: Source, names: set[str]) -> None:
    """Raise when a member the export needs is missing from *names*."""
    lowered = {name.lower() for name in names}
    missing = [need for need in source.require if need.lower() not in lowered]
    if missing:
        msg = f"[{source.key}] the bundle holds no {', '.join(missing)}"
        raise SystemExit(msg)


def _write_kept(
    source: Source,
    archive: zipfile.ZipFile,
    kept: list[tuple[str, zipfile.ZipInfo]],
    source_dir: Path = SOURCE_DIR,
) -> None:
    """Replace *source*'s directory with *kept*, atomically via a sibling tmp."""
    destination = out_dir(source, source_dir)
    tmp = destination.with_name(destination.name + ".tmp")
    rmtree(tmp)
    for rel, info in kept:
        target = tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))
    rmtree(destination)
    # On Windows the directory entry may still be locked for a moment after
    # rmtree returns, so the atomic rename can fail with PermissionError.
    _retry(lambda: tmp.replace(destination), exceptions=PermissionError)


def extract(source: Source, bundle: bytes, source_dir: Path = SOURCE_DIR) -> list[str]:
    """Write one bundle's files, replacing the old fetch only once checked."""
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        kept = _kept_members(source, archive)
        if not kept:
            msg = f"[{source.key}] the bundle holds none of {', '.join(source.keep)}"
            raise SystemExit(msg)
        names = {rel for rel, _ in kept}
        _require_present(source, names)
        _write_kept(source, archive, kept, source_dir)
    return sorted(names)


def compute_source_hashes(
    source: Source, source_dir: Path = SOURCE_DIR
) -> dict[str, dict[str, str]]:
    """SHA-256 of every data file in a source's output directory.

    Returns a mapping ``dataset_name -> {"file": rel, "sha256": hex}`` where
    the dataset name is the data file's stem. Written alongside the source as
    ``_sources.json`` so the change detector can compare against the hashes
    stored in the shipped ``_collection.json``.
    """
    base = out_dir(source, source_dir)
    hashes: dict[str, dict[str, str]] = {}
    for path in sorted(base.glob(source.data_glob)):
        if path.is_file():
            rel = path.relative_to(base).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes[path.stem] = {"file": rel, "sha256": digest}
    return hashes


def fetch(source: Source, source_dir: Path = SOURCE_DIR) -> list[str]:
    """Download one source and write the files its collection is exported from."""
    url = url_for(source)
    print(f"[{source.key}] downloading {url}")
    try:
        # the URL is built from this script's own registry, and is https
        request = urllib.request.Request(
            url, headers={"User-Agent": "pharmadata-fetch/1.0"}
        )
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT) as response:
            bundle = response.read()
    except OSError as exc:
        msg = f"[{source.key}] cannot download {url}: {exc}"
        raise SystemExit(msg) from exc
    written = extract(source, bundle, source_dir)
    digest = hashlib.sha256(bundle).hexdigest()
    print(
        f"[{source.key}] {source.ref}: {len(written)} files, "
        f"sha256 {digest} -> {out_dir(source, source_dir).relative_to(PKG)}"
    )
    # Persist per-dataset source hashes for the change detector.
    hashes = compute_source_hashes(source, source_dir)
    (out_dir(source, source_dir) / "_sources.json").write_text(
        json.dumps(hashes, indent=1, ensure_ascii=False), encoding="utf-8", newline="\n"
    )
    return written


def main(source_dir: Path = SOURCE_DIR) -> None:
    """Fetch every source of ``SOURCES`` into ``data-raw/sources/``."""
    for source in SOURCES:
        fetch(source, source_dir)
    print(f"ok: {len(SOURCES)} sources in {source_dir.relative_to(PKG)}")


if __name__ == "__main__":
    main()
