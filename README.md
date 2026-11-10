# RAG Experiment Reports

이 저장소는 RAG 검색 방식의 실험을 기록하고, 평가 결과와 한계를 보고서로 공개합니다. 현재 대표 산출물은 [검색 방식 실험 보고서](rag/experiments/search_methods/EXPERIMENT_REPORT.md)와 [집계 결과](rag/experiments/search_methods/RESULTS.md)입니다.

저장소의 코드는 보고서와 실험을 위한 도구입니다. `rag/starter_rag/`는 독립 RAG CLI와 공개 `SearchPort` 구현을 제공하며, 이 저장소를 운영 서비스나 배포용 제품으로 정의하지 않습니다. 패키지와 CLI의 `starter-rag` 이름은 유지되는 내부 기술 이름입니다.

## 먼저 읽기

1. [실험 보고서](rag/experiments/search_methods/EXPERIMENT_REPORT.md): 질문, 비교 조건, 지표와 해석.
2. [검색 결과와 한계](rag/experiments/search_methods/RESULTS.md): 집계 수치, 비교 사례, 공개 범위.
3. [실험 보고 기준](docs/EXPERIMENT_REPORTING.md): 재현 가능성, 결과 기록, 개인정보·출처 원칙.
4. [데이터 출처 및 사용 조건](DATA_SOURCES.md): 실험 자료 출처와 공개 전 확인 사항.

## 도구 실행

Python 3.13과 [`uv`](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync --locked
uv run starter-rag status
uv run starter-rag --help
```

이 명령은 상태와 도움말을 표시합니다. PostgreSQL/pgvector, Ollama, 모델 가중치는 별도로 준비해야 하며 자동 설치되지 않습니다. 문서 파싱·색인·게시·검색 실행 방법은 [RAG CLI 안내서](rag/README.md)를 따릅니다. 실험을 재실행하기 전에는 입력 자료와 대상이 승인됐는지 확인하세요.

## 공개 범위와 안전

- 공개 보고서에는 집계 결과와 필요한 범위의 해석만 기록합니다. 원본 코퍼스, 비공개 부록, 질문 전문, 전체 추적과 원시 모델 로그는 저장소에 포함하지 않습니다.
- 출처를 기록했다고 해서 데이터나 미디어의 재배포 권한이 자동으로 확인되는 것은 아닙니다.
- 색인·게시·DB 변경, 운영 연결, 전체 검색 실험과 배포는 명시적 요청과 승인된 대상 없이 실행하지 않습니다.
