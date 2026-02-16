# PR Flow Agents

Press release crawler and story builder using LLM agents. Ingests press releases from URLs, stores them in MongoDB, and provides a web UI for browsing.

## What We Built (Day 1)

- **Crawler** – Crawl press release URLs and extract markdown content via crawl4ai
- **Storage** – MongoDB for `crawl_results` and `companies` with migrations
- **API** – FastAPI endpoints for companies and press releases (single + bulk CSV upload)
- **Frontend** – React + TypeScript + MUI app with:
  - **Ingestion** – Add companies and press releases (forms + CSV upload)
  - **Release Space** – File-browser view: companies → releases → content
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

## Start

### 1. Run migrations (creates indexes)

```bash
source .venv/bin/activate
python main.py
```

### 2. Start API server

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Start frontend

In another terminal:

```bash
cd frontend && npm run dev
```

Open http://localhost:5173 (Vite dev server proxies `/api` to the backend).

## Usage

### Ingestion

- **Ingestion** page: add companies (ticker, name, sector) and press releases (url, ticker, title, date)
- Bulk upload via CSV:
  - Companies: `ticker,name,sector`
  - Press releases: `url,ticker,title,date` (date in ISO, e.g. `2025-01-13T07:00:00-05:00`)

### Release Space

Select a company, then a press release, to view its content.

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
├── frontend/               # React + MUI
├── data/                   # Sample CSV data
├── pr_flow_agents/         # Crawler, ingestion, storage, models
│   ├── crawler.py
│   ├── scrapper.py
│   ├── ingestion.py
│   ├── models.py
│   └── storage/
│       ├── mongo_store.py
│       ├── company_store.py
│       ├── config.py
│       └── migrations/
└── requirements.txt
```
