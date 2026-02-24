# Frontend Changes — Dark/Light Theme Toggle

## Summary

Added a dark/light theme toggle button to allow users to switch between the existing dark theme and a new light theme. The preference is persisted in `localStorage`.

---

## Files Modified

### `frontend/style.css`

1. **New CSS variables in `:root`** — Added variables for source chip link colours (`--chip-link-*`), code block background (`--code-bg`), and toggle button appearance (`--toggle-bg`, `--toggle-color`).

2. **Light theme override block** (`body[data-theme="light"]`) — Defines a full light-mode palette:
   - `--background: #f8fafc` / `--surface: #ffffff` — light backgrounds
   - `--text-primary: #0f172a` / `--text-secondary: #64748b` — dark text for contrast
   - `--border-color: #e2e8f0` — subtle borders
   - Adjusted source chip, code block, and toggle colours for light mode

3. **Theme transitions** — Added `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease` to a targeted set of elements (`body`, `.sidebar`, `.chat-container`, `.message-content`, `#chatInput`, `.source-chip`, etc.) for smooth theme switching.

4. **Source chip colours converted to CSS variables** — Replaced hardcoded hex values (`#1e293b`, `#60a5fa`, `#0f2040`, etc.) in `.source-chip`, `a.source-chip`, and `a.source-chip:hover` with `var(--chip-link-*)` references so they update correctly in both themes.

5. **Code block background converted to CSS variable** — `rgba(0, 0, 0, 0.2)` in `.message-content code` and `.message-content pre` replaced with `var(--code-bg)` (light theme uses `rgba(0, 0, 0, 0.06)`).

6. **Theme toggle button styles** (`.theme-toggle`) — Fixed-position circular button (40 × 40 px, top-right corner, `z-index: 1000`) with hover scale and focus ring. Sun/moon icon visibility is controlled by `body[data-theme="light"]` selectors.

---

### `frontend/index.html`

- **Theme toggle button** added just before `</body>`:
  - Moon SVG icon (visible in dark mode)
  - Sun SVG icon (visible in light mode)
  - `aria-label="Toggle light/dark theme"` and `title="Toggle theme"` for accessibility
- Cache-buster version bumped from `v=9` → `v=10` on both `style.css` and `script.js` links.

---

### `frontend/script.js`

- **`initThemeToggle()` function** — called inside `DOMContentLoaded`:
  - On load: reads `localStorage.getItem('theme')` and applies `data-theme="light"` to `document.body` if saved.
  - On button click: toggles `data-theme` attribute on `document.body` between `"light"` (set) and dark (attribute removed), then persists choice to `localStorage`.

---

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
