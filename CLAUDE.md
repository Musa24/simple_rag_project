# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
# Install dependencies (first time or after pyproject.toml changes)
uv sync

# Start the server (from repo root)
./run.sh

# Or manually
cd backend && uv run uvicorn app:app --reload --port 8000
```

The server runs at `http://localhost:8000`. The frontend is served as static files from `/`. API docs at `/docs`.

## Environment

Requires a `.env` file at the repo root with:
```
ANTHROPIC_API_KEY=...
```

Python version is constrained to `>=3.11,<3.13` (see `pyproject.toml`). Always use `uv` to manage packages and run Python — never use `pip` or `python` directly. Use `uv add <package>` to add dependencies and `uv run <command>` to execute scripts.

## Architecture

This is a full-stack RAG chatbot. The **backend** (`backend/`) is a FastAPI app; the **frontend** (`frontend/`) is plain HTML/CSS/JS served as static files by the same FastAPI process. Course documents live in `docs/`.

### Request flow

1. User submits a query → `POST /api/query` (`app.py`)
2. `RAGSystem.query()` (`rag_system.py`) fetches session history, builds a prompt, and calls `AIGenerator`
3. `AIGenerator` makes a **first Claude API call** with `tool_choice: auto` and the `search_course_content` tool available
4. If Claude decides to search: `ToolManager` → `CourseSearchTool` → `VectorStore.search()` queries ChromaDB; results are returned to Claude in a **second API call** which synthesises the final answer
5. If Claude answers from general knowledge: the first call returns directly (no tool use)
6. Sources collected from `CourseSearchTool.last_sources` are returned to the frontend alongside the answer

### Key design decisions

- **Tool-based RAG**: retrieval is triggered by Claude itself via tool use, not unconditionally on every query. Claude skips the search for general knowledge questions.
- **Two ChromaDB collections**: `course_catalog` stores course-level metadata for fuzzy course-name resolution; `course_content` stores text chunks for semantic search. A query first resolves the course name via `course_catalog`, then filters `course_content`.
- **Session history is in-memory**: `SessionManager` stores sessions in a plain dict. Sessions are lost on server restart. History is injected into the Claude `system` prompt, not the `messages` array.
- **Startup ingestion with deduplication**: on startup, `app.py` calls `add_course_folder()`, which compares incoming course titles against existing ChromaDB IDs and skips already-indexed courses.

### Document format

Course `.txt` files in `docs/` must follow this structure for `DocumentProcessor` to parse them correctly:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <title>
Lesson Link: <url>
...lesson transcript...

Lesson 2: <title>
...
```

Chunking is sentence-aware (splits on `./?/!` before capitals) with `chunk_size=800` chars and `chunk_overlap=100` chars.

### Component responsibilities

| File | Responsibility |
|---|---|
| `backend/app.py` | FastAPI routes, startup ingestion, static file serving |
| `backend/rag_system.py` | Orchestrates all components; entry point for queries and document ingestion |
| `backend/ai_generator.py` | All Claude API calls; handles the tool-use two-pass flow |
| `backend/vector_store.py` | ChromaDB wrapper; course-name resolution + chunk retrieval |
| `backend/search_tools.py` | Anthropic tool definition + execution; source tracking |
| `backend/document_processor.py` | Parses course files, chunks text |
| `backend/session_manager.py` | In-memory conversation history |
| `backend/config.py` | Central config dataclass (model, chunk sizes, paths) |
