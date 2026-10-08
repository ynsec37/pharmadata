"""The package __init__: top-level re-exports and __all__."""

import pharmadata
from pharmadata import get_output_format, set_output_pandas, set_output_polars


def test_top_level_exports_are_available() -> None:
    """The output switchers are re-exported at the top level, not only in a submodule."""
    assert set_output_polars is pharmadata.set_output_polars
    assert set_output_pandas is pharmadata.set_output_pandas
    assert get_output_format is pharmadata.get_output_format
    assert {
        "set_output_polars",
        "set_output_pandas",
        "get_output_format",
    } <= set(pharmadata.__all__)
