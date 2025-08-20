
```markdown
# ⚡ Energy Forecast & CO₂ PoC — Gaia-X Edition

This project is a **hackathon-ready microservice** for the Future Energy Lab / Gaia-X data space.  
It demonstrates **secure, federated energy data sharing**:

- **Ingest** building energy & environment data (SMGW, tariffs, PV/wind forecasts, etc.)
- **Train** a lightweight ML model for short-term demand forecasting
- **Forecast** building load with confidence intervals
- **Estimate CO₂ emissions** using emission factors
- **Publish Gaia-X compliant service metadata** (discoverable in a federated data space)
- **Secure access** via JWT login
- Comes with a **dashboard (HTML/JS + Chart.js)**

---

## 🔐 Authentication (Gaia-X)

- Every API call requires a **JWT bearer token**
- Token is obtained from `/token` endpoint using username + password
- The dashboard already implements this login flow

Demo credentials:

```

username = hackathon
password = futurelab

````

---

## 📦 Build & Run Locally

```bash
# Build container
docker build -t energy-forecast-gaiax .

# Run container
docker run -p 8080:8080 energy-forecast-gaiax
````

* API docs: [http://localhost:8080/docs](http://localhost:8080/docs)
* Dashboard: [http://localhost:8080/ui/](http://localhost:8080/ui/)

---

## ☁️ Deploy on Google Cloud Run

```bash
gcloud auth login
gcloud config set project <your-project-id>
gcloud services enable run.googleapis.com containerregistry.googleapis.com

# Build & push
gcloud builds submit --tag gcr.io/<your-project-id>/energy-forecast-gaiax

# Deploy
gcloud run deploy energy-forecast-gaiax \
  --image gcr.io/<your-project-id>/energy-forecast-gaiax \
  --platform managed \
  --region europe-west1 \
  --allow-unauthenticated \
  --port 8080
```

After deployment, replace `http://localhost:8080` with the Cloud Run URL, e.g.:

```
https://energy-forecast-gaiax-xxxxx-europe-west1.a.run.app
```

---

## 📊 Data Format for `/ingest`

Expected JSON payload:

```json
{
  "building_id": "B-101",
  "records": [
    {
      "ts": "2025-08-18T00:00:00Z",
      "q_flow_heat": 120,
      "temperature": 22.5,
      "wind_speed": 4.2,
      "price": 0.31
    },
    {
      "ts": "2025-08-18T01:00:00Z",
      "q_flow_heat": 118,
      "temperature": 22.0,
      "wind_speed": 4.0,
      "price": 0.29
    }
  ]
}
```

* `building_id`: string ID of the building
* `ts`: ISO 8601 timestamp in UTC
* `q_flow_heat`: energy load (float)
* `temperature`, `wind_speed`, `price`: optional context variables

Sample file: `sample_data.json`

---

## 🌐 API Endpoints

All require `Authorization: Bearer <TOKEN>` unless stated.

| Endpoint    | Method | Purpose                               |
| ----------- | ------ | ------------------------------------- |
| `/health`   | GET    | Service health + DB row count         |
| `/token`    | POST   | Get JWT token                         |
| `/ingest`   | POST   | Insert building data                  |
| `/train`    | POST   | Train model for `building_id`         |
| `/forecast` | GET    | Load forecast with PI bands           |
| `/carbon`   | GET    | CO₂ estimate based on forecast        |
| `/history`  | GET    | Get past ingested records             |
| `/gaiax/*`  | GET    | Gaia-X metadata, contract, descriptor |

---

## 🛠 Cheatsheet — Linux/macOS

```bash
# 1. Get token
TOKEN=$(curl -s -X POST $BASE/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=hackathon&password=futurelab" | jq -r .access_token)

# 2. Ingest data
curl -X POST $BASE/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @sample_data.json

# 3. Train model
curl -X POST "$BASE/train?building_id=B-101" -H "Authorization: Bearer $TOKEN"

# 4. Forecast (24h)
curl "$BASE/forecast?building_id=B-101&hist=48&hours=24" -H "Authorization: Bearer $TOKEN"

# 5. CO₂ forecast
curl "$BASE/carbon?building_id=B-101&hours=24&factor_g_per_kwh=220" -H "Authorization: Bearer $TOKEN"

# 6. History
curl "$BASE/history?building_id=B-101&limit=50" -H "Authorization: Bearer $TOKEN"

# 7. Health check
curl $BASE/health
```

---

## 🛠 Cheatsheet — Windows (PowerShell)

```powershell
$BASE = "https://energy-forecast-gaiax-xxxxx-europe-west1.a.run.app"
$BID  = "B-101"

# 1. Get token
$resp  = curl -Method POST -Uri "$BASE/token" `
  -Headers @{ "Content-Type" = "application/x-www-form-urlencoded" } `
  -Body "username=hackathon&password=futurelab"
$TOKEN = ($resp.Content | ConvertFrom-Json).access_token

# 2. Ingest JSON file
curl -Method POST -Uri "$BASE/ingest" `
  -Headers @{ "Authorization"="Bearer $TOKEN"; "Content-Type"="application/json" } `
  -InFile ".\sample_data.json"

# 3. Train
curl -Method POST -Uri "$BASE/train?building_id=$BID" -Headers @{ "Authorization"="Bearer $TOKEN" }

# 4. Forecast (24h)
curl -Method GET -Uri "$BASE/forecast?building_id=$BID&hist=48&hours=24" -Headers @{ "Authorization"="Bearer $TOKEN" }

# 5. CO₂ forecast
curl -Method GET -Uri "$BASE/carbon?building_id=$BID&hours=24&factor_g_per_kwh=220" -Headers @{ "Authorization"="Bearer $TOKEN" }

# 6. History
curl -Method GET -Uri "$BASE/history?building_id=$BID&limit=50" -Headers @{ "Authorization"="Bearer $TOKEN" }

# 7. Health check
curl "$BASE/health"
```

---

## 📂 Repo Layout

```
.
├─ data/                # SQLite DB
├─ models/              # Trained models
├─ dashboard/           # Frontend: HTML/JS/CSS
├─ sample_data.json     # Example input
├─ main.py              # FastAPI backend
├─ requirements.txt     # Python deps
├─ Dockerfile           # Container build
└─ README.md            # ← this file
```

---

## 🚀 Demo Workflow (Step-by-step)

1. **Login** → `/token` → get JWT
2. **Ingest** → `/ingest` → send sample\_data.json
3. **Train** → `/train?building_id=B-101`
4. **Forecast** → `/forecast` → returns load curve + PI bands
5. **CO₂ forecast** → `/carbon` → gCO₂/kWh
6. **History** → `/history` → past data
7. **Gaia-X descriptors** → `/gaiax/*` → service discoverability
8. **Dashboard** → `/ui/` → interactive charts

---

## 🛡 Hackathon Notes

* **Gaia-X compliance**: Metadata + contracts published via `/gaiax/*`
* **Authentication**: JWT; can be extended with mTLS
* **Provided datasets**: SMGW, tariffs, PV/wind forecasts → ingest via `/ingest`
* **UI**: dashboard helps non-technical jury see results
* **Pitch tip**: highlight how your service can combine tariffs + forecasts + carbon impact

---

```
