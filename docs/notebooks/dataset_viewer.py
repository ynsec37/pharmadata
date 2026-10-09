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
        import micropip  # type: ignore[import-not-found]
        from js import location as js_location  # type: ignore[import-not-found]
        from pyodide.http import pyfetch  # type: ignore[import-not-found]

        # Dependencies with C extensions are provided as Pyodide packages;
        # tzdata is pure-python. Install them before unpacking the wheel.
        await micropip.install(["polars", "pyarrow", "tzdata"])  # noqa: F704

        # marimo's html-wasm export runs Pyodide inside a blob: Web Worker, so
        # location.href is a blob URL and location.origin is all we know. The
        # wheel lives at <site-root>/notebooks/pharmadata-0.0.0-py3-none-any.whl;
        # try the likely site-root paths against the worker's origin and keep the
        # first that serves the wheel.
        origin = str(js_location.origin)
        wheel_name = "pharmadata-0.0.0-py3-none-any.whl"
        candidates = [
            f"{origin}/pharmadata/notebooks/{wheel_name}",
            f"{origin}/notebooks/{wheel_name}",
        ]
        resp = None
        for candidate in candidates:
            resp = await pyfetch(candidate)  # noqa: F704
            if resp.status == 200:
                break
        if resp is None or resp.status != 200:
            raise RuntimeError(f"pharmadata wheel not found (tried {candidates})")

        # unpack_archive() unzips the wheel directly from the JS ArrayBuffer,
        # bypassing Python bytes conversion which corrupts large (>few MB)
        # buffers. Then add the unpacked dir to sys.path so imports resolve.
        import sys as _sys

        pkg_dir = "/tmp/pharmadata_pkg"
        await resp.unpack_archive(extract_dir=pkg_dir)  # noqa: F704
        _sys.path.insert(0, pkg_dir)
    from pharmadata import cdiscpilotadam, cdiscpilotsdtm, pharmaverseadam, pharmaversesdtm

    COLLECTIONS = [pharmaverseadam, pharmaversesdtm, cdiscpilotadam, cdiscpilotsdtm]
    return COLLECTIONS


@app.cell(hide_code=True)
def _():
    # In marimo islands the table's Markdown and Parquet exports do not work:
    # the Markdown download button is disabled and Parquet needs a kernel-side
    # writer. Hide both rows so only the functional CSV/TSV/JSON options show.
    # The Visualize/Explore toolbar buttons are hidden site-wide by
    # docs/assets/gd-marimo-toolbar.js, which injects CSS into the table's
    # shadow DOM (light-DOM CSS cannot reach it).
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
    nrows = mo.ui.slider(5, 100, value=10, step=5, label="Rows")
    mo.hstack([dataset, nrows], justify="start")


@app.cell(hide_code=True)
def _(dataset, lookup):
    import polars as pl

    selected = dataset.value if hasattr(dataset, "value") else dataset
    collection, name = lookup[selected]
    df = pl.DataFrame(getattr(collection, name))
    columns = mo.ui.multiselect(
        options=df.columns,
        value=df.columns[: min(10, len(df.columns))],
        label="Columns",
    )
    columns


@app.cell(hide_code=True)
def _(dataset, nrows, columns, df):
    sel = dataset.value if hasattr(dataset, "value") else dataset
    n = nrows.value if hasattr(nrows, "value") else nrows
    cols = columns.value if hasattr(columns, "value") else columns
    cols = list(cols) if cols else []
    # show_search=False hides the search box so the table's top-right toolbar
    # only keeps its native Columns and Export buttons.
    mo.ui.table(df.select(cols).head(n), selection=None, label=sel, show_search=False)


if __name__ == "__main__":
    app.run()
