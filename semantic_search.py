"""Catalog-grounded semantic search with optional external embeddings.

External mode uses an OpenAI-compatible embeddings endpoint when credentials are
configured. Otherwise a transparent local lexical/intent fallback remains usable.
No provider key is ever returned to the browser.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Any, Callable

DEFAULT_MODEL = os.environ.get("LIBRAAI_EMBEDDINGS_MODEL", "text-embedding-3-small")
DEFAULT_BASE_URL = os.environ.get("LIBRAAI_EMBEDDINGS_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MAX_EXTERNAL_BOOKS = max(1, min(250, int(os.environ.get("LIBRAAI_SEMANTIC_MAX_BOOKS", "150"))))

# Small concept map for useful results when external credentials are not set.
CONCEPTS = {
    "romance": {"romance", "romantic", "love", "love story", "relationship", "heartbreak", "প্রেম", "রোমান্স", "ভালোবাসা"},
    "mystery": {"mystery", "detective", "crime", "investigation", "clue", "রহস্য", "গোয়েন্দা"},
    "thriller": {"thriller", "suspense", "tension", "psychological", "fast paced", "রোমাঞ্চ", "সাসপেন্স"},
    "fantasy": {"fantasy", "magic", "magical", "dragon", "myth", "জাদু", "কল্পনা"},
    "science fiction": {"science fiction", "sci-fi", "scifi", "space", "future", "technology", "বিজ্ঞান কল্পকাহিনি"},
    "horror": {"horror", "scary", "ghost", "haunted", "supernatural", "ভৌতিক", "ভয়"},
    "self help": {"self help", "self-help", "personal growth", "habits", "motivation", "productivity", "আত্মউন্নয়ন"},
    "history": {"history", "historical", "ancient", "war", "ইতিহাস"},
    "adventure": {"adventure", "journey", "quest", "exploration", "অভিযান"},
    "business": {"business", "entrepreneurship", "startup", "leadership", "marketing", "ব্যবসা"},
    "psychology": {"psychology", "mind", "behavior", "mental models", "মানসিকতা", "মনোবিজ্ঞান"},
}
STOP_WORDS = set("a an the and or but to for of in on with from by is are was were be been being i me my we our you your like love enjoy want looking find recommend suggest book books read reading about that this something type kind very really please ami amar amar jonno chai porte valo bhalobashi pochondo ekta kichu dhoroner er theke".split())


def _text(book: dict[str, Any]) -> str:
    parts = [book.get(k) for k in ("title", "author", "genre", "description", "language", "format", "isbn")]
    return " ".join(str(p).strip() for p in parts if p not in (None, ""))[:5000]


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[\w\u0980-\u09FF]+", str(text).casefold()) if len(t) > 1 and t not in STOP_WORDS]


def _expanded_tokens(text: str) -> set[str]:
    tokens = set(_tokens(text))
    folded = str(text).casefold()
    for concept, aliases in CONCEPTS.items():
        if any(alias in folded for alias in aliases):
            tokens.update(_tokens(concept))
            for alias in aliases:
                tokens.update(_tokens(alias))
    return tokens


def _local_score(query: str, book: dict[str, Any], docs: list[dict[str, Any]]) -> float:
    qtokens = _expanded_tokens(query)
    title = set(_tokens(book.get("title", "")))
    author = set(_tokens(book.get("author", "")))
    genre = set(_tokens(book.get("genre", "")))
    content = set(_tokens(_text(book)))
    if not qtokens:
        return 0.0
    # BM25-lite: rarity matters, with strong title/genre matches.
    doc_freq = Counter()
    for doc in docs:
        doc_freq.update(set(_tokens(_text(doc))))
    total_docs = max(1, len(docs))
    score = 0.0
    for token in qtokens:
        if token not in content:
            continue
        idf = math.log(1 + (total_docs - doc_freq.get(token, 0) + 0.5) / (doc_freq.get(token, 0) + 0.5))
        score += idf * (4 if token in title else 2.8 if token in genre else 1.5 if token in author else 1)
    folded = query.casefold()
    for concept, aliases in CONCEPTS.items():
        if any(alias in folded for alias in aliases):
            if concept in str(book.get("genre", "")).casefold():
                score += 4.5
            if any(alias in _text(book).casefold() for alias in aliases):
                score += 1.2
    score += min(float(book.get("rating") or 0), 5) * 0.025
    return score


def _embedding_request(texts: list[str]) -> list[list[float]]:
    key = os.environ.get("LIBRAAI_EMBEDDINGS_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("External embeddings are not configured")
    body = json.dumps({"model": DEFAULT_MODEL, "input": texts, "encoding_format": "float"}).encode("utf-8")
    req = urllib.request.Request(
        f"{DEFAULT_BASE_URL}/embeddings", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise RuntimeError("Embeddings provider returned an unexpected response")
    data.sort(key=lambda item: int(item.get("index", 0)))
    vectors = [item.get("embedding") for item in data]
    if not all(isinstance(v, list) and v and all(isinstance(n, (int, float)) for n in v) for v in vectors):
        raise RuntimeError("Embeddings provider returned invalid vectors")
    return vectors


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _external_rank(query: str, books: list[dict[str, Any]], connect: Callable[[], Any]) -> list[tuple[float, dict[str, Any]]]:
    if not books:
        return []
    model = DEFAULT_MODEL
    conn = connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS semantic_embeddings (book_id INTEGER NOT NULL, model TEXT NOT NULL, fingerprint TEXT NOT NULL, embedding_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(book_id, model))")
        conn.execute("CREATE TABLE IF NOT EXISTS semantic_query_embeddings (query_hash TEXT NOT NULL, model TEXT NOT NULL, embedding_json TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(query_hash, model))")
        ids = [int(b["id"]) for b in books if b.get("id") is not None]
        cache_rows = {}
        if ids:
            marks = ",".join("?" for _ in ids)
            for row in conn.execute(f"SELECT book_id,fingerprint,embedding_json FROM semantic_embeddings WHERE model=? AND book_id IN ({marks})", [model, *ids]).fetchall():
                cache_rows[int(row[0])] = (row[1], row[2])
        missing = []
        for book in books:
            if book.get("id") is None:
                continue
            fp = _fingerprint(_text(book))
            cached = cache_rows.get(int(book["id"]))
            if not cached or cached[0] != fp:
                missing.append((book, fp))
        # Batch small chunks to keep provider requests bounded.
        for offset in range(0, len(missing), 32):
            batch = missing[offset:offset + 32]
            vectors = _embedding_request([_text(b) for b, _ in batch])
            for (book, fp), vector in zip(batch, vectors):
                conn.execute("INSERT INTO semantic_embeddings(book_id,model,fingerprint,embedding_json,updated_at) VALUES(?,?,?,?,CURRENT_TIMESTAMP) ON CONFLICT(book_id,model) DO UPDATE SET fingerprint=excluded.fingerprint,embedding_json=excluded.embedding_json,updated_at=CURRENT_TIMESTAMP", (int(book["id"]), model, fp, json.dumps(vector, separators=(",", ":"))))
                cache_rows[int(book["id"])] = (fp, json.dumps(vector, separators=(",", ":")))
        query_hash = _fingerprint(query.strip().casefold())
        cached_query = conn.execute("SELECT embedding_json FROM semantic_query_embeddings WHERE query_hash=? AND model=?", (query_hash, model)).fetchone()
        if cached_query:
            query_vector = json.loads(cached_query[0])
        else:
            query_vector = _embedding_request([query])[0]
            conn.execute("INSERT INTO semantic_query_embeddings(query_hash,model,embedding_json) VALUES(?,?,?) ON CONFLICT(query_hash,model) DO UPDATE SET embedding_json=excluded.embedding_json,updated_at=CURRENT_TIMESTAMP", (query_hash, model, json.dumps(query_vector, separators=(",", ":"))))
        conn.commit()
        def cosine(a: list[float], b: list[float]) -> float:
            if len(a) != len(b):
                return 0.0
            dot = sum(float(x) * float(y) for x, y in zip(a, b))
            na = math.sqrt(sum(float(x) * float(x) for x in a))
            nb = math.sqrt(sum(float(y) * float(y) for y in b))
            return dot / (na * nb) if na and nb else 0.0
        scored = []
        for book in books:
            cached = cache_rows.get(int(book["id"])) if book.get("id") is not None else None
            if not cached:
                continue
            try:
                vector = json.loads(cached[1])
                score = cosine(query_vector, vector)
                # Stable tie-breaks without overwhelming semantic relevance.
                score += min(float(book.get("rating") or 0), 5) * 0.001
                scored.append((score, book))
            except (ValueError, TypeError):
                continue
        if len(scored) >= min(1, len(books)):
            return scored
        raise RuntimeError("Could not score the catalog with embeddings")
    finally:
        conn.close()


def rank_books(query: str, books: list[dict[str, Any]], connect: Callable[[], Any] | None = None, limit: int = 10) -> dict[str, Any]:
    """Rank only supplied catalog records; returns mode and grounded book records."""
    safe_query = str(query or "").strip()[:500]
    candidates = books[:MAX_EXTERNAL_BOOKS]
    if not safe_query or not candidates:
        return {"mode": "local_semantic_fallback", "results": []}
    mode = "local_semantic_fallback"
    ranked: list[tuple[float, dict[str, Any]]] = []
    key = os.environ.get("LIBRAAI_EMBEDDINGS_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key and connect:
        try:
            ranked = _external_rank(safe_query, candidates, connect)
            mode = "external_embeddings"
        except Exception:
            # Provider, timeout, cache/database or response-shape failures fall back
            # to local ranking instead of making catalog search unavailable.
            ranked = []
    if not ranked:
        ranked = [(_local_score(safe_query, book, candidates), book) for book in candidates]
        # Keep meaningful matches only; broad semantic prompts may use all ranked catalog items.
        ranked = [pair for pair in ranked if pair[0] > 0]
    ranked.sort(key=lambda pair: (pair[0], float(pair[1].get("rating") or 0), str(pair[1].get("title") or "")), reverse=True)
    results = []
    for score, book in ranked[:max(1, min(20, int(limit)))]:
        item = dict(book)
        item["semantic_score"] = round(float(score), 5)
        results.append(item)
    return {"mode": mode, "results": results}
