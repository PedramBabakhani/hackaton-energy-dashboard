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
password = hackathon

````

---

## 📦 Build & Run with Docker

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

## 🛠 How to Get a Token

### Linux / macOS

```bash
curl -X POST http://localhost:8080/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=hackathon&password=hackathon"
```

### Windows PowerShell

```powershell
$username = "hackathon"
$password = "hackathon"

$tokenResponse = Invoke-RestMethod -Uri "http://localhost:8080/token" `
  -Method Post `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=$username&password=$password"

$TOKEN = $tokenResponse.access_token
```

The API will return JSON with an `access_token`.
Use it in every request with:

```
-H "Authorization: Bearer <TOKEN>"
```

---

## 🌐 API Endpoints & Example Commands

All requests must include the token header.
Examples for **Linux/macOS (curl)** and **Windows PowerShell** are provided.

---

### 🔎 Health Check

**Linux/macOS:**

```bash
curl -X GET http://localhost:8080/health \
  -H "Authorization: Bearer $TOKEN"
```

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/health" `
  -Headers @{ Authorization = "Bearer $TOKEN" }
```

---

### 📥 Ingest Data

**Linux/macOS:**

```bash
curl -X POST http://localhost:8080/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @sample_data.json
```

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/ingest" `
  -Method Post `
  -Headers @{ Authorization = "Bearer $TOKEN" } `
  -ContentType "application/json" `
  -InFile "sample_data.json"
```

---

### 🏋️ Train a Model

**Linux/macOS:**

```bash
curl -X POST "http://localhost:8080/train?building_id=B-101" \
  -H "Authorization: Bearer $TOKEN"
```

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/train?building_id=B-101" `
  -Method Post `
  -Headers @{ Authorization = "Bearer $TOKEN" }
```

---

### 🔮 Forecast Energy Demand

**Linux/macOS:**

```bash
curl -X GET "http://localhost:8080/forecast?building_id=B-101&hours=24" \
  -H "Authorization: Bearer $TOKEN"
```

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/forecast?building_id=B-101&hours=24" `
  -Headers @{ Authorization = "Bearer $TOKEN" }
```

---

### 🌍 Estimate CO₂ Emissions

**Linux/macOS:**

```bash
curl -X GET "http://localhost:8080/carbon?building_id=B-101&hours=24&factor_g_per_kwh=220" \
  -H "Authorization: Bearer $TOKEN"
```

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/carbon?building_id=B-101&hours=24&factor_g_per_kwh=220" `
  -Headers @{ Authorization = "Bearer $TOKEN" }
```

---

### 📜 Fetch History

**Linux/macOS:**

```bash
curl -X GET "http://localhost:8080/history?building_id=B-101&hours=48" \
  -H "Authorization: Bearer $TOKEN"
```

**Windows PowerShell:**

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/history?building_id=B-101&hours=48" `
  -Headers @{ Authorization = "Bearer $TOKEN" }
```

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

1. **Start the service** in Docker
2. **Get a token**: POST to `/token` with username/password
3. **Ingest data**: POST `sample_data.json` to `/ingest` with your token
4. **Train a model**: `POST /train?building_id=B-101`
5. **Forecast**: `GET /forecast?building_id=B-101&hours=24`
6. **Carbon emissions**: `GET /carbon?...`
7. **View results** in the dashboard (`/ui/`)

---

## 🛡 Notes

* **Gaia-X principle**: sovereign, trusted data exchange. Tokens simulate identity verification
* Default credentials are for demo only — replace with a real IAM service in production
* SQLite and local models are mounted inside the container; use PostgreSQL or cloud storage for production
* CORS is open (`*`) for hackathon speed — tighten for real deployments

```

---
