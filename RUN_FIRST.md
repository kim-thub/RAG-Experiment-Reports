# RAG 개발 환경

Python 3.13과 `uv`를 준비한 뒤 저장소 루트에서 실행합니다.

```bash
uv sync --locked
uv run starter-rag status
uv run pytest tests
```

문서 파싱·청킹·검수 CLI는 기본 설치에 포함된 `ingestion` extra를 사용합니다. PostgreSQL/pgvector, EmbeddingGemma 가중치, Ollama는 별도로 준비해야 하며 자동 설치되지 않습니다.

색인, 게시, 검색 실행 방법과 로컬 데이터베이스 제한은 [`rag/README.md`](rag/README.md)를 따릅니다. 운영 DB에 `db-init`을 실행하지 마세요.

로컬 pgvector가 설치되어 있고 migration 방식으로 스키마를 만들려면 `RAG_DATABASE_URL`을 로컬 `starter_rag_integration` DB로 설정한 뒤 다음 명령을 실행합니다.

```bash
uv run alembic -c backend/alembic.ini upgrade head
```

기존 `starter-rag db-init`도 같은 로컬 `rag_test.chunks` 스키마를 준비합니다. 두 방식을 동시에 실행할 필요는 없습니다.
