"""Context-local output format for dataset attributes.

Each thread and asyncio task carries its own format, so a switch never leaks.
Re-exported by the top-level package; the state lives here to avoid an import
cycle.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Literal, get_args

if TYPE_CHECKING:
    from collections.abc import Generator

OutputFormat = Literal["arrow", "polars", "pandas"]

_output_format: ContextVar[OutputFormat] = ContextVar(
    "pharmadata_output_format", default="polars"
)


def get_output_format() -> OutputFormat:
    """Return the current dataset output format.

    Context-local: the one set in this thread or asyncio task, or the default
    ``"polars"``.

    Returns
    -------
    OutputFormat
        ``"arrow"``, ``"polars"`` (the default) or ``"pandas"``.

    Examples
    --------
    >>> pharmadata.get_output_format()
    'polars'
    """
    return _output_format.get()


def set_output_arrow() -> None:
    """Return datasets and metadata as pyarrow Tables for the current context.

    This is the zero-copy format: the shipped parquet is read into an
    immutable ``pyarrow.Table``, which is what the ``"arrow"`` output hands
    back directly.

    Notes
    -----
    Context-local: applies only to the current thread or asyncio task.

    Examples
    --------
    >>> pharmadata.set_output_arrow()
    >>> tbl = pharmadata.pharmaverseadam.adsl
    >>> type(tbl).__module__.split(".")[0]
    'pyarrow'
    >>> pharmadata.set_output_polars()  # restore the default
    """
    _output_format.set("arrow")


def set_output_polars() -> None:
    """Return dataset attributes as polars DataFrames for the current context.

    This is the default output format. Call :func:`set_output_pandas` to switch.

    Notes
    -----
    Context-local: applies only to the current thread or asyncio task.

    Examples
    --------
    >>> pharmadata.set_output_pandas()
    >>> df = pharmadata.pharmaverseadam.adsl
    >>> type(df).__module__.split(".")[0]
    'pandas'
    >>> pharmadata.set_output_polars()
    >>> pharmadata.get_output_format()
    'polars'
    """
    _output_format.set("polars")


def set_output_pandas() -> None:
    """Return dataset attributes as pandas DataFrames for the current context.

    See :func:`set_output_polars` for the context-locality notes.

    Examples
    --------
    >>> pharmadata.set_output_pandas()
    >>> df = pharmadata.pharmaverseadam.adsl
    >>> type(df).__module__.split(".")[0]
    'pandas'
    >>> pharmadata.set_output_polars()  # restore the default
    """
    _output_format.set("pandas")


@contextmanager
def use_output_format(name: OutputFormat) -> Generator[None, None, None]:
    """Use *name* as the dataset output format for a ``with`` block.

    The previous format is restored on exit, including when the block raises.
    The switch is context-local.

    Parameters
    ----------
    name : OutputFormat
        The format to use inside the block: ``"arrow"``, ``"polars"`` or
        ``"pandas"``.

    Raises
    ------
    ValueError
        If *name* is not ``"arrow"``, ``"polars"`` or ``"pandas"``.

    Examples
    --------
    >>> with pharmadata.output_format("pandas"):
    ...     df = pharmadata.pharmaverseadam.adsl
    ...     type(df).__module__.split(".")[0]
    'pandas'
    >>> pharmadata.get_output_format()  # restored on exit
    'polars'
    """
    formats = get_args(OutputFormat)
    if name not in formats:
        spelled = ", ".join(repr(fmt) for fmt in formats)
        msg = f"output format must be one of {spelled}, got {name!r}"
        raise ValueError(msg)
    token = _output_format.set(name)
    try:
        yield
    finally:
        _output_format.reset(token)
