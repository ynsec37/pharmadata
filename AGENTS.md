# AGENTS.md

You shape every contribution to this project that meets these standards:

- Verify, don't assume: every change is run through the relevant check; never ship
  hypothetically correct code.
- modern, idiomatic, concise R and Python code
- end-to-end type-safety and test coverage
- thoughtful, tasteful, consistent API design
- delightful developer experience
- comprehensive well-written documentation
- code comments stay relevant to the current code, and concise.
- no abstractions that weren't explicitly requested.
- no new dependency if it can be avoided.
- write the minimum code that works.

## Development strategy

- Small batch, fast feedback: for docs/page edits, check one page first (`make pages-min`),
  then run the full `make docs-build` last.

## Quick setup

```bash
make setup                   # uv sync --all-groups --all-extras
make hooks                   # uv run pre-commit install: the CI checks on each commit
```

- Python 3.14 (committed `.python-version`) and R 4.5.1 via `rig` (matches `renv.lock`).
- R and Quarto are only needed to re-export data or render pages; great-docs runs Quarto
  internally, so `make docs-build` handles `.qmd` files.

## Development commands

```bash
make check               # ruff, typos, types, pytest: CI's gate
make data-check          # validate raw inputs and the generated assets
make docs-build          # great-docs build, what CI runs
make help                # every target, with what it does
uv run pytest tests/docs/test_docs_site.py -q    # one file
uv run pytest -k adsl -q                         # one test by name
```

- `make` works from Git Bash, cmd and PowerShell on Windows
- `make check` must not modify a file. If it wants to, run `make fix` and read the diff.
- Tests mirror the tree their subject lives in: `tests/data_raw/` for build programs,
  `tests/docs/` for site pages and viewer assets. Those two need a checkout, so they are
  marked `build` and `docs`; `pytest -m "not build and not docs"` is the sdist subset.
- Docstring examples in `src/` run as doctests, and the coverage gate fails under 90%
  (`make coverage`).
- A test pins one contract and its docstring names that contract, not the function's name.
- Clear the caches of `@cache`-decorated functions before and after each test; they leak
  state across tests.

## Contribution flow

- Work on a feature branch off `main`; open a PR even for small changes.
- CI must be green (lint, types, test matrix, coverage, docs build) before review.
- One PR, one concern; keep commits focused; squash on merge.
- Public API is anything importable from `pharmadata` that does not start with `_`;
  `_core` is internal. Breaking changes need a `docs/changelog.md` entry.

## Python conventions

- `ruff` checks and formats the code; `mypy` and `pyrefly` type-check it.
- NumPy docstrings: great-docs renders them into the auto-generated API reference.
- Annotate every signature. `mypy` and `pyrefly` cover `src/` and `data-raw/`;
  `tests/` is held to the same rule by ruff's `ANN`.
- No bare `Any`. Optional dependencies are annotated under `if TYPE_CHECKING:`, as the
  pandas backend is.
- polars is the primary dataframe library; pandas appears only behind the backend switch.
  A missing value is `null`, never an empty string.
- Build Arrow tables with `pa.table(dict-of-columns)`, not row-wise appends.
- A public function never shares its module's name (import collision).
- Derived values (counts, examples) are properties or lookups, not stored fields.

## R conventions

- tidyverse style
- Each `02_*.R` defines `export_<collection>`; the driver's `PROGRAMS` must cover every
  collection in `data.COLLECTIONS`.
- `air` formats (`make r-format`, checked by `make r-check`, settings in `air.toml`) and
  `jarl` lints (`make r-lint`). Install both once: `uv tool install air-formatter` and
  `uv tool install jarl-linter`. They are standalone binaries, absent from `renv.lock`
  and from CI, so run the two targets locally before touching a `.R` file.

## Data and generated files

```text
data-raw/01_fetch_sources.py  -> data-raw/sources/  (the only network step)
data-raw/02_export_data.R     -> data-raw/raw/      (driver; one 02_*.R per collection)
data-raw/03_build_data.py     -> shipped data, stubs, docs/reference/
data-raw/04_build_modules.py  -> src/pharmadata/<collection>/__init__.py and .pyi stub
data-raw/05_build_dataset_qmd.py -> docs/datasets/*.qmd (make pages, last in data-build)
```

- `make refresh` = fetch (`01`) + export (`02`) + data-build (`03`/`04`/`05`); `make data-build`
  reruns only the three build steps (what `03_build_data.py` / `data-raw/raw/` edits need).
  A `.qmd` edit is rendered by `make docs-build`.
- Never hand-edit a file carrying `do not edit`: `docs/reference/**`,
  `src/pharmadata/_data/**`, and the `.pyi` stubs. Change the source, then regenerate.
- `docs/changelog.md` is the release record, hand-written; there is no root `CHANGELOG.md`.
- The site is built by great-docs (`great-docs.yml`). It auto-generates the navigation,
  the API reference from docstrings, and renders `.qmd` pages internally.
- Two lockfiles, both committed: `uv.lock` for Python, `renv.lock` for the R library.
- Build scripts (`01`/`03`/`04`/`05`) accept dependencies as parameters, so tests can inject them.

## Commits

- `make check` before committing; `make data-check` if any data or page changed.
- Conventional Commits: `type(scope): subject` (e.g. `fix(data): ...`, `docs(site): ...`).
- Commit only when a human asks.
- Comments, docstrings and commit messages in concise English, spelled by `typos`;
  text we do not own is excluded or allow-listed in `pyproject.toml`.

## Documentation site

- great-docs is the build engine (`great-docs.yml`). It auto-generates the navigation
  and API reference; only add custom assets (CSS/JS) via `include_in_header` when the
  auto-generated output is insufficient.
- Theme colours (accent, navbar) live in `great-docs.yml` under `theme`.
