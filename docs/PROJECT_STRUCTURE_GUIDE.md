<!-- 책임: [실험 도구] 실행 코드·보고서·평가 fixture·문서의 파일 배치와 소유권을 안내한다.
구현할 기능: RAG 패키지, 실험 보고서, 테스트와 보관 자료의 책임을 표시한다.
완료 기준: 새 코드와 결과를 해당 경계에 배치하고 과거 기록을 현행 기준과 구분한다. -->
# RAG 실험 저장소 구조

| 경로 | 책임 |
|---|---|
| `rag/starter_rag/contracts/` | 공개 DTO와 `SearchPort` Protocol |
| `rag/starter_rag/embedding/` | 고정 EmbeddingGemma 2 모델 adapter |
| `rag/starter_rag/ingestion/` | 파싱, 청킹, 검수, 색인 서비스 |
| `rag/starter_rag/retrieval/` | 게시 자료 검색과 출력 |
| `rag/starter_rag/storage/` | PostgreSQL·pgvector 저장 및 publication 상태 |
| `rag/starter_rag/evaluation/` | 오프라인 평가 로직 |
| `rag/evaluation/` | 합성 평가 fixture와 사용자 로컬 평가 입력; 비공개 입력은 커밋하지 않음 |
| `rag/experiments/search_methods/` | 검색 방법 실험 도구와 보고서 |
| `rag/experiments/search_methods/EXPERIMENT_REPORT.md` | 실험 질문·방법·해석을 담은 대표 보고서 |
| `rag/experiments/search_methods/RESULTS.md` | 집계 지표·사례·공개 범위와 한계 |
| `rag/experiments/search_methods/RESTORATION_STATUS.md` | 코드 복원과 재실행 여부의 구분 |
| `docs/EXPERIMENT_REPORTING.md` | 실험 보고서의 근거·재현성·공개 기준 |
| `backend/migrations/` | 로컬 RAG DB용 Alembic migration만 보관. Backend 앱은 두지 않음 |
| `tests/` | RAG 패키지 단위·통합 테스트 |
| `scripts/` | RAG 모델 파일 패키징 보조 도구 |

RAG 외부 소비자는 공개 contracts만 사용한다. 원본 자료와 생성 결과는 로컬 경로에 두며 커밋하지 않는다. 보고서 안내는 [`README.md`](README.md), 상세 실행법은 [`../rag/README.md`](../rag/README.md)를 본다.
