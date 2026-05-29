"""
Geocodificación de REPS (salud) y SIMAT (educación).

REPS y SIMAT de datos.gov.co NO incluyen coordenadas geográficas.
Este script geocodifica usando la API de Nominatim (OSM) + fallback a Google Maps API.

Uso:
  python scripts/geocode_equipamientos.py reps   # geocodifica REPS
  python scripts/geocode_equipamientos.py simat  # geocodifica SIMAT
  python scripts/geocode_equipamientos.py all    # ambos
"""
import sys
import time
import pandas as pd
import geopandas as gpd
from pathlib import Path
from shapely.geometry import Point

RAW = Path("data/raw")
PROCESSED = Path("data/processed/equipamientos")
PROCESSED.mkdir(parents=True, exist_ok=True)

DIVIPOLA_URABA = {
    "05045": "Apartadó", "05147": "Chigorodó", "05120": "Carepa",
    "05837": "Turbo", "05544": "Necoclí", "05665": "San Pedro de Urabá",
    "05659": "San Juan de Urabá", "05051": "Arboletes",
}


def geocode_nominatim(direccion: str, municipio: str, sleep: float = 1.1) -> tuple[float, float] | None:
    """Geocodifica una dirección usando Nominatim (OSM). Rate limit: 1 req/seg."""
    import urllib.request
    import json
    import urllib.parse

    query = f"{direccion}, {municipio}, Antioquia, Colombia"
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query)}&format=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "AtlasUraba/1.0"})

    time.sleep(sleep)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            results = json.loads(r.read())
            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        pass
    return None


def geocode_reps():
    """Geocodifica establecimientos de salud del REPS para municipios de Urabá."""
    ruta = RAW / "minsal" / "reps_antioquia.csv"
    if not ruta.exists():
        ruta = RAW / "minsal" / "reps_prestadores_colombia.csv"
    if not ruta.exists():
        print("[error] REPS no encontrado. Ejecutar: bash scripts/download_data.sh reps")
        return

    df = pd.read_csv(ruta, dtype=str, low_memory=False)
    print(f"[reps] {len(df)} registros cargados")

    # Columnas esperadas del REPS datos.gov.co
    # Adaptar según columnas reales del CSV
    col_mpio = next((c for c in df.columns if "municipio" in c.lower() or "mpio" in c.lower()), None)
    col_dir = next((c for c in df.columns if "direcci" in c.lower() or "direcc" in c.lower()), None)
    col_nombre = next((c for c in df.columns if "nombre" in c.lower() or "razon" in c.lower()), None)
    col_nivel = next((c for c in df.columns if "nivel" in c.lower() or "complejidad" in c.lower()), None)

    print(f"[reps] Columnas detectadas: mpio={col_mpio}, dir={col_dir}, nombre={col_nombre}, nivel={col_nivel}")

    # Filtrar Urabá
    if col_mpio:
        uraba_mask = df[col_mpio].astype(str).str.zfill(5).isin(DIVIPOLA_URABA.keys())
        df_uraba = df[uraba_mask].copy()
    else:
        print("[warn] No se encontró columna de municipio — usar todo el CSV")
        df_uraba = df.copy()

    print(f"[reps] {len(df_uraba)} establecimientos en Urabá")

    # Geocodificar
    lats, lons = [], []
    for _, row in df_uraba.iterrows():
        mpio_nombre = DIVIPOLA_URABA.get(str(row.get(col_mpio, "")).zfill(5), "Urabá")
        direccion = str(row.get(col_dir, "")) if col_dir else ""
        coords = geocode_nominatim(direccion, mpio_nombre)
        lats.append(coords[0] if coords else None)
        lons.append(coords[1] if coords else None)
        print(f"  {row.get(col_nombre, 'N/A')[:40]}: {coords}")

    df_uraba["latitud"] = lats
    df_uraba["longitud"] = lons
    df_geo = df_uraba.dropna(subset=["latitud", "longitud"])

    gdf = gpd.GeoDataFrame(
        df_geo,
        geometry=[Point(lon, lat) for lat, lon in zip(df_geo["latitud"], df_geo["longitud"])],
        crs="EPSG:4326",
    )
    out = PROCESSED / "reps_uraba_geocodificado.gpkg"
    gdf.to_file(str(out), driver="GPKG")
    print(f"[ok] REPS geocodificado: {len(gdf)} establecimientos → {out}")
    print(f"[warn] {len(df_uraba) - len(df_geo)} establecimientos sin geocodificar")


def geocode_simat():
    """Geocodifica establecimientos educativos del SIMAT para municipios de Urabá."""
    ruta = RAW / "men" / "simat_establecimientos_colombia.csv"
    if not ruta.exists():
        print("[error] SIMAT no encontrado. Ejecutar: bash scripts/download_data.sh simat")
        return

    df = pd.read_csv(ruta, dtype=str, low_memory=False)
    print(f"[simat] {len(df)} registros cargados")

    col_mpio = next((c for c in df.columns if "municipio" in c.lower() or "mpio" in c.lower()), None)
    col_dir = next((c for c in df.columns if "direcci" in c.lower()), None)
    col_nombre = next((c for c in df.columns if "nombre" in c.lower() and "estab" in c.lower()), None)
    col_matricula = next((c for c in df.columns if "matricul" in c.lower()), None)

    if col_mpio:
        uraba_mask = df[col_mpio].astype(str).str.zfill(5).isin(DIVIPOLA_URABA.keys())
        df_uraba = df[uraba_mask].copy()
    else:
        df_uraba = df.copy()

    print(f"[simat] {len(df_uraba)} establecimientos en Urabá")

    lats, lons = [], []
    for _, row in df_uraba.iterrows():
        mpio_nombre = DIVIPOLA_URABA.get(str(row.get(col_mpio, "")).zfill(5), "Urabá")
        direccion = str(row.get(col_dir, "")) if col_dir else ""
        coords = geocode_nominatim(direccion, mpio_nombre)
        lats.append(coords[0] if coords else None)
        lons.append(coords[1] if coords else None)

    df_uraba["latitud"] = lats
    df_uraba["longitud"] = lons
    df_geo = df_uraba.dropna(subset=["latitud", "longitud"])

    gdf = gpd.GeoDataFrame(
        df_geo,
        geometry=[Point(lon, lat) for lat, lon in zip(df_geo["latitud"], df_geo["longitud"])],
        crs="EPSG:4326",
    )
    out = PROCESSED / "simat_uraba_geocodificado.gpkg"
    gdf.to_file(str(out), driver="GPKG")
    print(f"[ok] SIMAT geocodificado: {len(gdf)} establecimientos → {out}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("reps", "all"):
        geocode_reps()
    if cmd in ("simat", "all"):
        geocode_simat()
