<!-- 책임: [RAG] RAG 작업에 필요한 기준 문서를 연결한다.
구현할 기능: 패키지 경계·이름·공개 SearchPort 계약의 확인 순서를 안내한다.
완료 기준: RAG 개발자가 필요한 정본을 이 문서에서 찾는다. -->
# RAG 문서 시작점

1. [`ARCHITECTURE.md`](ARCHITECTURE.md): RAG 데이터 흐름과 운영 안전 경계.
2. [`PROJECT_STRUCTURE_GUIDE.md`](PROJECT_STRUCTURE_GUIDE.md): 패키지·테스트 파일 책임.
3. [`NAMING_CONVENTIONS.md`](NAMING_CONVENTIONS.md): Python 이름 규칙.
4. `rag/starter_rag/contracts/`: public DTOs and the `SearchPort` protocol.
5. [`../rag/README.md`](../rag/README.md): CLI 설치와 사용법.

The package contract describes the RAG boundary only; it does not define deployment or external service integration.
