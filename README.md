# ResumeIQ — Intelligent Resume Screening and Skill Matching

Phase 1 of an MLOps project: a working resume-screening application (React frontend + FastAPI backend).
MLflow, DVC, Airflow, Docker/Kubernetes, CI/CD and monitoring are **not** implemented yet; the code is
structured so they can be added later (see "Where MLOps plugs in").

```
resumeiq/
  backend/    FastAPI API, parsing, skill extraction, semantic model, scoring, tests
  frontend/   React + Vite recruiter UI
```

## How it works

1. The recruiter enters a job (title, description, required/preferred skills, optional experience/education).
2. They upload PDF/DOCX resumes. Files are validated (extension, size, real file signature) and parsed **in memory**.
3. Skills are found with a configurable dictionary (`backend/config/skills.json`) using boundary-aware matching.
4. `sentence-transformers/all-MiniLM-L6-v2` (pretrained, inference only) embeds the job and each resume; cosine similarity is the semantic score.
5. A transparent score is computed: **50% required skills + 35% semantic similarity + 15% preferred skills**
   (`backend/config/scoring.json`). If a group has no skills, its weight is redistributed and the UI says so.
   With no skills at all, the score is semantic similarity only, and this is stated.
6. Candidates are ranked; each has a breakdown, "found / not found in resume" skill lists and evidence excerpts.
7. Results can be exported to CSV (formula-injection safe).

Scores are **estimates of similarity to the job description**, not probabilities of hiring success. The tool assists a
human reviewer; it never accepts or rejects anyone, and it does not use names, photos or protected characteristics.

## Frontend ↔ backend connection

The frontend (`http://localhost:5173`) calls the backend (`http://localhost:8000`) with Axios (`frontend/src/services/api.js`).
The base URL comes from `VITE_API_BASE_URL`. The backend allows only the origins in `CORS_ORIGINS`.
`POST /api/v1/match` receives the job fields and resumes as `multipart/form-data`; the UI keeps the response in memory
(no browser storage) and the Export button posts the visible rows to `POST /api/v1/export/csv`.
The navbar badge polls `GET /health` to show whether the backend is up and the model is ready.

## Windows 11 setup (PowerShell, VS Code)

Prerequisites: Python 3.10–3.12, Node.js 18+ (LTS), internet access for the **first** run only (model download, ~90 MB).

### Backend
```powershell
cd resumeiq\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```
If activation is blocked: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.
The first start downloads the model into the Hugging Face cache; watch the console for "Semantic model ready".

### Frontend (second terminal)
```powershell
cd resumeiq\frontend
Copy-Item .env.example .env
npm install
npm run dev
```
Open http://localhost:5173.

### Useful URLs
| What | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API docs (Swagger) | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

### Try the API in Swagger
Open `/docs` → `POST /api/v1/match` → *Try it out*. Fill `job_title`, `job_description`, optional `required_skills`
(`Python, Docker` or a JSON array), choose one or more files for `resumes`, and *Execute*.

### Run the tests
```powershell
cd resumeiq\backend
.\.venv\Scripts\Activate.ps1
pytest                      # fast tests, mocked embedder, no download needed
pytest -m integration -s    # smoke test with the REAL model (needs the model files / internet once)
```

## API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + model readiness (always 200 while the process is up) |
| GET | `/health/ready` | Readiness probe: 200 only when the model is loaded, else 503 |
| GET | `/api/v1/model-info` | Model id/type, scoring config version, readiness |
| GET | `/api/v1/config` | Weights, supported formats, limits, skill dictionary version/hash |
| GET | `/api/v1/version` | App and API version |
| POST | `/api/v1/match` | Analyse resumes against a job |
| POST | `/api/v1/export/csv` | Build a CSV from results the client sends back (stateless) |

Errors always look like `{"error": {"code": "...", "message": "..."}}`:
422 invalid input (`invalid_job`, `job_description_too_short`, `no_files`, `too_many_files`), 413 `request_too_large`,
503 `model_unavailable`, 500 `internal_error` (no stack traces are returned).
Per-file problems (`unsupported_file_type`, `file_too_large`, `file_type_mismatch`, `corrupted_file`, `encrypted_file`,
`empty_file`, `empty_document`, `no_extractable_text`, `insufficient_text`) are returned inside a normal 200 response in `errors`,
so valid resumes in the same request are still ranked.

### Example: `POST /api/v1/match`
```powershell
curl.exe -X POST http://localhost:8000/api/v1/match `
  -F "job_title=ML Engineer" `
  -F "job_description=We need an engineer to build Python APIs and deploy ML models with Docker and Kubernetes." `
  -F "required_skills=Python, Docker, Kubernetes" `
  -F "preferred_skills=AWS" `
  -F "min_experience_years=3" `
  -F "resumes=@C:\resumes\alice.pdf" -F "resumes=@C:\resumes\bob.docx"
```
Response (abridged; values depend on the resumes and model):
```json
{
  "request_id": "9f2c1a7b3d40",
  "job": {"job_title": "ML Engineer", "required_skills": ["Python", "Docker", "Kubernetes"],
          "preferred_skills": ["AWS"], "min_experience_years": 3.0, "description_characters": 98},
  "model_id": "sentence-transformers/all-MiniLM-L6-v2",
  "scoring_version": "1.0.0",
  "summary": {"total_uploaded": 2, "processed": 2, "failed": 0, "candidates_with_results": 2, "average_score": 61.2},
  "candidates": [{
    "resume_id": "a1b2c3d4e5", "rank": 1, "upload_index": 0, "filename": "alice.pdf", "status": "processed",
    "score": 78.4, "semantic_score": 52.1, "semantic_cosine": 0.521,
    "required_matched": ["Python", "Docker"], "required_not_found": ["Kubernetes"],
    "preferred_matched": [], "preferred_not_found": ["AWS"],
    "extracted_skills": ["Python", "Docker", "Git"],
    "score_breakdown": {"final_score": 78.4, "scoring_version": "1.0.0", "notes": [],
      "components": [{"key": "required_skills", "score": 66.67, "effective_weight": 0.5, "contribution": 33.33, "available": true,
                      "label": "Required-skill coverage", "configured_weight": 0.5, "detail": "2 of 3 required skills found in resume"}]},
    "evidence": [{"skill": "Python", "snippet": "Built REST APIs in Python and FastAPI", "line": 4}],
    "experience": {"status": "mentions_found", "required_years": 3.0, "max_stated_years": 5.0, "mentions": [], "note": "..."},
    "warnings": [], "extracted_characters": 2310, "model_id": "sentence-transformers/all-MiniLM-L6-v2"
  }],
  "errors": [],
  "score_disclaimer": "Scores estimate how closely a resume matches the job description. ..."
}
```
(The numbers above are illustrative of the shape only; real responses are computed per request.)

## Configuration
`backend/.env` (see `.env.example`): origins, upload limits, model name, offline mode, config file paths.
`backend/config/scoring.json`: weights and semantic normalisation. `backend/config/skills.json`: skills, aliases,
case-sensitive terms (e.g. `ML`, `React`) — edit and restart.

## Security and privacy (prototype)
Implemented: extension + signature + size checks, DOCX zip-bomb guard, PDF page limit, in-memory processing, no file paths
from user filenames, nothing executed, no resume text in logs (counts and error codes only), generic error responses,
CORS restricted to configured origins, CSV formula-injection protection, e-mail/phone masking in evidence excerpts,
results held only in browser memory.

Caveats: Starlette may spool large multipart uploads to the OS temp directory while parsing the request (deleted afterwards).
This is **not** an authenticated multi-user system. Before real recruiters use it you need: authentication and per-user
authorization, TLS, encryption at rest for any stored data, a documented retention/deletion policy, audit logging,
rate limiting, malware scanning of uploads, a privacy/consent review (resumes are personal data), and bias/fairness
evaluation of the scoring approach.

## Limitations
- Scanned/image PDFs are rejected (no OCR yet; add one in `resume_parser.py`).
- Skill detection finds only configured skills; it cannot understand skill level or context.
- Semantic similarity splits long texts into chunks and averages their embeddings (up to about 5,400 words per document); it is a rough signal.
- Experience and education are shown for reviewers, not scored.
- Two-column or heavily designed PDFs may extract text in a different order.

## Where MLOps plugs in later (not implemented)
| Future component | Seam in this code |
|---|---|
| MLflow registry / versioned model | Implement another `EmbeddingBackend` (`services/semantic_matcher.py`) and pass it to `create_app(matcher=...)` |
| DVC / data versioning | `config/skills.json` and `config/scoring.json` are plain versioned files; `/api/v1/config` exposes version + SHA-256 |
| Evaluation / quality gates | `compute_score` and `SemanticMatcher` are pure, importable functions; `tests/` shows how to evaluate with a stub embedder |
| Docker / Kubernetes | Settings come from env vars; `/health` (liveness) and `/health/ready` (readiness) are ready for probes |
| Prometheus / Grafana / drift | Single orchestration point `MatchingService.run` (add metrics there); `request_id` and model/scoring versions are in every response |
| Airflow / retraining | Inference is isolated from training; the API never trains or downloads on a prediction request |
| CI/CD | `pytest` (fast, offline) and `pytest -m integration` (real model) are separate commands |

## Troubleshooting
- **`Cannot reach the ResumeIQ backend`** — start uvicorn; check `VITE_API_BASE_URL`; restart `npm run dev` after editing `.env`.
- **Browser CORS error** — add the exact origin to `CORS_ORIGINS` in `backend/.env` and restart the backend.
- **"Model not ready" / 503** — the model could not load. First run needs internet to download it. Check the backend console for the real error; behind a proxy set `HTTPS_PROXY`. After a successful download you can set `MODEL_LOCAL_FILES_ONLY=true`. The next analysis retries loading automatically.
- **Slow or huge `torch` install** — install the CPU build first: `pip install torch --index-url https://download.pytorch.org/whl/cpu`, then `pip install -r requirements-dev.txt`.
- **`pip` build errors** — use Python 3.10–3.12 64-bit and upgrade pip.
- **Port in use** — `uvicorn app.main:app --port 8001` and update `VITE_API_BASE_URL`; port 5173 is fixed (`strictPort`), add the new origin to CORS if you change it.
- **`npm install` fails** — use Node 18+; delete `node_modules` and retry.
- **Everything is "failed: no_extractable_text"** — the PDFs are scans; use text-based PDFs or DOCX.
