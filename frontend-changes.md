# Code Quality Tooling — Changes

## Summary

This change set adds **black** as the canonical Python formatter and wires it
into two developer scripts. No frontend (HTML/CSS/JS) files were modified.

---

## Files Changed

### `pyproject.toml`
- Added `[dependency-groups]` section with `black>=24.0.0` as a dev dependency.
- Added `[tool.black]` configuration:
  - `line-length = 88` (black default)
  - `target-version = ["py311"]` (matches `requires-python`)

### `backend/*.py` and `backend/tests/*.py` (12 files reformatted)
All Python source files were reformatted by black for consistent style:
- Trailing whitespace removed from blank lines inside classes/functions.
- Two blank lines between top-level definitions (PEP 8).
- Aligned inline comments normalised (e.g. `= 800       #` → `= 800  #`).
- No logic changes — pure formatting only.

Files touched:
- `backend/app.py`
- `backend/ai_generator.py`
- `backend/config.py`
- `backend/document_processor.py`
- `backend/models.py`
- `backend/rag_system.py`
- `backend/search_tools.py`
- `backend/session_manager.py`
- `backend/vector_store.py`
- `backend/tests/test_ai_generator.py`
- `backend/tests/test_rag_system.py`
- `backend/tests/test_search_tools.py`

### `scripts/format.sh` *(new)*
Runs `uv run black backend/` to reformat all Python files in one command.

```bash
./scripts/format.sh
```

### `scripts/check_quality.sh` *(new)*
Runs black in `--check` mode (read-only, exits non-zero on failure).
Suitable for CI pipelines or pre-commit hooks.

```bash
./scripts/check_quality.sh
```

---

## Frontend files
No changes to `frontend/index.html`, `frontend/style.css`, or
`frontend/script.js`.
