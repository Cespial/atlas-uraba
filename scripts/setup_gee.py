"""
Configuración y descarga de datos de Google Earth Engine para Atlas Urabá.

Uso:
    python scripts/setup_gee.py auth       # autenticar (abre navegador)
    python scripts/setup_gee.py check      # verificar autenticación
    python scripts/setup_gee.py ndvi       # descargar NDVI Sentinel-2 por manzana
    python scripts/setup_gee.py lst        # descargar LST Landsat por manzana
    python scripts/setup_gee.py all        # ndvi + lst

El script lee las manzanas de data/processed/manzanas/mgn2024_cnpv_uraba.gpkg
y descarga las estadísticas zonales (mean, std) por manzana, exportando CSV.
"""
import sys
import time
from pathlib import Path

RAW_GEE = Path("data/raw/gee")
RAW_GEE.mkdir(parents=True, exist_ok=True)


def authenticate():
    """Autenticar con GEE. Requiere cuenta Google con GEE habilitado."""
    try:
        import ee
        ee.Authenticate()
        # Reemplazar 'tu-proyecto-gcp' con el project ID de Google Cloud
        project = input("Ingresa tu Google Cloud Project ID (ej: my-atlas-uraba): ").strip()
        ee.Initialize(project=project)
        # Guardar project para uso futuro
        (RAW_GEE / ".gee_project").write_text(project)
        print(f"[gee] Autenticado. Proyecto: {project}")
    except ImportError:
        print("[error] earthengine-api no instalado: pip install earthengine-api")
        sys.exit(1)


def get_ee():
    """Inicializar GEE con proyecto guardado."""
    import ee
    project_file = RAW_GEE / ".gee_project"
    if project_file.exists():
        project = project_file.read_text().strip()
    else:
        project = input("Google Cloud Project ID: ").strip()
    ee.Initialize(project=project)
    return ee


def check_auth():
    try:
        ee = get_ee()
        info = ee.Number(1).getInfo()
        print(f"[gee] ✓ Autenticación correcta. Test: {info}")
    except Exception as e:
        print(f"[gee] ✗ Error: {e}")
        print("[gee] Ejecutar: python scripts/setup_gee.py auth")


def download_ndvi(year: int = 2023, batch_size: int = 100):
    """
    Descarga NDVI medio anual (Sentinel-2, 10m) por manzana para toda Urabá.
    Guarda CSV: cod_manzana, ndvi_mean, ndvi_std, n_imagenes.
    """
    import ee
    import geopandas as gpd
    import pandas as pd
    import json

    ee = get_ee()
    mzn = gpd.read_file("data/processed/manzanas/mgn2024_cnpv_uraba.gpkg").to_crs("EPSG:4326")
    out_path = RAW_GEE / f"ndvi_manzanas_{year}.csv"

    if out_path.exists():
        print(f"[gee] NDVI ya descargado: {out_path}")
        return

    print(f"[gee] Descargando NDVI {year} para {len(mzn):,} manzanas...")

    # Colección Sentinel-2 anual
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .select(["B8", "B4"])
        .map(lambda img: img.normalizedDifference(["B8", "B4"]).rename("NDVI"))
    )
    ndvi_mean = s2.mean()

    results = []
    for i in range(0, len(mzn), batch_size):
        batch = mzn.iloc[i:i+batch_size]
        print(f"  Procesando manzanas {i}-{i+len(batch)}...", end="\r")
        for _, row in batch.iterrows():
            try:
                geom = ee.Geometry(json.loads(row.geometry.to_json()))
                stats = ndvi_mean.reduceRegion(
                    reducer=ee.Reducer.mean().combine(
                        reducer2=ee.Reducer.stdDev(), sharedInputs=True
                    ),
                    geometry=geom,
                    scale=10,
                    maxPixels=1e8,
                ).getInfo()
                results.append({
                    "cod_manzana": row["cod_manzana"],
                    "ndvi_mean": stats.get("NDVI_mean"),
                    "ndvi_std": stats.get("NDVI_stdDev"),
                })
            except Exception as e:
                results.append({"cod_manzana": row["cod_manzana"], "ndvi_mean": None, "ndvi_std": None})
            time.sleep(0.05)  # evitar rate limit

    df = pd.DataFrame(results)
    df.to_csv(out_path, index=False)
    valid = df["ndvi_mean"].notna().sum()
    print(f"\n[gee] NDVI descargado: {valid}/{len(mzn)} manzanas → {out_path}")


def download_lst(year: int = 2023, batch_size: int = 100):
    """
    Descarga amplitud térmica anual (Landsat 8 LST) por manzana.
    Guarda CSV: cod_manzana, lst_calido_c, lst_frio_c, amplitud_c.

    Colombia: periodo cálido = dic-mar, frío = may-oct.
    """
    import ee
    import geopandas as gpd
    import pandas as pd
    import json

    ee = get_ee()
    mzn = gpd.read_file("data/processed/manzanas/mgn2024_cnpv_uraba.gpkg").to_crs("EPSG:4326")
    out_path = RAW_GEE / f"lst_manzanas_{year}.csv"

    if out_path.exists():
        print(f"[gee] LST ya descargado: {out_path}")
        return

    def to_celsius(img):
        return img.select("ST_B10").multiply(0.00341802).add(149.0).subtract(273.15).rename("LST_C")

    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filter(ee.Filter.lt("CLOUD_COVER", 30)).map(to_celsius)

    lst_calido = l8.filterDate(f"{year}-12-01", f"{year+1}-03-31").mean()
    lst_frio   = l8.filterDate(f"{year}-05-01", f"{year}-10-31").mean()

    results = []
    for i in range(0, len(mzn), batch_size):
        batch = mzn.iloc[i:i+batch_size]
        print(f"  Procesando manzanas {i}-{i+len(batch)}...", end="\r")
        for _, row in batch.iterrows():
            try:
                geom = ee.Geometry(json.loads(row.geometry.to_json()))
                calido = lst_calido.reduceRegion(ee.Reducer.mean(), geom, 30, maxPixels=1e8).getInfo().get("LST_C")
                frio   = lst_frio.reduceRegion(ee.Reducer.mean(), geom, 30, maxPixels=1e8).getInfo().get("LST_C")
                amplitud = (calido - frio) if (calido and frio) else None
                results.append({
                    "cod_manzana": row["cod_manzana"],
                    "lst_calido_c": calido,
                    "lst_frio_c": frio,
                    "amplitud_c": amplitud,
                })
            except Exception as e:
                results.append({"cod_manzana": row["cod_manzana"], "lst_calido_c": None, "lst_frio_c": None, "amplitud_c": None})
            time.sleep(0.05)

    df = pd.DataFrame(results)
    df.to_csv(out_path, index=False)
    valid = df["amplitud_c"].notna().sum()
    print(f"\n[gee] LST descargado: {valid}/{len(mzn)} manzanas → {out_path}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "auth":
        authenticate()
    elif cmd == "check":
        check_auth()
    elif cmd == "ndvi":
        download_ndvi()
    elif cmd == "lst":
        download_lst()
    elif cmd == "all":
        download_ndvi()
        download_lst()
    else:
        print(__doc__)
