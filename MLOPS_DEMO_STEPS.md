# ResumeIQ MLOps Demo: Step-by-Step Presentation Runbook

Use this checklist to demonstrate the project's MLOps workflow. It includes
the commands to run, the pages to open, what output to point at, and what to
say. This is a local demo plus GitHub Actions; it does not require Kubernetes.

## Before the presentation

### Requirements

- Windows with Docker Desktop running.
- PowerShell opened in the repository root (the folder containing `compose.yaml`).
- Internet access for initial Docker image and pretrained model downloads.
- For the GitHub Actions section: the workflow must already be pushed to GitHub.
- A sample PDF or DOCX resume for the frontend upload. Use synthetic or
  consented demo data, not a real person's resume.

### Verify the repository folder

Run this in PowerShell:

```powershell
Get-Location
Test-Path .\compose.yaml
Test-Path .\.github\workflows\ci.yml
```

Both `Test-Path` commands should print `True`.

## Demo 1: Start the complete local MLOps stack

From the repository root:

```powershell
docker compose up --build -d
```

This builds the app images if needed and starts five services in the
background. Check their status:

```powershell
docker compose ps
```

Expect services named `resumeiq-frontend`, `resumeiq-backend`,
`resumeiq-mlflow`, `resumeiq-prometheus`, and `resumeiq-grafana` to be running.
The backend loads the pretrained model at startup. The first start can take
several minutes; later starts should be faster because the model is kept in a
named Docker volume.

Check that the model is ready:

```powershell
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $health = Invoke-RestMethod http://localhost:8000/health
        if ($health.ready) {
            $ready = $true
            break
        }
    } catch {
        # The API may still be starting.
    }
    Start-Sleep -Seconds 2
}
if (-not $ready) {
    throw "Backend/model did not become ready. Inspect: docker compose logs backend"
}
$health
```

Expected: `ready` is `True` and the model status is `ready`.

**Say:** “Docker Compose runs the user interface, inference API, experiment
tracker, and monitoring service together. The model is pretrained; this
application runs inference and does not train it.”

## Demo 2: Show the resume-matching application

Open these pages in a browser:

| Component | URL |
|---|---|
| ResumeIQ frontend | http://localhost:8080 |
| FastAPI Swagger/API documentation | http://localhost:8000/docs |
| Backend health | http://localhost:8000/health |
| Grafana dashboards | http://localhost:3000 |

On the frontend:

1. Enter a job title and a job description of at least 20 characters.
2. Add required skills, for example `Python, FastAPI, Docker`.
3. Optionally add preferred skills, for example `PostgreSQL, pytest`.
4. Upload a sample PDF or DOCX resume.
5. Click **Analyze Resumes**.
6. Show the ranked results and score breakdown.

The input can also be tested from Swagger at `/docs` using
`POST /api/v1/match`.

**Point out:** The API parses resumes in memory, uses the pretrained
sentence-transformer for semantic similarity, combines that with configured
skill scores, and returns a ranking for human review. Scores are not
probabilities of hiring success and should not be presented as automated
hiring decisions.

If you do not have a sample resume, the synthetic benchmark in Demo 6 still
creates DOCX files and exercises this endpoint.

## Demo 3: Show MLflow experiment tracking

Open:

```text
http://localhost:5000
```

Then:

1. Click **Experiments**.
2. Open `ResumeIQ-Resume-Screening`.
3. Show a `resume-matching` run created after the frontend analysis.
4. Point at model/scoring configuration and aggregate metrics such as counts,
   average score, and duration.

If the run is not visible yet, refresh after making a successful frontend
request. The MLflow database is persisted in the `mlflow_data` Docker volume.

**Say:** “MLflow gives us a history of which model and scoring configuration
was used and safe aggregate measurements. The tracking code deliberately does
not log resume contents, filenames, or candidate names.”

Relevant code: `backend/mlops/tracking.py` and
`backend/app/services/matching_service.py`.

## Demo 4: Show Prometheus monitoring

### Verify Prometheus can scrape the API

Open http://localhost:9090. In the expression field:

1. Enter `up`.
2. Click **Execute**.
3. Find the `resumeiq-backend` target. A value of `1` means the last scrape
   succeeded.

Prometheus scrapes the API every 15 seconds, configured in
`monitoring/prometheus.yml`.

### Show API request metrics

Make one request to the health endpoint from PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Then visit http://localhost:8000/metrics and point out lines similar to:

```text
resumeiq_http_requests_total{method="GET",route="/health",status="200"} 1.0
resumeiq_http_request_duration_seconds_count{method="GET",route="/health"} 1.0
```

The values increase as requests are served; they will differ on your run.

Back at http://localhost:9090, run:

```promql
resumeiq_http_requests_total
```

Optionally show recent request rate:

```promql
rate(resumeiq_http_requests_total[5m])
```

**Say:** “Prometheus measures API traffic and request duration. These are
service-health metrics, not measures of model accuracy or model drift. Labels
use route templates, not raw URLs or user-provided values.”

Relevant code: `backend/app/main.py` and `monitoring/prometheus.yml`.

## Demo 5: Show the Grafana dashboard

Open:

```text
http://localhost:3000
```

Sign in with the initial local-demo credentials `admin` / `admin` and change
the password if prompted. From **Dashboards**, open the **ResumeIQ** folder
and select **ResumeIQ API Monitoring**. Grafana provisions both the
Prometheus data source and dashboard from files, so you do not need to add a
data source or import a dashboard manually.

Show the panels:

- **Backend scrape status:** `UP` means Prometheus can scrape the backend.
- **Total API requests:** total counted requests since the backend started.
- **API request rate by route and status:** request traffic over time.
- **95th percentile API latency:** approximate p95 response time by route.
- **Response rate by HTTP status:** response traffic split by status.

Generate fresh samples by using the frontend or running
`Invoke-RestMethod http://localhost:8000/health`. Wait for the 15-second
Prometheus scrape interval. Rate and latency panels need enough samples, so
they may initially show “No data.”

Relevant files:

- `compose.yaml` (`grafana` service and `grafana_data` volume)
- `monitoring/grafana/provisioning/datasources/prometheus.yml`
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- `monitoring/grafana/dashboards/resumeiq-api.json`

Grafana visualizes Prometheus service metrics; it does not measure model
accuracy or detect model drift in this project.

## Demo 6: Run the synthetic ranking evaluation

Run in a **new** PowerShell terminal from the repository root while Docker
Compose remains running:

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m mlops.run_evaluation
Pop-Location
```

The script generates four synthetic DOCX resumes, submits them to the running
API, compares the ranked results with fixed synthetic grades, prints ranking
metrics, and records an evaluation run in MLflow.

Expect output containing:

- model ID and scoring version;
- ranked synthetic candidates and their reference grades;
- `precision_at_3`, `recall_at_3`, `mrr`, and `ndcg_at_3`;
- confirmation that the evaluation run was logged to MLflow.

The actual order and metric values depend on the runtime model and should not
be promised in advance. Return to MLflow and refresh
`ResumeIQ-Resume-Screening`; show the
`synthetic-ranking-evaluation` run and its metrics.

Metric explanation:

- **Precision@3:** fraction of the first three results graded highly relevant.
- **Recall@3:** fraction of all highly relevant examples found in the first
  three.
- **MRR:** rewards finding the first highly relevant result near the top.
- **NDCG@3:** evaluates ordering while accounting for relevance grades.

**Say:** “This demonstrates how we can evaluate and track ranking changes. The
examples and labels are synthetic, so these numbers prove the evaluation
pipeline runs; they are not real-world accuracy or fairness results.”

Relevant code: `backend/mlops/run_evaluation.py`,
`backend/mlops/evaluation.py`, and `backend/tests/test_evaluation.py`.

## Demo 7: Show automated tests and builds locally (optional)

The same basic checks can be run locally. From the repository root:

```powershell
Push-Location .\backend
.\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

Expect the offline backend tests to pass. The test suite uses a fake embedder
for fast tests; this command does not prove that GitHub Actions ran.

To build the frontend locally:

```powershell
Push-Location .\frontend
npm run build
Pop-Location
```

Expect Vite to report that the production build completed.

## Demo 8: Show GitHub Actions automation

### First check whether a live workflow exists

Open the GitHub repository:

```text
https://github.com/Yug-doshi/MLOPS_Project
```

Click **Actions**. If **MLOps CI** and a recent run are listed, open the newest
run and continue at “Present the run” below.

If no workflow/run is listed, GitHub has not run the local workflow yet. A
workflow file on the computer is not enough: GitHub must receive it in a push
or pull request.

### Publish the workflow for its first run

First inspect local changes:

```powershell
git status --short
```

Do **not** blindly use `git add .`. This project folder may contain local
SQLite databases or backup files. Stage only the intended application and
workflow files, after confirming their changes are yours and ready to share:

```powershell
git add README.md MLOPS_PRESENTATION.md MLOPS_DEMO_STEPS.md
git add .github\workflows\ci.yml compose.yaml monitoring\prometheus.yml
git add backend\Dockerfile backend\.dockerignore
git add backend\app\main.py backend\app\services\matching_service.py
git add backend\requirements.txt backend\mlops backend\tests\test_evaluation.py backend\tests\test_metrics.py
git add frontend\Dockerfile frontend\.dockerignore frontend\nginx.conf
```

Review exactly what will be committed:

```powershell
git diff --cached --check
git status --short
git diff --cached --stat
```

Do not commit `backend\.env`, `backend\mlflow.db`, root `mlflow.db`, or
`backend\app\services\matching_service.py.backup`. If the staged list includes
files you do not intend to publish, stop and review before committing.

Once satisfied, commit and push:

```powershell
git commit -m "Add MLOps CI and container publishing"
git push origin main
```

This push should trigger the workflow on GitHub. It can take a few minutes.
Open the repository's **Actions** tab and refresh until the `MLOps CI` run
appears. GitHub Actions/package publishing must be enabled for the repository.

### Present the run

1. Open the latest **MLOps CI** run and point out the triggering event and
   branch.
2. Show `backend-tests`: it installs Python dependencies and runs pytest.
3. Show `frontend-build`: it installs npm dependencies and runs the Vite
   production build.
4. Explain that `publish-images` has `needs: [backend-tests, frontend-build]`,
   so it waits for both quality checks to succeed.
5. Open `publish-images` and show the two Docker image build steps.
6. For a push to `main`, show the GHCR login/push steps and, if available, the
   repository's **Packages** page.

The workflow lives in `.github/workflows/ci.yml`. Highlight:

- `on`: the push-to-main and pull-request triggers;
- `backend-tests` and `frontend-build`: independent automated checks;
- `needs`: the quality gate before image building;
- `push: ${{ github.event_name != 'pull_request' }}`: images are not published
  from pull requests.

For a safe pull-request demonstration, push a feature branch and open a PR to
`main`. The checks and image builds should run, but package publishing should
not. A merge then produces a push to `main`, which enables publishing.

**Set expectations:** The workflow builds and publishes containers; it does
not deploy them to a server or Kubernetes.

## If something does not work

### View container status and logs

```powershell
docker compose ps
docker compose logs --tail 100 backend
docker compose logs --tail 100 mlflow
docker compose logs --tail 100 prometheus
```

If the model is still downloading, wait and check backend logs again:

```powershell
docker compose logs -f backend
```

Press `Ctrl+C` to stop following logs; this does not stop the containers.

### Prometheus has no series yet

Wait at least 15 seconds, query `up`, and verify the target is `1`. Also check
`docker compose ps` and the backend logs.

### MLflow run is not visible

Make a successful matching request, refresh the experiment page, and check:

```powershell
docker compose logs --tail 100 backend
```

### Stop the demo

From the repository root:

```powershell
docker compose down
```

This stops/removes containers but preserves named volumes. Do **not** add
`--volumes` unless you deliberately want to delete the cached model and
persisted MLflow/Prometheus/Grafana data.
