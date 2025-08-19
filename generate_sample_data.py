import json
import numpy as np
import pandas as pd

# Generates a sample_data.json ready for POST /ingest

def make_sample(building_id="B-101", days=10):
    # Use tz_convert if already tz-aware, otherwise tz_localize
    start = pd.Timestamp.utcnow()
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")

    start = start - pd.Timedelta(hours=days * 24)
    rng = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    np.random.seed(42)

    # simple daily pattern
    base_temp = 20 + 10 * np.sin(2 * np.pi * (rng.hour) / 24.0)
    heat = 150 + 40 * np.cos(2 * np.pi * (rng.hour) / 24.0) + np.random.normal(0, 5, size=len(rng))

    records = [
        {
            "ts": t.isoformat(),
            "q_flow_heat": round(float(max(0, q)), 2),
            "temperature": round(float(temp), 2),
            "hour": int(t.hour),
            "weekday": int(t.weekday()),
            "month": int(t.month)
        }
        for t, temp, q in zip(rng, base_temp, heat)
    ]

    payload = {"building_id": building_id, "records": records}
    with open("sample_data.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote sample_data.json with {len(records)} rows for building {building_id}")

if __name__ == "__main__":
    make_sample()
