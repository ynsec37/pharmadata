# Cross-platform Makefile (Git Bash, cmd, PowerShell). `make` lists targets.

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# TRAE sandbox cannot write to the system temp dir, so tools fall back to .tmp.
export TMPDIR := .tmp
export TMP    := .tmp
export TEMP   := .tmp

# Normalize CURDIR to forward slashes (Windows uses backslashes).
CURDIR_POSIX := $(subst \,/,$(CURDIR))

# venv Python for reticulate/quarto (great-docs' embedded interpreter lacks polars).
ifeq ($(OS),Windows_NT)
  VENV_PYTHON := $(CURDIR_POSIX)/.venv/Scripts/python.exe
else
  VENV_PYTHON := $(CURDIR_POSIX)/.venv/bin/python
endif

# Absolute temp for docs: R graphics and Quarto Deno need a non-relative path.
DOCS_TMP := $(CURDIR_POSIX)/.tmp

# ---------------------------------------------------------------------------
# Setup & install
# ---------------------------------------------------------------------------
.PHONY: setup install install-system dist hooks

setup:          ## Install dev tools, docs deps and the package
	uv sync --all-groups --all-extras

install:        ## Build and install (non-editable) into the current env
	uv pip install .

# --system avoids replacing the .venv editable install.
install-system: ## Install into the system interpreter, leaving .venv alone
	uv pip install --system .

dist: clean     ## Build sdist and wheel into dist/
	uv build

hooks:          ## Install pre-commit hooks
	uv run pre-commit install

# ---------------------------------------------------------------------------
# Data pipeline
#   01_fetch -> 02_export (R) -> 03_build -> 04_build_modules -> 05_pages
# ---------------------------------------------------------------------------
.PHONY: fetch export data-build data-check build_modules pages pages-min refresh

fetch: .tmp       ## Fetch upstream files (the only network step)
	uv run python data-raw/01_fetch_sources.py

export:           ## Re-export parquet into data-raw/raw/ (needs R)
	Rscript data-raw/02_export_data.R

data-build: .tmp  ## Repackage data, regenerate modules, stubs and docs pages
	uv run python data-raw/03_build_data.py
	uv run python data-raw/04_build_modules.py
	uv run python data-raw/05_build_dataset_qmd.py

data-check: .tmp  ## Validate raw inputs
	uv run python data-raw/03_build_data.py --check

build_modules: .tmp  ## Regenerate collection modules and stubs (04_build_modules)
	uv run python data-raw/04_build_modules.py

pages: .tmp       ## Regenerate dataset index and per-dataset pages
	uv run python data-raw/05_build_dataset_qmd.py

pages-min: .tmp   ## Regenerate at most N datasets per collection (default 2)
	uv run python data-raw/05_build_dataset_qmd.py --limit $(or $(ARGS),2)

refresh: fetch export data-build  ## Full pipeline refresh

# ---------------------------------------------------------------------------
# R toolchain (supports the export step of the data pipeline)
# ---------------------------------------------------------------------------
.PHONY: r-lock r-restore r-export r-test r-check r-lint r-format

# renv lives in the user library; prepend renv/library so snapshot sees both.
r-lock: export R_LIBS := $(CURDIR_POSIX)/renv/library
r-lock:           ## Re-record renv.lock from the R library
	Rscript data-raw/renv_lock.R

r-restore: .tmp    ## Install renv.lock into renv/library
	@uv run python -c "import os; os.makedirs('renv/library', exist_ok=True)"
	Rscript -e "renv::restore(lockfile = 'renv.lock', library = 'renv/library', prompt = FALSE)"

r-export: export R_LIBS := $(CURDIR_POSIX)/renv/library
r-export: r-restore  ## Re-export collections from the locked library
	Rscript data-raw/02_export_data.R

r-test: export R_LIBS := $(CURDIR_POSIX)/renv/library
r-test: r-restore  ## Run export-stage testthat suite
	Rscript data-raw/tests/testthat.R

# air and jarl are standalone binaries, not R packages (not in renv.lock).
r-check:          ## Check R formatting (needs air binary)
	air format --check data-raw

r-lint:           ## Lint R sources (needs jarl binary)
	jarl check data-raw

r-format:         ## Format R sources (needs air binary)
	air format data-raw

# ---------------------------------------------------------------------------
# Quality gate
# ---------------------------------------------------------------------------
.PHONY: check fix fix-and-check test coverage

check: .tmp     ## CI gate: format, lint, spelling, types, tests (no file changes)
	uv run ruff format --check .
	uv run ruff check .
	uv run typos
	uv run mypy
	uv run pyrefly check
	uv run pytest

fix: .tmp       ## Auto-fix formatting, lint and spelling
	uv run ruff format .
	uv run ruff check . --fix
	uv run typos --write-changes

fix-and-check: fix check

test: .tmp      ## Run tests; pass args via ARGS, e.g. make test ARGS="-k adsl"
	uv run pytest $(ARGS)

coverage: .tmp  ## Run tests with the 90% coverage gate
	uv run pytest --cov --cov-report=term-missing --cov-fail-under=90

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------
.PHONY: site docs docs-serve docs-build docs-min docs-build-min notebook-wheel notebook-build

site: data-build docs-build  ## Build data, then the docs site

# Docs targets share env vars: absolute temp, R library, venv Python.
docs docs%: export TEMP := $(DOCS_TMP)
docs docs%: export TMP := $(DOCS_TMP)
docs docs%: export TMPDIR := $(DOCS_TMP)
docs docs%: export R_LIBS_USER := $(CURDIR_POSIX)/renv/library
docs docs%: export RETICULATE_PYTHON := $(VENV_PYTHON)
docs docs%: export QUARTO_PYTHON := $(VENV_PYTHON)

docs: data-build notebook-wheel  ## Regenerate data, then serve the site
	uv run great-docs preview

docs-serve: .tmp  ## Serve already-generated pages
	uv run great-docs preview

docs-build: notebook-wheel  ## Build the docs site
	@uv run python -c "import shutil,pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ('docs/_quarto','docs/_site')]"
	uv run great-docs build

# Temporarily drop docs/datasets to only N pages, then restore the full set so
# the working tree stays clean. Run `make pages` manually if preview/build
# exits with an error before reaching the restore step.
docs-min: notebook-wheel .tmp  ## Serve with at most N datasets per collection (default 2)
	@uv run python -c "import shutil,pathlib;[shutil.rmtree(p) if p.is_dir() else p.unlink() for p in pathlib.Path('docs/datasets').iterdir()]"
	uv run python data-raw/05_build_dataset_qmd.py --limit $(or $(ARGS),2)
	uv run great-docs preview
	$(MAKE) pages

docs-build-min: notebook-wheel .tmp  ## Build with at most N datasets per collection (default 2)
	@uv run python -c "import shutil,pathlib;[shutil.rmtree(p) if p.is_dir() else p.unlink() for p in pathlib.Path('docs/datasets').iterdir()]"
	uv run python data-raw/05_build_dataset_qmd.py --limit $(or $(ARGS),2)
	uv run great-docs build
	$(MAKE) pages

# The WASM notebook installs the package wheel via micropip; fixed name keeps
# the notebook source version-agnostic.
notebook-wheel: .tmp  ## Build the wheel for the WASM notebook viewer
	uv build
	@uv run python -c "import shutil,glob; shutil.copy(glob.glob('dist/pharmadata-*.whl')[0], 'docs/notebooks/pharmadata-0.0.0-py3-none-any.whl')"

notebook-build: notebook-wheel  ## Alias for notebook-wheel

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------
.PHONY: help clean

help:  ## Show available targets
	@uv run python -c "import re,sys; [print(f'  {m.group(1):<14} {m.group(2)}') for m in (re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*):.*## (.*)', l) for l in sys.stdin) if m]" < $(MAKEFILE_LIST)

clean: ## Remove build, docs, test and render artifacts
	@uv run python -c "import shutil,glob,os; \
	[shutil.rmtree(p) for p in ['_site','great-docs','docs/_site','docs/_quarto','docs/.cache','dist','htmlcov','.pytest_cache','.ruff_cache','.mypy_cache','.tmp'] if os.path.isdir(p)]; \
	[os.remove(p) if os.path.isfile(p) else shutil.rmtree(p) for g in ['.coverage','.coverage.*','tmp/quarto_*','docs/notebooks/*.whl'] for p in glob.glob(g)]"

# mkdir (no -p) works under sh, cmd and PowerShell.
.tmp:
	@$(if $(wildcard .tmp),,mkdir .tmp)
