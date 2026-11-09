from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "rag" / "experiments" / "search_methods"
sys.path.insert(0, str(EXPERIMENTS))

from starter_rag_experiments import g1_ollama_light as g1


class G1JsonSchemaRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunk = {
            "a": {
                "source_id": "sample.md",
                "text": "Example owns debt in 2022",
                "chunk_id": "a",
            }
        }
        self.valid_response = {
            "entities": [
                {"name": "Example", "type": "company"},
                {"name": "debt", "type": "concept"},
                {"name": "not in source", "type": "concept"},
            ],
            "relations": [
                {"source": "Example", "relation": "owns", "target": "debt"},
                {"source": "Example", "relation": "owns", "target": "missing"},
            ],
        }

    def test_valid_schema_response_is_grounded_and_filtered(self) -> None:
        with patch.object(g1, "ollama", return_value=(self.valid_response, {})) as ollama:
            entities, relations = g1.extract_graph_chunk("unused", "model", self.chunk["a"]["text"])

        self.assertEqual([entity["name"] for entity in entities], ["Example", "debt"])
        self.assertEqual(len(relations), 1)
        self.assertEqual(ollama.call_args.kwargs["format"], g1.GRAPH_EXTRACTION_SCHEMA)

    def test_invalid_schema_response_is_rejected(self) -> None:
        with (
            patch.object(
                g1, "ollama", return_value=({"entities": ["bad"], "relations": []}, {})
            ),
            self.assertRaisesRegex(ValueError, "entities contain no valid objects"),
        ):
            g1.extract_graph_chunk("unused", "model", self.chunk["a"]["text"])

    def test_invalid_response_retries_twice_and_keeps_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            malformed = {"entities": ["bad"], "relations": []}
            with (
                patch.object(g1, "ollama", return_value=(malformed, {})) as ollama,
                patch.object(g1.time, "sleep"),
            ):
                rows = g1.build_graph(["a"], self.chunk, Path(temp_dir), "unused", "model")

        self.assertEqual(ollama.call_count, 2)
        self.assertIn("ValueError", rows[0]["error"])
        self.assertEqual(rows[0]["entities"], [])
        self.assertEqual(rows[0]["relations"], [])

    def test_previous_success_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            (output / "graph_edges.jsonl").write_text(
                json.dumps(
                    {
                        "chunk_id": "a",
                        "source_id": "sample.md",
                        "entities": [],
                        "relations": [],
                        "error": None,
                    }
                )
                + "\n"
            )
            with patch.object(g1, "ollama") as ollama:
                rows = g1.build_graph(["a"], self.chunk, output, "unused", "model")

        ollama.assert_not_called()
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
