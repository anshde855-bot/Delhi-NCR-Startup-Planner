import React, { useEffect, useMemo, useState } from 'react'
import L from 'leaflet'

type Restaurant = {
  name?: string
  lat: number
  lng: number
  rating?: number | null
  locality?: string
}

type ScoreResponse = {
  score: number
  metrics: any
}

const BACKEND_URL = (import.meta as any).env?.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default function App() {
  const [restaurants, setRestaurants] = useState<Restaurant[]>([])
  const [score, setScore] = useState<number | null>(null)
  const [metrics, setMetrics] = useState<any>(null)
  const [radiusKm, setRadiusKm] = useState<number>(2)
  const [weights, setWeights] = useState({
    w_population: 0.4,
    w_competitors: 0.35,
    w_competitor_distance: 0.25,
  })

  const mapCenter = useMemo<[number, number]>(() => [28.6139, 77.209], [])

  useEffect(() => {
    fetch(`${BACKEND_URL}/restaurants`)
      .then((r) => r.json())
      .then((data) => setRestaurants(data))
      .catch((e) => console.error(e))
  }, [])

  useEffect(() => {
    const map = L.map('map', { zoomControl: true }).setView(mapCenter, 11)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)

    const pointsLayer = L.layerGroup().addTo(map)

    const renderPoints = () => {
      pointsLayer.clearLayers()
      for (const r of restaurants) {
        const marker = L.circleMarker([r.lat, r.lng], {
          radius: 3,
          fillOpacity: 0.6,
          color: '#ff7a00',
          weight: 1,
        })
        marker.bindPopup(
          `<b>${r.name ?? 'Restaurant'}</b><br/>Rating: ${r.rating ?? 'N/A'}<br/>${r.locality ?? ''}`,
        )
        marker.addTo(pointsLayer)
      }
    }

    renderPoints()

    let qMarker: L.CircleMarker | null = null

map.on('click', async (e: any) => {
      const lat = e.latlng.lat
      const lng = e.latlng.lng

      if (qMarker) qMarker.remove()
      qMarker = L.circleMarker([lat, lng], {
        radius: 6,
        color: '#0066ff',
        weight: 2,
        fillOpacity: 0.15,
      }).addTo(map)

      const body = {
        lat,
        lng,
        radius_km: radiusKm,
        ...weights,
      }

      const res = await fetch(`${BACKEND_URL}/score`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data: ScoreResponse = await res.json()

      setScore(data.score)
      setMetrics(data.metrics)
    })

    return () => {
      map.remove()
    }
  }, [restaurants, mapCenter, radiusKm, weights, BACKEND_URL])

  return (
    <div className="page">
      <header className="header">
        <div>
          <div className="title">SpatialSite — Site Success Score (MVP)</div>
          <div className="subtitle">Click any location on the map to get a score based on nearby restaurant density & proximity.</div>
        </div>
      </header>

      <main className="grid">
        <section className="card">
          <div className="cardTitle">Controls</div>

          <label className="label">
            Radius (km)
            <input
              className="input"
              type="number"
              min={0.1}
              max={20}
              step={0.1}
              value={radiusKm}
              onChange={(e) => setRadiusKm(parseFloat(e.target.value))}
            />
          </label>

          <div className="weights">
            <label className="label">
              W Population proxy
              <input
                className="input"
                type="number"
                step={0.05}
                value={weights.w_population}
                onChange={(e) => setWeights((w) => ({ ...w, w_population: parseFloat(e.target.value) }))}
              />
            </label>
            <label className="label">
              W Competitors
              <input
                className="input"
                type="number"
                step={0.05}
                value={weights.w_competitors}
                onChange={(e) => setWeights((w) => ({ ...w, w_competitors: parseFloat(e.target.value) }))}
              />
            </label>
            <label className="label">
              W Competitor distance
              <input
                className="input"
                type="number"
                step={0.05}
                value={weights.w_competitor_distance}
                onChange={(e) => setWeights((w) => ({ ...w, w_competitor_distance: parseFloat(e.target.value) }))}
              />
            </label>
          </div>

          <div className="divider" />

          <div className="cardTitle">Result</div>
          <div className="scoreBox">
            <div className="score">{score === null ? '—' : `${score.toFixed(1)} / 100`}</div>
            {metrics ? (
              <div className="metrics">
                <div><b>Nearby points:</b> {metrics.nearby_points}</div>
                <div><b>Mean distance (km):</b> {metrics.mean_competitor_distance_km.toFixed(3)}</div>
                <div><b>Population proxy:</b> {metrics.population_proxy}</div>
                <div><b>Competitor density:</b> {metrics.competitor_density}</div>
              </div>
            ) : (
              <div className="hint">Click on the map to compute a score.</div>
            )}
          </div>
        </section>

        <section className="mapWrap">
          <div id="map" className="map" />
        </section>
      </main>
    </div>
  )
}

