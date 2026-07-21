# SpatialSite (Location Intelligence) — MVP

## What this repo is
A B.Tech-friendly prototype for the **SpatialSite** startup idea.

- **Frontend:** React + Leaflet map (click-to-score)
- **Backend:** FastAPI + a simple scoring algorithm using restaurant point density & proximity
- **Data used:**
  - `Delhi_Boundary.geojson` (area of interest)
  - `DelhiNCR Restaurants.csv` (restaurant points + ratings)

## Architecture
1. Backend loads Delhi boundary polygon and filters restaurant points inside it.
2. Frontend fetches restaurant points and renders them.
3. User clicks a location; frontend calls backend `/score`.
4. Backend computes a Site Success Score (0–100) using:
   - Population proxy ≈ nearby venue density
   - Competitor density penalty ≈ high nearby density reduces score
   - Competitor distance bonus ≈ higher mean distance improves score

## Run (Backend)

### 1) Create virtual env (Python 3.10+ recommended)
```bash
cd spatialsite-backend
python -m venv .venv
.\ .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Run (Frontend)

### 1) Install
```bash
cd spatialsite-frontend
npm install
```

### 2) Dev server
```bash
set VITE_BACKEND_URL=http://127.0.0.1:8000
npm run dev
```

Open the shown localhost URL in a browser.

## Demo usage
- Load the app.
- Click on the map.
- The score + nearby metrics appear.

## Notes for presentation
- Explain that in real product you’d replace proxies with proper layers (footfall data, census, EV/competitor POIs, isochrones, etc.).
- Your MVP proves the end-to-end engineering loop: data → API → geospatial scoring → UI.

