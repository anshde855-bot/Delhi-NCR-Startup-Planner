from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any

import math
import json
import os
from functools import lru_cache

import pandas as pd
from shapely.geometry import Point, shape
from shapely.prepared import prep

APP_DIR = os.path.dirname(__file__)
REPO_DIR = os.path.abspath(os.path.join(APP_DIR, ".."))
DATA_DIR = REPO_DIR

CSV_PATH = os.path.join(DATA_DIR, "..", "DelhiNCR Restaurants.csv")
BOUNDARY_PATH = os.path.join(DATA_DIR, "..", "Delhi_Boundary.geojson")


app = FastAPI(title="SpatialSite Backend (MVP)")


class ScoreRequest(BaseModel):
    lat: float
    lng: float
    radius_km: float = Field(default=2.0, ge=0.1, le=20)

    # Weight knobs (sum not required; we normalize internally)
    w_population: float = 0.40
    w_competitors: float = 0.35
    w_competitor_distance: float = 0.25


class ScoreResponse(BaseModel):
    score: float
    metrics: dict[str, Any]


class RestaurantPoint(BaseModel):
    name: str | None = None
    lat: float
    lng: float
    rating: float | None = None
    locality: str | None = None


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
    # Load boundary polygon(s)
    with open(BOUNDARY_PATH, "r", encoding="utf-8") as f:
        boundary_geo = json.load(f)

    geoms = []
    for feat in boundary_geo.get("features", []):
        geoms.append(shape(feat["geometry"]))

    boundary_union = geoms[0]
    for g in geoms[1:]:
        boundary_union = boundary_union.union(g)

    boundary_prepared = prep(boundary_union)

    # Load restaurants
    df = pd.read_csv(CSV_PATH)

    # Ensure numeric
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    if "Dining_Rating" in df.columns:
        df["Dining_Rating"] = pd.to_numeric(df["Dining_Rating"], errors="coerce")

    df = df.dropna(subset=["Latitude", "Longitude"]).copy()

    points: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        lat = float(row["Latitude"])
        lng = float(row["Longitude"])
        p = Point(lng, lat)  # shapely expects lon,lat
        if boundary_prepared.contains(p) or boundary_prepared.touches(p):
            points.append(
                {
                    "name": row.get("Restaurant_Name"),
                    "lat": lat,
                    "lng": lng,
                    "rating": (None if pd.isna(row.get("Dining_Rating")) else float(row.get("Dining_Rating"))),
                    "locality": row.get("Locality"),
                }
            )

    return boundary_union, boundary_prepared, points


def normalize_weights(*weights: float) -> tuple[float, ...]:
    s = sum(max(0.0, w) for w in weights)
    if s <= 0:
        # fallback to equal
        n = len(weights)
        return tuple(1.0 / n for _ in range(n))
    return tuple(max(0.0, w) / s for w in weights)


@app.get("/health")
def health():
    # Force load on startup-ish
    _ = load_boundary_and_points()
    return {"status": "ok", "points_loaded": len(load_boundary_and_points()[2])}


@app.get("/restaurants", response_model=list[RestaurantPoint])
def restaurants(bbox: str | None = None):
    # bbox: "minLng,minLat,maxLng,maxLat"
    _, _, points = load_boundary_and_points()

    if not bbox:
        return [RestaurantPoint(**p) for p in points]

    parts = [float(x) for x in bbox.split(",")]
    min_lng, min_lat, max_lng, max_lat = parts

    out = []
    for p in points:
        if p["lng"] >= min_lng and p["lng"] <= max_lng and p["lat"] >= min_lat and p["lat"] <= max_lat:
            out.append(RestaurantPoint(**p))
    return out


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    _, _, points = load_boundary_and_points()

    # Candidate point
    q_lat, q_lng = req.lat, req.lng

    # Metrics within radius
    nearby = []
    for p in points:
        d = haversine_km(q_lat, q_lng, p["lat"], p["lng"])
        if d <= req.radius_km:
            nearby.append((p, d))

    competitor_density = len(nearby)

    # Use competitor proximity: closer competitors reduce score (we can invert)
    if nearby:
        mean_distance = sum(d for _, d in nearby) / len(nearby)
        min_distance = min(d for _, d in nearby)
    else:
        # If no nearby competitors/restaurants, treat as very good for competitors-distance metric
        mean_distance = req.radius_km
        min_distance = req.radius_km

    # Population proxy: in absence of census grid in MVP, use an accessibility proxy:
    # - density of nearby venues (assume more activity => more footfall potential)
    population_proxy = len(nearby)

    # Normalize components to [0,1] with reasonable caps for MVP.
    # - population_proxy: cap at 50 nearby points
    pop_norm = min(1.0, population_proxy / 50.0)

    # - competitors_density: more competitors can be bad for independent sites; cap at 50
    comp_density_norm = min(1.0, competitor_density / 50.0)

    # - competitor_distance: larger mean distance => better (less saturation)
    #   normalize by radius: mean_distance in [0, radius]
    comp_dist_norm = min(1.0, mean_distance / max(1e-6, req.radius_km))

    # Convert to desirability:
    #   population: higher better => pop_norm
    #   competitors: lower better => (1 - comp_density_norm)
    #   distance: higher better => comp_dist_norm
    desirability_population = pop_norm
    desirability_low_competitors = 1.0 - comp_density_norm
    desirability_distance = comp_dist_norm

    w_pop, w_comp, w_dist = normalize_weights(req.w_population, req.w_competitors, req.w_competitor_distance)

    raw = (
        w_pop * desirability_population
        + w_comp * desirability_low_competitors
        + w_dist * desirability_distance
    )

    score_0_100 = float(max(0.0, min(100.0, raw * 100.0)))

    metrics = {
        "radius_km": req.radius_km,
        "nearby_points": len(nearby),
        "population_proxy": population_proxy,
        "competitor_density": competitor_density,
        "mean_competitor_distance_km": mean_distance,
        "min_competitor_distance_km": min_distance,
        "normalized": {
            "population": desirability_population,
            "low_competitors": desirability_low_competitors,
            "competitor_distance": desirability_distance,
        },
        "weights_normalized": {
            "w_population": w_pop,
            "w_competitors": w_comp,
            "w_competitor_distance": w_dist,
        },
    }

    return ScoreResponse(score=score_0_100, metrics=metrics)

