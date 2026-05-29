import pandas as pd
import geopandas as gpd
import time, urllib.request, urllib.parse, json
from shapely.geometry import Point
from pathlib import Path

def geocode(direccion, municipio, sleep=1.1):
    """Geocodifica con Nominatim. Fallback a centroide municipal."""
    time.sleep(sleep)
    queries = [
        f"{direccion}, {municipio}, Antioquia, Colombia",
        f"{municipio}, Antioquia, Colombia"
    ]
    for query in queries:
        url = (
            "https://nominatim.openstreetmap.org/search"
            f"?q={urllib.parse.quote(query)}&format=json&limit=1&countrycodes=co"
        )
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "AtlasUraba/1.0 geocoding"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                res = json.loads(r.read())
                if res:
                    return float(res[0]["lat"]), float(res[0]["lon"]), query
        except Exception:
            pass
    return None, None, "fallido"

MUNICIPIOS_MAP = {
    "05045": "Apartadó",
    "05147": "Chigorodó",
    "05120": "Carepa",
    "05837": "Turbo",
    "05544": "Necoclí",
    "05665": "San Pedro de Urabá",
    "05659": "San Juan de Urabá",
    "05051": "Arboletes",
}

# ── REPS ──────────────────────────────────────────────────────────────────────
print("=== Geocodificando REPS (339 prestadores) ===", flush=True)
reps = pd.read_csv(
    "/Users/cristianespinal/atlas-uraba/data/processed/equipamientos/reps_uraba.csv",
    dtype=str,
)

col_dir = next((c for c in reps.columns if "direcci" in c.lower()), None)
col_mun = next(
    (c for c in reps.columns if "municipio" in c.lower() and "prestador" in c.lower()),
    None,
)
col_nom = next(
    (c for c in reps.columns if "nombre" in c.lower() and "sede" in c.lower()), None
)
print(f"Columnas: dir={col_dir}, mun={col_mun}, nombre={col_nom}", flush=True)

lats, lons, metodo = [], [], []
total = len(reps)
for i, (_, row) in enumerate(reps.iterrows()):
    if i % 50 == 0:
        print(f"  REPS: {i}/{total} ({round(i/total*100)}%)", flush=True)
    mpio_cod = str(row.get(col_mun, "")).zfill(5)
    mpio_nom = MUNICIPIOS_MAP.get(mpio_cod, "Urabá")
    dire = str(row.get(col_dir, "")) if col_dir else ""
    lat, lon, met = geocode(dire, mpio_nom)
    lats.append(lat)
    lons.append(lon)
    metodo.append(met)

reps["lat"] = lats
reps["lon"] = lons
reps["geocode_query"] = metodo
reps_geo = reps.dropna(subset=["lat", "lon"])
gdf_reps = gpd.GeoDataFrame(
    reps_geo,
    geometry=[
        Point(lon, lat) for lat, lon in zip(reps_geo["lat"], reps_geo["lon"])
    ],
    crs="EPSG:4326",
)
out_reps = "/Users/cristianespinal/atlas-uraba/data/processed/equipamientos/reps_uraba_geo.gpkg"
gdf_reps.to_file(out_reps, driver="GPKG")
pct_reps = round(len(gdf_reps) / total * 100)
print(f"REPS geocodificados: {len(gdf_reps)}/{total} ({pct_reps}%)", flush=True)

# Municipio con más establecimientos REPS
top_reps = reps_geo[col_mun].value_counts().idxmax()
top_reps_n = reps_geo[col_mun].value_counts().max()
top_reps_nom = MUNICIPIOS_MAP.get(str(top_reps).zfill(5), top_reps)
print(f"REPS top municipio: {top_reps_nom} ({top_reps_n} registros)", flush=True)

# ── SIMAT ─────────────────────────────────────────────────────────────────────
print("=== Geocodificando SIMAT (180 establecimientos) ===", flush=True)
simat = pd.read_csv(
    "/Users/cristianespinal/atlas-uraba/data/processed/equipamientos/simat_uraba.csv",
    dtype=str,
)
col_dir_s = next((c for c in simat.columns if "direcci" in c.lower()), None)
col_mun_s = next(
    (c for c in simat.columns if "codigomunicipio" in c.lower()), "codigomunicipio"
)
col_nom_s = next(
    (c for c in simat.columns if "nombreestablecimiento" in c.lower()), None
)
print(f"Columnas SIMAT: dir={col_dir_s}, mun={col_mun_s}, nombre={col_nom_s}", flush=True)

lats2, lons2, met2 = [], [], []
total2 = len(simat)
for i, (_, row) in enumerate(simat.iterrows()):
    if i % 50 == 0:
        print(f"  SIMAT: {i}/{total2} ({round(i/total2*100)}%)", flush=True)
    mpio_cod = str(row.get(col_mun_s, "")).zfill(5)
    mpio_nom = MUNICIPIOS_MAP.get(mpio_cod, "Urabá")
    dire = str(row.get(col_dir_s, "")) if col_dir_s else ""
    lat, lon, met = geocode(dire, mpio_nom)
    lats2.append(lat)
    lons2.append(lon)
    met2.append(met)

simat["lat"] = lats2
simat["lon"] = lons2
simat["geocode_query"] = met2
simat_geo = simat.dropna(subset=["lat", "lon"])
gdf_simat = gpd.GeoDataFrame(
    simat_geo,
    geometry=[
        Point(lon, lat) for lat, lon in zip(simat_geo["lat"], simat_geo["lon"])
    ],
    crs="EPSG:4326",
)
out_simat = "/Users/cristianespinal/atlas-uraba/data/processed/equipamientos/simat_uraba_geo.gpkg"
gdf_simat.to_file(out_simat, driver="GPKG")
pct_simat = round(len(gdf_simat) / total2 * 100)
print(f"SIMAT geocodificados: {len(gdf_simat)}/{total2} ({pct_simat}%)", flush=True)

# Municipio con más establecimientos SIMAT
top_simat = simat_geo[col_mun_s].value_counts().idxmax()
top_simat_n = simat_geo[col_mun_s].value_counts().max()
top_simat_nom = MUNICIPIOS_MAP.get(str(top_simat).zfill(5), top_simat)
print(f"SIMAT top municipio: {top_simat_nom} ({top_simat_n} registros)", flush=True)

print("=== GEOCODIFICACIÓN COMPLETA ===", flush=True)
print(f"Archivos generados:", flush=True)
print(f"  {out_reps}", flush=True)
print(f"  {out_simat}", flush=True)
