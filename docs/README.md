# 문서 안내

이 저장소의 현행 문서는 실험 보고서와 RAG 실험 도구를 설명합니다. 결과를 먼저 확인하고, 코드를 실행할 때는 해당 보고서와 데이터 사용 조건을 함께 읽으세요.

## 실험 보고서

- [검색 방식 실험 보고서](../rag/experiments/search_methods/EXPERIMENT_REPORT.md): 실험 질문, 비교 방법, 평가 범위와 해석.
- [검색 결과와 한계](../rag/experiments/search_methods/RESULTS.md): 집계 지표, 사례 차이, 공개 범위.
- [검색 실험 실행 안내](../rag/experiments/search_methods/README.md): 검색 방식 도구와 GraphRAG 래퍼의 구분 및 실행 절차.
- [구현 복원 상태](../rag/experiments/search_methods/RESTORATION_STATUS.md): 복원된 코드와 실행하지 않은 실험의 구분.
- [실험 보고 기준](EXPERIMENT_REPORTING.md): 결과를 기록하고 공개할 때 지킬 기준.
- [데이터 출처 및 사용 조건](../DATA_SOURCES.md): 사용 자료의 출처와 공개 전 확인 사항.

## 실행 도구와 계약

- [RAG 아키텍처](ARCHITECTURE.md): 실험 도구의 데이터 흐름과 운영 경계.
- [프로젝트 구조](PROJECT_STRUCTURE_GUIDE.md): 실행 도구, 보고서, 테스트의 위치와 책임.
- [네이밍 규칙](NAMING_CONVENTIONS.md): 코드 식별자와 실험 표기 규칙.
- `rag/starter_rag/contracts/`: 현재 공개 `SearchPort`와 DTO의 코드 정본.
- [RAG CLI 안내서](../rag/README.md): 설치와 명시적 CLI 실행법.

