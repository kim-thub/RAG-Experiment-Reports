<!-- 책임: [RAG] 독립 패키지의 데이터 흐름과 운영 경계를 안내한다.
구현할 기능: 파싱·청킹·임베딩·게시·검색 흐름과 금지 의존성을 설명한다.
완료 기준: RAG 코드 경계와 데이터 안전 규칙을 한 문서에서 확인한다. -->
# RAG 아키텍처

`rag/starter_rag/`는 독립 Python 패키지이며 `starter-rag` CLI와 `SearchPort` 구현을 제공한다. Backend나 LLM 패키지를 import하지 않는다.

## 데이터 흐름

```mermaid
flowchart LR
    I[사용자 제공 자료] --> P[Docling Parser]
    P --> C[청킹·사람 검수]
    C --> E[EmbeddingGemma 2 · 768d]
    E --> V[(PostgreSQL + pgvector)]
    Q[검색 질의] --> E
    E --> V
    V --> S[게시 자료만 반환]
```

- Parsing, indexing, publishing, DB initialization are explicit CLI actions. Application startup never performs them.
- Search returns only published material. Law text must not be embedded or stored in the vector index.
- Local integration uses a dedicated local database. Production Supabase changes require separate approval; no automatic schema migration is run.
- Input data, review files, raw logs, credentials, and database URLs stay outside version control.

## Source map

See [`PROJECT_STRUCTURE_GUIDE.md`](PROJECT_STRUCTURE_GUIDE.md) for module ownership. The public package contracts are defined in `rag/starter_rag/contracts/` and do not depend on the former multi-service workspace.
