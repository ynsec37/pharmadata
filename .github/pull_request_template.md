## What and why

Describe the change and the problem it solves. Link any related issue (`Closes #`).

## Checklist

- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run mypy` passes
- [ ] `uv run pytest` passes (add tests for new behaviour)
- [ ] Generated files (`docs/`, `_data/`, `.pyi`, nav) were regenerated with
      `uv run python data-raw/03_build_data.py`, not edited by hand
- [ ] `docs/changelog.md` updated where the change is user-facing
- [ ] Comments, docstrings and commit messages are in concise English
