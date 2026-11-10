<!-- 책임: [실험 도구] RAG 실행 도구의 데이터 흐름과 안전 경계를 안내한다.
구현할 기능: 파싱·청킹·임베딩·게시·검색 흐름과 금지 의존성을 설명한다.
완료 기준: 실험 실행 도구의 코드 경계와 데이터 안전 규칙을 한 문서에서 확인한다. -->
# RAG 실험 도구 아키텍처

`rag/starter_rag/`는 보고서 작성과 승인된 재현을 지원하는 독립 Python 도구다. `starter-rag` CLI와 공개 `SearchPort` 구현을 제공하며 Backend나 별도 LLM 서비스 패키지를 import하지 않는다. 저장소의 목적과 현행 보고서는 [문서 안내](README.md)에서 확인한다.

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

- 파싱·색인·게시·DB 초기화는 CLI에서 명시적으로 요청한 경우에만 수행한다. 앱 시작 시 자동으로 실행하지 않는다.
- 검색은 게시된 자료만 반환한다. 법령 원문을 임베딩하거나 벡터 인덱스에 저장하지 않는다.
- 통합 확인에는 전용 로컬 데이터베이스를 사용한다. 운영 DB 변경은 별도 승인이 필요하며 자동 스키마 마이그레이션은 실행하지 않는다.
- 입력 자료, 검수 파일, 원시 로그, 자격정보와 DB URL은 버전 관리에 포함하지 않는다.

## 모듈 안내

See [`PROJECT_STRUCTURE_GUIDE.md`](PROJECT_STRUCTURE_GUIDE.md) for module ownership. The public package contracts are defined in `rag/starter_rag/contracts/`; the archived multi-service interface document is not the current package contract.
