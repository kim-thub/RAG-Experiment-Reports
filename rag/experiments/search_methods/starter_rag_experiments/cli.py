"""Command-line entry points for isolated retrieval and GraphRAG experiments."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from starter_rag.embedding.model import EmbeddingGemma
from starter_rag.storage.database import PostgresRagDatabase, database_url_from_environment
from starter_rag.storage.models import DEFAULT_COLLECTION_ID
from starter_rag.storage.vector_store import PGVectorStore

from starter_rag_experiments.graph_rag import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_CHAT_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    export_graph_provenance,
    initialize_graph_project,
    prepare_graph_input,
    run_graph_index,
    run_graph_query,
)
from starter_rag_experiments.retrieval import RRF_K, search


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="starter-rag-experiment")
    commands = parser.add_subparsers(dest="command", required=True)

    search_command = commands.add_parser("search", help="dense/current/hybrid RAG comparison")
    search_command.add_argument("query")
    search_command.add_argument("--method", choices=("dense", "current", "hybrid"), required=True)
    search_command.add_argument("--top-k", type=int, choices=range(1, 11), default=3)
    search_command.add_argument("--candidates", type=int, choices=range(1, 11), default=10)
    search_command.add_argument("--collection-id", default=DEFAULT_COLLECTION_ID)
    search_command.add_argument("--allow-synthetic", action="store_true")

    graph = commands.add_parser("graph", help="prepare, index, query, and trace GraphRAG")
    graph_commands = graph.add_subparsers(dest="graph_command", required=True)

    graph_init = graph_commands.add_parser("init", help="initialize an isolated GraphRAG run")
    graph_init.add_argument("--root", type=Path, required=True)
    graph_init.add_argument("--chat-model", default=DEFAULT_CHAT_MODEL)
    graph_init.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    graph_init.add_argument("--api-key-env", default=DEFAULT_API_KEY_ENV)

    graph_prepare = graph_commands.add_parser("prepare", help="load frozen chunks into GraphRAG")
    graph_prepare.add_argument("--chunks", type=Path, required=True)
    graph_prepare.add_argument("--root", type=Path, required=True)

    graph_index = graph_commands.add_parser("index", help="build the GraphRAG index")
    graph_index.add_argument("--root", type=Path, required=True)
    graph_index.add_argument("--method", choices=("standard", "fast"), default="standard")

    graph_query = graph_commands.add_parser("query", help="run Local or Global Search")
    graph_query.add_argument("--root", type=Path, required=True)
    graph_query.add_argument("--method", choices=("local", "global"), required=True)
    graph_query.add_argument("--output", type=Path)
    graph_query.add_argument("query")

    graph_trace = graph_commands.add_parser(
        "provenance", help="map graph entities, edges, and reports to frozen chunk IDs"
    )
    graph_trace.add_argument("--root", type=Path, required=True)
    graph_trace.add_argument("--output", type=Path)
    return parser


async def _search(args: argparse.Namespace) -> dict[str, object]:
    database = PostgresRagDatabase(database_url_from_environment())
    try:
        await database.validate_existing_table()
        embedding = EmbeddingGemma()
        store = PGVectorStore(database, embedding, collection_id=args.collection_id)
        from starter_rag.contracts.models import SearchRequest

        result, trace = await search(
            args.method,
            SearchRequest(args.query, top_k=args.top_k),
            store,
            embedding,
            allow_synthetic=args.allow_synthetic,
            candidate_count=args.candidates,
        )
        return {
            "success": True,
            "method": args.method,
            "topK": args.top_k,
            "candidateCount": args.candidates,
            "rrfK": RRF_K if args.method == "hybrid" else None,
            "collectionId": args.collection_id,
            "evidence": [asdict(item) for item in result.evidence],
            "rankTrace": trace,
        }
    finally:
        await database.close()


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            print(json.dumps(asyncio.run(_search(args)), ensure_ascii=False))
        elif args.graph_command == "init":
            initialize_graph_project(
                args.root,
                chat_model=args.chat_model,
                embedding_model=args.embedding_model,
                api_key_env=args.api_key_env,
            )
            print(json.dumps({"success": True, "root": str(args.root)}, ensure_ascii=False))
        elif args.graph_command == "prepare":
            print(json.dumps(prepare_graph_input(args.chunks, args.root), ensure_ascii=False))
        elif args.graph_command == "index":
            run_graph_index(args.root, method=args.method)
        elif args.graph_command == "query":
            run_graph_query(args.root, args.method, args.query, output=args.output)
        elif args.graph_command == "provenance":
            print(
                json.dumps(
                    export_graph_provenance(args.root, output=args.output), ensure_ascii=False
                )
            )
        return 0
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        print(f"experiment error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001  # Never dump connection details from exception reprs.
        print(f"experiment failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
