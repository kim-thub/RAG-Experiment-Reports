<!-- 책임: [실험 도구] RAG 도구와 공개 SearchPort 계약의 기준 문서를 연결한다.
구현할 기능: 실험 보고서, 패키지 경계, 이름, 공개 계약을 확인할 순서를 안내한다.
완료 기준: 보고서 독자와 도구 개발자가 필요한 현행 문서를 이 문서에서 찾는다. -->
# 실험 도구와 계약 문서 시작점

1. [`EXPERIMENT_REPORTING.md`](EXPERIMENT_REPORTING.md): 실험 결과와 한계를 기록하는 기준.
2. [`../rag/experiments/search_methods/EXPERIMENT_REPORT.md`](../rag/experiments/search_methods/EXPERIMENT_REPORT.md): 현재 검색 실험 보고서.
3. [`ARCHITECTURE.md`](ARCHITECTURE.md): RAG 실행 도구의 데이터 흐름과 안전 경계.
4. [`PROJECT_STRUCTURE_GUIDE.md`](PROJECT_STRUCTURE_GUIDE.md): 실행 도구·보고서·테스트의 책임.
5. `rag/starter_rag/contracts/`: 현재 공개 DTO와 `SearchPort` Protocol. 설치·CLI 사용법은 [`../rag/README.md`](../rag/README.md)를 본다.

패키지 계약은 RAG 검색 경계만 정의하며 제품 배포나 외부 서비스 통합을 정의하지 않는다.
