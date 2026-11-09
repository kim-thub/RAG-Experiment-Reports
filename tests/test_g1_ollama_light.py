from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Self
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "rag" / "experiments" / "search_methods"
sys.path.insert(0, str(EXPERIMENTS))

from starter_rag_experiments import g1_ollama_light as g1


class TestGraph(unittest.TestCase):
    def test_graph_traversal_and_trace(self) -> None:
        c1, c2, c3 = "sha256:aaa", "sha256:bbb", "sha256:ccc"
        byid = {
            chunk_id: {
                "chunk_id": chunk_id,
                "source_id": "sample.md",
                "text": text,
                "element_ids": ["e1"],
                "version": "v1",
                "location_statuses": ["unverified"],
            }
            for chunk_id, text in (
                (c1, "Example Corporation debt in 2022"),
                (c2, "Example bonds mature in March 2023"),
                (c3, "Unrelated sample content"),
            )
        }
        rows = [
            {
                "chunk_id": c1,
                "source_id": "sample.md",
                "entities": [
                    {"name": "Example", "type": "org"},
                    {"name": "debt", "type": "concept"},
                ],
                "relations": [{"source": "Example", "target": "debt", "relation": "has"}],
            },
            {
                "chunk_id": c2,
                "source_id": "sample.md",
                "entities": [
                    {"name": "debt", "type": "concept"},
                    {"name": "March 2023", "type": "date"},
                ],
                "relations": [
                    {"source": "debt", "target": "March 2023", "relation": "matures"}
                ],
            },
        ]
        entities, adjacency, _ = g1.construct_index(rows)
        ranking, _ = g1.graph_search(
            {"question": "When was Example debt due?"},
            {"V1": [c1, c3], "H1": [c1, c3]},
            entities,
            adjacency,
            byid,
            {c1, c2},
            top_k=10,
        )
        ranked_ids = [row["chunk_id"] for row in ranking]
        self.assertIn(c2, ranked_ids)
        self.assertTrue(
            any(trace["kind"] == "graph" for trace in ranking[ranked_ids.index(c2)]["trace"])
        )
        items, context = g1.context_for(ranking, byid)
        self.assertIn("CHUNK=", context)
        self.assertEqual(items[0]["chunk_text_full"], byid[items[0]["chunk_id"]]["text"])

    def test_metrics(self) -> None:
        questions = [
            {
                "id": "q1",
                "mapping_status": "mapped",
                "answerability_in_md": True,
                "gold_chunk_ids": ["b"],
            }
        ]
        records = [
            {
                "question_id": "q1",
                "method": "G1",
                "retrieved_chunks": [{"chunk_id": "a"}, {"chunk_id": "b"}],
            }
        ]
        self.assertEqual(g1.metric(records, questions)["G1"]["hit@3"], 1.0)

    def test_bundle_integrity_with_synthetic_fixture(self) -> None:
        chunks = [
            {"chunk_id": "a", "source_id": "sample.md", "text": "alpha"},
            {"chunk_id": "b", "source_id": "sample.md", "text": "beta"},
        ]
        questions = [{"id": "q1", "question": "sample"}]
        search = [{"query_id": "q1", "ranked_chunk_ids": ["b"]}]

        with tempfile.TemporaryDirectory() as temp_dir:
            bundle_path = Path(temp_dir) / "synthetic.zip"
            with zipfile.ZipFile(bundle_path, "w") as archive:
                for name, rows in (
                    ("chunks.jsonl", chunks),
                    ("questions_with_chunk_mapping.jsonl", questions),
                    ("search_results_silver.jsonl", search),
                ):
                    payload = "".join(json.dumps(row) + "\n" for row in rows)
                    archive.writestr(g1.PREFIX + name, payload)

            _, loaded_chunks, loaded_questions, loaded_search = g1.get_bundle(bundle_path)
            self.assertEqual(len(loaded_chunks), 2)
            self.assertEqual(len(loaded_questions), 1)
            selected, _ = g1.select_for_graph(
                loaded_chunks, loaded_search, loaded_questions, cap=1
            )
            self.assertEqual(selected, ["b"])

    def test_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "report.md"
            g1.markdown_report(report_path, [], {}, [], [], {"total_chunks": 1})
            self.assertIn("질문별 추적", report_path.read_text())

    def test_final_schema_file_matches_embedded_schema(self) -> None:
        schema_path = (
            EXPERIMENTS
            / "starter_rag_experiments"
            / "schemas"
            / "g1_graph_extraction.schema.json"
        )
        self.assertEqual(json.loads(schema_path.read_text()), g1.GRAPH_EXTRACTION_SCHEMA)

    def test_ollama_request_uses_final_schema_without_network(self) -> None:
        response = {
            "model": "test-model",
            "message": {
                "content": json.dumps(
                    {
                        "entities": [{"name": "Example", "type": "company"}],
                        "relations": [],
                    }
                )
            },
        }

        class FakeResponse(io.BytesIO):
            def __enter__(self) -> Self:
                return self

            def __exit__(self, *_: object) -> None:
                self.close()

        with patch.object(
            g1.urllib.request, "urlopen", return_value=FakeResponse(json.dumps(response).encode())
        ) as urlopen:
            parsed, _ = g1.ollama(
                "http://127.0.0.1:11434",
                "test-model",
                [],
                format=g1.GRAPH_EXTRACTION_SCHEMA,
            )

        request = urlopen.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(parsed["entities"][0]["name"], "Example")
        self.assertEqual(body["format"], g1.GRAPH_EXTRACTION_SCHEMA)


if __name__ == "__main__":
    unittest.main()
