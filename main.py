import os, json, math, sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from joblib import dump, load
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

# ========================
# Security imports
# ========================
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext

# ========================
# App config
# ========================
APP_NAME = "Energy Forecast & CO2 PoC"
DB_PATH = os.environ.get("DB_PATH", "./data/energy.db")
MODELS_DIR = os.environ.get("MODELS_DIR", "./models")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)

app = FastAPI(title=APP_NAME, version="0.1.0", description="Ingest → Train → Forecast → CO2")

# CORS for dashboard and quick tests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten later in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
app.mount("/ui", StaticFiles(directory="dashboard", html=True), name="ui")

# ========================
# Security settings
# ========================
SECRET_KEY = "CHANGE_THIS_SECRET_TO_A_RANDOM_STRING"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Demo in-memory user DB
fake_users_db = {
    "hackathon": {
        "username": "hackathon",
        "full_name": "Hackathon Future Lab",
        "hashed_password": pwd_context.hash("futurelab"),
        "disabled": False,
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username)
    if user is None:
        raise credentials_exception
    return user

# Token endpoint
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# ========================
# Database helpers
# ========================
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

# ========================
# Schemas
# ========================
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

# ========================
# Core logic
# ========================
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
    df["temperature"] = df.get("temperature", pd.Series(np.nan, index=df.index))
    df["temperature"] = df["temperature"].astype(float).ffill().bfill()
    return df

def _train(building_id: str, min_rows: int = 72) -> Dict[str, Any]:
    df = _df_from_db(building_id)
    if df.empty or len(df) < min_rows:
        raise HTTPException(400, f"Not enough data to train. Need ≥{min_rows} hourly rows.")
    df = _fe(df).dropna().reset_index(drop=True)
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
    mae = float(mean_absolute_error(yte, yhat))
    resid_std = float(np.std(yte - yhat))
    dump({"model": model, "feats": feats}, os.path.join(MODELS_DIR, f"{building_id}.joblib"))
    with open(os.path.join(MODELS_DIR, f"{building_id}.meta.json"), "w") as f:
        json.dump({"building_id": building_id, "resid_std": resid_std}, f)
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
    return (t + t * 10)[:steps]

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

# ========================
# Routes
# ========================
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
    return [HistoryPoint(ts=pd.to_datetime(r["ts"], utc=True).to_pydatetime(),
                         q_flow_heat=float(r["q_flow_heat"]),
                         temperature=None if pd.isna(r.get("temperature")) else float(r["temperature"]))
            for _, r in df.iterrows()]

@app.post("/ingest")
async def ingest(payload: IngestPayload, current_user: User = Depends(get_current_user)):
    if not payload.records:
        raise HTTPException(400, "No records provided.")
    n = _insert_records(payload.building_id, payload.records)
    return {"inserted": int(n), "building_id": payload.building_id}

@app.post("/train")
async def train(building_id: str = Query(...), min_rows: int = Query(72, ge=24), current_user: User = Depends(get_current_user)):
    return {"building_id": building_id, **_train(building_id, min_rows=min_rows)}

@app.get("/forecast", response_model=ForecastResponse)
async def forecast(building_id: str, hours: int = Query(24, ge=1, le=168), current_user: User = Depends(get_current_user)):
    return _forecast(building_id, hours)

@app.get("/carbon", response_model=CarbonResponse)
async def carbon(building_id: str,
                 hours: int = Query(24, ge=1, le=168),
                 factor_g_per_kwh: float = Query(220.0),
                 current_user: User = Depends(get_current_user)):
    fc = _forecast(building_id, hours)
    co2 = [float(v) * float(factor_g_per_kwh) for v in fc.q_forecast]
    total = float(np.sum(co2))
    return CarbonResponse(building_id=building_id, horizon=hours,
                          factor_g_per_kwh=factor_g_per_kwh, ts=fc.ts,
                          co2_g=co2, total_co2_g=total)





from fastapi.responses import JSONResponse

# ---------- Gaia-X Self Description ----------
@app.get("/gaiax/metadata")
def gaiax_metadata():
    return JSONResponse(content={
        "@context": "https://www.w3.org/ns/odrl.jsonld",
        "@type": "gx:ServiceOffering",
        "gx:provider": {
            "gx:legalName": "Hackathon Future Lab",
            "gx:participantId": "urn:gx:participant:pedram-lab",
            "gx:contact": "mailto:info@hackathonfuturelab.org"
        },
        "gx:service": {
            "gx:title": APP_NAME,
            "gx:description": "Energy Forecast & CO₂ API for federated energy data spaces",
            "gx:version": "0.1.0",
            "gx:accessPolicy": "JWT Token",
            "gx:endpoints": [
                {"url": "/ingest", "method": "POST", "securedBy": "JWT"},
                {"url": "/forecast", "method": "GET", "securedBy": "JWT"},
                {"url": "/carbon", "method": "GET", "securedBy": "JWT"}
            ]
        }
    })

# ---------- Gaia-X Data Contract ----------
@app.get("/gaiax/datacontract")
def gaiax_data_contract():
    return JSONResponse(content={
        "@context": "https://www.w3.org/ns/odrl.jsonld",
        "@type": "odrl:Policy",
        "odrl:permission": [
            {
                "odrl:target": "Energy consumption & CO₂ forecast",
                "odrl:action": "use",
                "odrl:constraint": {"odrl:operator": "eq", "odrl:rightOperand": "research"}
            }
        ],
        "odrl:prohibition": [],
        "odrl:obligation": [
            {"odrl:action": "delete", "odrl:constraint": {"odrl:operator": "lteq", "odrl:rightOperand": "30d"}}
        ],
        "license": "CC-BY-4.0",
        "security": "JWT authentication + mTLS (planned)"
    })

# ---------- Gaia-X Self-Description ----------
@app.get("/gaiax/descriptor")
def gaiax_descriptor():
    """
    Minimal Gaia-X Service Self-Description (for hackathon prototype)
    Format: JSON-LD (Gaia-X standard for interoperability)
    """
    descriptor = {
        "@context": "https://www.w3.org/ns/odrl.jsonld",
        "@type": "gx:ServiceOffering",
        "gx:legalEntity": {
            "gx:legalName": "Hackathon Future Lab",
            "gx:legalRegistrationNumber": "DE-HFL-2025",
            "gx:location": "Berlin, Germany"
        },
        "gx:serviceDescription": {
            "gx:name": APP_NAME,
            "gx:version": "0.1.0",
            "gx:description": "Energy forecasting and CO2 estimation service using federated building data.",
            "gx:endpoints": [
                {
                    "gx:entrypoint": "/ingest",
                    "gx:method": "POST",
                    "gx:description": "Ingest new measurement data for a building."
                },
                {
                    "gx:entrypoint": "/train",
                    "gx:method": "POST",
                    "gx:description": "Train a forecast model for a building."
                },
                {
                    "gx:entrypoint": "/forecast",
                    "gx:method": "GET",
                    "gx:description": "Retrieve energy forecast for a building."
                },
                {
                    "gx:entrypoint": "/carbon",
                    "gx:method": "GET",
                    "gx:description": "Retrieve CO2 emissions forecast."
                }
            ]
        },
        "gx:dataCategories": ["Energy usage", "Temperature"],
        "gx:compliance": ["Gaia-X Hackathon Prototype"],
        "gx:security": {
            "gx:authentication": "JWT Bearer Token",
            "gx:encryption": "TLS 1.2+",
            "gx:identity": "Self-issued for hackathon, mTLS planned"
        }
    }
    return descriptor




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), reload=True)
