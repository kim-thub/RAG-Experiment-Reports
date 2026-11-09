from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import html
import json
import time
import zipfile
from pathlib import Path

RUN_DIR: Path
BEFORE: Path
AFTER: Path
SOURCE_RUN: Path
MODEL = "qwen3:4b-instruct"
OLLAMA_URL = "http://127.0.0.1:11434"

from . import g1_ollama_light as run_graph

ARTIFACTS_TO_PRESERVE = (
    "graph_edges.jsonl",
    "graph_summary.json",
    "graph_relations.jsonl",
    "comparison_graph_silver.json",
    "question_traces.jsonl",
    "manifest.json",
    "graph_progress.json",
    "GraphRAG_질문별_검증보고서.md",
)

def utc_now() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat()

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

def metric_table(records: list[dict], questions: list[dict]) -> dict[str, dict]:
    base = run_graph.metric(records, questions)
    qmap = {q["id"]: q for q in questions}
    by_method = collections.defaultdict(list)
    for row in records:
        if row["question_id"] in qmap and qmap[row["question_id"]].get("answerability_in_md"):
            by_method[row["method"]].append(row)
    for method, rows in by_method.items():
        for k in (3, 5, 10):
            all_evidence = []
            for row in rows:
                gold = set(qmap[row["question_id"]]["gold_chunk_ids"])
                found = {item["chunk_id"] for item in row["retrieved_chunks"][:k]}
                all_evidence.append(float(gold.issubset(found)))
            base.setdefault(method, {})[f"all_evidence@{k}"] = round(sum(all_evidence) / len(all_evidence), 5) if all_evidence else 0.0
    return base

def first_gold_rank(row: dict | None, gold: set[str]) -> int | None:
    if not row:
        return None
    for index, item in enumerate(row.get("retrieved_chunks", [])[:10], 1):
        if item["chunk_id"] in gold:
            return index
    return None

def gold_ranks(row: dict | None, gold: list[str]) -> dict[str, int | None]:
    found = {item["chunk_id"]: index for index, item in enumerate((row or {}).get("retrieved_chunks", [])[:10], 1)}
    return {chunk_id: found.get(chunk_id) for chunk_id in gold}

def rank_change(old_rank: int | None, new_rank: int | None) -> str:
    if old_rank == new_rank:
        return "unchanged"
    if old_rank is None:
        return "improved"
    if new_rank is None:
        return "worsened"
    if new_rank < old_rank:
        return "improved"
    if new_rank > old_rank:
        return "worsened"
    return "unchanged"

def append_block(lines: list[str], title: str, value: str) -> None:
    lines.extend([f"##### {title}", "", "<pre>", html.escape(value), "</pre>", ""])

def main(argv: list[str] | None = None) -> None:
    global RUN_DIR, BEFORE, AFTER, SOURCE_RUN, MODEL, OLLAMA_URL
    parser = argparse.ArgumentParser(
        description="Reproduce the Ollama G1 JSON Schema retry run from a saved source run."
    )
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args(argv)

    RUN_DIR = args.output_dir.expanduser().resolve()
    BEFORE = RUN_DIR / "before"
    AFTER = RUN_DIR / "after"
    SOURCE_RUN = args.source_run.expanduser().resolve()
    MODEL = args.model
    OLLAMA_URL = args.ollama_url
    if not SOURCE_RUN.is_dir():
        raise FileNotFoundError("source run directory does not exist")
    if RUN_DIR.exists():
        raise FileExistsError("output directory already exists; choose a new run directory")
    RUN_DIR.parent.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir()
    AFTER.mkdir()

    started_at = utc_now()
    wall_started = time.monotonic()
    source_edges_path = SOURCE_RUN / "graph_edges.jsonl"
    source_trace_path = SOURCE_RUN / "question_traces.jsonl"
    source_manifest = json.loads((SOURCE_RUN / "manifest.json").read_text(encoding="utf-8"))
    old_lines = source_edges_path.read_text(encoding="utf-8").splitlines()
    old_rows = [json.loads(line) for line in old_lines if line.strip()]
    old_traces = read_jsonl(source_trace_path)
    json.loads((SOURCE_RUN / "graph_summary.json").read_text(encoding="utf-8"))
    old_metrics = json.loads((SOURCE_RUN / "comparison_graph_silver.json").read_text(encoding="utf-8"))

    success_lines = [line for line in old_lines if line.strip() and not json.loads(line).get("error")]
    success_rows = [json.loads(line) for line in success_lines]
    failed_rows = [row for row in old_rows if row.get("error")]
    failed_ids = {row["chunk_id"] for row in failed_rows}
    selected_ids = source_manifest["selected_graph_chunk_ids"]
    if len(success_rows) != 57 or len(failed_ids) != 63 or len(selected_ids) != 120:
        raise RuntimeError("Source graph counts changed from the verified 57/63/120 snapshot")

    traces_by_q: dict[str, dict[str, dict]] = collections.defaultdict(dict)
    trace_lines_by_q: dict[str, dict[str, str]] = collections.defaultdict(dict)
    q_order: list[str] = []
    chunk_records: dict[str, dict] = {}
    for raw_line in source_trace_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        qid = row["question_id"]
        if qid not in traces_by_q:
            q_order.append(qid)
        traces_by_q[qid][row["method"]] = row
        trace_lines_by_q[qid][row["method"]] = raw_line
        for chunk in row.get("retrieved_chunks", []):
            cid = chunk.get("chunk_id")
            text = chunk.get("chunk_text_full")
            if cid and isinstance(text, str):
                candidate = {
                    "chunk_id": cid,
                    "source_id": chunk["source_id"],
                    "text": text,
                    "version": chunk.get("source_version"),
                    "element_ids": chunk.get("element_ids", []),
                    "location_statuses": chunk.get("location_statuses", []),
                }
                prior = chunk_records.get(cid)
                if prior and prior["text"] != text:
                    raise RuntimeError(f"Conflicting source text for chunk {cid}")
                chunk_records.setdefault(cid, candidate)

    if len(q_order) != 29 or any(set(traces_by_q[qid]) != {"V1", "H1", "G1"} for qid in q_order):
        raise RuntimeError("Expected the original 29 questions with V1/H1/G1 traces")
    if not set(selected_ids).issubset(chunk_records):
        raise RuntimeError("The preserved traces do not contain all graph input chunk texts")
    byid = chunk_records
    if any(qid not in traces_by_q or not traces_by_q[qid]["V1"].get("retrieved_chunks") or not traces_by_q[qid]["H1"].get("retrieved_chunks") for qid in q_order):
        raise RuntimeError("V1/H1 baseline retrieval traces are incomplete")

    questions = []
    for qid in q_order:
        old = traces_by_q[qid]["G1"]
        gold_ids = old.get("gold_chunk_ids_silver", [])
        questions.append({
            "id": qid,
            "question": old["question"],
            "answer": old.get("expected_answer_silver"),
            "gold_chunk_ids": gold_ids,
            "answerability_in_md": old.get("answerability_in_md"),
            "mapping_status": "mapped" if gold_ids else "unmapped",
            "file": old.get("source_file"),
            "review_status": old.get("label_status"),
        })

    baselines: dict[str, dict[str, list[str]]] = {}
    for qid in q_order:
        baselines[qid] = {
            method: [item["chunk_id"] for item in traces_by_q[qid][method].get("retrieved_chunks", [])]
            for method in ("V1", "H1")
        }

    # The new directory starts with the exact 57 successful cache lines. Failed rows are not copied.
    with (AFTER / "graph_edges.jsonl").open("w", encoding="utf-8") as stream:
        for line in success_lines:
            stream.write(line + "\n")
    new_manifest = dict(source_manifest)
    new_manifest.update({
        "run_id": RUN_DIR.name,
        "parent_run": str(SOURCE_RUN),
        "run_started_at": started_at,
        "graph_extraction_format": "JSON Schema via Ollama /api/chat format",
        "preserved_success_cache_rows": len(success_lines),
        "reextraction_candidate_ids": [cid for cid in selected_ids if cid in failed_ids],
        "reextraction_scope": "previously failed chunk IDs only",
        "baseline_methods_reused": ["V1", "H1"],
        "g1_answers_regenerated": len(questions),
    })
    write_json(AFTER / "manifest.json", new_manifest)
    write_json(AFTER / "graph_extraction_schema.json", run_graph.GRAPH_EXTRACTION_SCHEMA)
    write_jsonl(AFTER / "graph_input_chunks.jsonl", [byid[cid] for cid in selected_ids])

    call_log_path = AFTER / "ollama_calls.jsonl"
    if call_log_path.exists():
        raise RuntimeError("Refusing to overwrite Ollama call log")
    call_log_path.touch()
    excerpt_to_chunk = {
        hashlib.sha256(byid[cid]["text"][:4800].encode("utf-8")).hexdigest(): cid
        for cid in selected_ids
    }
    call_context = {"question_id": None}
    original_ollama = run_graph.ollama

    def tracked_ollama(host, model, messages, timeout=180, format="json"):
        call_number = len(read_jsonl(call_log_path)) + 1
        kind = "graph_extraction" if isinstance(format, dict) else "g1_answer"
        chunk_id = None
        qid = call_context["question_id"]
        if kind == "graph_extraction" and len(messages) > 1:
            user_content = messages[-1].get("content", "")
            chunk_id = excerpt_to_chunk.get(hashlib.sha256(user_content.encode("utf-8")).hexdigest())
        call_started = time.monotonic()
        try:
            parsed, raw = original_ollama(host, model, messages, timeout=timeout, format=format)
            event = {
                "call_number": call_number,
                "kind": kind,
                "chunk_id": chunk_id,
                "question_id": qid if kind == "g1_answer" else None,
                "format": "json_schema" if isinstance(format, dict) else format,
                "model": raw.get("model", model),
                "elapsed_s": round(time.monotonic() - call_started, 3),
                "prompt_eval_count": raw.get("prompt_eval_count"),
                "eval_count": raw.get("eval_count"),
                "total_duration_ns": raw.get("total_duration"),
                "done_reason": raw.get("done_reason"),
                "error": None,
            }
            with call_log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            return parsed, raw
        except Exception as exc:
            event = {
                "call_number": call_number,
                "kind": kind,
                "chunk_id": chunk_id,
                "question_id": qid if kind == "g1_answer" else None,
                "format": "json_schema" if isinstance(format, dict) else format,
                "model": model,
                "elapsed_s": round(time.monotonic() - call_started, 3),
                "prompt_eval_count": None,
                "eval_count": None,
                "total_duration_ns": None,
                "done_reason": None,
                "error": f"{type(exc).__name__}: {str(exc)[:180]}",
            }
            with call_log_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            raise

    run_graph.ollama = tracked_ollama
    extraction_started = time.monotonic()
    graph_rows = run_graph.build_graph(
        selected_ids,
        byid,
        AFTER,
        OLLAMA_URL,
        MODEL,
        redo=False,
    )
    extraction_elapsed = round(time.monotonic() - extraction_started, 3)
    new_cache_lines = (AFTER / "graph_edges.jsonl").read_text(encoding="utf-8").splitlines()
    if new_cache_lines[:len(success_lines)] != success_lines:
        raise RuntimeError("Previously successful cache lines changed in the new run")
    rows_by_id = {row["chunk_id"]: row for row in graph_rows}
    if len(rows_by_id) != 120 or not failed_ids.issubset(rows_by_id):
        raise RuntimeError("Updated graph cache does not contain the 120 unique selected IDs")
    reextracted = [rows_by_id[cid] for cid in selected_ids if cid in failed_ids]
    extraction_successes = [row for row in reextracted if not row.get("error")]
    extraction_failures = [row for row in reextracted if row.get("error")]
    if len(reextracted) != 63:
        raise RuntimeError("The extraction pass did not process exactly the 63 failed IDs")

    entity_chunks, adjacency, relations = run_graph.construct_index(graph_rows)
    graph_summary = {
        "entities": len(entity_chunks),
        "relations": len(relations),
        "graph_chunks": len(graph_rows),
        "failed_chunks": sum(bool(row.get("error")) for row in graph_rows),
        "entity_samples": list(entity_chunks)[:30],
        "preserved_success_rows": len(success_rows),
        "reextracted_success_rows": len(extraction_successes),
        "reextracted_failed_rows": len(extraction_failures),
    }
    write_json(AFTER / "graph_summary.json", graph_summary)
    run_graph.save_jsonl(AFTER / "graph_relations.jsonl", relations)
    write_jsonl(AFTER / "reextraction_failures.jsonl", extraction_failures)

    # Reuse the prior V1/H1 searches and answers; generate only the new G1 search and answer.
    new_g1_records: dict[str, dict] = {}
    answer_started = time.monotonic()
    for index, q in enumerate(questions, 1):
        qid = q["id"]
        ranked, explanation = run_graph.graph_search(
            q,
            baselines[qid],
            entity_chunks,
            adjacency,
            byid,
            set(selected_ids),
        )
        retrieved, reference_payload = run_graph.context_for(ranked, byid)
        record = {
            "question_id": qid,
            "question": q["question"],
            "expected_answer_silver": q["answer"],
            "gold_chunk_ids_silver": q["gold_chunk_ids"],
            "answerability_in_md": q["answerability_in_md"],
            "source_file": q["file"],
            "label_status": q["review_status"],
            "method": "G1",
            "retrieved_chunks": retrieved,
            "model_reference_payload": reference_payload,
            "prompt_policy": "answer from provided references only; cite chunk ids; abstain if insufficient",
            "answer_model": MODEL,
            "final_answer": None,
            "graph_explanation": explanation,
            "created_at": run_graph.now(),
        }
        call_context["question_id"] = qid
        final_answer = run_graph.answer(q["question"], reference_payload, OLLAMA_URL, MODEL)
        call_context["question_id"] = None
        valid_ids = {item["chunk_id"] for item in retrieved}
        citations = final_answer.get("citations")
        final_answer["citations_valid"] = (
            all(isinstance(cid, str) and cid in valid_ids for cid in citations)
            if isinstance(citations, list)
            else False
        )
        record["final_answer"] = final_answer
        new_g1_records[qid] = record
        with (AFTER / "g1_regenerated_traces.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
        print(f"G1 {index}/29 {qid}", flush=True)
    answer_elapsed = round(time.monotonic() - answer_started, 3)

    # Preserve V1/H1 JSONL lines exactly and replace only the G1 records.
    final_trace_path = AFTER / "question_traces.jsonl"
    if final_trace_path.exists():
        raise RuntimeError("Refusing to overwrite a pre-existing after trace")
    final_rows: list[dict] = []
    with final_trace_path.open("w", encoding="utf-8") as stream:
        for qid in q_order:
            for method in ("V1", "H1"):
                raw_line = trace_lines_by_q[qid][method]
                stream.write(raw_line + "\n")
                final_rows.append(traces_by_q[qid][method])
            new_row = new_g1_records[qid]
            stream.write(json.dumps(new_row, ensure_ascii=False) + "\n")
            final_rows.append(new_row)
    if len(final_rows) != 87:
        raise RuntimeError("Expected 87 traces after baseline reuse and G1 regeneration")

    old_recomputed_metrics = metric_table(old_traces, questions)
    new_metrics = metric_table(final_rows, questions)
    reported_before_matches = {}
    for method in ("V1", "H1", "G1"):
        reported_before_matches[method] = all(
            abs(old_recomputed_metrics.get(method, {}).get(key, 0.0) - old_metrics.get(method, {}).get(key, 0.0)) < 0.00002
            for key in old_metrics.get(method, {})
            if isinstance(old_metrics.get(method, {}).get(key), (int, float))
        )

    old_g1 = {row["question_id"]: row for row in old_traces if row["method"] == "G1"}
    new_g1 = {row["question_id"]: row for row in final_rows if row["method"] == "G1"}
    v1 = {row["question_id"]: row for row in final_rows if row["method"] == "V1"}
    h1 = {row["question_id"]: row for row in final_rows if row["method"] == "H1"}
    question_changes = []
    added_pairs_old = set()
    added_pairs_new = set()
    baseline_union_pairs = set()
    new_pairs = set()
    old_pairs = set()
    for q in questions:
        qid = q["id"]
        gold = set(q["gold_chunk_ids"])
        old_rank = first_gold_rank(old_g1.get(qid), gold)
        new_rank = first_gold_rank(new_g1.get(qid), gold)
        change = rank_change(old_rank, new_rank)
        old_top = {item["chunk_id"] for item in old_g1[qid]["retrieved_chunks"][:10]}
        new_top = {item["chunk_id"] for item in new_g1[qid]["retrieved_chunks"][:10]}
        base_top = (
            {item["chunk_id"] for item in v1[qid]["retrieved_chunks"][:10]}
            | {item["chunk_id"] for item in h1[qid]["retrieved_chunks"][:10]}
        )
        old_correct = {(qid, cid) for cid in gold & old_top}
        new_correct = {(qid, cid) for cid in gold & new_top}
        baseline_correct = {(qid, cid) for cid in gold & base_top}
        old_pairs |= old_correct
        new_pairs |= new_correct
        baseline_union_pairs |= baseline_correct
        added_pairs_old |= new_correct - old_correct
        added_pairs_new |= new_correct - baseline_correct
        question_changes.append({
            "question_id": qid,
            "question": q["question"],
            "old_g1_first_gold_rank": old_rank,
            "new_g1_first_gold_rank": new_rank,
            "first_gold_rank_change": change,
            "old_g1_gold_ranks": gold_ranks(old_g1.get(qid), q["gold_chunk_ids"]),
            "new_g1_gold_ranks": gold_ranks(new_g1.get(qid), q["gold_chunk_ids"]),
            "old_g1_gold_hits_at_10": len(gold & old_top),
            "new_g1_gold_hits_at_10": len(gold & new_top),
            "v1_h1_union_gold_hits_at_10": len(gold & base_top),
            "new_correct_gold_chunks_not_in_v1_h1_top10": sorted(gold & new_top - base_top),
        })

    citation_audit = {
        "questions": len(questions),
        "answer_errors": 0,
        "abstained": 0,
        "abstention_unknown": 0,
        "citation_ids_outside_retrieved_chunks": 0,
        "citation_ids_not_in_silver_gold_mapping": 0,
        "questions_with_citation_ids_outside_retrieved_chunks": [],
        "questions_with_not_gold_mapped_citations": [],
    }
    for q in questions:
        row = new_g1[q["id"]]
        answer = row.get("final_answer") or {}
        if answer.get("error"):
            citation_audit["answer_errors"] += 1
        if answer.get("abstained") is True:
            citation_audit["abstained"] += 1
        elif answer.get("abstained") is None:
            citation_audit["abstention_unknown"] += 1
        citations = answer.get("citations")
        if not isinstance(citations, list):
            citations = []
        retrieved_ids = {item["chunk_id"] for item in row.get("retrieved_chunks", [])}
        gold_ids = set(q["gold_chunk_ids"])
        outside = [cid for cid in citations if not isinstance(cid, str) or cid not in retrieved_ids]
        not_gold = [cid for cid in citations if isinstance(cid, str) and cid not in gold_ids]
        citation_audit["citation_ids_outside_retrieved_chunks"] += len(outside)
        citation_audit["citation_ids_not_in_silver_gold_mapping"] += len(not_gold)
        if outside:
            citation_audit["questions_with_citation_ids_outside_retrieved_chunks"].append(q["id"])
        if not_gold:
            citation_audit["questions_with_not_gold_mapped_citations"].append(q["id"])

    call_events = read_jsonl(call_log_path)
    usage = {}
    for kind in ("graph_extraction", "g1_answer"):
        events = [event for event in call_events if event["kind"] == kind]
        usage[kind] = {
            "calls": len(events),
            "calls_with_token_metrics": sum(event["prompt_eval_count"] is not None or event["eval_count"] is not None for event in events),
            "prompt_eval_count": sum(event["prompt_eval_count"] or 0 for event in events),
            "eval_count": sum(event["eval_count"] or 0 for event in events),
            "total_duration_ns": sum(event["total_duration_ns"] or 0 for event in events),
            "transport_errors": sum(bool(event["error"]) for event in events),
        }
    run_finished_at = utc_now()
    run_elapsed = round(time.monotonic() - wall_started, 3)
    metric_output = {
        "before_reported": old_metrics,
        "before_recomputed_from_full_traces": old_recomputed_metrics,
        "after": new_metrics,
        "before_metrics_match_reported": reported_before_matches,
        "g1_delta_vs_before": {
            key: round(new_metrics["G1"].get(key, 0.0) - old_recomputed_metrics["G1"].get(key, 0.0), 5)
            for key in new_metrics["G1"]
        },
    }
    write_json(RUN_DIR / "metrics_comparison.json", metric_output)
    write_json(RUN_DIR / "question_rank_changes.json", question_changes)
    write_json(RUN_DIR / "citation_audit.json", citation_audit)
    write_json(RUN_DIR / "usage_and_runtime.json", {
        "run_started_at": started_at,
        "run_finished_at": run_finished_at,
        "wall_elapsed_s": run_elapsed,
        "graph_reextraction_elapsed_s": extraction_elapsed,
        "g1_answers_elapsed_s": answer_elapsed,
        "model": MODEL,
        "ollama_url": OLLAMA_URL,
        "calls": usage,
        "total_ollama_calls": sum(item["calls"] for item in usage.values()),
        "tokens_available": {
            "prompt_eval_count": sum(item["prompt_eval_count"] for item in usage.values()),
            "eval_count": sum(item["eval_count"] for item in usage.values()),
        },
    })
    run_graph.markdown_report(
        AFTER / "GraphRAG_질문별_검증보고서.md",
        final_rows,
        new_metrics,
        graph_rows,
        questions,
        new_manifest,
    )

    # Full trace: each question/method, complete retrieved chunk texts, source IDs,
    # the exact reference payload passed to the model, and final answer.
    details = [
        "# GraphRAG G1 전체 질문 추적",
        "",
        "Silver Set의 29개 질문입니다. V1/H1 검색·답변은 기존 기록을 재사용했고, G1은 새 그래프에서 다시 생성했습니다.",
        "",
    ]
    trace_lookup = {(row["question_id"], row["method"]): row for row in final_rows}
    for q in questions:
        details.extend([f"## {q['id']} — {q['question']}", ""])
        for method in ("V1", "H1", "G1"):
            row = trace_lookup[(q["id"], method)]
            details.extend([f"### {method}", "", "#### 검색한 청크 전문과 출처", ""])
            for item in row.get("retrieved_chunks", []):
                details.extend([
                    f"##### Rank {item['rank']} — {item['chunk_id']}",
                    f"출처: {item['source_id']}",
                    f"출처 요소: {', '.join(item.get('element_ids', []))}",
                    "",
                    "<pre>",
                    html.escape(item.get("chunk_text_full", "")),
                    "</pre>",
                    "",
                ])
            details.extend(["#### 모델에 실제 전달한 참고자료 전문", "", "<pre>", html.escape(row.get("model_reference_payload", "")), "</pre>", ""])
            answer = row.get("final_answer") or {}
            details.extend([
                "#### 최종 답변",
                "",
                answer.get("answer", ""),
                "",
                "인용: " + json.dumps(answer.get("citations", []), ensure_ascii=False),
                "답변 보류: " + str(answer.get("abstained")),
                "인용 ID 검증: " + str(answer.get("citations_valid")),
                "",
            ])
    (RUN_DIR / "full_question_traces.md").write_text("\n".join(details) + "\n", encoding="utf-8")

    rank_counts = collections.Counter(item["first_gold_rank_change"] for item in question_changes)
    additional_vs_base = sorted([{"question_id": qid, "chunk_id": cid} for qid, cid in new_pairs - baseline_union_pairs], key=lambda x: (x["question_id"], x["chunk_id"]))
    added_vs_old = sorted([{"question_id": qid, "chunk_id": cid} for qid, cid in new_pairs - old_pairs], key=lambda x: (x["question_id"], x["chunk_id"]))
    removed_vs_old = sorted([{"question_id": qid, "chunk_id": cid} for qid, cid in old_pairs - new_pairs], key=lambda x: (x["question_id"], x["chunk_id"]))
    extraction_errors = collections.Counter(row.get("error") for row in extraction_failures)
    before_success_lines_match = new_cache_lines[:len(success_lines)] == success_lines
    final_report = [
        "# GraphRAG G1 JSON Schema 재실험 보고서",
        "",
        f"- Run ID: {RUN_DIR.name}",
        "- 상태: Silver Set 임시 비교 실험이며 범용 성능 검증 아님",
        f"- 모델: {MODEL}",
        f"- 부모 실행: {SOURCE_RUN}",
        f"- 실행 시작/종료: {started_at} / {run_finished_at}",
        f"- 전체 경과: {run_elapsed}초; 재추출 {extraction_elapsed}초; G1 답변 생성 {answer_elapsed}초",
        "",
        "## 범위 및 보존",
        "",
        f"- 기존 성공 cache {len(success_rows)}행을 새 after/graph_edges.jsonl의 첫 행들로 원문 그대로 복사했습니다. 바이트 단위 일치: {before_success_lines_match}.",
        f"- 이전 오류 ID {len(failed_ids)}개만 새 JSON Schema 추출기에 전달했습니다. 신규 실패 {len(extraction_failures)}개, 성공 {len(extraction_successes)}개.",
        "- 기존 V1/H1 검색·답변 58행을 JSONL 원문 라인 그대로 재사용했습니다. 새 G1은 29개 질문에서만 생성했습니다.",
        "- 기존 실행 디렉터리와 ZIP을 수정하지 않았고, starter-kit 저장소 및 운영 DB를 건드리지 않았습니다.",
        "- G2는 실행하지 않았습니다.",
        "",
        "## 추출 결과",
        "",
        f"- 그래프 대상: {len(graph_rows)} / 2,100 청크",
        f"- 총 그래프 엔티티: {graph_summary['entities']} (정규화된 이름 기준 unique)",
        f"- 총 관계: {graph_summary['relations']}",
        f"- 기존 성공 보존: {len(success_rows)}",
        f"- 63개 재추출: 성공 {len(extraction_successes)}, 실패 {len(extraction_failures)}",
        f"- 재추출 실패 원인: {json.dumps(dict(extraction_errors), ensure_ascii=False)}",
        "- 빈 엔티티를 임의 생성하거나 문자열을 객체로 변환하지 않았습니다.",
        "",
        "## 검색 지표 비교",
        "",
        "|방법|세트|Hit@3|Recall@3|Hit@5|Recall@5|Hit@10|Recall@10|MRR@10|모든 근거 @3|모든 근거 @5|모든 근거 @10|",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method in ("V1", "H1", "G1"):
        for label, metrics in (("이전", old_recomputed_metrics), ("재실험", new_metrics)):
            row = metrics.get(method, {})
            final_report.append(
                    f"|{method}|{label}|{row.get('hit@3', 0):.3f}|{row.get('recall@3', 0):.3f}|{row.get('hit@5', 0):.3f}|{row.get('recall@5', 0):.3f}|{row.get('hit@10', 0):.3f}|{row.get('recall@10', 0):.3f}|{row.get('mrr@10', 0):.3f}|{row.get('all_evidence@3', 0):.3f}|{row.get('all_evidence@5', 0):.3f}|{row.get('all_evidence@10', 0):.3f}|"
                )
    final_report.extend([
        "",
        "V1/H1 재실험 값은 같은 이전 검색/답변 기록으로부터 다시 계산했으며 새 모델 호출은 하지 않았습니다. G1 이전 값은 부모 run의 추적에서 다시 계산했습니다.",
        "",
        "## 질문별 G1 순위 변화",
        "",
        f"- 첫 정답 청크 순위: 개선 {rank_counts['improved']}문항, 악화 {rank_counts['worsened']}문항, 동일 {rank_counts['unchanged']}문항.",
        "- 세부 순위와 질문별 정답 청크는 question_rank_changes.json에 있습니다.",
        "",
        "|질문 ID|이전 첫 정답 순위|새 첫 정답 순위|변화|이전 정답 청크 @10|새 정답 청크 @10|V1/H1 합집합 정답 @10|",
        "|---|---:|---:|---|---:|---:|---:|",
    ])
    for row in question_changes:
        final_report.append(
            f"|{row['question_id']}|{row['old_g1_first_gold_rank'] or '없음'}|{row['new_g1_first_gold_rank'] or '없음'}|{row['first_gold_rank_change']}|{row['old_g1_gold_hits_at_10']}|{row['new_g1_gold_hits_at_10']}|{row['v1_h1_union_gold_hits_at_10']}|"
        )
    final_report.extend([
        "",
        f"- 새 G1의 V1/H1 Top10 합집합 외 추가 정답 청크(질문-청크 쌍): {len(additional_vs_base)}",
        f"- 이전 G1 대비 새로 얻은 정답 청크 쌍: {len(added_vs_old)}; 사라진 쌍: {len(removed_vs_old)}",
        "- 상세 쌍은 metrics_comparison.json 및 question_rank_changes.json을 확인하세요.",
        "",
        "## 답변·인용 검증",
        "",
        f"- G1 답변 오류: {citation_audit['answer_errors']} / 29",
        f"- 답변 보류: {citation_audit['abstained']} / 29; 보류 상태 미확인: {citation_audit['abstention_unknown']}",
        f"- 검색하지 않은 청크 ID 인용: {citation_audit['citation_ids_outside_retrieved_chunks']}건, 해당 질문 {len(citation_audit['questions_with_citation_ids_outside_retrieved_chunks'])}개",
        f"- Silver 정답 매핑에 없는 인용: {citation_audit['citation_ids_not_in_silver_gold_mapping']}건. 이는 자동으로 오인용 판정하지 않고 매핑 밖 인용으로 별도 표시합니다.",
        "- 인용 ID가 검색 결과에 포함되는지 자동 검증했습니다. 인용 내용이 답변 주장을 실제로 뒷받침하는지는 사람 검수 대상입니다.",
        "",
        "## Ollama 호출·토큰",
        "",
        f"- 추출 호출: {usage['graph_extraction']['calls']}회 (재시도 포함); G1 최종답변 호출: {usage['g1_answer']['calls']}회; 총 {sum(item['calls'] for item in usage.values())}회.",
        f"- 확인된 prompt tokens: {sum(item['prompt_eval_count'] for item in usage.values())}; 확인된 output tokens: {sum(item['eval_count'] for item in usage.values())}.",
        "- 호출별 메트릭과 HTTP/파싱 오류는 after/ollama_calls.jsonl에 있습니다. Ollama 응답에서 토큰 수를 제공하지 않은 호출은 합계에 포함되지 않습니다.",
        "",
        "## 전체 추적",
        "",
        "- full_question_traces.md에는 29개 질문 각각의 V1/H1/G1 검색 청크 전문, 출처, 모델에 전달한 참고자료 전문, 최종 답변·인용·보류 여부가 있습니다.",
        "- before/와 after/에 수정 전·후 원시 실험 파일이 분리되어 있습니다.",
        "- Silver Set은 29문항·부분 그래프 120/2,100개 범위입니다. 결과를 최종 범용 성능으로 해석하지 않습니다.",
        "",
    ])
    (RUN_DIR / "final_report.md").write_text("\n".join(final_report), encoding="utf-8")

    # Verify baselines, success cache preservation, extraction scope, and trace counts before packaging.
    reused_vh_lines = [
        line for line in source_trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line).get("method") in ("V1", "H1")
    ]
    after_vh_rows = [row for row in read_jsonl(final_trace_path) if row["method"] in ("V1", "H1")]
    if len(reused_vh_lines) != 58 or len(after_vh_rows) != 58:
        raise RuntimeError("V1/H1 baseline trace count mismatch")
    if sum(row["kind"] == "graph_extraction" for row in call_events) != usage["graph_extraction"]["calls"]:
        raise RuntimeError("Ollama extraction call accounting mismatch")
    if len([row for row in reextracted if row.get("error") is None]) + len(extraction_failures) != 63:
        raise RuntimeError("Re-extraction outcome accounting mismatch")

    run_summary = {
        "run_id": RUN_DIR.name,
        "source_run": str(SOURCE_RUN),
        "preserved_success_cache_rows": len(success_rows),
        "preserved_success_cache_byte_identical": before_success_lines_match,
        "reextracted_chunk_ids": len(reextracted),
        "reextraction_successes": len(extraction_successes),
        "reextraction_failures": len(extraction_failures),
        "graph_entities": graph_summary["entities"],
        "graph_relations": graph_summary["relations"],
        "questions": len(questions),
        "v1_h1_traces_reused": len(after_vh_rows),
        "g1_traces_regenerated": len(new_g1_records),
        "metrics": metric_output,
        "citation_audit": citation_audit,
        "runtime_and_usage": {
            "run_started_at": started_at,
            "run_finished_at": run_finished_at,
            "wall_elapsed_s": run_elapsed,
            "graph_reextraction_elapsed_s": extraction_elapsed,
            "g1_answers_elapsed_s": answer_elapsed,
            "calls": usage,
        },
    }
    write_json(RUN_DIR / "run_summary.json", run_summary)

    zip_path = RUN_DIR / "GraphRAG_G1_JsonSchema_전체추적.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(RUN_DIR.rglob("*")):
            if not path.is_file() or path == zip_path or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            archive.write(path, path.relative_to(RUN_DIR.parent))
    print("REPORT=" + str(RUN_DIR / "final_report.md"))
    print("SUMMARY=" + str(RUN_DIR / "run_summary.json"))
    print("ZIP=" + str(zip_path))
    print("SEND_FILE=" + str(zip_path))

if __name__ == "__main__":
    main()
