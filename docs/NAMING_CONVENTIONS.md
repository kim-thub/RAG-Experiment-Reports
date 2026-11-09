<!-- 책임: [RAG] RAG Python 소스와 테스트의 이름 규칙을 정의한다.
구현할 기능: 모듈·함수·변수·클래스·Protocol 이름을 일관되게 유지한다.
완료 기준: 새 RAG 코드가 같은 규칙을 따른다. -->
# RAG 네이밍 규칙

- Python 파일·함수·변수·모듈은 PEP 8 `snake_case`를 사용한다. 모듈 파일명에 하이픈을 쓰지 않는다.
- 클래스·Protocol·예외 타입은 `PascalCase`를 사용한다.
- 상수는 `UPPER_SNAKE_CASE`를 사용한다.
- 테스트는 `tests/test_rag_<subject>.py` 형식을 우선한다. 공유 fixture는 `tests/rag_test_fixtures.py`에 둔다.
- 설정 환경변수는 `RAG_` 접두사를 사용한다. LLM 서비스의 환경변수 이름을 재사용하지 않는다.
- 데이터베이스 schema·table·column 이름은 `snake_case`를 사용한다. 스키마 변경은 승인 전에 만들지 않는다.
