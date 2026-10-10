"""Semantic similarity using a pretrained sentence-embedding model.

The model is behind the small ``EmbeddingBackend`` interface. Today the only
backend loads ``sentence-transformers/all-MiniLM-L6-v2`` from the Hugging Face
cache. A later phase can add a backend that loads a versioned artifact (for
example from an MLflow registry) without touching the API or scoring code.

This module only does inference; it never trains or fine-tunes.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional, Protocol, Sequence

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.exceptions import ModelUnavailableError

logger = logging.getLogger(__name__)


class EmbeddingBackend(Protocol):
    model_id: str

    def load(self) -> None: ...

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return an (n, d) float array of L2-normalised embeddings."""
        ...


class SentenceTransformerBackend:
    def __init__(self, model_id: str, cache_dir: Optional[str] = None, local_files_only: bool = False,
                 batch_size: int = 32):
        self.model_id = model_id
        self._cache_dir = cache_dir
        self._local_files_only = local_files_only
        self._batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def load(self) -> None:
        from sentence_transformers import SentenceTransformer  # imported lazily: heavy

        kwargs = {}
        if self._cache_dir:
            kwargs["cache_folder"] = self._cache_dir
        if self._local_files_only:
            kwargs["local_files_only"] = True
        self._model = SentenceTransformer(self.model_id, device="cpu", **kwargs)

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Model is not loaded")
        with self._lock:
            return np.asarray(
                self._model.encode(
                    list(texts),
                    batch_size=self._batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
            )


def chunk_words(text: str, words_per_chunk: int, max_chunks: int) -> list[str]:
    """Split text into word windows so long resumes are not silently truncated by the model."""
    words = text.split()
    if not words:
        return []
    chunks = [" ".join(words[i : i + words_per_chunk]) for i in range(0, len(words), words_per_chunk)]
    return chunks[:max_chunks]


class SemanticMatcher:
    """Loads the model once and scores resumes against a job description."""

    def __init__(self, backend: EmbeddingBackend, words_per_chunk: int = 180, max_chunks: int = 30):
        self._backend = backend
        self._words_per_chunk = words_per_chunk
        self._max_chunks = max_chunks
        self._lock = threading.Lock()
        self._status = "not_loaded"  # not_loaded | loading | ready | failed
        self._error_code: Optional[str] = None

    @property
    def model_id(self) -> str:
        return self._backend.model_id

    @property
    def status(self) -> str:
        return self._status

    @property
    def is_ready(self) -> bool:
        return self._status == "ready"

    @property
    def error_code(self) -> Optional[str]:
        return self._error_code

    def load(self) -> None:
        """Load the model once. Raises ``ModelUnavailableError`` on failure (never fakes scores)."""
        with self._lock:
            if self._status == "ready":
                return
            self._status = "loading"
            try:
                self._backend.load()
            except Exception:
                # Full details go to the server log; clients only get a generic message.
                logger.exception("Semantic model failed to load (model_id=%s)", self._backend.model_id)
                self._status = "failed"
                self._error_code = "model_load_failed"
                raise ModelUnavailableError(
                    "The semantic model could not be loaded. If this is the first run, the model files must be "
                    "downloaded once with an internet connection. See the backend README troubleshooting section."
                )
            self._status = "ready"
            self._error_code = None
            logger.info("Semantic model ready (model_id=%s)", self._backend.model_id)

    def ensure_loaded(self) -> None:
        if not self.is_ready:
            self.load()

    def _embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        """One mean-pooled, re-normalised embedding per document (chunked, single batch call)."""
        chunk_lists = [chunk_words(t, self._words_per_chunk, self._max_chunks) for t in texts]
        flat = [c for chunks in chunk_lists for c in chunks]
        if not flat:
            raise ValueError("No text to embed")
        vectors = self._backend.encode(flat)
        out = []
        cursor = 0
        for chunks in chunk_lists:
            if not chunks:
                out.append(np.zeros(vectors.shape[1], dtype=float))
                continue
            pooled = vectors[cursor : cursor + len(chunks)].mean(axis=0)
            cursor += len(chunks)
            norm = np.linalg.norm(pooled)
            out.append(pooled / norm if norm > 0 else pooled)
        return np.vstack(out)

    def calculate_semantic_similarity(self, job_description: str, resume_texts: Sequence[str]) -> list[float]:
        """Return one cosine similarity (in [-1, 1]) per resume text, in the same order."""
        if not job_description or not job_description.strip():
            raise ValueError("job_description must not be empty")
        if not resume_texts:
            return []
        self.ensure_loaded()
        try:
            vectors = self._embed_documents([job_description, *resume_texts])
        except ValueError:
            raise
        except Exception:
            logger.exception("Semantic inference failed")
            raise ModelUnavailableError("Semantic similarity could not be computed.")
        scores = cosine_similarity(vectors[:1], vectors[1:])[0]
        return [float(s) for s in scores]
