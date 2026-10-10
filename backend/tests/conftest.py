import io
import re
import zlib
from typing import Sequence

import numpy as np
import pymupdf
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services.semantic_matcher import SemanticMatcher

DIM = 256

PYTHON_RESUME = (
    "Senior engineer with 6 years of experience building REST APIs in Python and FastAPI.\n"
    "Deployed services with Docker and Kubernetes on AWS using CI/CD pipelines.\n"
    "Trained machine learning models with scikit-learn and PyTorch.\n"
    "Contact: jane.doe@example.com +1 415 555 0134"
)
JAVA_RESUME = (
    "Backend developer experienced with Java and SQL databases.\n"
    "Worked with JavaScript front ends and GitHub for source control.\n"
    "Built reporting dashboards for the finance team over four years."
)
JOB_DESCRIPTION = (
    "We are hiring a machine learning engineer to build Python APIs, deploy them with Docker "
    "and Kubernetes and maintain CI/CD pipelines on AWS."
)


class FakeBackend:
    """Deterministic bag-of-words embedder so tests never download the real model."""

    model_id = "fake/bag-of-words"

    def __init__(self, fail_load: bool = False):
        self.fail_load = fail_load
        self.load_calls = 0
        self.encode_batches = []

    def load(self) -> None:
        self.load_calls += 1
        if self.fail_load:
            raise RuntimeError("cannot reach hub from /secret/path")

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        self.encode_batches.append(len(texts))
        out = np.zeros((len(texts), DIM))
        for i, text in enumerate(texts):
            for token in re.findall(r"[a-z0-9+#]+", text.lower()):
                out[i, zlib.crc32(token.encode()) % DIM] += 1
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in text.split("\n"):
        page.insert_text((50, y), line, fontsize=9)
        y += 14
    data = doc.tobytes()
    doc.close()
    return data


def make_blank_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def make_docx(text: str) -> bytes:
    document = Document()
    for line in text.split("\n"):
        document.add_paragraph(line)
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


@pytest.fixture
def settings():
    return Settings(_env_file=None, preload_model=True, max_file_size_mb=1.0, max_files_per_request=5)


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def client(settings, backend):
    app = create_app(settings, SemanticMatcher(backend))
    with TestClient(app) as test_client:
        yield test_client


def form(**overrides):
    data = {
        "job_title": "ML Engineer",
        "job_description": JOB_DESCRIPTION,
        "required_skills": "Python, Docker, Kubernetes",
        "preferred_skills": "Airflow, AWS",
    }
    data.update(overrides)
    return data


def files(*items):
    """items: (filename, bytes) -> multipart list for the `resumes` field."""
    return [("resumes", (name, content, "application/octet-stream")) for name, content in items]
