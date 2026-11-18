"""Embedding providers.

hash   - offline, deterministic bag-of-words hashing. No API key needed; good
         enough for keyword-style retrieval in development and tests.
openai - OpenAI embeddings API (text-embedding-3-small is 1536-dim).
"""
import hashlib
import math
import re
from typing import Protocol

import httpx

from app.config import get_settings

STOPWORDS = set(
    "a an and are as at be been by for from had has have in into is it its of on or that the this to was were "
    "with after before during about over under than then there their they them which while also any all not no "
    "only same other per each".split()
)


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _stem(word: str) -> str:
    for suffix in ("ings", "ing", "ies", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


class HashEmbedder:
    name = "hash"

    def __init__(self, dim: int):
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = tokenize(text)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        counts: dict[str, int] = {}
        for f in features:
            counts[f] = counts.get(f, 0) + 1
        for feat, c in counts.items():
            h = int.from_bytes(hashlib.md5(feat.encode()).digest()[:8], "big")
            idx = h % self.dim
            sign = 1.0 if (h >> 63) & 1 else -1.0
            weight = (1.0 + math.log(c)) * (0.7 if "_" in feat else 1.0)
            vec[idx] += sign * weight
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class OpenAIEmbedder:
    name = "openai"

    def __init__(self, api_key: str, model: str, dim: int):
        self.api_key, self.model, self.dim = api_key, model, dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = httpx.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts, "dimensions": self.dim},
            timeout=60,
        )
        resp.raise_for_status()
        return [d["embedding"] for d in sorted(resp.json()["data"], key=lambda d: d["index"])]


def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "openai":
        if not s.openai_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai needs OPENAI_API_KEY")
        return OpenAIEmbedder(s.openai_api_key, s.embedding_model, s.embedding_dim)
    return HashEmbedder(s.embedding_dim)
