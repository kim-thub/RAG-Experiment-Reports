from __future__ import annotations

import pytest
from starter_rag_experiments.graphrag_json_schema import extract_graphrag_response


def test_extract_graphrag_response_accepts_valid_graph_result() -> None:
    assert (
        extract_graphrag_response(
            {"method": "local", "query": "relationship?", "response": "Answer."}
        )
        == "Answer."
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"method": "other", "query": "question", "response": "answer"},
        {"method": "local", "query": "", "response": "answer"},
        {"method": "global", "query": "question"},
        {"method": "local", "query": "question", "response": "answer", "extra": True},
        [],
    ],
)
def test_extract_graphrag_response_rejects_invalid_graph_result(payload: object) -> None:
    with pytest.raises(ValueError, match="invalid GraphRAG result"):
        extract_graphrag_response(payload)
