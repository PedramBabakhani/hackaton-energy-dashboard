# Setup venv, install deps, generate sample, run API

# Create venv if missing
if (-not (Test-Path ".\.venv")) {
  python -m venv .venv
}

# Activate
. .\.venv\Scripts\Activate.ps1

# Deps
python -m pip install --upgrade pip
pip install -r requirements.txt

# Sample data file (for seeding)
python .\generate_sample_data.py

# Run server
python -m uvicorn main:app --reload
