# RAG 검색 방식 실험

이 실험 패키지는 기존 `starter-rag`와 별도 설치·실행 경로를 사용합니다. 기본 `SearchPort`, 운영 인덱스, 기존 `starter-rag search` 동작은 변경하지 않습니다.

## 고정 비교군 이름

V0=`dense`, V1=`current`, H1=`hybrid`는 복원된 검색 CLI의 모드입니다. **기존 G1은 Ollama 기반 경량 그래프 실험**이며 Microsoft GraphRAG 래퍼와 다른 방법입니다. G1에 기록된 기존 지표는 Ollama 경량 그래프에만 해당합니다.

기존 G1 코드는 `starter_rag_experiments/g1_ollama_light.py`, JSON Schema 재실행기는
`starter_rag_experiments/g1_jsonschema_runner.py`, Schema 원본은
`starter_rag_experiments/schemas/g1_graph_extraction.schema.json`입니다. 실행기 상수와 JSON 파일이
같은지 단위 테스트에서 비교합니다. Schema에는 JSON Schema Draft 식별자(`$schema`)가 선언돼 있지
않으며, 최종 원본처럼 Ollama `/api/chat`의 `format` 필드에 Schema 객체를 전달합니다.

과거 G1 평가는 일부 청크의 부분 그래프와 제한된 질문 집합을 사용한 로컬 파일럿이었습니다. 이 저장소에는 해당 평가 점수, 질문 추적, 코퍼스 또는 원시 로그가 포함되지 않습니다. 점수를 전체 코퍼스의 GraphRAG 성능이나 일반 검색 품질로 일반화하지 않으며 Microsoft GraphRAG 래퍼 결과와 혼합하지 않습니다.

### G1 실행 조건

Python 의존성은 표준 라이브러리만 사용합니다. 별도 로컬 Ollama 서버와 모델
`qwen3:4b-instruct`가 필요합니다. 첫 실행은 입력 ZIP과 새 결과 디렉터리를 지정합니다.

```bash
uv sync --project rag/experiments/search_methods
uv run --project rag/experiments/search_methods starter-rag-g1-ollama \
  /path/to/previous-results.zip --output /path/to/new-run
```

JSON Schema 재실행기는 호환되는 이전 실행 폴더와 비어 있는 새 출력 경로를 요구합니다. 원본처럼
저장된 성공 추출 캐시는 유지하고 실패 행을 다시 시도한 뒤 G1 답변·평가 산출물을 생성합니다.
전체 실행은 Ollama를 호출하고 로컬 산출물을 만들므로 실제 재실행 전에 데이터·모델·출력 경로를
검토해야 합니다.

```bash
uv run --project rag/experiments/search_methods starter-rag-g1-jsonschema-run \
  --source-run /path/to/prior-run --output-dir /path/to/new-run
```

회귀 검증은 합성 입력과 모의 Ollama 응답을 사용합니다. 공개용 스냅샷에는 실험 코퍼스, 모델 로그, 질문 추적 또는 평가 산출물이 없습니다. 사용자는 승인된 입력을 저장소 외부 경로에 두고 실행해야 합니다.

아래 `graph` 하위 명령은 별도로 추가된 **Microsoft GraphRAG Local/Global 래퍼**입니다. 이를 기존 G1로 부르거나 G1 성능 지표를 이 래퍼의 결과로 표시하지 않습니다. 래퍼가 만든 query-result envelope는 `starter-rag-graphrag-extract <query-result.json>`로 JSON Schema 검증 후 `response`를 추출할 수 있습니다. 이 파서는 응답 형식 검증 도구이며 기존 G1의 지표를 만들거나 변환하지 않습니다.

전체 데이터셋과 실험 산출물은 저장소에 포함하지 않습니다. 데이터 출처와 공개 조건은 [`../../../DATA_SOURCES.md`](../../../DATA_SOURCES.md)를 참고하세요.

## 설치 및 dense 비교

```bash
uv sync --project rag/experiments/search_methods
uv run --project rag/experiments/search_methods starter-rag-experiment search "질문" --method dense
uv run --project rag/experiments/search_methods starter-rag-experiment search "질문" --method current
uv run --project rag/experiments/search_methods starter-rag-experiment search "질문" --method hybrid
```

`dense`는 코사인 순위만, `current`는 현재 dense 후보 + 기존 재랭커, `hybrid`는 dense 상위 후보와 Okapi BM25 상위 후보를 RRF(`k=60`)로 합칩니다. 결과 JSON의 `rankTrace`는 각 후보의 구성 순위와 결합 점수를 남깁니다. BM25는 전체 게시 청크를 메모리에 올리므로 소규모 비교 코퍼스용입니다. 질문·본문 모두 NFC 정규화, casefold, 유니코드 단어/숫자 토큰화를 적용합니다.

`--top-k`와 `--candidates`는 1~10입니다. 모든 방식에 같은 값을 줍니다. `--collection-id`로 색인된 비교 코퍼스를 지정할 수 있습니다. 합성 자료는 격리된 collection에서만 `--allow-synthetic`을 사용합니다.

## Microsoft GraphRAG Local/Global 래퍼

GraphRAG 인덱싱은 Gemini 호출과 비용이 발생합니다. 별도 실행 폴더를 사용하고, 기본 키 이름은 `RAG_CHUNKING_GEMINI_API_KEY`입니다. 키 값은 파일에 기록하지 말고 실행 환경변수로 주입합니다. 현재 요청 범위에서는 실행하지 않습니다.

```bash
uv run --project rag/experiments/search_methods starter-rag-experiment graph init --root rag/experiments/runs/graph_demo
uv run --project rag/experiments/search_methods starter-rag-experiment graph prepare --root rag/experiments/runs/graph_demo --chunks rag/experiments/chunks.jsonl
uv run --project rag/experiments/search_methods starter-rag-experiment graph index --root rag/experiments/runs/graph_demo
uv run --project rag/experiments/search_methods starter-rag-experiment graph query --root rag/experiments/runs/graph_demo --method local --output rag/experiments/runs/graph_demo/local-results.jsonl "두 회사의 관계는 무엇인가?"
uv run --project rag/experiments/search_methods starter-rag-experiment graph query --root rag/experiments/runs/graph_demo --method global --output rag/experiments/runs/graph_demo/global-results.jsonl "자료 전반에서 반복되는 주제는 무엇인가?"
uv run --project rag/experiments/search_methods starter-rag-experiment graph provenance --root rag/experiments/runs/graph_demo
```

`graph prepare`는 `chunks.jsonl` 또는 `starter-rag chunk`의 JSON 결과를 읽어 `input/chunks.csv`, `source_manifest.jsonl`, `experiment_config.json`을 만듭니다. GraphRAG의 토크나이저 기준으로 청크 크기를 최대 기존 청크보다 1 크게 설정하고 overlap은 0으로 둡니다. `graph query --output`은 답변을 JSONL로 저장합니다. `graph provenance`는 GraphRAG의 `text_units`, entities, relationships, communities, community reports를 원본 `chunk_id`와 연결합니다. `chunkPreserved: false`이면 GraphRAG 재청킹 또는 텍스트 변경이 있었으므로 해당 실행을 동일 청크 대조군으로 취급하지 않습니다.

GraphRAG Local은 그래프와 원문 청크를 함께 사용하고, Global은 커뮤니티 보고서를 map-reduce로 검색합니다. 둘은 청크 순위 결과가 아니라 답변·근거 문맥 실험입니다. GraphRAG는 자체 엔티티/청크 임베딩을 생성하므로 EmbeddingGemma dense와 임베딩 동일성 비교군은 아닙니다. [GraphRAG Local/Global 설명](https://microsoft.github.io/graphrag/query/overview/)

## 실험 산출물

GraphRAG 입력, 설정, 인덱스와 provenance 파일은 지정한 run root 아래 저장합니다. 실험 코드는 서비스를 색인하거나 게시 상태를 변경하지 않습니다. 표준 검색 CLI는 `starter-rag search`로 계속 실행합니다.
