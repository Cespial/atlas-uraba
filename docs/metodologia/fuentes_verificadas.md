# Fuentes verificadas — Atlas Urabá
> Deep-research: 112 agentes · 952 tool calls · mayo 2026

## Estado de verificación

| Símbolo | Significado |
|---------|-------------|
| ✅ 3-0 | Verificado unánimemente |
| ⚠️ 2-1 | Verificado con un disidente |
| ❌ REFUTADO | Claim falso o no confirmado |
| 🔍 No verificado | No revisado en esta ronda |

---

## A. IGAC — Catastro

### ⚠️ IGAC: Antioquia requiere catastro departamental (CONFIRMADO)

> Antioquia opera un catastro descentralizado y **NO está incluida** en la
> descarga nacional de la Base Catastral Pública IGAC 2026. Lo mismo aplica
> para Bogotá D.C., Medellín y Cali.
>
> La descarga IGAC 2026 cubre únicamente los departamentos bajo jurisdicción
> directa del IGAC. Para Urabá/Antioquia se debe gestionar el catastro a través
> de la Gobernación de Antioquia o la Lonja de Propiedad Raíz local.
>
> **Capas disponibles en la descarga IGAC 2026** (confirmadas):
> - `U_MANZANA` — manzanas urbanas
> - `U_TERRENO` — terrenos/predios urbanos
> - `U_CONSTRUCCION` — construcciones urbanas
> - `R_VEREDA` — veredas rurales
> - `R_TERRENO` — terrenos/predios rurales
> - `R_SECTOR` — sectores rurales
>
> **Columna de código municipal real**: `codigo_mun` (string 5 dígitos, ej: `"05045"`)

### Base Catastral Pública IGAC 2026 ✅ 3-0
- **Portal**: https://datos.icde.gov.co/datasets/2e26ee016ce14c359a5037231da25a86
- **Descarga**: `wget -L 'https://www.arcgis.com/sharing/rest/content/items/2e26ee016ce14c359a5037231da25a86/data' -O CatastroPublicoIGAC_2026.zip`
- **Formato**: Shapefile en ZIP (tamaño real desconocido — claim de 2.92 GB REFUTADO)
- **Licencia**: CC BY-SA 4.0 — libre
- **Nota**: La URL S3 a la que redirige expira en 5 min; usar el endpoint ArcGIS REST como referencia estable
- **Cobertura Urabá**: ❌ Antioquia NO incluida (catastro descentralizado) — ver nota arriba

### IGAC SharePoint departamental ⚠️ 2-1
- **URL**: https://igacoffice365.sharepoint.com/:f:/g/El_cx99zlE5FrMda2G7Ff9oB8nRia9fawp_SoYlLixSHNA?e=ewJbmZ
- **Nota**: Puede requerir cuenta Microsoft — verificar acceso manualmente

### ICDE WFS/Feature Services ✅ 3-0
- **Búsqueda**: https://datos.icde.gov.co/search?q=CATASTRO&type=wfs%2Cfeature%20layer%2Cmap%20service%2Cfeature%20service
- **Formato**: WFS, Feature Service, Map Service — acceso directo desde QGIS

---

## B. DANE — Cartografía y Censos

### Marco Geoestadístico Nacional (MGN) 2024 ✅ 3-0
- **Hub ArcGIS**: https://cdge-dane-danehub.hub.arcgis.com/maps/1f88b146756f4a6dac586c813b7040b3
- **Capa manzana**: sub-capa _215
- **Descarga via Python**:
  ```python
  from arcgis.features import FeatureLayer
  layer = FeatureLayer("https://services.arcgis.com/.../FeatureServer/215")
  sdf = layer.query(where="MPIO_CCDGO IN ('05045','05147','05120',...)", out_sr=4326).sdf
  ```
- **Formato**: Feature Service / Shapefile / GeoPackage
- **Libre**: sin autenticación

### CNPV 2018 — Variables por manzana ✅ 3-0
- **Portal de descarga**: https://geoportal.dane.gov.co/servicios/descarga-y-metadatos/datos-geoestadisticos/?cod=4
- **Geovisor detallado**: https://geoportal.dane.gov.co/geovisores/sociedad/cnpv2018-detallado/
- **Descarga manual**: portal → Manzana → Shapefile
- **Variables por manzana**: materiales vivienda, servicios públicos, hacinamiento, escolaridad, empleo, migración

### ❌ REFUTADO: URL directa shapefile manzanas CNPV 2018 (1-2)
> La URL del directorio RAR (~277 MB) NO fue confirmada — no usar.

### ❌ REFUTADO: Microdatos CNPV 2018 a nivel manzana (0-3)
> Los microdatos en microdatos.dane.gov.co/catalog/643 llegan a nivel municipal/cabecera/resto.
> **NO hay disagregación a manzana individual** en los microdatos.
> Usar el Geovisor Detallado para variables a nivel manzana.

---

## C. MinSalud — REPS

### REPS Prestadores de Salud ✅ 3-0 — GEOCODIFICADO
- **Portal**: https://www.datos.gov.co/Salud-y-Protecci-n-Social/Registro-Especial-de-Prestadores-y-Sedes-de-Servic/c36g-9fc2
- **Descarga directa CSV**: `wget 'https://www.datos.gov.co/api/views/c36g-9fc2/rows.csv?accessType=DOWNLOAD'`
- **Registros Urabá**: 339 prestadores confirmados
  - Apartadó: 196 · Turbo: 79 · Chigorodó: 32 · resto: ~32
- **Formato**: CSV
- **Columnas reales**: `CodigoPrestador`, `NombrePrestador`, `NombreSede`,
  `MunicipioPrestador` (5d), `DepartamentoPrestadorDesc`, `DireccionPrestador`,
  `ClasePrestador`, `NivelAtencion`
- **SIN coordenadas geográficas** — geocodificados por dirección
- **Archivo filtrado Urabá**: `data/processed/equipamientos/reps_uraba.csv`
- **Geocodificado**: `data/processed/equipamientos/reps_uraba_geo.gpkg` ✅

---

## D. MEN — SIMAT

### Establecimientos Educativos Colombia ✅ 3-0 — GEOCODIFICADO
- **Portal**: https://www.datos.gov.co/Educaci-n/ESTABLECIMIENTOS-EDUCATIVOS-COLOMBIA/upkm-vdjb
- **Descarga directa CSV**: `wget 'https://www.datos.gov.co/api/views/upkm-vdjb/rows.csv?accessType=DOWNLOAD'`
- **Registros Urabá**: 180 establecimientos confirmados (datos 2016)
- **Formato**: CSV
- **Columnas reales**: `año`, `codigomunicipio`, `nombreestablecimiento`, `zona`,
  `direccion`, `niveles`, `matricula_Contratada`
- **SIN coordenadas** — geocodificados por dirección
- **⚠️ Datos de 2016** — pueden estar desactualizados
- **⚠️ Sin desglose de matrícula por nivel** — solo `matricula_Contratada` como proxy
- **Geocodificado**: `data/processed/equipamientos/simat_uraba_geo.gpkg` ✅

---

## E. OpenStreetMap 🔍 No verificado adversarialmente (URL conocida y confiable)
- **Colombia PBF**: https://download.geofabrik.de/south-america/colombia-latest.osm.pbf
- **Descarga**: `wget 'https://download.geofabrik.de/south-america/colombia-latest.osm.pbf'`
- **Tamaño**: ~299 MB (actualizado ~semanalmente)
- **Recorte Urabá** (osmium): `osmium extract --bbox="-77.2,7.3,-75.8,8.7" colombia-latest.osm.pbf -o uraba.osm.pbf`
- **Formato**: PBF → convertir con pyosmium o usar osmnx directamente

---

## F. Google Earth Engine 🔍 Requiere configuración
- **Registro gratuito**: https://code.earthengine.google.com/register
- **Colecciones**:
  - Sentinel-2: `COPERNICUS/S2_SR_HARMONIZED` (10m, NDVI)
  - Landsat 8: `LANDSAT/LC08/C02/T1_L2` (30m, LST)
- **BBox Urabá**: `ee.Geometry.BBox(-77.2, 7.3, -75.8, 8.7)`
- **Notebook**: `notebooks/04_satelital_gee.ipynb`

---

## G. Fuentes sin verificar (acceso manual requerido)

| Fuente | Portal | Notas |
|--------|--------|-------|
| **SIEDCO Policía** | https://www.policia.gov.co/estadisticas-criminalidad | Georeferenciado solo en ciudades grandes; Urabá: nivel municipal |
| **UARIV Desplazamiento** | https://www.unidadvictimas.gov.co/es/reportes | Excel por municipio, histórico |
| **SIAC/Manglares** | https://siac.mads.gov.co/SIAC/ | Manglares Caribe colombiano |
| **SINAP Áreas protegidas** | https://runap.parquesnacionales.gov.co/datos-abiertos | Shapefile |
| **INVIAS Red vial** | https://herramientas.invias.gov.co/infraestructura/ | Shapefile red nacional |
| **DANE NBI Antioquia** | https://www.dane.gov.co (buscar NBI) | Excel por municipio |

---

## Guía de descarga rápida

```bash
# Todo automático (lo que se puede)
bash scripts/download_data.sh all

# Por fuente
bash scripts/download_data.sh igac     # Catastro IGAC 2026
bash scripts/download_data.sh mgn      # MGN 2024 manzanas
bash scripts/download_data.sh reps     # REPS MinSalud
bash scripts/download_data.sh simat    # SIMAT MEN
bash scripts/download_data.sh osm      # OpenStreetMap Colombia

# Geocodificar REPS y SIMAT (después de descargar)
python scripts/geocode_equipamientos.py all

# Configurar GEE
bash scripts/download_data.sh gee      # instrucciones + script Python

# Ver fuentes manuales
bash scripts/download_data.sh manual
```
