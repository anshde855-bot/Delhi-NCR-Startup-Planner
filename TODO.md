# SpatialSite MVP - TODO

## Step 1: Backend scaffold
- [x] Create FastAPI app with endpoints: /health, /restaurants, /score
- [ ] Implement in-memory geospatial indexing from DelhiNCR Restaurants.csv
- [ ] Clip/filter to Delhi boundary using Delhi_Boundary.geojson

## Step 2: Scoring algorithm
- [ ] Implement Site Success Score (0-100) using weighted proximity/density metrics
- [ ] Return score + metric breakdown

## Step 3: Frontend scaffold
- [ ] Create React UI with a map (Leaflet) and click-to-score
- [ ] Fetch restaurants and render as points

## Step 4: Integration
- [ ] Connect frontend to backend /score and show results
- [ ] Add simple heat/density visualization (radius aggregation/bins)

## Step 5: Docs + demo
- [ ] Write README explaining architecture, algorithm, and business model
- [ ] Provide run instructions

