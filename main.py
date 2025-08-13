import os, json, math, sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from joblib import dump, load
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

APP_NAME = "Energy Forecast & CO2 PoC"
DB_PATH = os.environ.get("DB_PATH", "./data/energy.db")
MODELS_DIR = os.environ.get("MODELS_DIR", "./models")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

app = FastAPI(title=APP_NAME, version="0.1.0", description="Ingest → Train → Forecast → CO2")

# CORS for local dashboard and quick tests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten later (e.g., ["http://127.0.0.1:5050"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles

# Serve the dashboard folder at /ui
app.mount("/ui", StaticFiles(directory="dashboard", html=True), name="ui")


# ---------- DB ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.execute("""CREATE TABLE IF NOT EXISTS measurements(
        building_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        q_flow_heat REAL NOT NULL,
        temperature REAL,
        PRIMARY KEY(building_id, ts)
    );""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_meas_bid_ts ON measurements(building_id, ts);")
    return conn

# ---------- Schemas ----------
class Record(BaseModel):
    ts: datetime
    q_flow_heat: float = Field(..., description="kWh during the hour")
    temperature: Optional[float] = None

    @validator("ts", pre=True)
    def _ts(cls, v):
        if isinstance(v, datetime):
            dt = v
        else:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

class IngestPayload(BaseModel):
    building_id: str
    records: List[Record]

class ForecastResponse(BaseModel):
    building_id: str
    horizon: int
    ts: List[datetime]
    q_forecast: List[float]
    pi_low: List[float]
    pi_high: List[float]

class CarbonResponse(BaseModel):
    building_id: str
    horizon: int
    factor_g_per_kwh: float
    ts: List[datetime]
    co2_g: List[float]
    total_co2_g: float

class HistoryPoint(BaseModel):
    ts: datetime
    q_flow_heat: float
    temperature: Optional[float] = None

# ---------- Helpers ----------
def _df_from_db(building_id: str) -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT building_id, ts, q_flow_heat, temperature FROM measurements WHERE building_id=? ORDER BY ts ASC",
        conn, params=(building_id,)
    )
    conn.close()
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df

def _insert_records(building_id: str, recs: List[Record]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    rows = [
        (
            building_id,
            r.ts.isoformat(),
            float(r.q_flow_heat),
            (None if r.temperature is None else float(r.temperature)),
        )
        for r in recs
    ]
    for row in rows:
        cur.execute(
            "INSERT OR REPLACE INTO measurements(building_id, ts, q_flow_heat, temperature) VALUES (?,?,?,?)",
            row,
        )
    conn.commit()
    n = cur.rowcount or len(rows)
    conn.close()
    return n

def _fe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("ts").drop_duplicates("ts").copy()
    df["hour"] = df["ts"].dt.hour
    df["dow"] = df["ts"].dt.dayofweek
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7.0)
    df["lag_1"] = df["q_flow_heat"].shift(1)
    df["lag_24"] = df["q_flow_heat"].shift(24)
    df["roll_3"] = df["q_flow_heat"].rolling(3).mean().shift(1)
    df["roll_6"] = df["q_flow_heat"].rolling(6).mean().shift(1)
    df["roll_24"] = df["q_flow_heat"].rolling(24).mean().shift(1)
    df["temperature"] = (df.get("temperature") if "temperature" in df else pd.Series(np.nan, index=df.index))
    df["temperature"] = df["temperature"].astype(float).ffill().bfill()
    return df

def _train(building_id: str, min_rows: int = 72) -> Dict[str, Any]:
    df = _df_from_db(building_id)
    if df.empty or len(df) < min_rows:
        raise HTTPException(400, f"Not enough data to train. Need ≥{min_rows} hourly rows.")
    df = _fe(df).dropna().reset_index(drop=True)
    if df.empty:
        raise HTTPException(400, "No usable rows after feature engineering.")
    feats = [
        "hour","dow","hour_sin","hour_cos","dow_sin","dow_cos",
        "temperature","lag_1","lag_24","roll_3","roll_6","roll_24"
    ]
    X, y = df[feats], df["q_flow_heat"]
    split = int(len(df) * 0.9)
    Xtr, Xte, ytr, yte = X.iloc[:split], X.iloc[split:], y.iloc[:split], y.iloc[split:]
    model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
    model.fit(Xtr, ytr)
    yhat = model.predict(Xte)
    mae = float(mean_absolute_error(yte, yhat)) if len(yte) else 0.0
    resid_std = float(np.std(yte - yhat)) if len(yte) else 0.0
    dump({"model": model, "feats": feats}, os.path.join(MODELS_DIR, f"{building_id}.joblib"))
    with open(os.path.join(MODELS_DIR, f"{building_id}.meta.json"), "w") as f:
        json.dump(
            {"building_id": building_id, "resid_std": resid_std, "trained_at": datetime.utcnow().isoformat() + "Z"},
            f,
        )
    return {"mae": mae, "resid_std": resid_std, "rows": int(len(df))}

def _load_model(building_id: str):
    p = os.path.join(MODELS_DIR, f"{building_id}.joblib")
    m = os.path.join(MODELS_DIR, f"{building_id}.meta.json")
    if not os.path.exists(p):
        raise HTTPException(404, "Model not trained yet. Call /train first.")
    bundle = load(p)
    resid_std = 0.0
    if os.path.exists(m):
        with open(m, "r") as f:
            resid_std = float(json.load(f).get("resid_std", 0.0))
    return bundle["model"], bundle["feats"], resid_std

def _repeat_last_day_temps(hist: pd.DataFrame, steps: int) -> List[float]:
    tail = hist.tail(24)
    if len(tail) < 24 or tail["temperature"].isna().any():
        last = float(hist["temperature"].dropna().iloc[-1]) if hist["temperature"].dropna().any() else 20.0
        return [last] * steps
    t = tail["temperature"].tolist()
    return (t + t * 10)[:steps]  # repeat safely

def _forecast(building_id: str, horizon: int) -> ForecastResponse:
    model, feats, resid_std = _load_model(building_id)
    hist = _df_from_db(building_id)
    if hist.empty or len(hist) < 48:
        raise HTTPException(400, "Need ≥48 hours history to forecast.")
    hist = hist.sort_values("ts")
    sim = _fe(hist).reset_index(drop=True)
    last_ts = sim["ts"].iloc[-1]
    future_t = _repeat_last_day_temps(sim, horizon)
    preds, times = [], []
    for h in range(1, horizon + 1):
        t = last_ts + timedelta(hours=h)
        hour, dow = t.hour, t.weekday()
        row = {
            "hour": hour, "dow": dow,
            "hour_sin": math.sin(2 * math.pi * hour / 24.0), "hour_cos": math.cos(2 * math.pi * hour / 24.0),
            "dow_sin": math.sin(2 * math.pi * dow / 7.0), "dow_cos": math.cos(2 * math.pi * dow / 7.0),
            "temperature": future_t[h - 1],
            "lag_1": sim["q_flow_heat"].iloc[-1],
            "lag_24": sim["q_flow_heat"].iloc[-24] if len(sim) >= 24 else sim["q_flow_heat"].iloc[-1],
            "roll_3": float(pd.Series(sim["q_flow_heat"].iloc[-3:]).mean()),
            "roll_6": float(pd.Series(sim["q_flow_heat"].iloc[-6:]).mean()),
            "roll_24": float(pd.Series(sim["q_flow_heat"].iloc[-24:]).mean()),
        }
        yhat = float(model.predict(pd.DataFrame([row])[feats])[0])
        preds.append(yhat)
        times.append(t.replace(tzinfo=timezone.utc))
        sim = pd.concat(
            [sim, pd.DataFrame({"ts": [t], "q_flow_heat": [yhat], "temperature": [row["temperature"]]})],
            ignore_index=True,
        )
    z = 1.96
    pi_low = [max(0.0, p - z * resid_std) for p in preds]
    pi_high = [p + z * resid_std for p in preds]
    return ForecastResponse(building_id=building_id, horizon=horizon, ts=times, q_forecast=preds, pi_low=pi_low, pi_high=pi_high)

# ---------- Routes ----------
@app.get("/health")
def health():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM measurements;")
    n = cur.fetchone()[0]
    conn.close()
    return {"status": "ok", "rows": int(n), "app": APP_NAME, "version": "0.1.0"}

@app.get("/history", response_model=List[HistoryPoint])
def history(building_id: str, hours: int = Query(48, ge=1, le=720)):
    df = _df_from_db(building_id)
    if df.empty:
        raise HTTPException(404, "No data for that building_id")
    df = df.sort_values("ts").tail(hours)
    out: List[HistoryPoint] = []
    for _, r in df.iterrows():
        out.append(
            HistoryPoint(
                ts=pd.to_datetime(r["ts"], utc=True).to_pydatetime(),
                q_flow_heat=float(r["q_flow_heat"]),
                temperature=None if pd.isna(r.get("temperature")) else float(r["temperature"]),
            )
        )
    return out

@app.post("/ingest")
def ingest(payload: IngestPayload):
    if not payload.records:
        raise HTTPException(400, "No records provided.")
    n = _insert_records(payload.building_id, payload.records)
    return {"inserted": int(n), "building_id": payload.building_id}

@app.post("/train")
def train(building_id: str = Query(...), min_rows: int = Query(72, ge=24)):
    return {"building_id": building_id, **_train(building_id, min_rows=min_rows)}

@app.get("/forecast", response_model=ForecastResponse)
def forecast(building_id: str, hours: int = Query(24, ge=1, le=168)):
    return _forecast(building_id, hours)

@app.get("/carbon", response_model=CarbonResponse)
def carbon(
    building_id: str,
    hours: int = Query(24, ge=1, le=168),
    factor_g_per_kwh: float = Query(220.0),
):
    fc = _forecast(building_id, hours)
    co2 = [float(v) * float(factor_g_per_kwh) for v in fc.q_forecast]
    total = float(np.sum(co2))
    return CarbonResponse(
        building_id=building_id,
        horizon=hours,
        factor_g_per_kwh=factor_g_per_kwh,
        ts=fc.ts,
        co2_g=co2,
        total_co2_g=total,
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=True)
