"""Metadata of one dataset: the ``DatasetMeta`` value object."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, ClassVar, Literal

import pyarrow as pa

from pharmadata._core import data, output_format

if TYPE_CHECKING:
    import pandas as pd
    import polars as pl


@dataclass(frozen=True, slots=True)
class DatasetMeta:
    """Metadata of one dataset, in the style of pyreadstat's metadata object.

    A read-only view: the field names and parallel-tuple layout follow
    pyreadstat, extended with the CDISC dimensions (``structure``,
    ``mandatory``, ``role``). The data itself is reached through the module
    attribute of the same name (e.g. ``pharmaverseadam.adsl``).

    Attributes
    ----------
    dataset : str
        The dataset name, e.g. ``"adsl"``.
    collection : str
        The collection it belongs to, e.g. ``"pharmaverseadam"``.
    file_label : str or None
        The dataset label, equivalent to a SAS dataset label.
    structure : str or None
        The CDISC structure, e.g. ``"One record per subject"``; None when the
        source specifications do not provide one.
    number_rows : int
        Row count, read from the parquet footer without loading any data.
    number_columns : int
        Column count, i.e. ``len(column_names)``.
    column_names : tuple of str
        The column names, in column order.
    column_labels : tuple of str or None
        The column labels, parallel to ``column_names``.
    column_types : tuple of str or None
        The column types, parallel to ``column_names``.
    column_mandatory : tuple of str or None
        The CDISC mandatory flags, parallel to ``column_names``.
    column_roles : tuple of str or None
        The CDISC roles, parallel to ``column_names``.
    file_format : str
        Always ``"parquet"``, the storage format of every dataset.
    file_encoding : str
        Always ``"utf-8"``: the encoding of the shipped parquet data, not of
        the original source file.

    Examples
    --------
    >>> meta = pharmaverseadam.meta("adsl")
    >>> meta.dataset
    'adsl'
    >>> meta.file_label
    'Subject Level Analysis'
    >>> meta.column_names_to_labels["STUDYID"]
    'Study Identifier'
    >>> (meta.number_rows, meta.number_columns)
    (306, 55)
    """

    dataset: str
    collection: str
    file_label: str | None
    structure: str | None
    number_rows: int
    column_names: tuple[str, ...]
    column_labels: tuple[str | None, ...]
    column_types: tuple[str | None, ...]
    column_mandatory: tuple[str | None, ...]
    column_roles: tuple[str | None, ...]

    file_format: ClassVar[Literal["parquet"]] = "parquet"
    file_encoding: ClassVar[Literal["utf-8"]] = "utf-8"

    def __repr__(self) -> str:
        """One line: which dataset, and how big."""
        return (
            f"DatasetMeta({self.collection}.{self.dataset}, "
            f"{self.number_rows} rows x {self.number_columns} columns)"
        )

    @property
    def number_columns(self) -> int:
        """Column count, i.e. ``len(column_names)``."""
        return len(self.column_names)

    @property
    def column_names_to_labels(self) -> dict[str, str | None]:
        """The column names mapped to their labels, in column order.

        Returns
        -------
        dict[str, str or None]
            A dict mapping each column name to its CDISC label.

        Examples
        --------
        >>> pharmaverseadam.adsl_meta.column_names_to_labels["AGE"]
        'Age'
        """
        return dict(zip(self.column_names, self.column_labels, strict=True))

    @property
    def specs(self) -> pa.Table | pl.DataFrame | pd.DataFrame:
        """Column-level specifications of the dataset, in the active format.

        Returns
        -------
        pa.Table or pl.DataFrame or pd.DataFrame
            One row per variable with the columns ``variable, label, type,
            mandatory, role`` (mandatory/role are null when the source
            specifications do not provide them). The frame is served in the
            active output format, like the dataset attributes.

        Examples
        --------
        >>> pharmaverseadam.adsl_meta.specs.columns
        ['variable', 'label', 'type', 'mandatory', 'role']
        """
        table = pa.table(
            {
                "variable": self.column_names,
                "label": self.column_labels,
                "type": self.column_types,
                "mandatory": self.column_mandatory,
                "role": self.column_roles,
            }
        )
        return data.to_output(table, output_format.get_output_format())


@cache
def build(collection: str, name: str) -> DatasetMeta:
    """The DatasetMeta of one dataset, built once and shared process-wide."""
    entry = data._meta_entry(collection, name)
    n_rows, _ = data.shape(collection, name)
    columns = entry["columns"]
    return DatasetMeta(
        dataset=name,
        collection=collection,
        file_label=entry.get("label"),
        structure=entry.get("structure"),
        number_rows=n_rows,
        column_names=tuple(columns),
        column_labels=tuple(info.get("label") for info in columns.values()),
        column_types=tuple(info.get("type") for info in columns.values()),
        column_mandatory=tuple(info.get("mandatory") for info in columns.values()),
        column_roles=tuple(info.get("role") for info in columns.values()),
    )
