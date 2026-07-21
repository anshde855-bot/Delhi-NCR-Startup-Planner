from __future__ import annotations

import json
import math
import os
from functools import lru_cache

import pandas as pd
from flask import Flask, jsonify, request, render_template_string
from shapely.geometry import Point, shape
from shapely.prepared import prep

BASE_DIR = os.path.dirname(__file__)
DATA_CSV_PATH = os.path.join(BASE_DIR, "..", "DelhiNCR Restaurants.csv")
BOUNDARY_PATH = os.path.join(BASE_DIR, "..", "Delhi_Boundary.geojson")

app = Flask(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@lru_cache(maxsize=1)
def load_boundary_and_points():
    with open(BOUNDARY_PATH, "r", encoding="utf-8") as f:
        boundary_geo = json.load(f)

    geoms = [shape(feat["geometry"]) for feat in boundary_geo.get("features", [])]
    boundary_union = geoms[0]
    for g in geoms[1:]:
        boundary_union = boundary_union.union(g)

    boundary_prepared = prep(boundary_union)

    df = pd.read_csv(DATA_CSV_PATH)
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    if "Dining_Rating" in df.columns:
        df["Dining_Rating"] = pd.to_numeric(df["Dining_Rating"], errors="coerce")

    df = df.dropna(subset=["Latitude", "Longitude"]).copy()

    points: list[dict] = []
    for _, row in df.iterrows():
        lat = float(row["Latitude"])
        lng = float(row["Longitude"])
        p = Point(lng, lat)  # shapely uses lon,lat

        if boundary_prepared.contains(p) or boundary_prepared.touches(p):
            points.append(
                {
                    "name": row.get("Restaurant_Name"),
                    "lat": lat,
                    "lng": lng,
                    "rating": None if pd.isna(row.get("Dining_Rating")) else float(row.get("Dining_Rating")),
                    "locality": row.get("Locality"),
                }
            )

    return boundary_union, boundary_prepared, points


def normalize_weights(*weights: float) -> tuple[float, ...]:
    s = sum(max(0.0, w) for w in weights)
    if s <= 0:
        n = len(weights)
        return tuple(1.0 / n for _ in range(n))
    return tuple(max(0.0, w) / s for w in weights)


INDEX_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SpatialSite - Python MVP</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
      body { font-family: system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif; background:#0b1020; color:#e8eefc; margin:0; }
      .wrap { display:grid; grid-template-columns: 360px 1fr; gap: 14px; padding: 14px; height: 100vh; box-sizing:border-box; }
      @media (max-width: 900px){ .wrap { grid-template-columns:1fr; height:auto; } #map { height: 520px; } }
      .card { background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius:14px; padding:14px; }
      .title { font-weight:800; font-size:18px; margin-bottom:4px; }
      .sub { opacity:.8; font-size:13px; margin-top:4px; }
      .label { display:flex; flex-direction:column; gap:6px; font-size:13px; margin:10px 0; }
      input { padding: 8px 10px; border-radius:10px; border: 1px solid rgba(255,255,255,.12); background:#0f1730; color:#e8eefc; }
      .btn { padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,.15); background:#162048; color:#e8eefc; cursor:pointer; font-weight:700; width:100%; margin-top:10px; }
      .map { border-radius:14px; overflow:hidden; border: 1px solid rgba(255,255,255,.08); }
      #map { width:100%; height: calc(100vh - 28px); }
      .score { font-size:26px; font-weight:900; letter-spacing:.2px; }
      .hint { opacity:.8; font-size:13px; margin-top:8px; }
      .metrics { font-size:13px; line-height:1.6; margin-top:10px; opacity:.95; }
      .divider { height:1px; background:rgba(255,255,255,.08); margin:12px 0; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <div class="title">SpatialSite — Python MVP</div>
        <div class="sub">Click the map to compute a Site Success Score using Delhi restaurant density & proximity.</div>

        <label class="label">Radius (km)
          <input id="radius" type="number" min="0.1" max="20" step="0.1" value="2" />
        </label>

        <label class="label">W Population proxy
          <input id="w_pop" type="number" step="0.05" value="0.4" />
        </label>
        <label class="label">W Competitors
          <input id="w_comp" type="number" step="0.05" value="0.35" />
        </label>
        <label class="label">W Competitor distance
          <input id="w_dist" type="number" step="0.05" value="0.25" />
        </label>

        <div class="divider"></div>

        <div class="score" id="score">— / 100</div>
        <div class="hint" id="hint">Loading restaurants...</div>
        <div class="metrics" id="metrics"></div>
      </div>

      <div class="map" id="map"></div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
      const API_BASE = '';

      async function getRestaurants(){
        const res = await fetch(`${API_BASE}/restaurants`);
        return await res.json();
      }

      async function getScore(lat, lng, radiusKm, weights){
        const body = { lat, lng, radius_km: radiusKm, ...weights };
        const res = await fetch(`${API_BASE}/score`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
        return await res.json();
      }

      const mapCenter = [28.6139, 77.209];
      const map = L.map('map', { zoomControl:true }).setView(mapCenter, 11);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution:'&copy; OSM contributors' }).addTo(map);

      const pointsLayer = L.layerGroup().addTo(map);
      const qMarkerStyle = { radius: 6, color: '#0066ff', weight: 2, fillOpacity: 0.15 };
      let qMarker = null;

      function setMetricsHtml(metrics){
        const lines = [
          `<div><b>Nearby points:</b> ${metrics.nearby_points}</div>`,
          `<div><b>Mean distance (km):</b> ${metrics.mean_competitor_distance_km.toFixed(3)}</div>`,
          `<div><b>Population proxy:</b> ${metrics.population_proxy}</div>`,
          `<div><b>Competitor density:</b> ${metrics.competitor_density}</div>`,
        ];
        document.getElementById('metrics').innerHTML = lines.join('');
      }

      function readInputs(){
        const radiusKm = parseFloat(document.getElementById('radius').value);
        const weights = {
          w_population: parseFloat(document.getElementById('w_pop').value),
          w_competitors: parseFloat(document.getElementById('w_comp').value),
          w_competitor_distance: parseFloat(document.getElementById('w_dist').value),
        };
        return { radiusKm, weights };
      }

      map.on('click', async (e) => {
        const lat = e.latlng.lat;
        const lng = e.latlng.lng;

        if(qMarker) map.removeLayer(qMarker);
        qMarker = L.circleMarker([lat, lng], qMarkerStyle).addTo(map);

        const { radiusKm, weights } = readInputs();

        document.getElementById('hint').textContent = 'Computing...';
        document.getElementById('metrics').innerHTML = '';

        const data = await getScore(lat, lng, radiusKm, weights);
        document.getElementById('score').textContent = `${data.score.toFixed(1)} / 100`;
        setMetricsHtml(data.metrics);
        document.getElementById('hint').textContent = '';
      });

      (async () => {
        const restaurants = await getRestaurants();
        for(const r of restaurants){
          const marker = L.circleMarker([r.lat, r.lng], { radius: 3, fillOpacity: 0.6, color:'#ff7a00', weight:1 });
          const rating = r.rating ?? 'N/A';
          marker.bindPopup(`<b>${r.name ?? 'Restaurant'}</b><br/>Rating: ${rating}<br/>${r.locality ?? ''}`);
          marker.addTo(pointsLayer);
        }
        document.getElementById('hint').textContent = 'Click anywhere on the map to compute a score.';
      })();
    </script>
  </body>
</html>
"""




# Serve the UI at root
@app.get("/")
def index():
    return render_template_string(INDEX_HTML)



@app.get("/health")
def health():
    _, _, points = load_boundary_and_points()
    return jsonify({"status": "ok", "points_loaded": len(points)})


@app.get("/restaurants")
def restaurants():
    _, _, points = load_boundary_and_points()
    return jsonify(points)


@app.post("/score")
def score():
    payload = request.get_json(force=True) or {}
    q_lat = float(payload.get("lat"))
    q_lng = float(payload.get("lng"))
    radius_km = float(payload.get("radius_km", 2.0))

    w_population = float(payload.get("w_population", 0.40))
    w_competitors = float(payload.get("w_competitors", 0.35))
    w_competitor_distance = float(payload.get("w_competitor_distance", 0.25))

    _, _, points = load_boundary_and_points()

    nearby = []
    for p in points:
        d = haversine_km(q_lat, q_lng, p["lat"], p["lng"])
        if d <= radius_km:
            nearby.append((p, d))

    competitor_density = len(nearby)

    if nearby:
        mean_distance = sum(d for _, d in nearby) / len(nearby)
        min_distance = min(d for _, d in nearby)
    else:
        mean_distance = radius_km
        min_distance = radius_km

    population_proxy = len(nearby)

    pop_norm = min(1.0, population_proxy / 50.0)
    comp_density_norm = min(1.0, competitor_density / 50.0)
    comp_dist_norm = min(1.0, mean_distance / max(1e-6, radius_km))

    desirability_population = pop_norm
    desirability_low_competitors = 1.0 - comp_density_norm
    desirability_distance = comp_dist_norm

    w_pop, w_comp, w_dist = normalize_weights(w_population, w_competitors, w_competitor_distance)

    raw = (
        w_pop * desirability_population
        + w_comp * desirability_low_competitors
        + w_dist * desirability_distance
    )

    score_0_100 = max(0.0, min(100.0, raw * 100.0))

    metrics = {
        "radius_km": radius_km,
        "nearby_points": len(nearby),
        "population_proxy": population_proxy,
        "competitor_density": competitor_density,
        "mean_competitor_distance_km": mean_distance,
        "min_competitor_distance_km": min_distance,
    }

    return jsonify({"score": score_0_100, "metrics": metrics})


if __name__ == "__main__":
    #app.run(host="127.0.0.1", port=5000, debug=True)

