# Energy Forecast & CO₂ PoC — **Full Documentation**

A batteries-included, hackathon-ready microservice for **ingesting hourly energy data**, **training a quick forecasting model**, **serving forecasts with prediction intervals**, and **estimating CO₂ emissions**. Ships with a lightweight **HTML/JS dashboard** (Chart.js) and simple seeding scripts.

This README covers **everything**: file layout, how to run on Windows/Mac/Linux, virtualenv, Docker, endpoints (with request/response samples), data schema, troubleshooting, perf notes, and extension ideas.

---

## Table of Contents

1. [What this project does](#what-this-project-does)
2. [Repository layout](#repository-layout)
3. [Requirements](#requirements)
4. [Quick start (Windows)](#quick-start-windows)
5. [Quick start (macOS / Linux)](#quick-start-macos--linux)
6. [Running the dashboard](#running-the-dashboard)
7. [Environment variables & storage](#environment-variables--storage)
8. [API reference](#api-reference)

   * [/health](#get-health)
   * [/ingest](#post-ingest)
   * [/train](#post-train)
   * [/forecast](#get-forecast)
   * [/carbon](#get-carbon)
   * [/history](#get-history)
9. [Data schema](#data-schema)
10. [Model details](#model-details)
11. [Seeding and demos](#seeding-and-demos)
12. [Docker](#docker)
13. [Operational notes](#operational-notes)
14. [Troubleshooting](#troubleshooting)
15. [Roadmap / extensions](#roadmap--extensions)
16. [FAQ](#faq)

---

## What this project does

* **Ingests** hourly measurements (per `building_id`):
  – `ts` (ISO-8601 UTC), `q_flow_heat` (kWh during that hour), optional `temperature` (°C).

* **Stores** them in a local SQLite DB (`./data/energy.db`).

* **Trains** a quick **RandomForestRegressor** using calendar/lag/rolling features.

* **Forecasts** next N hours (default 24) and computes **95% prediction intervals** from residuals.

* **Estimates CO₂** by multiplying forecasted kWh by a user-provided emission factor (g/kWh).

* **Visualizes** with a small dashboard (Chart.js) that calls the REST API.

---

## Repository layout

```
hackaton/
├─ .venv/                       # Python virtualenv (local)
├─ __pycache__/                 # Python cache
├─ data/                        # SQLite DB lives here (energy.db)
├─ models/                      # Trained models (.joblib) and metadata
├─ dashboard/
│  ├─ index.html                # UI — forms & charts
│  ├─ script.js                 # UI logic — API calls & Chart.js renders
│  └─ styles.css                # UI styles
├─ Dockerfile                   # Container build file (optional)
├─ generate_sample_data.py      # Creates sample_data.json for quick demos
├─ main.py                      # FastAPI service (all endpoints)
├─ README.md                    # ← You are here
├─ requirements.txt             # Python dependencies (pinned)
├─ run.ps1                      # Windows: venv, install, sample, run API
├─ seed.ps1                     # Windows: POST sample_data.json to /ingest
└─ sample_data.json             # Generated sample payload (not tracked by git)
```

---

## Requirements

* **Python** 3.10–3.11 (3.11 recommended)
* **Pip** (ships with Python)
* **Windows PowerShell** 5+ or **macOS/Linux** shell
* Optional: **Docker** (if you prefer containerized run)
* Browser (Chrome/Edge/Firefox) for the dashboard

---

## Quick start (Windows)

> All commands from the **project root** (e.g., `C:\Users\<you>\Desktop\hackaton`).

1. **Create & activate venv**

```powershell
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
```

2. **Install deps**

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3. **Generate sample data** (creates `sample_data.json`)

```powershell
python .\generate_sample_data.py
```

4. **Start API**

```powershell
python -m uvicorn main:app --reload
```

* API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* Health:   [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

5. **Ingest** the sample (in a **second** PowerShell window):

```powershell
. .\.venv\Scripts\Activate.ps1
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingest" `
  -Method POST `
  -ContentType "application/json" `
  -Body (Get-Content ".\sample_data.json" -Raw)
```

6. **Train** a model:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/train?building_id=B-101" -Method POST
```

7. **Forecast** (example):

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/forecast?building_id=B-101&hours=24"
```

8. **CO₂ estimate** (example, 220 g/kWh):

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/carbon?building_id=B-101&hours=24&factor_g_per_kwh=220"
```

---

## Quick start (macOS / Linux)

```bash
# 1) venv
python3 -m venv .venv
source .venv/bin/activate

# 2) deps
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3) sample
python generate_sample_data.py

# 4) run API
python -m uvicorn main:app --reload
# open http://127.0.0.1:8000/docs

# 5) ingest
curl -X POST "http://127.0.0.1:8000/ingest" \
  -H "Content-Type: application/json" \
  --data-binary @sample_data.json

# 6) train
curl -X POST "http://127.0.0.1:8000/train?building_id=B-101"

# 7) forecast & CO2
curl "http://127.0.0.1:8000/forecast?building_id=B-101&hours=24"
curl "http://127.0.0.1:8000/carbon?building_id=B-101&hours=24&factor_g_per_kwh=220"
```

---

## Running the dashboard

Two options:

### Option A — Serve dashboard folder on a separate port (zero code changes)

```powershell
cd .\dashboard
python -m http.server 5050
```

Open **[http://127.0.0.1:5050](http://127.0.0.1:5050)** (FastAPI stays on **[http://127.0.0.1:8000](http://127.0.0.1:8000)**).
The dashboard calls `/health`, `/history`, `/forecast`, `/carbon` on port **8000**.

### Option B — Serve the dashboard from FastAPI (single port)

In **main.py**, add:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/ui", StaticFiles(directory="dashboard", html=True), name="ui")
```

Restart the API, then open **[http://127.0.0.1:8000/ui/](http://127.0.0.1:8000/ui/)**

> The dashboard expects CORS to be open (already configured in `main.py`).

---

## Environment variables & storage

* `DB_PATH` (default `./data/energy.db`) — SQLite DB.
* `MODELS_DIR` (default `./models`) — joblib bundle + meta JSON per building.

Files created at runtime:

* `data/energy.db` — SQLite file with table `measurements`.
* `models/<building_id>.joblib` — trained estimator and feature list.
* `models/<building_id>.meta.json` — residual std, trained timestamp.

---

## API reference

All endpoints are under `http://127.0.0.1:8000`. See interactive docs at **/docs** (Swagger) or **/redoc**.

### `GET /health`

**Purpose:** Liveness + row count.

**Response**

```json
{
  "status": "ok",
  "rows": 240,
  "app": "Energy Forecast & CO2 PoC",
  "version": "0.1.0"
}
```

---

### `POST /ingest`

**Purpose:** Insert or update hourly measurements for a building.

**Body**

```json
{
  "building_id": "B-101",
  "records": [
    {
      "ts": "2025-08-10T00:00:00Z",
      "q_flow_heat": 153.2,
      "temperature": 21.4
    }
    // ...
  ]
}
```

* `ts` must be ISO-8601 (UTC recommended).
* Duplicate `(building_id, ts)` rows will be **upserted** (replaced).

**Response**

```json
{ "inserted": 240, "building_id": "B-101" }
```

**Examples**

* PowerShell:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingest" `
  -Method POST -ContentType "application/json" `
  -Body (Get-Content ".\sample_data.json" -Raw)
```

* curl:

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  --data-binary @sample_data.json
```

---

### `POST /train`

**Purpose:** Train (or retrain) a model for a building.

**Query params**

* `building_id` (required)
* `min_rows` (optional, default **72**, min **24**)

**Response**

```json
{
  "building_id": "B-101",
  "mae": 4.59,
  "resid_std": 5.67,
  "rows": 216
}
```

**Notes**

* The service builds features (hour/day-of-week cyclic, lags, rolling means).
* `resid_std` is used to form ±1.96σ prediction intervals.

---

### `GET /forecast`

**Purpose:** Next-N-hours forecast and prediction intervals.

**Query params**

* `building_id` (required)
* `hours` (default 24, min 1, max 168)

**Response**

```json
{
  "building_id": "B-101",
  "horizon": 24,
  "ts": ["2025-08-13T14:00:00+00:00", "..."],
  "q_forecast": [160.2, ...],
  "pi_low": [148.1, ...],
  "pi_high": [172.3, ...]
}
```

**Prereq:** Must **train** first. Requires ≥48 hrs history for lags.

---

### `GET /carbon`

**Purpose:** Convert forecast energy to emissions.

**Query params**

* `building_id` (required)
* `hours` (default 24, min 1, max 168)
* `factor_g_per_kwh` (default 220.0) — grams CO₂ per kWh

**Response**

```json
{
  "building_id": "B-101",
  "horizon": 24,
  "factor_g_per_kwh": 220.0,
  "ts": ["..."],
  "co2_g": [35244.0, "..."],
  "total_co2_g": 845612.0
}
```

---

### `GET /history`

**Purpose:** Retrieve last N hours of actuals for a building.

**Query params**

* `building_id` (required)
* `hours` (default 48, min 1, max 720)

**Response**

```json
[
  { "ts": "2025-08-11T10:00:00+00:00", "q_flow_heat": 151.1, "temperature": 21.3 },
  ...
]
```

---

## Data schema

SQLite table **`measurements`**:

| Column        | Type | Notes                                         |
| ------------- | ---- | --------------------------------------------- |
| building\_id  | TEXT | Key part 1                                    |
| ts            | TEXT | ISO-8601 string (UTC recommended). Key part 2 |
| q\_flow\_heat | REAL | Energy (kWh) for the hour                     |
| temperature   | REAL | Optional (°C)                                 |

Constraint: **PRIMARY KEY (building\_id, ts)**.
Index: `idx_meas_bid_ts` on `(building_id, ts)`.

---

## Model details

* **Algorithm:** `RandomForestRegressor` (sklearn), `n_estimators=300`, `n_jobs=-1`.
* **Features:**

  * Calendar: `hour`, `dow` + sine/cosine encodings for cyclic patterns.
  * Lags: `lag_1`, `lag_24`.
  * Rolling means: `roll_3`, `roll_6`, `roll_24`.
  * Temperature (ffill/bfill).
* **Train/Val split:** first 90% train, last 10% validation (chronological split).
* **Uncertainty:** `resid_std = std(y_true - y_pred)` on the validation split;
  the API returns **95% PI** using ±1.96·resid\_std.

Artifacts written to `./models`:

* `<building_id>.joblib` — `{ "model": estimator, "feats": [ ... ] }`
* `<building_id>.meta.json` — `{ "resid_std": ..., "trained_at": ... }`

---

## Seeding and demos

### Generate sample payload

```powershell
. .\.venv\Scripts\Activate.ps1
python .\generate_sample_data.py
```

This writes `sample_data.json`:

```json
{
  "building_id": "B-101",
  "records": [ { "ts": "...", "q_flow_heat": 153.2, "temperature": 21.4 }, ... ]
}
```

### Ingest sample (Windows)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingest" `
  -Method POST -ContentType "application/json" `
  -Body (Get-Content ".\sample_data.json" -Raw)
```

### One-click helper (Windows)

* `run.ps1` — create venv, install deps, generate sample, run API.
* `seed.ps1` — posts `sample_data.json` to `/ingest` (use after API is up).

---

## Docker

Build and run with Docker (no local Python needed):

```bash
# from project root
docker build -t energy-forecast-poc .
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" -v "$(pwd)/models:/app/models" energy-forecast-poc
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

To seed inside Docker, either:

* `docker cp sample_data.json <container_id>:/app/` then POST from host to container’s 8000, **or**
* Run another container that curls the running API, **or**
* Mount the file and `curl` from host as usual (the API is on localhost:8000).

---

## Operational notes

* **CORS** is open to `*` for hackathon speed. Consider restricting in production.
* **Persistence:** SQLite and models are local folders. Mount volumes or use cloud storage for durability.
* **Scaling:** For real traffic, put behind a process manager (gunicorn + uvicorn workers) and a reverse proxy (nginx). Move from SQLite to Postgres.
* **Security:** No auth is implemented. Add an API key or OAuth if needed.
* **Validation:** Pydantic validates inputs; malformed ISO timestamps will 422.

---

## Troubleshooting

**“The term '..venv\Scripts\Activate.ps1' is not recognized”**
→ You’re not in the project root. `cd` to the folder that contains `.venv`.

**`Error loading ASGI app. Could not import module "main".`**
→ You ran `uvicorn` from the wrong directory (e.g., `dashboard/`). Run from project root.

**PowerShell: `curl` header errors**
→ PowerShell aliases `curl` to `Invoke-WebRequest`. Use `Invoke-RestMethod` or `curl.exe`:

```powershell
curl.exe -X POST ... -H "Content-Type: application/json" --data-binary "@sample_data.json"
```

**`Need ≥72 hourly rows` when training**
→ You haven’t ingested enough rows. Run the seeding; or pass `&min_rows=24` temporarily:

```
POST /train?building_id=B-101&min_rows=24
```

**`forecast` says model not trained**
→ Call `/train` first.

**Dashboard loads but charts are empty**

* Open **DevTools Console** (F12) and check network calls.
* Make sure API is running on **8000** and you seeded + trained.
* If you serve dashboard on port 5050, CORS must allow `*` (already set).

**FutureWarning for pandas frequency “H”**
→ Change `freq="H"` to `freq="h"` in `generate_sample_data.py`.

---

## Roadmap / extensions

* Add `/buildings` endpoint (distinct building list).
* Add `/ingest/csv` supporting bulk CSV uploads.
* Swap in **XGBoost/LightGBM** for speed/accuracy sensitivity.
* Weather enrichment: external forecast API; switch `_repeat_last_day_temps` to real predictions.
* Proper **train/validation split** via TimeSeriesSplit & backtesting metrics.
* Persist **MAE history** and display on dashboard.
* Authentication / rate limiting.
* Deploy templates (Azure App Service, AWS App Runner, Fly.io).
* Container health checks and logging configuration.

---

## FAQ

**Q: Do I need to keep uvicorn running in the same window?**
A: Yes. It’s your server. Open a second window for `seed.ps1`, training, and curl commands.

**Q: Can I change the storage location?**
A: Yes. Set `DB_PATH` and `MODELS_DIR` env vars before starting the server.

**Q: Where do I change the forecast horizon?**
A: Client-side (dashboard inputs) or by calling `/forecast?hours=...`.

**Q: What’s the unit for `q_flow_heat`?**
A: The code treats it as **kWh per hour**. Keep units consistent in your ingested data.

**Q: How are prediction intervals computed?**
A: Simple normal approximation using validation residual std (`±1.96σ`). This is a demo—improve as needed.

---
