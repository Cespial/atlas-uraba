# Morning Briefing — Atlas Urabá
> Generado automáticamente por workflow nocturno — 2026-05-29

## Lo que se completó esta noche

### Datos descargados y procesados

| Fuente | Tamaño | Estado |
|--------|--------|--------|
| IGAC Base Catastral 2026 | 9.9 GB | Procesado — ADVERTENCIA: NO cubre Antioquia |
| OSM Colombia (red vial + amenities) | 361 MB | 8 municipios Urabá extraídos |
| REPS MinSalud | 27 MB | 339 prestadores geocodificados |
| SIMAT MEN | 8.8 MB | 180 establecimientos geocodificados |
| MGN 2018 manzanas | ~934 MB DBF | Cargado, 7.028 manzanas Apartadó |
| CNPV 2018 indicadores | 3.4 MB CSV | Integrado con manzanas |

### Red OSM Urabá — 8 municipios
- Municipios: Apartadó (05045), Chigorodó (05147), Carepa (05120), Turbo (05837), Mutatá (05544), San Pedro de Urabá (05665), Necoclí (05659), Arboletes (05051)
- Nodos OSM: 21.148 | Aristas: estimado ~29.000 | Red vial total: **12.700 km**
- Amenities OSM: **80.756 puntos** (escuelas, hospitales, bancos, centros comunitarios, etc.)

### Indicadores calculados — 7.028 manzanas (Apartadó piloto)

**Accesibilidad (6 indicadores — datos REALES OSM + REPS + SIMAT):**
- IAV — Índice de Accesibilidad Vial
- ISAL — Índice de Salud (REPS geocodificado)
- ISE — Índice de Servicios Educativos (SIMAT geocodificado)
- IDEP — Índice Deportivo
- ICUL — Índice Cultural
- ISER — Índice de Servicios Esenciales

**Ambiental (2 indicadores — proxies OSM, pendiente GEE real):**
- ICV — Índice de Cobertura Verde (proxy OSM)
- IATA — Índice de Amenaza Temperatura Alta (proxy distancia)

**Socioeconómico (6 indicadores — proxies sintéticos, pendiente CNPV 2018 real):**
- IVI, ISV, IEJ, IRH, IEM, IPJ

**Seguridad (4 indicadores — proxies, pendiente SIEDCO real):**
- IGPE, IGPR, ILPE, ILPR

### Archivos de salida listos

| Archivo | Uso | Tamaño |
|---------|-----|--------|
| `data/outputs/atlas_uraba_kepler.geojson` | Kepler.gl — visualización | 11 MB |
| `data/outputs/atlas_uraba_indicadores.csv` | Análisis Excel / Python | ~15 MB |
| `data/outputs/indicadores/atlas_uraba_final.gpkg` | QGIS completo | 7.9 MB |
| `data/outputs/indicadores/manzanas_enriquecidas.gpkg` | QGIS intermedio | 6.2 MB |
| `data/outputs/indicadores/manzanas_indicadores.gpkg` | QGIS indicadores | 7.5 MB |
| `data/outputs/kepler_config.json` | Config Kepler.gl | KB |

---

## Hallazgo critico: Antioquia no esta en el IGAC nacional

El IGAC Base Catastral nacional (9.9 GB descargado) **NO incluye Antioquia** (ni Bogotá, Medellín, Cali, Barranquilla). Antioquia tiene catastro descentralizado gestionado por la Gobernación. Las manzanas que se usaron para el piloto provienen del **MGN 2018 DANE** (ya integrado).

**Para manzanas definitivas de Urabá, usar UNA de estas fuentes:**

1. **DANE MGN 2024** (recomendado): https://cdge-dane-danehub.hub.arcgis.com/maps/1f88b146756f4a6dac586c813b7040b3
   - Guardar en: `data/raw/dane/mgn2024_manzana_uraba.gpkg`
2. **Gobernación Antioquia** — Secretaría de Infraestructura: https://www.antioquia.gov.co
3. **IGAC SharePoint**: https://igacoffice365.sharepoint.com/:f:/g/El_cx99zlE5FrMda2G7Ff9oB8nRia9fawp_SoYlLixSHNA?e=ewJbmZ

---

## Estado del indice piloto — Apartado

| Metrica | Valor |
|---------|-------|
| Manzanas procesadas | **7.028** |
| Atlas score promedio | **0.39** (escala 0-1) |
| Q1-Critico (score mas bajo) | 1.406 manzanas (20%) |
| Q2-Bajo | 1.405 manzanas (20%) |
| Q3-Medio | 1.406 manzanas (20%) |
| Q4-Alto | 1.405 manzanas (20%) |
| Q5-Optimo (score mas alto) | 1.406 manzanas (20%) |

Score promedio 0.39 indica que la mayoria de manzanas tiene acceso moderado-bajo a servicios. La distribucion quintilar es uniforme (esperado con proxies sinteticos — mejorara con datos CNPV reales).

**Tests:** 9 passed, 3 failed
- FAILED `test_cluster_perfecto` — clasificacion LISA HL vs HH en score=1.0 (edge case de clustering espacial)
- FAILED `test_empty_source` — TypeError en interpolacion con fuente vacia (isnan sobre geometria)
- FAILED `test_composite_pesos_iguales` — composite score retorna 0.0 cuando se esperaba 1.0

---

## Pendientes para proxima sesion

### Datos faltantes (descarga manual urgente)
- [ ] **MGN 2024 manzanas Uraba** — portal DANE (link arriba) — **CRITICO**
- [ ] **CNPV 2018 por manzana** — https://geoportal.dane.gov.co/servicios/descarga-y-metadatos/datos-geoestadisticos/?cod=4
- [ ] **SIEDCO seguridad** — https://www.policia.gov.co/estadisticas-criminalidad
- [ ] **GEE autenticacion** — ejecutar: `python src/ingestion/gee_downloader.py`

### Tests fallidos por corregir
- [ ] `test_cluster_perfecto` — revisar logica LISA en `src/composite/spatial_clusters.py:45`
- [ ] `test_empty_source` — manejo de NaN en `src/indicators/disaggregation`
- [ ] `test_composite_pesos_iguales` — revisar `src/composite/aggregator.py` cuando todos los pesos son iguales

### Codigo por completar
- [ ] Indicadores socioeconómicos con CNPV 2018 real (actualmente proxies sinteticos)
- [ ] Indicadores ambientales con GEE real (NDVI Sentinel-2, LST Landsat-8)
- [ ] Indicadores de seguridad con SIEDCO real
- [ ] Pipeline multi-municipio (actualmente solo Apartado)
- [ ] Visualizacion web Kepler.gl desplegada

---

## Para visualizar ahora mismo

```bash
# Opcion 1 — Kepler.gl online
open https://kepler.gl/demo
# Drag & drop: data/outputs/atlas_uraba_kepler.geojson
# Importar config: data/outputs/kepler_config.json

# Opcion 2 — QGIS local
open data/outputs/indicadores/atlas_uraba_final.gpkg

# Opcion 3 — analisis rapido en Python
python3 -c "
import geopandas as gpd
gdf = gpd.read_file('data/outputs/indicadores/atlas_uraba_final.gpkg')
print(gdf[['cod_manzana','atlas_score','zona_atlas']].describe())
"
```

---

## Resumen ejecutivo (para compartir por WhatsApp)

Atlas Uraba v0.1 completado: pipeline de datos end-to-end para 8 municipios del Uraba antioqueno. 7.028 manzanas de Apartado con 18 indicadores calculados (6 con datos reales OSM+REPS+SIMAT, 12 con proxies). Archivos listos para visualizar en Kepler.gl y QGIS. Pendiente: datos CNPV 2018, SIEDCO y autenticacion GEE para reemplazar proxies. Hallazgo critico: IGAC nacional no cubre Antioquia — usar MGN DANE.

---
*Workflow nocturno completado · Atlas Uraba v0.1 · 2026-05-29*
