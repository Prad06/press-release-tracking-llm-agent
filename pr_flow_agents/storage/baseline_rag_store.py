"""Chroma-backed store for baseline summary chunks."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pr_flow_agents.storage.config import (
    get_chroma_baseline_collection,
    get_chroma_persist_directory,
)

try:
    import chromadb
except Exception:  # noqa: BLE001
    chromadb = None


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class BaselineRagStore:
    """Persist chunked baseline summaries into a Chroma collection."""

    def __init__(
        self,
        *,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        chunk_chars: int = 800,
        overlap_chars: int = 120,
        embedding_dim: int = 256,
    ) -> None:
        self._persist_directory = Path(persist_directory or get_chroma_persist_directory())
        self._collection_name = str(collection_name or get_chroma_baseline_collection()).strip()
        self._chunk_chars = max(200, int(chunk_chars))
        self._overlap_chars = max(0, min(int(overlap_chars), self._chunk_chars - 1))
        self._embedding_dim = max(32, int(embedding_dim))
        self._client = None
        self._collection = None

    def _get_collection(self):
        if chromadb is None:
            raise RuntimeError("chromadb is not installed. Add chromadb to requirements and reinstall dependencies.")
        if self._collection is None:
            self._persist_directory.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self._persist_directory))
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def ingest_release_summary(
        self,
        *,
        ticker: str,
        press_release_id: str,
        press_release_title: str,
        press_release_timestamp: str,
        summary_scope: str,
        summary_text: str,
        fiscal_year: Optional[int] = None,
        fiscal_quarter: Optional[str] = None,
    ) -> int:
        scope = str(summary_scope or "").strip().upper()
        if scope not in {"COMPANY", "QUARTERLY"}:
            raise ValueError("summary_scope must be COMPANY or QUARTERLY")

        raw = str(summary_text or "").strip()
        if not raw:
            return 0

        chunks = _chunk_text(raw, chunk_chars=self._chunk_chars, overlap_chars=self._overlap_chars)
        if not chunks:
            return 0

        collection = self._get_collection()
        where = {
            "$and": [
                {"press_release_id": {"$eq": str(press_release_id)}},
                {"summary_scope": {"$eq": scope}},
            ]
        }
        collection.delete(where=where)

        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []
        embeds: List[List[float]] = []

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{press_release_id}:{scope}:{idx:03d}"
            ids.append(chunk_id)
            docs.append(chunk)
            metas.append(
                {
                    "ticker": str(ticker).upper(),
                    "press_release_id": str(press_release_id),
                    "press_release_title": str(press_release_title or ""),
                    "press_release_timestamp": str(press_release_timestamp or ""),
                    "summary_scope": scope,
                    "fiscal_year": int(fiscal_year) if fiscal_year is not None else -1,
                    "fiscal_quarter": str(fiscal_quarter or ""),
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                }
            )
            embeds.append(_hash_embedding(chunk, dim=self._embedding_dim))

        collection.upsert(ids=ids, embeddings=embeds, metadatas=metas, documents=docs)
        return len(ids)


def _chunk_text(text: str, *, chunk_chars: int, overlap_chars: int) -> List[str]:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return []
    if len(cleaned) <= chunk_chars:
        return [cleaned]

    chunks: List[str] = []
    step = max(1, chunk_chars - overlap_chars)
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_chars)
        window = cleaned[start:end]
        if end < len(cleaned):
            split_at = window.rfind(" ")
            if split_at > max(40, chunk_chars // 3):
                window = window[:split_at]
                end = start + split_at
        chunk = window.strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = min(len(cleaned), end - overlap_chars)
        if start <= 0:
            start += step
    return chunks


def _hash_embedding(text: str, *, dim: int) -> List[float]:
    vec = [0.0] * dim
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return vec
    return [v / norm for v in vec]
