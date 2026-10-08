"""Access CDISC ADaM and SDTM test datasets in Python for clinical programming."""

import importlib
import importlib.metadata as _metadata

from pharmadata._core.data import COLLECTIONS as _COLLECTIONS
from pharmadata._core.meta import DatasetMeta
from pharmadata._core.output_format import (
    get_output_format,
    set_output_arrow,
    set_output_pandas,
    set_output_polars,
)
from pharmadata._core.output_format import (
    use_output_format as output_format,
)

# The version lives in pyproject.toml
try:
    __version__ = _metadata.version("pharmadata")
except (
    _metadata.PackageNotFoundError
):  # pragma: no cover - only in an unpacked source tree
    __version__ = "0.0.0"

# Import every discovered collection so ``pharmadata.<name>`` resolves. The set
# comes from ``_data``, not a hardcoded list, so a new collection appears here
# without an edit.
for _name in _COLLECTIONS:
    globals()[_name] = importlib.import_module(f"pharmadata.{_name}")

__all__ = [
    "DatasetMeta",
    "__version__",
    "get_output_format",
    "output_format",
    "set_output_arrow",
    "set_output_pandas",
    "set_output_polars",
    *sorted(_COLLECTIONS),
]
