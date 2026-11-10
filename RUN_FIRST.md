# 먼저 읽기

이 저장소는 RAG 검색 실험의 결과와 한계를 보고합니다. 데이터나 DB를 준비하기 전에 아래 문서부터 확인하세요.

1. [실험 보고서](rag/experiments/search_methods/EXPERIMENT_REPORT.md): 비교한 방법, 평가 범위와 요약.
2. [집계 결과와 한계](rag/experiments/search_methods/RESULTS.md): 지표, 사례, 재현 및 공개 범위.
3. [실험 보고 기준](docs/EXPERIMENT_REPORTING.md): 측정 결과를 읽고 기록하는 기준.

## 도구 개발 환경

Python 3.13과 `uv`를 준비한 뒤 저장소 루트에서 실행합니다.

```bash
uv sync --locked
uv run starter-rag status
uv run starter-rag --help
```

이 명령들은 CLI 상태와 도움말을 확인합니다. PostgreSQL/pgvector, 모델 가중치와 Ollama는 별도로 준비해야 하며 자동 설치되지 않습니다. 테스트는 합성 fixture를 기본으로 사용합니다.

문서 파싱·색인·게시·검색의 상세 절차와 로컬 DB 제한은 [RAG CLI 안내서](rag/README.md)를 따릅니다. 색인·게시·DB 변경이나 전체 검색 실험은 승인된 대상과 명시적 요청이 있을 때만 실행합니다.
