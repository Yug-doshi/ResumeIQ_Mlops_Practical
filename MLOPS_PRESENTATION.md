# ResumeIQ MLOps: presentation and demonstration guide

This guide explains what the project implements, where to find the code, what
to demonstrate, and how to describe the outputs. It is written for a project
demo or viva.

## 1. Short project explanation

> “ResumeIQ is a resume-matching application with an MLOps support pipeline.
> The application uses a pretrained sentence-transformer to compare resumes
> with a job description. Docker Compose runs the app, MLflow records safe
> experiment information, Prometheus monitors API traffic, and GitHub Actions
> tests code and builds container images. The project demonstrates model
> inference and operations; it does not train or automatically retrain a
> model.”

The scores are matching estimates to help a human reviewer. They are not
probabilities of hiring success or evidence of real-world accuracy.

## 2. What “MLOps” means in this project

MLOps applies software engineering and operations practices to machine-learning
systems: packaging, repeatable evaluation, tracking, deployment, and
monitoring. Here is how those ideas map to this repository:

| MLOps concept | What this project does | Main implementation |
|---|---|---|
| Model inference | Loads a pretrained `sentence-transformers/all-MiniLM-L6-v2` model and computes semantic similarity. | `backend/app/services/semantic_matcher.py`, `backend/app/services/matching_service.py` |
| Reproducible packaging | Builds the backend and frontend as Docker images. | `backend/Dockerfile`, `frontend/Dockerfile` |
| Local orchestration | Starts the app, MLflow, Prometheus, and Grafana together with persistent named volumes. | `compose.yaml` |
| Experiment tracking | Logs model/scoring versions and aggregate matching metrics to MLflow, without resume text or candidate names. | `backend/mlops/tracking.py`, `backend/app/services/matching_service.py` |
| Model/ranking evaluation | Runs a small synthetic benchmark and calculates ranking measures. | `backend/mlops/run_evaluation.py`, `backend/mlops/evaluation.py` |
| Service monitoring and visualization | Exposes API request count and latency metrics; Prometheus scrapes them and Grafana displays them in a provisioned dashboard. | `backend/app/main.py`, `monitoring/prometheus.yml`, `monitoring/grafana/` |
| Continuous integration | Runs backend tests and builds the frontend for pushes to `main` and pull requests. | `.github/workflows/ci.yml` |
| Container publishing | Builds both images and publishes them to GHCR on pushes (not pull requests). | `.github/workflows/ci.yml` |

The project does **not** currently train or retrain a model, use DVC, run
Kubernetes, automatically promote models, or detect data/model
drift. MLflow is used for tracking, not as a model registry in this setup.

## 3. Architecture and request flow

```text
Recruiter
   |
   v
React frontend :8080
   |  POST /api/v1/match (job fields + PDF/DOCX resumes)
   v
FastAPI backend :8000
   |-- validate and parse files in memory
   |-- extract configured skills
   |-- pretrained transformer embeds job and resumes
   |-- score and rank candidates
   |-- send aggregate run details to MLflow :5000
   |
   +-- /metrics <--- Prometheus :9090 scrapes every 15 seconds
                         ^
                         | Grafana :3000 queries Prometheus
```

Docker Compose creates a private network, so services talk to each other by
their Compose service names. For example, the backend uses
`http://mlflow:5000`; the browser uses `http://localhost:8000`.

The matching flow is implemented in
[`matching_service.py`](backend/app/services/matching_service.py). The HTTP
endpoint is in [`matching.py`](backend/app/api/matching.py). The app uses a
configured weighted score (required skills, semantic similarity, and preferred
skills); its weights are in `backend/config/scoring.json`. The embedding model
is pretrained and used for inference: this repository does not contain a
training job.

## 4. Component-by-component explanation and evidence

### A. Docker and Docker Compose

**Concept:** Docker packages code and dependencies into images. Compose
connects the containers and gives the whole local stack one start command.
Named volumes keep selected data when containers stop.

**Code to show:**

- [`compose.yaml`](compose.yaml): service definitions, ports, environment
  variables, health check, and named volumes.
- [`backend/Dockerfile`](backend/Dockerfile): Python API image.
- [`frontend/Dockerfile`](frontend/Dockerfile): frontend build and Nginx image.

**Run:**

```powershell
docker compose up --build
```

In another terminal:

```powershell
docker compose ps
```

**What to show and say:**

- `resumeiq-frontend` serves the UI on `http://localhost:8080`.
- `resumeiq-backend` serves the API on `http://localhost:8000`.
- `resumeiq-mlflow` serves tracking/UI on `http://localhost:5000`.
- `resumeiq-prometheus` serves its query UI on `http://localhost:9090`.
- The MLflow health check must pass before Compose starts the backend.
- `model_cache`, `mlflow_data`, and `prometheus_data` are named volumes, so
  normal container stops do not remove their data.

`docker compose down` stops and removes the containers but preserves named
volumes. `docker compose down --volumes` also deletes those volumes, including
cached model and MLflow/Prometheus/Grafana data; use that only when you intend to erase
them.

### B. The ML model and inference

**Concept:** Inference means applying an already-trained model to new input.
This project embeds job and resume text and uses semantic similarity as part
of its ranking score.

**Code to show:**

- `backend/app/services/semantic_matcher.py`: loads and calls the embedding
  model.
- [`matching_service.py`](backend/app/services/matching_service.py): connects
  parsing, skill extraction, similarity, scoring, and ranking.
- `backend/config/scoring.json`: score weights.

**Demo:** In the frontend, enter a job description, add PDF/DOCX resumes, and
click **Analyze Resumes**. Or use `http://localhost:8000/docs` and try
`POST /api/v1/match`.

The app should show ranked candidates and score breakdowns. Explain that these
are similarity estimates, not hiring decisions. The model is downloaded on
first startup and cached in the `model_cache` volume; the backend health badge
shows whether it is ready.

### C. MLflow experiment tracking

**Concept:** Experiment tracking records which model/configuration was used
and numerical results, so runs can be inspected and compared later.

**Code to show:**

- [`tracking.py`](backend/mlops/tracking.py): configures MLflow and logs run
  parameters, tags, and numerical metrics.
- [`matching_service.py`](backend/app/services/matching_service.py): wraps
  each match operation and supplies aggregate values such as processed count,
  failed count, average score, and duration.
- `compose.yaml`: starts the MLflow server and directs the backend to it.

**Demo:**

1. Open `http://localhost:5000` and select **Experiments**.
2. Run a matching request in the application.
3. Refresh the experiment page and open the `ResumeIQ-Resume-Screening`
   experiment. A matching run should show model/scoring parameters and
   aggregate metrics.

The tracking code explicitly avoids logging resume text, filenames, candidate
names, or personal information. If MLflow is unavailable, the matching service
logs the tracking failure and continues matching rather than pretending a run
was recorded.

### D. Evaluation of ranking results

**Concept:** Evaluation compares the order produced by the system with known
relevance grades. It is separate from serving a real user request.

**Code to show:**

- [`run_evaluation.py`](backend/mlops/run_evaluation.py): creates synthetic
  DOCX resumes, sends them to the running API, and records metrics in MLflow.
- [`evaluation.py`](backend/mlops/evaluation.py): calculates Precision@k,
  Recall@k, MRR, and NDCG@k.
- `backend/tests/test_evaluation.py`: checks metric behavior on a known example.

**Run in PowerShell** while the Compose services are running:

```powershell
Push-Location backend
.\.venv\Scripts\Activate.ps1
python -m mlops.run_evaluation
Pop-Location
```

The terminal reports the model ID, scoring version, candidate ranking,
metrics, and the MLflow experiment name. The exact ranking and values depend
on the model and runtime. Open MLflow’s `ResumeIQ-Resume-Screening` experiment
to show the `synthetic-ranking-evaluation` run.

Metric meanings:

- **Precision@k:** fraction of the top-k results with grade 2 (highly relevant).
- **Recall@k:** fraction of all grade-2 candidates found in the top-k.
- **MRR:** reciprocal position of the first grade-2 candidate; earlier is
  better.
- **NDCG@k:** ranking quality that accounts for the graded relevance and
  rewards highly relevant candidates near the top.

**Important limitation:** The resumes and grades are synthetic examples made
for a pipeline smoke test. These numbers do not measure production accuracy,
fairness, or hiring outcomes. A real evaluation needs appropriately governed,
representative data and human-reviewed relevance labels.

### E. Prometheus monitoring

**Concept:** Prometheus periodically scrapes numerical metrics from services
and lets an operator query them. It monitors service behavior; it does not
measure model quality or detect model drift in this project.

**Code to show:**

- [`main.py`](backend/app/main.py): instruments HTTP request counts and request
  duration, and exposes `/metrics`.
- [`prometheus.yml`](monitoring/prometheus.yml): tells Prometheus to scrape
  `backend:8000/metrics` every 15 seconds.
- `backend/tests/test_metrics.py`: verifies the metrics endpoint and sample
  output.

**Demo:**

1. Open `http://localhost:9090`.
2. Enter `up` and click **Execute**. The backend target should show `1` once
   Prometheus has scraped it.
3. Enter `resumeiq_http_requests_total` and click **Execute**.
4. Make a request in ResumeIQ, wait up to one scrape interval, then run the
   query again.
5. Optionally enter:

```promql
rate(resumeiq_http_requests_total[5m])
```

It shows the approximate request rate over five minutes.

At `http://localhost:8000/metrics`, output includes series shaped like:

```text
resumeiq_http_requests_total{method="GET",route="/health",status="200"} 1.0
resumeiq_http_request_duration_seconds_count{method="GET",route="/health"} 1.0
```

Counts and durations depend on the requests made. The code uses route
templates, not query strings or raw request paths, to avoid exposing input and
creating a separate time series for every URL. Requests to `/metrics` itself
are excluded from these metrics.

### F. Grafana dashboards

**Concept:** Grafana queries a data source and turns time-series values into
charts and status panels. In this project, Prometheus remains the metrics
collector and storage layer; Grafana is the visualization layer.

**Code to show:**

- [`prometheus.yml`](monitoring/grafana/provisioning/datasources/prometheus.yml):
  provisions Prometheus as Grafana's default data source at
  `http://prometheus:9090` on the Compose network.
- [`dashboards.yml`](monitoring/grafana/provisioning/dashboards/dashboards.yml):
  configures automatic dashboard loading.
- [`resumeiq-api.json`](monitoring/grafana/dashboards/resumeiq-api.json):
  defines the dashboard panels and PromQL queries.
- `compose.yaml`: runs Grafana on host port 3000 and persists its state in
  `grafana_data`.

**Demo:**

1. Open `http://localhost:3000` and sign in with the initial local-demo
   credentials `admin` / `admin`; change the password if prompted.
2. Open **Dashboards → ResumeIQ → ResumeIQ API Monitoring**.
3. Show backend scrape status, total requests, request rate by route/status,
   p95 latency, and response rate by HTTP status.
4. Generate traffic via the frontend or
   `Invoke-RestMethod http://localhost:8000/health`. Wait for a Prometheus
   scrape and dashboard refresh to see new values.

The dashboard visualizes API/service metrics. It does not show model accuracy,
data drift, or hiring quality. Rate and latency panels may show no data until
there are enough Prometheus samples.

### G. GitHub Actions CI and container publishing

**Concept:** Continuous integration (CI) automatically checks changes. A
passing build can then produce deployable container images. This workflow
publishes images but does not deploy them to a server or Kubernetes.

**Code to show:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

It defines three jobs:

1. `backend-tests`: installs `backend/requirements-dev.txt` and runs
   `python -m pytest -q` with Python 3.11.
2. `frontend-build`: runs `npm ci` and `npm run build` with Node 20.
3. `publish-images`: waits for the first two jobs, builds backend and frontend
   images, and pushes them to GHCR on non-pull-request events.

The workflow runs for pull requests and pushes to `main`. Pull requests build
the images but do not publish them. Pushes publish images under
`ghcr.io/<owner>/<repository>/backend` and
`ghcr.io/<owner>/<repository>/frontend`, tagged with the branch and commit.

#### What is automated, in order

1. GitHub detects a push to `main` or a pull request.
2. It creates an Ubuntu runner and checks out the repository.
3. `backend-tests` installs the Python test dependencies and runs the offline
   test suite.
4. At the same time, `frontend-build` installs the locked npm dependencies and
   builds the React app.
5. `publish-images` waits for **both** jobs to pass (`needs`). It builds
   backend and frontend Docker images.
6. On a push event, it logs into GHCR with GitHub's temporary `GITHUB_TOKEN`
   and pushes branch/commit-tagged images. On a pull request, the image build
   still runs but `push` is false, and the login step is skipped.

This is CI plus container publishing (a small CD-related artifact step). It is
not automatic deployment: no VM, Kubernetes cluster, or production server is
updated by this workflow.

#### First-time setup: make the workflow run

The workflow must be committed and pushed to GitHub before GitHub can execute
it. In this workspace, `.github/workflows/ci.yml` and the supporting MLOps
changes are currently **local uncommitted changes**. The GitHub repository
currently reports no Actions workflow or runs, so there is not yet a live run
to show. Do not use `git add .` blindly: inspect `git status` and stage only the
intended project files; local database and backup files should not be included.

After committing the intended workflow and its required application/Docker
files, push to `main`. For example, if you have reviewed and staged the
intended files:

```powershell
git status
git commit -m "Add MLOps CI and container publishing"
git push origin main
```

The push to `main` starts the first live run. GitHub Actions and package
publishing must be enabled/allowed for the repository. If the run fails, open
the failed job and read the first error in its logs; do not treat a workflow
file sitting on your computer as proof that GitHub ran it.

#### Live demo for a presentation

For the first run:

1. Open `https://github.com/Yug-doshi/MLOPS_Project`.
2. Click **Actions**.
3. Select **MLOps CI** in the workflow list and open the newest run. The event
   should say `push` and the branch should be `main`.
4. Show the two parallel checks: `backend-tests` and `frontend-build`.
5. Show `publish-images` starting only after both checks are green.
6. Open the publish job logs. Explain that the build steps create images and,
   for a push to `main`, push tags to GHCR.
7. Open the repository **Packages** page to show published backend/frontend
   packages, if package visibility/settings permit them to be displayed.

For the repeatable pull-request demo, create a feature branch, push it, and
open a PR targeting `main`. The PR run should test the backend, build the
frontend, and build both Docker images, but it must **not** push images to
GHCR. Merge the PR only after its checks pass; the resulting push to `main`
will run the publishing path.

#### What the output means

| Actions result | Meaning |
|---|---|
| Green check on `backend-tests` | The configured offline backend tests passed. |
| Green check on `frontend-build` | npm dependencies installed and the Vite production build succeeded. |
| Green check on `publish-images` | Both Docker builds succeeded; on `main`, the push steps also completed. |
| Red X | A step failed. Open the job, expand the failed step, and use the error text to identify the problem. |
| Yellow circle / queued | GitHub has not finished running that job yet. |
| Pull request: image build succeeds, no package is pushed | Expected: publish is disabled for pull-request events. |

To make the automation especially clear, point to `on` (triggers), the two
independent check jobs, `needs` (quality gate), and
`push: ${{ github.event_name != 'pull_request' }}` (prevents publishing
unreviewed PR images) in `.github/workflows/ci.yml`.

**Demo/evidence:** A local run does not create a GitHub Actions result. Use the
Actions page after the workflow has been pushed. GHCR publishing also depends
on repository Actions/package permissions.

## 5. Suggested live demo (about five minutes)

1. **Introduce the scope:** “This is inference plus MLOps operations; it does
   not train a model.”
2. **Show Compose:** run `docker compose ps` and point out the five services.
3. **Show the app:** submit a job description and sample resumes; explain the
   ranking output.
4. **Show MLflow:** open the experiment and the matching run created by that
   request.
5. **Show Prometheus:** query `up`, then
   `resumeiq_http_requests_total`.
6. **Show Grafana:** open **ResumeIQ → ResumeIQ API Monitoring** and point out
   the status, traffic, and latency panels.
7. **Show evaluation:** run `python -m mlops.run_evaluation` and explain its
   four ranking metrics and synthetic-data limitation.
8. **Show CI:** open the GitHub Actions run, if the workflow has been pushed.

## 6. Example presentation script

> “The frontend sends a matching request to the FastAPI backend. The backend
> validates and parses uploaded files in memory, uses the pretrained
> sentence-transformer for semantic similarity, combines that with configured
> skill scores, and returns a ranked list. Docker Compose runs the frontend,
> backend, MLflow, Prometheus, and Grafana together. MLflow records the model
> and scoring versions plus aggregate metrics. Prometheus scrapes HTTP request
> counts and latency every 15 seconds, and Grafana visualizes them. GitHub Actions runs tests and a frontend build, and
> builds container images; on a push to main it publishes them to GHCR. The
> benchmark uses synthetic resumes, so its metrics demonstrate that evaluation
> and logging work, not real-world hiring accuracy. This project uses a
> pretrained model for inference and does not include model training,
> retraining, drift detection, or Kubernetes deployment.”

## 7. URLs and commands at a glance

| Purpose | Address / command |
|---|---|
| Start all local services | `docker compose up --build` |
| Check containers | `docker compose ps` |
| ResumeIQ frontend | `http://localhost:8080` |
| API documentation | `http://localhost:8000/docs` |
| Liveness/readiness | `http://localhost:8000/health`, `http://localhost:8000/health/ready` |
| Raw Prometheus metrics | `http://localhost:8000/metrics` |
| Prometheus query page | `http://localhost:9090` |
| Grafana dashboards | `http://localhost:3000` (initial local login: `admin` / `admin`) |
| MLflow UI | `http://localhost:5000` |
| Stop services, retain data | `docker compose down` |
