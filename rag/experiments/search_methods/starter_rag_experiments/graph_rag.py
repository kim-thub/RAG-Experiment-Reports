"""Prepare and run isolated Microsoft GraphRAG experiments from fixed chunks."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from importlib.metadata import version
from pathlib import Path
from typing import Any

import pandas as pd
import tiktoken
import yaml

DEFAULT_CHAT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_API_KEY_ENV = "RAG_CHUNKING_GEMINI_API_KEY"


def _load_chunk_rows(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        decoded = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(decoded, dict):
        decoded = [decoded]
    if not isinstance(decoded, list):
        raise TypeError("chunk snapshot must be JSON or JSON Lines")

    result: list[dict[str, Any]] = []
    for payload in decoded:
        if not isinstance(payload, dict):
            raise TypeError("every chunk snapshot entry must be a JSON object")
        parent = {key: value for key, value in payload.items() if key != "chunks"}
        nested = payload.get("chunks")
        if isinstance(nested, list):
            entries = nested
        else:
            entries = [payload]
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("chunk entries must be JSON objects")
            record = {**parent, **entry}
            chunk_id = record.get("chunk_id") or record.get("chunkId")
            body = record.get("text")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise ValueError("each chunk requires a non-empty chunk_id")
            if not isinstance(body, str) or not body.strip():
                raise ValueError(f"chunk {chunk_id!r} requires non-empty text")
            source_id = record.get("source_id") or record.get("sourceId") or "unknown"
            source = record.get("source")
            if isinstance(source, Mapping):
                source_id = source.get("source_id", source_id)
                source_title = source.get("title")
                source_url = source.get("url")
                publisher = source.get("publisher")
                version = source.get("version")
            else:
                source_title = record.get("source_title") or record.get("title")
                source_url = record.get("source_url") or record.get("url")
                publisher = record.get("publisher")
                version = record.get("version")
            location = record.get("location")
            if not isinstance(location, str) or not location.strip():
                locations = record.get("locations")
                location = json.dumps(locations, ensure_ascii=False) if locations else "unknown"
            result.append(
                {
                    "id": chunk_id.strip(),
                    "title": chunk_id.strip(),
                    "text": body,
                    "source_id": str(source_id),
                    "source_title": source_title,
                    "source_url": source_url,
                    "publisher": publisher,
                    "version": version,
                    "location": location,
                    "raw_metadata": json.dumps(record, ensure_ascii=False, sort_keys=True),
                }
            )
    ids = [row["id"] for row in result]
    if not result or len(ids) != len(set(ids)):
        raise ValueError("chunk snapshot must contain unique chunk IDs and at least one chunk")
    return result


def _read_settings(root: Path) -> tuple[Path, dict[str, Any]]:
    settings_path = root / "settings.yaml"
    if not settings_path.is_file():
        raise FileNotFoundError(
            f"GraphRAG settings not found: {settings_path}; run graph init first"
        )
    settings = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    if not isinstance(settings, dict):
        raise TypeError("GraphRAG settings.yaml must contain a YAML mapping")
    return settings_path, settings


def _write_settings(path: Path, settings: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(settings, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def initialize_graph_project(
    root: Path,
    *,
    chat_model: str = DEFAULT_CHAT_MODEL,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    api_key_env: str = DEFAULT_API_KEY_ENV,
) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", api_key_env):
        raise ValueError("api-key-env must be a valid environment variable name")
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to initialize non-empty directory: {root}")
    executable = shutil.which("graphrag")
    if executable is None:
        raise RuntimeError("graphrag CLI is missing; install rag/experiments/search_methods first")
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run([executable, "init", "--root", str(root)], check=True)
    settings_path, settings = _read_settings(root)
    settings["completion_models"] = {
        "default_completion_model": {
            "model_provider": "gemini",
            "model": chat_model,
            "auth_method": "api_key",
            "api_key": f"${{{api_key_env}}}",
            "call_args": {"temperature": 0},
        }
    }
    settings["embedding_models"] = {
        "default_embedding_model": {
            "model_provider": "gemini",
            "model": embedding_model,
            "auth_method": "api_key",
            "api_key": f"${{{api_key_env}}}",
        }
    }
    _write_settings(settings_path, settings)


def prepare_graph_input(snapshot: Path, root: Path) -> dict[str, object]:
    rows = _load_chunk_rows(snapshot)
    settings_path, settings = _read_settings(root)
    input_dir = root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    csv_path = input_dir / "chunks.csv"
    manifest_path = root / "source_manifest.jsonl"
    config_path = root / "experiment_config.json"
    if csv_path.exists() or manifest_path.exists() or config_path.exists():
        raise FileExistsError(
            "GraphRAG input or source manifest already exists; use a fresh run folder"
        )

    encoding_name = settings.get("chunking", {}).get("encoding_model", "cl100k_base")
    encoding = tiktoken.get_encoding(encoding_name)
    token_counts = [len(encoding.encode(row["text"])) for row in rows]
    max_tokens = max(token_counts)
    chunking = settings.setdefault("chunking", {})
    chunking.update(
        {
            "type": "tokens",
            "encoding_model": encoding_name,
            "size": max_tokens + 1,
            "overlap": 0,
            "prepend_metadata": [],
        }
    )
    input_config = settings.setdefault("input", {})
    input_config.update(
        {
            "type": "csv",
            "file_pattern": r".*chunks\.csv$",
            "id_column": "id",
            "title_column": "title",
            "text_column": "text",
        }
    )

    fields = tuple(rows[0])
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with manifest_path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    _write_settings(settings_path, settings)
    config = {
        "method": "graph-rag",
        "graphragVersion": version("graphrag"),
        "inputSha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "chunkCount": len(rows),
        "tokenizer": encoding_name,
        "maxGraphRagTokens": max_tokens,
        "chunkSize": max_tokens + 1,
        "overlap": 0,
        "chatModel": settings.get("completion_models", {})
        .get("default_completion_model", {})
        .get("model"),
        "embeddingModel": settings.get("embedding_models", {})
        .get("default_embedding_model", {})
        .get("model"),
    }
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "input": str(csv_path),
        "manifest": str(manifest_path),
        "config": str(config_path),
        **config,
    }


def run_graph_index(root: Path, *, method: str = "standard") -> None:
    _read_settings(root)
    executable = shutil.which("graphrag")
    if executable is None:
        raise RuntimeError("graphrag CLI is missing; install rag/experiments/search_methods first")
    subprocess.run(
        [executable, "index", "--root", str(root), "--method", method], check=True
    )


def run_graph_query(
    root: Path,
    method: str,
    query: str,
    *,
    output: Path | None = None,
) -> None:
    _read_settings(root)
    if method not in {"local", "global"}:
        raise ValueError("GraphRAG method must be local or global")
    executable = shutil.which("graphrag")
    if executable is None:
        raise RuntimeError("graphrag CLI is missing; install rag/experiments/search_methods first")
    if output is not None and output.exists():
        raise FileExistsError(f"refusing to overwrite query output: {output}")
    result = subprocess.run(
        [
            executable,
            "query",
            "--root",
            str(root),
            "--method",
            method,
            "--response-type",
            "Multiple Paragraphs",
            query,
        ],
        check=False,
        stdout=subprocess.PIPE,
        text=True,
    )
    print(result.stdout, end="")
    if result.returncode:
        raise RuntimeError(f"GraphRAG query exited with status {result.returncode}")
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {"method": method, "query": query, "response": result.stdout},
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


def _as_list(value: object) -> list[object]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return list(value)
    return []


def _json_default(value: object) -> object:
    return value.tolist() if hasattr(value, "tolist") else str(value)


def export_graph_provenance(root: Path, *, output: Path | None = None) -> dict[str, object]:
    manifest_path = root / "source_manifest.jsonl"
    output_dir = root / "output"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"source manifest not found: {manifest_path}")
    if not output_dir.is_dir():
        raise FileNotFoundError(f"GraphRAG output directory not found: {output_dir}")
    manifest = {
        row["id"]: row
        for row in (
            json.loads(line)
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
        )
        if row.get("id")
    }

    def read_table(name: str, required: bool = True) -> pd.DataFrame:
        path = output_dir / f"{name}.parquet"
        if not path.is_file():
            if required:
                raise FileNotFoundError(f"GraphRAG table not found: {path}")
            return pd.DataFrame()
        return pd.read_parquet(path)

    documents = read_table("documents")
    text_units = read_table("text_units")
    units_by_id: dict[str, str] = {}
    doc_to_chunk: dict[str, str] = {}
    for row in documents.to_dict(orient="records"):
        document_id = str(row.get("id", row.get("name", "")))
        title = str(row.get("title", ""))
        raw_data = row.get("raw_data")
        original_id = None
        if isinstance(raw_data, Mapping):
            original_id = raw_data.get("id") or raw_data.get("source_chunk_id")
        chunk_id = str(original_id or title)
        if chunk_id not in manifest:
            chunk_id = document_id if document_id in manifest else ""
        if document_id and chunk_id in manifest:
            doc_to_chunk[document_id] = chunk_id
    for row in text_units.to_dict(orient="records"):
        unit_id = str(row.get("id", row.get("name", "")))
        document_id = str(row.get("document_id", ""))
        chunk_id = doc_to_chunk.get(document_id, document_id if document_id in manifest else "")
        if unit_id and chunk_id in manifest:
            units_by_id[unit_id] = chunk_id

    expected = set(manifest)
    mapped = set(units_by_id.values())
    counts_by_chunk: dict[str, int] = {}
    exact_text: dict[str, bool] = {}
    for row in text_units.to_dict(orient="records"):
        unit_id = str(row.get("id", row.get("name", "")))
        chunk_id = units_by_id.get(unit_id)
        if not chunk_id:
            continue
        counts_by_chunk[chunk_id] = counts_by_chunk.get(chunk_id, 0) + 1
        text_value = row.get("text")
        exact_text[chunk_id] = (
            exact_text.get(chunk_id, True) and text_value == manifest[chunk_id]["text"]
        )
    chunk_preservation = (
        mapped == expected
        and all(counts_by_chunk.get(chunk_id) == 1 for chunk_id in expected)
        and all(exact_text.get(chunk_id, False) for chunk_id in expected)
    )

    records: list[dict[str, object]] = []

    for row in text_units.to_dict(orient="records"):
        unit_id = str(row.get("id", row.get("name", "")))
        chunk_id = units_by_id.get(unit_id)
        if chunk_id:
            records.append(
                {
                    "kind": "text_units",
                    "graphId": unit_id,
                    "sourceChunkIds": [chunk_id],
                    "chunkPreserved": chunk_preservation,
                }
            )

    graph_fields = (
        "title",
        "type",
        "description",
        "source",
        "target",
        "community",
        "level",
        "summary",
        "full_content",
    )

    def graph_object(row: Mapping[str, Any]) -> dict[str, object]:
        return {
            field: row[field]
            for field in graph_fields
            if field in row and row[field] is not None
        }

    def append_records(table_name: str, id_field: str, unit_field: str = "text_unit_ids") -> None:
        table = read_table(table_name, required=False)
        for row in table.to_dict(orient="records"):
            unit_ids = _as_list(row.get(unit_field))
            chunk_ids = sorted(
                {
                    units_by_id[str(unit_id)]
                    for unit_id in unit_ids
                    if str(unit_id) in units_by_id
                }
            )
            records.append(
                {
                    "kind": table_name,
                    "graphId": row.get("id", row.get("name")),
                    "label": row.get(id_field),
                    "graphObject": graph_object(row),
                    "sourceChunkIds": chunk_ids,
                    "chunkPreserved": chunk_preservation,
                }
            )

    append_records("entities", "title")
    append_records("relationships", "name")
    append_records("communities", "community")
    communities = read_table("communities", required=False)
    unit_ids_by_community = {
        str(row.get("community")): _as_list(row.get("text_unit_ids"))
        for row in communities.to_dict(orient="records")
    }
    for row in read_table("community_reports", required=False).to_dict(orient="records"):
        unit_ids = unit_ids_by_community.get(str(row.get("community")), [])
        chunk_ids = sorted(
            {units_by_id[str(unit_id)] for unit_id in unit_ids if str(unit_id) in units_by_id}
        )
        records.append(
            {
                "kind": "community_reports",
                "graphId": row.get("id", row.get("community")),
                "label": row.get("title"),
                "graphObject": graph_object(row),
                "sourceChunkIds": chunk_ids,
                "chunkPreserved": chunk_preservation,
            }
        )

    destination = output or (root / "graph_provenance.jsonl")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite provenance file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        for record in records:
            line = json.dumps(record, ensure_ascii=False, default=_json_default)
            stream.write(line + "\n")
    return {
        "output": str(destination),
        "graphObjectCount": len(records),
        "inputChunkCount": len(expected),
        "mappedChunkCount": len(mapped),
        "textUnitCount": len(text_units),
        "chunkPreserved": chunk_preservation,
    }
