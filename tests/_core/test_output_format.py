"""The output_format module: the context-local switch and its context manager."""

import threading

import polars as pl
import pytest

from pharmadata import get_output_format, output_format, set_output_pandas
from pharmadata import pharmaverseadam as adam


def test_default_output_is_polars() -> None:
    """An untouched process serves polars frames; pyarrow reads, polars is default."""
    assert get_output_format() == "polars"
    assert isinstance(adam.adsl, pl.DataFrame)


def test_output_format_context_manager_switches_and_restores() -> None:
    """The with-statement form selects inside and restores the previous format."""
    assert get_output_format() == "polars"
    with output_format("pandas"):
        assert get_output_format() == "pandas"
    assert get_output_format() == "polars"


def test_output_format_context_manager_restores_after_an_error() -> None:
    """A raised exception still restores the previous format on the way out."""
    boom = "boom"
    with output_format("pandas"):
        assert get_output_format() == "pandas"
        with pytest.raises(RuntimeError, match=boom):
            raise RuntimeError(boom)
    assert get_output_format() == "polars"


def test_output_format_rejects_unknown_names() -> None:
    """Only the three known formats are accepted; a typo fails loudly."""
    with (
        pytest.raises(ValueError, match="must be one of 'arrow', 'polars', 'pandas'"),
        output_format("numpy"),
    ):
        pass  # pragma: no cover


def test_output_is_context_local() -> None:
    """A thread's output switch stays in its own context; the caller keeps theirs."""
    seen: list[str] = []

    def switch() -> None:
        set_output_pandas()
        seen.append(get_output_format())

    with output_format("polars"):
        thread = threading.Thread(target=switch)
        thread.start()
        thread.join()
        assert seen == ["pandas"]
        assert get_output_format() == "polars"


def test_a_bare_thread_starts_from_the_default_backend() -> None:
    """A threading.Thread does not copy contextvars: it reads the default backend."""
    seen: list[str] = []

    with output_format("pandas"):
        thread = threading.Thread(target=lambda: seen.append(get_output_format()))
        thread.start()
        thread.join()
        assert seen == ["polars"]
