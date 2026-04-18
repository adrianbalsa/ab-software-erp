# [DONE] Maps API & Route Optimization Implementation

## Backend Optimization

### 1. routes_optimizer.py [DONE]
```python
POST /api/v1/routes/optimize-route
- Google Distance Matrix API integration
- CO₂ footprint calculation via esg_engine
- Returns routes sorted by lowest emissions
- Supports waypoints for multi-stop routes
- Vehicle-specific normativa_euro factors
```

### 2. ESG Engine Integration [DONE]
```python
- calculate_co2_emissions(distancia_km, categoria_euro)
- get_co2_factor_kg_per_km(normativa_euro)
- EURO VI/V/IV/III emission factors
```

## Frontend Live Tracking

### 3. FleetMap.tsx [DONE]
```typescript
- react-google-maps integration
- Polyline routes (origin → vehicle → destination)
- ETA tooltips with real-time traffic data
- Origin/Destination markers with custom icons
- Truck markers with green branding
- Dark mode map styling
- InfoWindow with porte details + ETA
```

## Integration

### 4. API Keys & Rate Limiting [DONE]
```env
NEXT_PUBLIC_GOOGLE_MAPS_API_KEY (frontend)
Maps_API_KEY (backend; única variable soportada)
```

```python
Rate limiting: /api/v1/routes exempt from strict limits
RATE_LIMIT_EXEMPT_PREFIXES includes /api/v1/routes
```

### 5. Main Router Registration [DONE]
```python
app.include_router(
    routes_optimizer_v1.router,
    prefix="/api/v1/routes",
    tags=["Optimización de rutas"]
)
```

## Requirements
```txt
googlemaps>=4.10.0 (already in requirements.txt)
httpx>=0.27.0 (already in requirements.txt)
```

## Response Schema
```json
{
  "rutas": [
    {
      "route_id": 1,
      "distancia_km": 120.5,
      "tiempo_estimado_min": 95,
      "co2_kg": 74.71,
      "nox_g": 0,
      "tiene_peajes": false,
      "normativa_euro": "Euro VI",
      "factor_co2_kg_per_km": 0.62
    }
  ],
  "ruta_recomendada": { ... }
}
```

All checkpoints marked [DONE].
