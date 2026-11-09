# Starter RAG

`rag/starter_rag/` is the source package for a standalone RAG CLI and public `SearchPort` implementation. This repository is dedicated to RAG. `backend/` contains only an optional Alembic migration for a local RAG database; it has no application or Supabase code.

## Install

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
uv run starter-rag status
uv run starter-rag --help
```

The default workspace install includes the `ingestion` extra for Docling parsing and review.

## Tests

```bash
uv run pytest tests
```

Tests use synthetic fixtures by default. PostgreSQL/pgvector integration tests require explicit local configuration and do not initialize production databases.

## Runtime requirements

The package does not install PostgreSQL, pgvector, Ollama, or model weights. EmbeddingGemma 2 is pinned in `rag/starter_rag/embedding/model.py`; model files must be available locally. RAG settings use `RAG_*` environment variables. See the [RAG CLI guide](rag/README.md).

Parsing, indexing, and publication happen only when explicitly requested. Search returns published sources only. Do not vectorize statutory text.

## Repository map

- `rag/starter_rag/`: RAG package and CLI.
- `rag/evaluation/`: local evaluation fixtures; only the clearly synthetic ranking fixture is included.
- `tests/`: RAG package tests.
- `backend/migrations/`: local-only RAG schema migration.
- `DATA_SOURCES.md`: dataset sources, license labels, and publication cautions.
