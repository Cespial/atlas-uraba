# Stack tecnológico — Atlas Urabá

Basado en investigación de 110 agentes verificando 27 fuentes (mayo 2026).
Referente arquitectónico principal: [GHSCI v4.13.1](https://github.com/healthysustainablecities/global-indicators).

## Capa de datos

| Herramienta | Versión | Rol | Justificación |
|-------------|---------|-----|---------------|
| PostgreSQL + PostGIS | 16 + 3.4 | Base de datos espacial central | Estándar en proyectos geoespaciales de escala; maneja millones de geometrías de manzanas |
| pgRouting | 3.x | Análisis de red vial | Routing desde manzana → equipamiento para indicadores de accesibilidad real |
| GDAL/OGR | 3.8+ | Conversión de formatos | Shapefile IGAC, GeoJSON DANE, rasters GEE → PostgreSQL |

Levantamiento local: `docker-compose up` en `infra/`.

## Pipeline analítico (Python)

| Herramienta | Versión | Rol | Por qué (no otra) |
|-------------|---------|-----|-------------------|
| GeoPandas | 0.14+ | Manipulación geoespacial core | Base de todo el stack Python geoespacial |
| OSMnx | 1.9+ (v2.1, Feb 2026) | Red vial OSM + isócronas + métricas de red | `intersection_density`, `circuity`, routing multi-criterio en una sola línea |
| r5py | 1.0.7 | Matrices de tiempo de viaje multimodal | Wrappea motor R5 (Conveyal); el más preciso para walk+transit+bike; acepta GeoDataFrames |
| PySAL-esda | latest | Autocorrelación espacial (LISA, Moran) | Estándar académico para detección de clusters espaciales (Zonas Atlas) |
| tobler | latest | Interpolación areal + dasymetría | **Crítico**: disagregar datos DANE sector → manzana cuando hay supresión de privacidad |
| Rasterio | 1.3+ | Rasters satelitales | Procesar GeoTIFFs de GEE (NDVI, LST) por manzana |
| scikit-learn | latest | PCA y normalización | Método dep_index: PCA sobre variables censales → índice compuesto |
| earthengine-api | latest | Google Earth Engine | Descarga NDVI Sentinel-2 y LST Landsat para dimensión ambiental |

> **⚠️ Deck.gl refutado** — no usar directamente. Kepler.gl (que usa deck.gl internamente) es la herramienta validada.

## Visualización web

| Herramienta | Versión | Rol |
|-------------|---------|-----|
| Kepler.gl | 3.1 (2025) | Visualización web de alto rendimiento; soporta PMTiles; data-agnostic |
| Mapbox GL JS | latest | Mapas base y estilos personalizados |
| PMTiles | latest | Servir tiles de manzanas sin servidor dedicado |

## Entorno y reproducibilidad

```bash
# Levantar base de datos
docker-compose -f infra/docker-compose.yml up -d

# Crear entorno Python
conda env create -f infra/environment.yml
conda activate atlas-uraba

# Instalar paquete en modo desarrollo
pip install -e .
```

## Diagrama de flujo de datos

```
Fuentes externas                  Pipeline Python              Salida
──────────────────────────────────────────────────────────────────────
DANE CNPV 2018 (CSV/SHP)  ──┐
IGAC Catastro (SHP)        ──┤  dane_loader.py
OSM (PBF)                  ──┤  osm_extractor.py    ┌─ PostgreSQL/PostGIS
REPS MinSalud (CSV)        ──┤  igac_loader.py       │  (esquemas: raw →
SIMAT MEN (CSV)            ──┤                        │   staging → indicators
SIEDCO (CSV)               ──┤                        │   → outputs)
GEE Sentinel-2/Landsat     ──┘  gee_downloader.py    └─────────────┐
                                                                      │
                           ┌── disaggregate.py (tobler)              │
                           │   (sector → manzana)                    │
                           ├── indicators/*/                          │
                           │   (18+ indicadores, 0-1 normalizados)   │
                           ├── composite/aggregator.py                │
                           │   (PCA + ponderación → índice Atlas)    │
                           └── composite/spatial_clusters.py ─────────┘
                               (LISA → Zonas Atlas HH/LL/HL/LH)
                                          │
                                    kepler_export.py
                                          │
                                    Kepler.gl / Mapbox GL JS
```
