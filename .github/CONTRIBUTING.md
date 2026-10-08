# Contributing

Thank you for your interest in improving pharmadata! Contributions of any
kind are welcome - bug reports, documentation fixes, new datasets, and code
contributions alike. If you're unsure where to start, please open an issue
and we'll be glad to help you get going.

## Setup

- [uv](https://docs.astral.sh/uv/)
- [rig](https://rig.r-lib.org/)
- [Quarto](https://github.com/quarto-dev/quarto-cli)

```bash
uv sync --all-groups --all-extras
```

## Other tools

```bash
uv tool install air-formatter    # R formatter
uv tool install jarl-linter      # R linter
```

## Pre-commit hooks

```bash
uv run pre-commit install
```

## Data workflow

```bash
make refresh       # fetch sources -> export with R -> build data, stubs, docs
```

## Check

```bash
make check         # ruff format --check, ruff, typos, mypy, pyrefly, pytest
```

## Lint

```bash
make fix           # ruff format, ruff --fix, typos --write-changes
```

## Test

```bash
make test          # uv run pytest; make test ARGS="-k adsl"
```

## Doc

```bash
make docs-build   # build site
make docs-serve   # serve the already-generated site
```
