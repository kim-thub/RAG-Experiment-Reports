<!-- 책임: [RAG] RAG 독립 저장소의 파일 배치와 소유권을 안내한다.
구현할 기능: 패키지·평가 fixture·테스트·문서의 책임을 표시한다.
완료 기준: 새 코드를 기존 RAG 경계에 배치한다. -->
# RAG 프로젝트 구조

| 경로 | 책임 |
|---|---|
| `rag/starter_rag/contracts/` | 공개 DTO와 `SearchPort` Protocol |
| `rag/starter_rag/embedding/` | 고정 EmbeddingGemma 2 모델 adapter |
| `rag/starter_rag/ingestion/` | 파싱, 청킹, 검수, 색인 서비스 |
| `rag/starter_rag/retrieval/` | 게시 자료 검색과 출력 |
| `rag/starter_rag/storage/` | PostgreSQL·pgvector 저장 및 publication 상태 |
| `rag/starter_rag/evaluation/` | 오프라인 평가 로직 |
| `rag/evaluation/` | 합성 평가 fixture와 사용자 로컬 평가 입력; 비공개 입력은 커밋하지 않음 |
| `backend/migrations/` | 로컬 RAG DB용 Alembic migration만 보관. Backend 앱은 두지 않음 |
| `tests/` | RAG 패키지 단위·통합 테스트 |
| `scripts/` | RAG 모델 파일 패키징 보조 도구 |

RAG 외부 소비자는 공개 contracts만 사용한다. 원본 자료와 생성 결과는 로컬 경로에 두며 커밋하지 않는다. 상세 사용법은 [`../rag/README.md`](../rag/README.md)를 본다.
