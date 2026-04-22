# IPL Live Prediction System (Scaffold)

Complete starter scaffold for:
- Pre-match winner prediction (XGBoost classifier)
- Live prediction after match start (XGBoost regressor/classifier-style output)
- FastAPI backend
- Live score scraping/API integration placeholders

## Project Structure

```text
cric/
  data/
    raw/
    processed/
  models/
  notebooks/
  backend/
    app/
      __init__.py
      main.py
      api.py
      config.py
      schemas.py
      services/
        __init__.py
        data_service.py
        prediction_service.py
        live_service.py
        scrape_service.py
      utils/
        __init__.py
        preprocessing.py
        features.py
        helpers.py
  frontend/
    app/
  scripts/
    download_data.py
    preprocess_data.py
    train_winner_model.py
    train_score_model.py
    predict_live.py
    test_pipeline.py
  tests/
  docs/
  requirements.txt
  README.md
  .gitignore
```

## Prerequisites

- Python 3.10+ recommended
- CPU-only environment

## Setup

```bash
cd cric
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
```

## Data Placement

Place raw datasets at:
- `data/raw/matches.csv`
- `data/raw/deliveries.csv`

No data is bundled in this scaffold.

## Run Commands

```bash
# (Optional) create data directory reminder
python scripts/download_data.py

# Preprocess raw CSVs
python scripts/preprocess_data.py

# Train pre-match winner model
python scripts/train_winner_model.py

# Train live score model
python scripts/train_score_model.py

# Run a local live prediction demo
python scripts/predict_live.py

# Run smoke checks
python scripts/test_pipeline.py

# Start FastAPI server
uvicorn backend.app.main:app --reload
```

## API Endpoints

- `GET /api/v1/health`
- `POST /api/v1/predict/prematch`
- `POST /api/v1/predict/live`
- `GET /api/v1/live/match/{match_id}`

## Next Steps

1. Align target/feature columns with your dataset schema in:
   - `backend/app/utils/features.py`
   - `backend/app/services/prediction_service.py`
2. Replace scraper placeholder in `backend/app/services/scrape_service.py` with a real source.
3. Add evaluation metrics and tests in `tests/`.

