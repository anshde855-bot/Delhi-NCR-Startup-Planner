# SpatialSite (Python-only MVP)

This is a Python-only remake of the SpatialSite idea using your provided Delhi datasets:
- `Delhi_Boundary.geojson`
- `DelhiNCR Restaurants.csv`

## How to run

### 1) Create environment (recommended)
```bat
cd "c:/Users/anshd/Desktop/New folder/spatial_python_app"
python -m venv .venv
..venv\Scripts\activate
```

### 2) Install deps
```bat
pip install -r requirements.txt
```

### 3) Start web app
```bat
cd "c:/Users/anshd/Desktop/New folder/spatial_python_app"
python app.py
```
Then open:
- http://127.0.0.1:5000


## Features
- Loads restaurants inside the Delhi boundary polygon
- Click on the map to score a location
- Score formula (MVP proxy):
  - `population_proxy` = number of restaurants within `radius_km`
  - `competitor_density` = same density count
  - `competitor_distance` = mean distance to nearby restaurants
  - converts to `score` in range 0..100

