# SpatialSite Backend

FastAPI backend for MVP.

## Endpoints
- `GET /health`
- `GET /restaurants?bbox=minLng,minLat,maxLng,maxLat`
- `POST /score`

## Scoring
Uses restaurant-point density as a footfall proxy and inversely rewards low nearby density / high distance.

