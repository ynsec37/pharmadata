"""Interactive dataset viewer for pharmadata."""
import marimo

app = marimo.App()


@app.cell(hide_code=True)
def _():
    import marimo as mo

    # In WASM the package is not pre-installed; fetch the wheel served
    # alongside this notebook and install it with micropip.
    import sys

    if sys.platform == "emscripten":
        import gzip
        import io
        import zipfile

        import micropip  # type: ignore[import-not-found]
        from js import URL as js_URL  # type: ignore[import-not-found]
        from js import fetch as js_fetch  # type: ignore[import-not-found]
        from js import location as js_location  # type: ignore[import-not-found]

        # In iframe (html-wasm) mode this notebook runs inside a standalone HTML
        # page at <site-root>/notebooks/<stem>/index.html, so location is a real
        # URL — unlike islands mode where the Pyodide worker runs from a blob:
        # URL. The wheel sits one directory up, next to the notebooks.
        wheel_url = str(
            js_URL.new("../pharmadata-0.0.0-py3-none-any.whl", js_location.href)
        )

        # GitHub Pages serves the wheel with Content-Encoding: gzip. Fetch it
        # directly with js.fetch and decompress if the body is still compressed.
        js_resp = await js_fetch(wheel_url)  # noqa: F704
        wheel_bytes = (await js_resp.arrayBuffer()).to_bytes()
        if wheel_bytes[:2] == b"\x1f\x8b":
            wheel_bytes = gzip.decompress(wheel_bytes)
        if not zipfile.is_zipfile(io.BytesIO(wheel_bytes)):
            raise RuntimeError(
                f"pharmadata wheel is not a valid zip (status={js_resp.status})"
            )

        wheel_path = "/tmp/pharmadata-0.0.0-py3-none-any.whl"
        with open(wheel_path, "wb") as f:
            f.write(wheel_bytes)
        await micropip.install(f"file://{wheel_path}")  # noqa: F704
        # zoneinfo needs the IANA tz database; Pyodide ships it as the "tzdata"
        # package, which must be loaded before any tz-aware datetime is touched.
        await micropip.install("tzdata")  # noqa: F704
    from pharmadata import cdiscpilotadam, cdiscpilotsdtm, pharmaverseadam, pharmaversesdtm

    COLLECTIONS = [pharmaverseadam, pharmaversesdtm, cdiscpilotadam, cdiscpilotsdtm]
    return COLLECTIONS


@app.cell(hide_code=True)
def _():
    # In marimo islands the table's Markdown and Parquet exports do not work:
    # the Markdown download button is disabled and Parquet needs a kernel-side
    # writer. Hide both rows so only the functional CSV/TSV/JSON options show.
    mo.md(
        "<style>"
        "[data-testid='export-row-markdown'],"
        "[data-testid='export-row-parquet']"
        "{display:none!important}"
        "</style>"
    )


@app.cell(hide_code=True)
def _(COLLECTIONS):
    # Build "<collection>_<dataset>" keys for every dataset, matching the
    # naming the shipped parquet files use.
    entries: list[tuple[str, object, str]] = []
    for _coll in COLLECTIONS:
        _cname = _coll.__name__.rsplit(".", 1)[-1]
        for _name in _coll.list_datasets():
            entries.append((f"{_cname}_{_name}", _coll, _name))
    options = {key.replace("_", " / ", 1): key for key, _, _ in entries}
    lookup = {key: (coll, name) for key, coll, name in entries}
    dataset = mo.ui.dropdown(options=options, value=next(iter(options)), label="Dataset")
    nrows = mo.ui.slider(5, 100, value=20, step=5, label="Rows")
    mo.hstack([dataset, nrows], justify="start")


@app.cell(hide_code=True)
def _(dataset, lookup):
    import polars as pl

    selected = dataset.value if hasattr(dataset, "value") else dataset
    collection, name = lookup[selected]
    df = pl.DataFrame(getattr(collection, name))
    columns = mo.ui.multiselect(
        options=df.columns,
        value=df.columns[: min(8, len(df.columns))],
        label="Columns",
    )
    columns


@app.cell(hide_code=True)
def _(dataset, nrows, columns, df):
    sel = dataset.value if hasattr(dataset, "value") else dataset
    n = nrows.value if hasattr(nrows, "value") else nrows
    cols = columns.value if hasattr(columns, "value") else columns
    cols = list(cols) if cols else []
    mo.ui.table(df.select(cols).head(n), selection=None, label=sel)


if __name__ == "__main__":
    app.run()
