# ⚡ Energy Forecast & CO₂ PoC — Gaia-X Edition

This microservice demonstrates **secure, Gaia-X compliant energy data sharing**:

- **Ingests** hourly building energy measurements.  
- **Trains** lightweight ML models for short-term forecasting.  
- **Forecasts** energy demand and **estimates CO₂ emissions**.  
- **Protects access** via **JWT-based authentication** following Gaia-X trust principles.  
- Comes with a minimal **HTML/JS dashboard**.

---

## 🔐 Gaia-X Authentication

This PoC integrates **Gaia-X style authentication**:

- All API calls require a **JWT access token**.  
- The token encodes the `sub` (subject = your username) and expiry.  
- Only authenticated requests are accepted.  
- The dashboard includes a login form for username & password to request a token.

---

## 🛠 How to Get a Token

1. Request a token via `/token` with username and password (demo user = `hackathon`):

```bash
curl -X POST http://localhost:8080/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=hackathon&password=hackathon"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
  "token_type": "bearer"
}
```

2. Copy the `access_token`.  
3. Use it in every request with:

```
-H "Authorization: Bearer <your_token_here>"
```

---

## 📦 Build & Run with Docker

1. **Build the image**

```bash
docker build -t energy-forecast-gaiax .
```

2. **Run the container**

```bash
docker run -p 8080:8080 energy-forecast-gaiax
```

3. Open the API docs:  
👉 [http://localhost:8080/docs](http://localhost:8080/docs)

4. Open the dashboard:  
👉 [http://localhost:8080/ui/](http://localhost:8080/ui/)

---

## 🔑 Authentication in the Dashboard

- Open the UI at **`/ui/`**.  
- Enter your **username** (`hackathon`) and **password** (`hackathon`).  
- The dashboard will automatically request a token and attach it to every API call.  
- Without a valid token, the backend rejects requests with **401 Unauthorized**.  

---

## 🌐 API Endpoints (All Authenticated)

All requests must include:

```
-H "Authorization: Bearer <token>"
```

### `GET /health`  
Service status and row count.

---

### `POST /ingest`  
Ingest hourly energy records.

```bash
curl -X POST http://localhost:8080/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @sample_data.json
```

---

### `POST /train?building_id=B-101`  
Train or retrain model.

---

### `GET /forecast?building_id=B-101&hours=24`  
Retrieve forecast + prediction intervals.

---

### `GET /carbon?building_id=B-101&hours=24&factor_g_per_kwh=220`  
Estimate CO₂ emissions.

---

### `GET /history?building_id=B-101&hours=48`  
Fetch recent historical data.

---

## 📂 Repository Layout

```
hackaton/
├─ data/                  # SQLite DB
├─ models/                # Trained models
├─ dashboard/             # HTML/JS/CSS dashboard (token login included)
├─ main.py                # FastAPI service
├─ requirements.txt       # Python deps
├─ Dockerfile             # Container build
└─ README.md              # ← You are here
```

---

## 🚀 Quick Demo Workflow

1. **Start the service** in Docker.  
2. **Get a token**: POST to `/token` with username/password.  
3. **Ingest data**: POST `sample_data.json` to `/ingest` with your token.  
4. **Train a model**: `POST /train?building_id=B-101`.  
5. **Forecast**: `GET /forecast?building_id=B-101&hours=24`.  
6. **View results** in the dashboard (`/ui/`).  

---

## 🛡 Notes

- **Gaia-X principle**: sovereign, trusted data exchange. Tokens simulate identity verification.  
- Default credentials are for demo only — replace with a real IAM service in production.  
- SQLite and local models are mounted inside the container; use PostgreSQL or cloud storage for production.  
- CORS is open (`*`) for hackathon speed — tighten for real deployments.  

---
