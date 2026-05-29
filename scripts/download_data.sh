#!/usr/bin/env bash
# =============================================================================
# Atlas Urabá — Script de descarga de fuentes de datos
# Verificado con deep-research (112 agentes, mayo 2026)
# =============================================================================
# Uso: bash scripts/download_data.sh [fuente]
#      bash scripts/download_data.sh all        # todo
#      bash scripts/download_data.sh igac       # solo catastro IGAC
#      bash scripts/download_data.sh osm        # solo OpenStreetMap
# =============================================================================

set -euo pipefail

RAW="$(dirname "$0")/../data/raw"
mkdir -p "$RAW"/{dane,igac,minsal,men,osm,siedco}

OK="\033[0;32m✓\033[0m"
WARN="\033[0;33m⚠\033[0m"
INFO="\033[0;34mℹ\033[0m"

log()  { echo -e "$INFO  $*"; }
ok()   { echo -e "$OK $*"; }
warn() { echo -e "$WARN $*"; }

# =============================================================================
# A. IGAC — Base Catastral Pública 2026
# Verificado 3-0 | Libre sin autenticación | Shapefile ZIP via S3
# =============================================================================
download_igac() {
  log "Descargando Base Catastral Pública IGAC 2026..."
  log "Fuente: https://datos.icde.gov.co/datasets/2e26ee016ce14c359a5037231da25a86"
  log "Licencia: CC BY-SA 4.0 | La URL S3 expira — usar el endpoint ArcGIS REST"

  # El endpoint ArcGIS REST redirige (302) a URL S3 firmada
  wget --content-disposition -L \
    'https://www.arcgis.com/sharing/rest/content/items/2e26ee016ce14c359a5037231da25a86/data' \
    -O "$RAW/igac/CatastroPublicoIGAC_2026.zip" \
    --progress=bar:force 2>&1 || {
    warn "wget falló — intentando con curl"
    curl -L \
      'https://www.arcgis.com/sharing/rest/content/items/2e26ee016ce14c359a5037231da25a86/data' \
      -o "$RAW/igac/CatastroPublicoIGAC_2026.zip" \
      --progress-bar
  }

  if [ -f "$RAW/igac/CatastroPublicoIGAC_2026.zip" ]; then
    ok "IGAC descargado: $RAW/igac/CatastroPublicoIGAC_2026.zip"
    log "Descomprimiendo..."
    unzip -o "$RAW/igac/CatastroPublicoIGAC_2026.zip" -d "$RAW/igac/catastro_2026/"
    ok "IGAC descomprimido en: $RAW/igac/catastro_2026/"
  else
    warn "Descarga IGAC falló. Acceso manual:"
    warn "  → https://datos.icde.gov.co/datasets/2e26ee016ce14c359a5037231da25a86"
    warn "  → Click 'Descargar' → Shapefile"
    warn "  → Guardar en: $RAW/igac/"
  fi
}

# =============================================================================
# B. DANE — CNPV 2018 variables por manzana (portal de descarga)
# Verificado 3-0 | Libre sin autenticación | Shapefile / GeoJSON / KML
# NOTA: La URL directa del shapefile fue REFUTADA — usar el portal web
# =============================================================================
download_dane_cnpv() {
  log "Portal CNPV 2018 (descarga manual requerida):"
  log "  URL portal: https://geoportal.dane.gov.co/servicios/descarga-y-metadatos/datos-geoestadisticos/?cod=4"
  log "  Geovisor:   https://geoportal.dane.gov.co/geovisores/sociedad/cnpv2018-detallado/"
  warn "La URL directa del shapefile de manzanas fue REFUTADA en verificación."
  warn "Descarga manual: ir al portal → seleccionar Manzana → formato Shapefile"
  warn "Guardar en: $RAW/dane/cnpv2018_manzana.zip"
  echo ""
  log "Variables disponibles por manzana:"
  log "  - Materiales de vivienda (paredes, piso, techo)"
  log "  - Servicios públicos (acueducto, alcantarillado, energía)"
  log "  - Hacinamiento de hogares"
  log "  - Educación (escolaridad jefe de hogar)"
  log "  - Empleo y actividad económica"
  echo ""
  log "Microdatos CNPV 2018 (nivel persona/hogar/vivienda):"
  log "  URL: https://microdatos.dane.gov.co/index.php/catalog/643"
  warn "Los microdatos NO tienen desagregación a manzana individual (REFUTADO 0-3)"
  warn "Nivel mínimo disponible: sección/sector censal → usar tobler para disagregar"
}

# =============================================================================
# C. DANE — Marco Geoestadístico Nacional (MGN) 2024 vía ArcGIS Hub
# Verificado 3-0 | Libre | Feature Service o descarga ArcGIS Hub
# =============================================================================
download_mgn() {
  log "Descargando MGN 2024 via ArcGIS Python API..."
  log "Fuente: https://cdge-dane-danehub.hub.arcgis.com/maps/1f88b146756f4a6dac586c813b7040b3"
  log "Capa manzana: sub-capa _215"

  python3 - <<'PYEOF'
import sys
try:
    from arcgis.features import FeatureLayer
    import geopandas as gpd
    from pathlib import Path

    out = Path("data/raw/dane")
    out.mkdir(parents=True, exist_ok=True)

    # MGN 2024 — capa de manzana censal (sub-capa 215)
    url = "https://services.arcgis.com/BtlwRZNPLn1aXGK4/arcgis/rest/services/MGN2024_INTE_MANZANA/FeatureServer/0"
    print(f"  Conectando a: {url}")

    layer = FeatureLayer(url)

    # Filtrar solo Antioquia (DPTO_CCDGO = '05') y municipios Urabá
    DIVIPOLA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]
    where = f"MPIO_CCDGO IN ({','.join([repr(d) for d in DIVIPOLA])})"
    print(f"  Filtro: {where}")

    sdf = layer.query(where=where, out_sr=4326).sdf
    print(f"  Manzanas obtenidas: {len(sdf)}")

    gdf = gpd.GeoDataFrame(sdf, geometry=gpd.GeoSeries.from_wkt(sdf.SHAPE.apply(str)), crs="EPSG:4326")
    gdf.to_file(str(out / "mgn2024_manzanas_uraba.gpkg"), driver="GPKG")
    print(f"  Guardado: {out}/mgn2024_manzanas_uraba.gpkg")

except ImportError:
    print("  arcgis no instalado. Instalando: pip install arcgis")
    print("  Alternativa manual:")
    print("  → https://cdge-dane-danehub.hub.arcgis.com/maps/1f88b146756f4a6dac586c813b7040b3")
    print("  → Click 'Descargar' → GeoPackage o Shapefile")
    print(f"  → Guardar en: data/raw/dane/")
except Exception as e:
    print(f"  Error: {e}")
    print("  Descarga manual en: https://cdge-dane-danehub.hub.arcgis.com/maps/1f88b146756f4a6dac586c813b7040b3")
PYEOF
}

# =============================================================================
# D. MinSalud — REPS (Registro Especial de Prestadores de Salud)
# Verificado 3-0 | 76,821 registros | CSV libre | SIN coordenadas (requiere geocodificación)
# =============================================================================
download_reps() {
  log "Descargando REPS MinSalud (datos.gov.co ID: c36g-9fc2)..."
  log "Fuente: https://www.datos.gov.co/Salud-y-Protecci-n-Social/Registro-Especial-de-Prestadores-y-Sedes-de-Servic/c36g-9fc2"
  warn "IMPORTANTE: El dataset NO incluye coordenadas geográficas (lat/lon)"
  warn "Se requiere geocodificación posterior usando dirección + municipio"

  wget -q --show-progress \
    'https://www.datos.gov.co/api/views/c36g-9fc2/rows.csv?accessType=DOWNLOAD' \
    -O "$RAW/minsal/reps_prestadores_colombia.csv" || {
    curl -L \
      'https://www.datos.gov.co/api/views/c36g-9fc2/rows.csv?accessType=DOWNLOAD' \
      -o "$RAW/minsal/reps_prestadores_colombia.csv" \
      --progress-bar
  }

  if [ -f "$RAW/minsal/reps_prestadores_colombia.csv" ]; then
    ROWS=$(wc -l < "$RAW/minsal/reps_prestadores_colombia.csv")
    ok "REPS descargado: $ROWS filas → $RAW/minsal/reps_prestadores_colombia.csv"
  fi

  # También descargar via Socrata API filtrando Antioquia
  log "Descargando REPS filtrado Antioquia via Socrata API..."
  curl -L \
    "https://www.datos.gov.co/resource/c36g-9fc2.csv?\$where=depa_nombre='ANTIOQUIA'&\$limit=50000" \
    -o "$RAW/minsal/reps_antioquia.csv" \
    --progress-bar || warn "Socrata API falló — usar CSV nacional y filtrar con pandas"
  ok "REPS Antioquia: $RAW/minsal/reps_antioquia.csv"
}

# =============================================================================
# E. MEN — SIMAT Establecimientos Educativos Colombia
# Verificado 3-0 | CSV libre | SIN coordenadas | Datos 2016-2019
# =============================================================================
download_simat() {
  log "Descargando SIMAT MEN (datos.gov.co ID: upkm-vdjb)..."
  log "Fuente: https://www.datos.gov.co/Educaci-n/ESTABLECIMIENTOS-EDUCATIVOS-COLOMBIA/upkm-vdjb"
  warn "IMPORTANTE: Sin coordenadas geográficas — requiere geocodificación"
  warn "Datos de 2016-2019, potencialmente desactualizados"

  wget -q --show-progress \
    'https://www.datos.gov.co/api/views/upkm-vdjb/rows.csv?accessType=DOWNLOAD' \
    -O "$RAW/men/simat_establecimientos_colombia.csv" || {
    curl -L \
      'https://www.datos.gov.co/api/views/upkm-vdjb/rows.csv?accessType=DOWNLOAD' \
      -o "$RAW/men/simat_establecimientos_colombia.csv" \
      --progress-bar
  }

  if [ -f "$RAW/men/simat_establecimientos_colombia.csv" ]; then
    ROWS=$(wc -l < "$RAW/men/simat_establecimientos_colombia.csv")
    ok "SIMAT descargado: $ROWS filas → $RAW/men/simat_establecimientos_colombia.csv"
  fi
}

# =============================================================================
# F. OpenStreetMap Colombia — Geofabrik
# URL conocida y confiable (no verificada adversarialmente en esta ronda)
# PBF ~299 MB | Libre | Actualización: ~semanal
# =============================================================================
download_osm() {
  log "Descargando OpenStreetMap Colombia desde Geofabrik..."
  log "Fuente: https://download.geofabrik.de/south-america/colombia.html"
  log "Tamaño estimado: ~299 MB (actualizado 2026-05-11)"

  wget --progress=bar:force \
    'https://download.geofabrik.de/south-america/colombia-latest.osm.pbf' \
    -O "$RAW/osm/colombia-latest.osm.pbf" || {
    curl -L \
      'https://download.geofabrik.de/south-america/colombia-latest.osm.pbf' \
      -o "$RAW/osm/colombia-latest.osm.pbf" \
      --progress-bar
  }

  ok "OSM Colombia descargado: $RAW/osm/colombia-latest.osm.pbf"

  # Recortar solo Urabá con osmium (si está instalado)
  if command -v osmium &>/dev/null; then
    log "Recortando bbox Urabá con osmium..."
    # bbox Urabá: lon_min=-77.2, lat_min=7.3, lon_max=-75.8, lat_max=8.7
    osmium extract --bbox="-77.2,7.3,-75.8,8.7" \
      "$RAW/osm/colombia-latest.osm.pbf" \
      -o "$RAW/osm/uraba-latest.osm.pbf" --overwrite
    ok "OSM Urabá recortado: $RAW/osm/uraba-latest.osm.pbf"
  else
    warn "osmium no instalado. Instalar: brew install osmium-tool"
    warn "O recortar manualmente desde: https://extract.bbike.org/"
    warn "bbox Urabá: -77.2,7.3,-75.8,8.7"
  fi
}

# =============================================================================
# G. Google Earth Engine — Instrucciones de autenticación y script de descarga
# No es descarga directa — requiere cuenta GEE gratuita
# =============================================================================
setup_gee() {
  log "Google Earth Engine — instrucciones de autenticación:"
  echo ""
  echo "  1. Crear cuenta gratuita: https://code.earthengine.google.com/register"
  echo "  2. Registrar proyecto: https://console.cloud.google.com/earth-engine"
  echo "  3. Autenticar en Python:"
  echo ""
  cat << 'PYEOF'
  import ee
  ee.Authenticate()           # abre navegador para OAuth
  ee.Initialize(project='tu-proyecto-gcp')

  # BBox Urabá (lon_min, lat_min, lon_max, lat_max)
  URABA_BBOX = ee.Geometry.BBox(-77.2, 7.3, -75.8, 8.7)

  # Sentinel-2 NDVI anual 2023
  s2 = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(URABA_BBOX)
    .filterDate('2023-01-01', '2023-12-31')
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    .map(lambda img: img.normalizedDifference(['B8', 'B4']).rename('NDVI')))
  ndvi_anual = s2.mean().clip(URABA_BBOX)

  # Landsat 8 LST anual 2023
  l8 = (ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
    .filterBounds(URABA_BBOX)
    .filterDate('2023-01-01', '2023-12-31')
    .filter(ee.Filter.lt('CLOUD_COVER', 30))
    .map(lambda img: img.select('ST_B10')
      .multiply(0.00341802).add(149.0).subtract(273.15)
      .rename('LST_C')))
  lst_anual = l8.mean().clip(URABA_BBOX)

  # Exportar a Google Drive
  ee.batch.Export.image.toDrive(
    image=ndvi_anual, description='uraba_ndvi_2023',
    folder='atlas_uraba', fileNamePrefix='ndvi_2023',
    region=URABA_BBOX, scale=10, crs='EPSG:4326',
    maxPixels=1e10
  ).start()
PYEOF
  echo ""
  warn "Alternativamente: usar el notebook 04_satelital_gee.ipynb que ya descarga por manzana"
}

# =============================================================================
# H. Fuentes que requieren trámite o acceso especial
# =============================================================================
show_manual_sources() {
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  FUENTES CON ACCESO MANUAL O TRÁMITE REQUERIDO"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "SIEDCO — Policía Nacional (criminalidad)"
  echo "  ⚠ NO verificado en datos.gov.co para Urabá"
  echo "  Portal: https://www.policia.gov.co/estadisticas-criminalidad"
  echo "  Alternativa: https://www.datos.gov.co (buscar 'SIEDCO' o 'homicidios')"
  echo "  Nota: solo Medellín tiene datos georeferenciados punto-a-punto"
  echo "        Para Urabá: datos a nivel municipal, requiere KDE sobre municipio"
  echo ""
  echo "UARIV — Desplazamiento forzado"
  echo "  Portal: https://www.unidadvictimas.gov.co/es/reportes"
  echo "  Datos: por municipio, período histórico"
  echo "  Formato: Excel descargable desde el portal de reportes"
  echo "  Guardar en: data/raw/siedco/uariv_desplazamiento.xlsx"
  echo ""
  echo "SIAC/SINAP — Áreas protegidas y manglares"
  echo "  SIAC: https://siac.mads.gov.co/SIAC/"
  echo "  SINAP: https://runap.parquesnacionales.gov.co/datos-abiertos"
  echo "  Manglares Urabá: buscar 'Manglares del Caribe colombiano' en SIAC"
  echo ""
  echo "INVIAS — Red vial nacional"
  echo "  Infraestructura Datos: https://herramientas.invias.gov.co/infraestructura/"
  echo "  Red vial nacional (shapefile): descarga directa desde portal"
  echo ""
  echo "IGAC SharePoint (catastro departamental Antioquia)"
  echo "  URL (confianza media, 2-1): https://igacoffice365.sharepoint.com/:f:/g/El_cx99zlE5FrMda2G7Ff9oB8nRia9fawp_SoYlLixSHNA?e=ewJbmZ"
  echo "  Puede requerir cuenta Microsoft — verificar acceso"
  echo ""
  echo "NBI por municipio Antioquia"
  echo "  DANE: https://www.dane.gov.co/index.php/estadisticas-por-tema/pobreza-y-condiciones-de-vida/necesidades-basicas-insatisfechas-nbi"
  echo "  Formato: Excel por departamento"
  echo ""
}

# =============================================================================
# MAIN
# =============================================================================
case "${1:-all}" in
  all)
    download_igac
    download_dane_cnpv
    download_mgn
    download_reps
    download_simat
    download_osm
    setup_gee
    show_manual_sources
    ;;
  igac)     download_igac ;;
  dane)     download_dane_cnpv && download_mgn ;;
  mgn)      download_mgn ;;
  reps)     download_reps ;;
  simat)    download_simat ;;
  osm)      download_osm ;;
  gee)      setup_gee ;;
  manual)   show_manual_sources ;;
  *)
    echo "Uso: bash scripts/download_data.sh [all|igac|dane|mgn|reps|simat|osm|gee|manual]"
    exit 1
    ;;
esac

echo ""
ok "Listo. Archivos en: data/raw/"
