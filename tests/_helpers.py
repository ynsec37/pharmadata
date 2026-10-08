"""Shared helpers for the pharmadata test suite."""

import importlib
import importlib.util
import json
import re
import sys
from functools import cache
from importlib import resources
from pathlib import Path
from types import ModuleType

from pharmadata._core import data as registry

# Collection modules keyed by name, built from the package registry.
COLLECTIONS = {
    name: importlib.import_module(f"pharmadata.{name}") for name in registry.COLLECTIONS
}

# Repository root (tests/ and docs/ are siblings under it).
ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# great-docs section source dirs under docs/.
DATASETS = DOCS / "datasets"
RESOURCES = DOCS / "resources"
GUIDES = DOCS / "user_guide"


def dataset_page(collection: str, name: str) -> Path:
    """Resolve a dataset page path, honouring the numeric sidebar-order prefix.

    The build script writes pages under ``docs/datasets/<NN-collection>/`` so
    great-docs keeps the intended sidebar order; the prefix is stripped from
    the published URL.
    """
    gen = source_script("05_build_dataset_qmd")
    return DATASETS / gen._collection_dir(collection) / f"{name}.qmd"


def build_script() -> ModuleType:
    """Import data-raw/03_build_data.py, which is a build script, not package code."""
    return source_script("03_build_data")


@cache
def source_script(name: str) -> ModuleType:
    """Import a data-raw/ script by path, once per session.

    *name* is the file stem (e.g. ``"01_fetch_sources"``); the leading numeric
    prefix is stripped for module registration since Python identifiers cannot
    start with a digit.
    """
    path = ROOT / "data-raw" / f"{name}.py"
    module_name = re.sub(r"^\d+_", "", name)
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    # registered before execution because @dataclass resolves cls.__module__ here
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def meta_json(collection: str) -> dict:
    """Raw dataset metadata of a collection, straight from the shipped _meta.json."""
    path = resources.files("pharmadata") / "_data" / collection / "_meta.json"
    return json.loads(path.read_text(encoding="utf-8"))
