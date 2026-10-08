"""collection.py: install() wires helpers, lazy attributes and __dir__/__all__ onto a module."""

import sys
from types import ModuleType

import polars as pl
import pytest

from pharmadata._core import collection, data
from tests._helpers import COLLECTIONS

FUNCTIONS = collection.HELPER_FUNCTIONS

# One representative dataset per collection, named by the registry so the example
# and the collection cannot drift apart.
EXAMPLE = {name: spec.example for name, spec in data.COLLECTIONS.items()}


def test_each_collection_exposes_the_helpers() -> None:
    """Every collection module answers all documented helpers."""
    for module in COLLECTIONS.values():
        for name in FUNCTIONS:
            assert callable(getattr(module, name)), f"{module.__name__}.{name} missing"


def test_helpers_are_bound_to_their_own_module() -> None:
    """Each helper reports its own collection as __module__, so docs and reprs point home."""
    for module in COLLECTIONS.values():
        for name in FUNCTIONS:
            fn = getattr(module, name)
            assert fn.__module__ == module.__name__, (
                f"{module.__name__}.{name}.__module__ is {fn.__module__!r}"
            )
            assert fn.__qualname__ == name, (
                f"{module.__name__}.{name}.__qualname__ is {fn.__qualname__!r}"
            )


def test_helpers_are_separate_objects_per_collection() -> None:
    """No helper is shared between collections, so one collection cannot serve another's data."""
    modules = list(COLLECTIONS.values())
    for name in FUNCTIONS:
        helpers = [getattr(module, name) for module in modules]
        assert len({id(fn) for fn in helpers}) == len(modules), (
            f"{name} is shared between collections"
        )


def test_collections_are_distinct_modules() -> None:
    """The collections are separate modules, not one module aliased four times."""
    assert len({id(module) for module in COLLECTIONS.values()}) == len(COLLECTIONS)


def test_dir_lists_helpers_and_datasets() -> None:
    """dir() carries the helpers and every lazy dataset, so IPython completion finds them."""
    for module in COLLECTIONS.values():
        listing = dir(module)
        for fn in FUNCTIONS:
            assert fn in listing, f"{module.__name__}.{fn} missing from dir()"
        for name in module.list_datasets():
            assert name in listing, f"{module.__name__}.{name} missing from dir()"


def test_all_leads_with_the_helpers() -> None:
    """__all__ opens with the helpers, so the documented API comes first."""
    for module in COLLECTIONS.values():
        head = module.__all__[: len(collection.HELPER_FUNCTIONS)]
        assert head == list(collection.HELPER_FUNCTIONS)


def test_to_dict_serves_every_dataset_keyed_by_name() -> None:
    """to_dict() returns the whole collection at once, the frames the attributes serve."""
    for module in COLLECTIONS.values():
        frames = module.to_dict()
        assert set(frames) == set(module.list_datasets())
        assert all(isinstance(frame, pl.DataFrame) for frame in frames.values())
        # the same rows the lazy attribute serves, as an independent copy
        first = module.list_datasets()[0]
        assert frames[first].equals(getattr(module, first))


def test_helpers_delegate_to_the_right_collection() -> None:
    """A helper called on a collection reads that collection's metadata, not another's."""
    adam, sdtm = COLLECTIONS["pharmaverseadam"], COLLECTIONS["pharmaversesdtm"]
    pilot_adam = COLLECTIONS["cdiscpilotadam"]
    assert "STUDYID" in adam.meta("adsl").column_names_to_labels
    assert "USUBJID" in sdtm.meta("dm").column_names_to_labels
    assert adam.list_datasets() != sdtm.list_datasets()
    # the two pilot collections answer for their own data, not the pharmaverse one
    usubjid = pilot_adam.meta("adsl").column_names_to_labels["USUBJID"]
    assert usubjid == "Unique Subject Identifier"
    assert "adlbc" in pilot_adam.list_datasets()
    assert "lbch" in COLLECTIONS["cdiscpilotsdtm"].list_datasets()


def test_install_wires_datasets_onto_a_bare_module() -> None:
    """The install() call adds __getattr__/__dir__/__all__ to any module, so it is unit-testable."""
    module = ModuleType("pharmadata._test_collection")
    sys.modules[module.__name__] = module
    try:
        collection.install(module.__name__, data.COLLECTIONS["pharmaverseadam"])
        assert "adsl" in dir(module)
        assert isinstance(module.adsl, pl.DataFrame)
        with pytest.raises(AttributeError, match="has no dataset"):
            _ = module.not_a_dataset
    finally:
        del sys.modules[module.__name__]


def test_helpers_have_numpy_style_docstrings() -> None:
    """Public helpers document a Returns section and an Examples section; meta adds Parameters and Raises, and no Google-style marker survives."""
    for module in COLLECTIONS.values():
        for name in FUNCTIONS:
            doc = getattr(module, name).__doc__ or ""
            assert "Returns" in doc, f"{module.__name__}.{name} has no Returns section"
            assert "---" in doc, f"{module.__name__}.{name} has no Returns underline"
            assert "Examples" in doc, (
                f"{module.__name__}.{name} has no Examples section"
            )
            if name in ("meta",):
                assert "Parameters" in doc, (
                    f"{module.__name__}.{name} has no Parameters section"
                )
                assert "Raises" in doc, (
                    f"{module.__name__}.{name} has no Raises section"
                )
            for google in ("Args:", "Returns:", "Raises:", "Example:"):
                assert google not in doc, (
                    f"{module.__name__}.{name} still carries Google marker {google!r}"
                )


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_a_dataset_can_be_rebound_and_deleted(
    collection: str, module: ModuleType
) -> None:
    """A dataset is a normal module attribute now, not a frozen descriptor."""
    name = EXAMPLE[collection]
    module.__dict__[name] = "someone rebinds a dataset"
    try:
        assert getattr(module, name) == "someone rebinds a dataset"
    finally:
        del module.__dict__[name]
    # after the shadow is removed, the lazy lookup serves the real dataset again
    assert isinstance(getattr(module, name), pl.DataFrame)


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_a_served_frame_is_mutation_safe(collection: str, module: ModuleType) -> None:
    """Mutating a served frame never leaks into the next read of the dataset."""
    name = EXAMPLE[collection]
    frame = getattr(module, name)
    dropped = frame.columns[0]
    frame.drop_in_place(dropped)
    assert dropped not in frame.columns
    assert dropped in getattr(module, name).columns


def test_import_and_attribute_paths_agree() -> None:
    """A dataset imported by name serves the same rows the lazy attribute serves."""
    from pharmadata.pharmaverseadam import adsl as by_import

    assert by_import.equals(COLLECTIONS["pharmaverseadam"].adsl)


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_datasets_do_not_pollute_the_namespace(
    collection: str, module: ModuleType
) -> None:
    """Nothing is materialised until asked for, so globals stay small."""
    loaded = set(module.__dict__) & set(module.list_datasets())
    assert loaded == set(), f"datasets leaked into {collection}.__dict__: {loaded}"


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_missing_names_and_introspection_probes(
    collection: str, module: ModuleType
) -> None:
    """An unknown name raises with the dataset wording, and a dunder probe does not."""
    missing, dunder_probe = "not_a_dataset", "__wrapped__"
    with pytest.raises(AttributeError, match="has no dataset"):
        getattr(module, missing)
    # dunder probes must not answer with the dataset list (copy/pickle/IPython)
    with pytest.raises(AttributeError) as excinfo:
        getattr(module, dunder_probe)
    assert "has no dataset" not in str(excinfo.value)


@pytest.mark.parametrize("collection,module", COLLECTIONS.items())
def test_completion_lists_datasets(collection: str, module: ModuleType) -> None:
    """Every dataset a collection serves appears in dir(), so completion can offer it."""
    names = module.list_datasets()
    listing = dir(module)
    for name in names:
        assert name in listing, f"{collection}.{name} missing from dir()"
