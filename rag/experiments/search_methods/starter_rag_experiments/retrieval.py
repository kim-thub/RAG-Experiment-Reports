"""Dense and BM25/RRF search implementations for controlled comparisons."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from rank_bm25 import BM25Okapi
from sqlalchemy import text
from starter_rag.contracts.models import Evidence, SearchRequest, SearchResult, SourceRef
from starter_rag.contracts.ports import EmbeddingPort
from starter_rag.storage.models import DEFAULT_COLLECTION_ID
from starter_rag.storage.vector_store import DenseVectorHit, PGVectorStore

SearchMethod = Literal["dense", "current", "hybrid"]
TOKEN_PATTERN = re.compile(r"[^\W_]+(?:[._/-][^\W_]+)*", flags=re.UNICODE)
RRF_K = 60


@dataclass(frozen=True)
class PublishedChunk:
    chunk_id: str
    text: str
    metadata: Mapping[str, Any]


def tokenize(value: str) -> list[str]:
    """NFC + casefold + Unicode word/dotted-number tokens; apply to query and corpus."""
    normalized = unicodedata.normalize("NFC", value).casefold()
    return TOKEN_PATTERN.findall(normalized)


def _evidence(
    chunk_id: str,
    body: str,
    metadata: Mapping[str, Any],
    score: float,
) -> Evidence | None:
    source_id = metadata.get("source_id")
    title = metadata.get("source_title")
    publisher = metadata.get("publisher")
    version = metadata.get("version")
    location = metadata.get("location")
    url = metadata.get("source_url")
    if not all(
        isinstance(value, str) and value.strip()
        for value in (source_id, title, publisher, version, location, body)
    ):
        return None
    if url is not None and not isinstance(url, str):
        return None
    if not math.isfinite(score):
        return None
    try:
        source = SourceRef(
            source_id=source_id,
            title=title,
            url=url,
            publisher=publisher,
            version=version,
        )
        return Evidence(
            evidence_id=chunk_id,
            source=source,
            text=body,
            location=location,
            score=score,
        )
    except ValueError:
        return None


def _evidence_from_dense(
    hit: DenseVectorHit,
    *,
    allow_synthetic: bool,
) -> Evidence | None:
    if hit.metadata.get("publication_state") != "published":
        return None
    if not allow_synthetic and hit.metadata.get("is_synthetic") is not False:
        return None
    score = 1.0 - hit.cosine_distance
    return _evidence(hit.chunk_id, hit.text, hit.metadata, score)


async def _published_chunks(
    store: PGVectorStore,
    *,
    allow_synthetic: bool,
) -> tuple[PublishedChunk, ...]:
    if allow_synthetic and store.collection_id == DEFAULT_COLLECTION_ID:
        raise ValueError("synthetic search requires an isolated non-production collection")
    query = f"""SELECT chunk_id, content, source_id, version, publication_state,
        collection_id, location, source_title, source_url, publisher, is_synthetic
        FROM {store.table_name}
        WHERE collection_id = :collection_id AND publication_state = 'published'
          AND (:allow_synthetic OR is_synthetic = FALSE)
        ORDER BY chunk_id"""
    async with store.database.sql_engine.connect() as connection:
        await connection.execute(text("SET TRANSACTION READ ONLY"))
        rows = await connection.execute(
            text(query),
            {"collection_id": store.collection_id, "allow_synthetic": allow_synthetic},
        )
    return tuple(
        PublishedChunk(
            chunk_id=str(row["chunk_id"]),
            text=str(row["content"]),
            metadata={
                "source_id": row["source_id"],
                "version": row["version"],
                "publication_state": row["publication_state"],
                "collection_id": row["collection_id"],
                "location": row["location"],
                "source_title": row["source_title"],
                "source_url": row["source_url"],
                "publisher": row["publisher"],
                "is_synthetic": row["is_synthetic"],
            },
        )
        for row in rows.mappings()
        if isinstance(row["content"], str) and row["content"].strip()
    )


async def search(
    method: SearchMethod,
    request: SearchRequest,
    store: PGVectorStore,
    embedding: EmbeddingPort,
    *,
    allow_synthetic: bool = False,
    candidate_count: int = 10,
) -> tuple[SearchResult, list[dict[str, object]]]:
    if method not in {"dense", "current", "hybrid"}:
        raise ValueError("method must be dense, current, or hybrid")
    if not 1 <= candidate_count <= 10:
        raise ValueError("candidate_count must be within 1..10")

    if method == "current":
        from starter_rag.retrieval.search import PGVectorSearch

        result = await PGVectorSearch(
            store,
            embedding,
            allow_synthetic=allow_synthetic,
            candidate_count=candidate_count,
        ).search(request)
        return result, [
            {"rank": rank, "chunkId": item.evidence_id, "score": item.score}
            for rank, item in enumerate(result.evidence, start=1)
        ]

    vector = await embedding.embed_query(request.query)
    dense_hits = await store.search_vectors(
        vector,
        top_k=candidate_count,
        allow_synthetic=allow_synthetic,
    )
    dense_ranked = [
        hit
        for hit in dense_hits
        if _evidence_from_dense(hit, allow_synthetic=allow_synthetic) is not None
    ]

    if method == "dense":
        result_items: list[Evidence] = []
        trace: list[dict[str, object]] = []
        for rank, hit in enumerate(dense_ranked, start=1):
            item = _evidence_from_dense(hit, allow_synthetic=allow_synthetic)
            if item is None:
                continue
            result_items.append(item)
            trace.append(
                {
                    "chunkId": hit.chunk_id,
                    "denseRank": rank,
                    "cosineScore": item.score,
                }
            )
        return SearchResult(tuple(result_items[: request.top_k])), trace

    corpus = await _published_chunks(store, allow_synthetic=allow_synthetic)
    if not corpus:
        return SearchResult(()), []

    tokenized_corpus = [tokenize(item.text) for item in corpus]
    if not any(tokenized_corpus):
        return SearchResult(()), []
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(tokenize(request.query))
    bm25_ranked = [
        (index, float(score))
        for index, score in enumerate(bm25_scores)
        if math.isfinite(float(score)) and float(score) > 0
    ]
    bm25_ranked.sort(key=lambda item: (-item[1], corpus[item[0]].chunk_id))
    bm25_ranked = bm25_ranked[:candidate_count]

    dense_ranks = {hit.chunk_id: rank for rank, hit in enumerate(dense_ranked, start=1)}
    bm25_ranks = {
        corpus[index].chunk_id: (rank, score)
        for rank, (index, score) in enumerate(bm25_ranked, start=1)
    }
    chunks_by_id = {item.chunk_id: item for item in corpus}
    candidate_ids = set(dense_ranks) | set(bm25_ranks)
    rrf_scores: dict[str, float] = {}
    for chunk_id in candidate_ids:
        score = 0.0
        if chunk_id in dense_ranks:
            score += 1.0 / (RRF_K + dense_ranks[chunk_id])
        if chunk_id in bm25_ranks:
            score += 1.0 / (RRF_K + bm25_ranks[chunk_id][0])
        rrf_scores[chunk_id] = score

    sorted_ids = sorted(candidate_ids, key=lambda chunk_id: (-rrf_scores[chunk_id], chunk_id))
    result_items = []
    trace = []
    for rrf_rank, chunk_id in enumerate(sorted_ids, start=1):
        row = chunks_by_id[chunk_id]
        item = _evidence(chunk_id, row.text, row.metadata, rrf_scores[chunk_id])
        if item is None:
            continue
        result_items.append(item)
        bm25_rank = bm25_ranks.get(chunk_id)
        trace.append(
            {
                "chunkId": chunk_id,
                "rrfRank": rrf_rank,
                "denseRank": dense_ranks.get(chunk_id),
                "bm25Rank": bm25_rank[0] if bm25_rank else None,
                "bm25Score": bm25_rank[1] if bm25_rank else None,
                "rrfScore": rrf_scores[chunk_id],
            }
        )
    return SearchResult(tuple(result_items)), trace
