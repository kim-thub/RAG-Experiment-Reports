# 검색 실험 도구 복원 상태

이 문서는 구현 복원과 실험 재실행 여부를 구분합니다. 결과 해석은 [실험 보고서](EXPERIMENT_REPORT.md)와 [집계 결과](RESULTS.md)를 기준으로 합니다.

기존 Ollama 경량 G1 구현과 최종 JSON Schema를 별도 보관된 실험 원본과 대조해 전용 모듈로 이관했습니다.
Microsoft GraphRAG 래퍼 파일은 수정하지 않았습니다.

| 실험 표기 | 복원된 구현 | 확인 범위 |
|---|---|---|
| V0 | `dense` 검색 | 코드 복원; 검색 실험은 재실행하지 않음 |
| V1 | `current` 검색 | 코드 복원; 검색 실험은 재실행하지 않음 |
| H1 | `hybrid` 검색 | 코드 복원; 검색 실험은 재실행하지 않음 |
| G1 | Ollama 기반 경량 그래프; `starter_rag_experiments/g1_ollama_light.py` | 코드·회귀 테스트 이관; 전체 실험은 재실행하지 않음 |

최종 JSON Schema 코드는 `starter_rag_experiments/g1_jsonschema_runner.py`, 저장 Schema는
`starter_rag_experiments/schemas/g1_graph_extraction.schema.json`입니다. 단위 테스트는 실행 코드의
내장 Schema와 JSON 파일이 일치하는지 검사합니다. 원본 Schema에는 `$schema` Draft 선언이 없습니다.

Microsoft GraphRAG Local/Global은 `graph_rag.py`와 `graph` CLI가 제공하는 별도 래퍼입니다. 기존
G1과 알고리즘·실행 조건이 다릅니다. 이 저장소에는 G1 평가 점수·질문 추적·원시 로그가 포함되지 않습니다. 기존 파일럿 평가 범위는 부분 그래프와 제한된 질문 집합이었으므로, 과거 지표를 전체 코퍼스 성능이나 일반 검색 품질로 일반화하지 않습니다. G1은 Microsoft GraphRAG Local/Global 래퍼와 별도 구현입니다.

G1은 로컬 Ollama와 `qwen3:4b-instruct`를 실행 전제로 하며, Python 외부 패키지에 추가 의존하지
않습니다. 회귀 테스트는 합성 입력과 모의 응답만 사용해 Schema 전달·응답 검증·최대 두 차례 시도·검색
경로를 확인합니다. 실험 입력 코퍼스, 로그 및 평가 산출물은 이 공개용 스냅샷에 포함하지 않습니다. 기존 실패 응답 두 건을
수정하거나 재생성하지 않았고 전체 검색·품질 실험도 실행하지 않았습니다.

데이터셋·결과 경로는 `.gitignore`에서 제외됩니다. 전체 검증 결과는 과거 평가 점수를 재검증한
것으로 간주하지 않습니다.
