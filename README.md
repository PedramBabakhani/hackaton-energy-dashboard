
```markdown
# ⚡ Energy Forecast & CO₂ PoC — Gaia-X Edition

This microservice demonstrates **secure, Gaia-X compliant energy data sharing**:

- **Ingests** hourly building energy measurements  
- **Trains** lightweight ML models for short-term forecasting  
- **Forecasts** energy demand and **estimates CO₂ emissions**  
- **Protects access** via **JWT-based authentication** following Gaia-X trust principles  
- Comes with a minimal **HTML/JS dashboard**

---

## 🔐 Gaia-X Authentication

- All API calls require a **JWT access token**  
- The token encodes the `sub` (subject = username) and expiry  
- Only authenticated requests are accepted  
- The dashboard includes a login form for username & password to request a token  

Demo credentials:

```

username = hackathon
password = futurelab

````

---

## 📦 Build & Run Locally with Docker

1. **Build the image**:

```bash
docker build -t energy-forecast-gaiax .
````

2. **Run the container**:

```bash
docker run -p 8080:8080 energy-forecast-gaiax
```

3. Open the API docs:
   👉 [http://localhost:8080/docs](http://localhost:8080/docs)

4. Open the dashboard:
   👉 [http://localhost:8080/ui/](http://localhost:8080/ui/)

---

## ☁️ Deploy to Google Cloud Run

Authenticate and set up your project:

```bash
gcloud auth login
gcloud config set project hri-energy-forecast-469114
gcloud services enable run.googleapis.com containerregistry.googleapis.com
```

### 1. Build and push the container image

```bash
gcloud builds submit --tag gcr.io/hri-energy-forecast-469114/energy-forecast-gaiax
```

### 2. Deploy to Cloud Run

```bash
gcloud run deploy energy-forecast-gaiax \
  --image gcr.io/hri-energy-forecast-469114/energy-forecast-gaiax \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080
```

After deployment, you will see a service URL like:

```
https://energy-forecast-gaiax-xxxxx-europe-west1.a.run.app
```

Use this base URL instead of `http://localhost:8080`.

---

## 🛠 How to Get a Token

### Linux / macOS

```bash
curl -X POST http://localhost:8080/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=hackathon&password=futurelab"
```

### Windows PowerShell

```powershell
$username = "hackathon"
$password = "futurelab"

$tokenResponse = Invoke-RestMethod -Uri "http://localhost:8080/token" `
  -Method Post `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=$username&password=$password"

$TOKEN = $tokenResponse.access_token
```

When deployed on Cloud Run, replace the base URL:

```bash
curl -X POST https://energy-forecast-gaiax-xxxxx-europe-west1.a.run.app/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=hackathon&password=futurelab"
```

---

## 📊 Data Format (for `/ingest`)

The API expects **JSON records** in this format:

```json
[
  {
    "building_id": "B-101",
    "timestamp": "2024-01-01T00:00:00Z",
    "energy_kwh": 120.5
  },
  {
    "building_id": "B-101",
    "timestamp": "2024-01-01T01:00:00Z",
    "energy_kwh": 98.3
  }
]
```

* `building_id`: unique ID of the building
* `timestamp`: ISO 8601 UTC datetime string (`YYYY-MM-DDTHH:mm:ssZ`)
* `energy_kwh`: measured consumption in **kWh** (float)

Example file: **`sample_data.json`**

---

## 🌐 API Endpoints Explained

All requests require a **Bearer token** header.

### 🔎 `/health` (GET)

* **Purpose:** check service status + number of rows in DB
* **Params:** none
* **Output:** JSON with status + row count

---

### 📥 `/ingest` (POST)

* **Purpose:** add new building measurements to DB
* **Input:** JSON array of records (see format above)
* **Output:** confirmation with number of records ingested

---

### 🏋️ `/train` (POST)

* **Purpose:** train/retrain ML model for a building
* **Params:** `building_id` (query param)
* **Output:** JSON status message (training complete)

Example:

```bash
POST /train?building_id=B-101
```

---

### 🔮 `/forecast` (GET)

* **Purpose:** get future energy demand predictions
* **Params:**

  * `building_id` (required)
  * `hours` (forecast horizon, e.g., 24)
* **Output:** list of timestamps with predicted kWh

---

### 🌍 `/carbon` (GET)

* **Purpose:** estimate CO₂ emissions from forecast
* **Params:**

  * `building_id` (required)
  * `hours` (horizon)
  * `factor_g_per_kwh` (e.g., `220` g/kWh)
* **Output:** JSON with energy forecast + carbon emissions

---

### 📜 `/history` (GET)

* **Purpose:** retrieve past ingested data
* **Params:**

  * `building_id` (required)
  * `hours` (how many past hours to fetch)
* **Output:** list of past values from DB

---

## 📂 Repository Layout

```
hackaton/
├─ data/                  # SQLite DB
├─ models/                # Trained models
├─ dashboard/             # HTML/JS/CSS dashboard (token login included)
├─ sample_data.json       # Example dataset for ingestion
├─ main.py                # FastAPI service
├─ requirements.txt       # Python deps
├─ Dockerfile             # Container build
└─ README.md              # ← You are here
```

---

## 🚀 Quick Demo Workflow

1. **Run locally** (Docker) **or deploy to Cloud Run**
2. **Get a token**: POST to `/token` with username/password
3. **Ingest data**: POST `sample_data.json` to `/ingest` with your token
4. **Train a model**: `POST /train?building_id=B-101`
5. **Forecast**: `GET /forecast?building_id=B-101&hours=24`
6. **Carbon emissions**: `GET /carbon?...`
7. **History**: `GET /history?...`
8. **View results** in the dashboard (`/ui/`)

---

## 🛡 Notes

* **Gaia-X principle**: sovereign, trusted data exchange. Tokens simulate identity verification
* Default credentials are for demo only — replace with a real IAM service in production
* SQLite and local models are mounted inside the container; use PostgreSQL or cloud storage for production
* CORS is open (`*`) for hackathon speed — tighten for real deployments

```

---