import json
import numpy as np
import pandas as pd

# Generates a sample_data.json ready for POST /ingest
# Matching Record schema in main.py (q_flow_heat, temperature, wind_speed, price)

def make_sample(building_id="B-101", days=10):
    # Start timestamp in UTC
    start = pd.Timestamp.utcnow()
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    else:
        start = start.tz_convert("UTC")

    start = start - pd.Timedelta(hours=days * 24)
    rng = pd.date_range(start, periods=days * 24, freq="h", tz="UTC")
    np.random.seed(42)

    # Temperature: daily sinusoidal cycle with some noise
    base_temp = 10 + 10 * np.sin(2 * np.pi * (rng.hour) / 24.0)
    temperature = base_temp + np.random.normal(0, 1.5, size=len(rng))

    # Heat demand: inverse relation to temperature, daily cycle + noise
    heat = (
        200 - 5 * temperature +
        40 * np.cos(2 * np.pi * rng.hour / 24.0) +
        np.random.normal(0, 8, size=len(rng))
    )

    # Wind speed: random but with weekly trend
    wind_speed = 2 + 1.5 * np.sin(2 * np.pi * rng.dayofyear / 7.0) + np.random.normal(0, 0.5, size=len(rng))

    # Price: daily peak around 18h, cheaper at night
    price = 40 + 15 * np.sin(2 * np.pi * (rng.hour - 18) / 24.0) + np.random.normal(0, 2, size=len(rng))

    records = [
        {
            "ts": t.isoformat(),
            "q_flow_heat": round(float(max(0, q)), 2),
            "temperature": round(float(temp), 2),
            "wind_speed": round(float(ws), 2),
            "price": round(float(p), 2)
        }
        for t, temp, q, ws, p in zip(rng, temperature, heat, wind_speed, price)
    ]

    payload = {"building_id": building_id, "records": records}
    with open("sample_data.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote sample_data.json with {len(records)} rows for building {building_id}")

if __name__ == "__main__":
    make_sample()
