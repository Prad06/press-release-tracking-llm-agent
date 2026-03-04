# PR Flow Agents

Press release crawler and analysis pipeline using LLM agents. It ingests press releases into MongoDB, runs a sector-aware extraction + review loop, and provides a local web UI.

## Features

- **Crawler** – Crawl press release URLs and extract markdown content via crawl4ai
- **Storage** – MongoDB for `crawl_results` and `companies` with migrations
- **API** – FastAPI endpoints for companies and press releases (single + bulk CSV upload)
- **Ingestion Graph (Stage 2)** – Iterative extractor/reviewer flow with:
  - Sector routing (`biotech`, `aviation`)
  - LLM extractor prompt
  - LLM validator prompt
  - Multi-expert review loop with hop budget
- **MLflow Tracking** – Optional per-run and per-LLM-call tracking (latency, prompt/output artifacts, counts)
- **Frontend** – React + TypeScript + MUI app with:
  - **Ingestion** – Add companies and press releases (forms + CSV upload)
  - **Release Space** – File-browser view: companies → releases → content
  - **MLflow Link** – Quick link to local MLflow UI (`http://localhost:5001`)
  - **Agent Space** – Placeholder for future agents
  - **Chat** – Placeholder
- **Checkpoints** – Named MongoDB snapshots (create/list/restore)
- **Validation** – Press release date required (no default to crawl date); CSV format enforced

## Prerequisites

- Python 3.11+
- Node.js 18+
- MongoDB (local or Atlas)
- [Playwright browsers](https://playwright.dev/) for crawl4ai

## Install

### 1. Clone and enter project

```bash
cd pr_flow_agents
```

### 2. Python backend

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install         # for crawl4ai
```

### 3. Environment

Create a `.env` file in the project root:

```
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DATABASE=pr_flow
```

For Atlas, use your connection string. Database defaults to `pr_flow` if `MONGODB_DATABASE` is omitted.

### 4. Frontend

```bash
cd frontend
npm install
cd ..
```

## Run Locally

### 1. Run migrations (creates indexes)

```bash
source .venv/bin/activate
python main.py
```

### 2. Start everything (recommended)

```bash
./scripts/start_local_stack.sh
```

This starts:
- Frontend at `http://localhost:5173`
- Backend at `http://localhost:8000`
- MLflow UI at `http://localhost:5001`

Logs:
- `/tmp/pr_flow_frontend.log`
- `/tmp/pr_flow_backend.log`
- `/tmp/pr_flow_mlflow.log`

### 3. Start services manually (alternative)

API:

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (another terminal):

```bash
cd frontend && npm run dev
```

MLflow (optional, another terminal):

```bash
mlflow server --host 127.0.0.1 --port 5001 --workers 1 \
  --backend-store-uri sqlite:///$(pwd)/mlflow.db \
  --default-artifact-root $(pwd)/mlruns
```

## MLflow Configuration

Environment variables used by the app:

- `MLFLOW_TRACKING_ENABLED` (default `1`)
- `MLFLOW_TRACKING_URI` (example: `http://127.0.0.1:5001`)

Experiment name is hardcoded in ingestion CLI as `ingestion_flow`.

## Usage

### Ingestion

- **Ingestion** page: add companies (ticker, name, sector) and press releases (url, ticker, title, date)
- Bulk upload via CSV:
  - Companies: `ticker,name,sector`
  - Press releases: `url,ticker,title,date` (date in ISO, e.g. `2025-01-13T07:00:00-05:00`)

### Release Space

Select a company, then a press release, to view its content.

### Ingestion Graph Run (CLI)

Run the ingestion graph for a stored press release id:

```bash
python -m pr_flow_agents.graph.ingestion.run --press-release-id <mongo_id>
```

Output includes loop status and final extracted events.

### Checkpoints

```bash
python scripts/checkpoint.py create <name>   # Save current DB state
python scripts/checkpoint.py list            # List checkpoints
python scripts/checkpoint.py restore <name>  # Restore to checkpoint
```

## Project Layout

```
pr_flow_agents/
├── main.py                 # Run migrations
├── api/main.py             # FastAPI app
├── scripts/checkpoint.py   # MongoDB checkpoints
├── scripts/start_local_stack.sh
├── frontend/               # React + MUI
├── data/                   # Sample CSV data
├── pr_flow_agents/         # Crawler, ingestion, graph, storage, models
│   ├── crawler.py
│   ├── scrapper.py
│   ├── graph/
│   │   ├── ingestion/
│   │   └── ...
│   ├── llm/
│   ├── models.py
│   └── storage/
│       ├── mongo_store.py
│       ├── company_store.py
│       ├── config.py
│       └── migrations/
└── requirements.txt
```
