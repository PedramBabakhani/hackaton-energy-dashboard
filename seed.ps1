# Seeds the API by POSTing sample_data.json to /ingest
# Usage: run after the API is already running on http://127.0.0.1:8000

if (-not (Test-Path ".\sample_data.json")) {
  python .\generate_sample_data.py
}

curl -X POST "http://127.0.0.1:8080/ingest" -H "Content-Type: application/json" --data-binary "@sample_data.json"
