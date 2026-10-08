# Minimal type stubs for the pyarrow surface pharmadata and polars touch.
# pyarrow ships no stubs and no py.typed marker; these give the few symbols the
# codebase uses a real type instead of `Any`.

from collections.abc import Mapping, Sequence
from typing import Any

class DataType: ...

class Field:
    name: str
    type: DataType
    metadata: dict[bytes, bytes] | None

class Schema:
    metadata: dict[bytes, bytes] | None

    def field(self, i: str | int) -> Field: ...
    def __len__(self) -> int: ...
    def __iter__(self) -> Any: ...

class Array: ...
class ChunkedArray: ...
class RecordBatch: ...

class Table:
    schema: Schema
    num_rows: int
    num_columns: int
    columns: list[str]

    @classmethod
    def from_pylist(
        cls, mapping: Sequence[Mapping[str, Any]], **kwargs: Any
    ) -> Table: ...
    def select(self, columns: Sequence[str]) -> Table: ...
    def cast(self, target_schema: Schema, **kwargs: Any) -> Table: ...
    def to_pandas(self, *args: Any, **kwargs: Any) -> Any: ...

def table(
    data: Mapping[str, Sequence[Any]] | Mapping[str, Any], **kwargs: Any
) -> Table: ...
def field(
    name: str,
    type: DataType,
    *,
    metadata: Mapping[str, str] | Mapping[bytes, bytes] | None = None,
) -> Field: ...
def schema(
    fields: Sequence[Field] | Sequence[tuple[str, DataType]],
    *,
    metadata: Mapping[str, str] | Mapping[bytes, bytes] | None = None,
) -> Schema: ...
