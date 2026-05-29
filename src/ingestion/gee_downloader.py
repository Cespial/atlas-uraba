"""
Descarga de NDVI y LST desde Google Earth Engine para los municipios de Urabá.

Fuentes:
  - NDVI: Sentinel-2 SR Harmonized (COPERNICUS/S2_SR_HARMONIZED), bandas B8/B4
  - LST:  Landsat 8 Collection 2 Tier 1 Level 2 (LANDSAT/LC08/C02/T1_L2), banda ST_B10

Periodos climáticos Colombia:
  - Cálido (dic–mar): meses 12, 1, 2, 3
  - Frío  (may–oct): meses 5, 6, 7, 8, 9, 10

Requires:
    pip install earthengine-api
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd

DIVIPOLA_URABA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]

# Meses por periodo climático en Colombia
MESES_CALIDO = [12, 1, 2, 3]
MESES_FRIO   = [5, 6, 7, 8, 9, 10]

# Factor de escala LST Landsat C2 L2: DN * 0.00341802 + 149.0 → K
LST_SCALE  = 0.00341802
LST_OFFSET = 149.0
KELVIN_TO_CELSIUS = 273.15


def authenticate_gee() -> None:
    """
    Autentica e inicializa Google Earth Engine.

    Intenta primero autenticación con Application Default Credentials (service account
    o credencial guardada). Si falla, lanza ee.Authenticate() interactivo.

    Raises:
        ImportError: si el paquete `earthengine-api` no está instalado.
        Exception: si la autenticación o inicialización fallan.
    """
    try:
        import ee
    except ImportError as exc:
        raise ImportError(
            "[gee] Paquete 'earthengine-api' no instalado. "
            "Ejecuta: pip install earthengine-api"
        ) from exc

    try:
        ee.Initialize()
        print("[gee] Earth Engine inicializado con credenciales existentes.")
    except Exception:
        print("[gee] Credenciales no encontradas. Iniciando autenticación interactiva...")
        try:
            ee.Authenticate()
            ee.Initialize()
            print("[gee] Autenticación completada e Earth Engine inicializado.")
        except Exception as exc:
            raise RuntimeError(
                f"[gee] Fallo en autenticación/inicialización de Earth Engine: {exc}\n"
                "Asegúrate de tener acceso al proyecto GEE y conexión a internet."
            ) from exc


def _gdf_to_ee_fc(manzanas: gpd.GeoDataFrame):
    """Convierte un GeoDataFrame a un FeatureCollection de Earth Engine."""
    import ee
    gdf_4326 = manzanas.to_crs("EPSG:4326") if manzanas.crs.to_epsg() != 4326 else manzanas
    geojson = json.loads(gdf_4326[["cod_manzana", "geometry"]].to_json())
    return ee.FeatureCollection(geojson["features"])


def download_ndvi(
    manzanas: gpd.GeoDataFrame,
    year: int = 2023,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Descarga el NDVI medio anual por manzana usando Sentinel-2 SR.

    NDVI = (B8 - B4) / (B8 + B4), donde:
      - B8 = NIR (842 nm)
      - B4 = Red (665 nm)

    Aplica máscara de nubes usando la banda SCL (Scene Classification Layer).
    Calcula la mediana anual y hace zonal statistics por manzana.

    Args:
        manzanas: GeoDataFrame con columnas 'cod_manzana' y 'geometry'.
        year:     Año para el que se descarga (default 2023).
        output_path: Ruta donde guardar el CSV resultante.
                     Default: data/raw/gee/ndvi_{year}.csv

    Returns:
        Path al CSV generado con columnas: cod_manzana, ndvi_mean, ndvi_std

    Raises:
        AssertionError: si 'cod_manzana' no está en el GeoDataFrame.
        RuntimeError:   si falla la descarga o el procesamiento GEE.
    """
    assert "cod_manzana" in manzanas.columns, (
        "[gee] El GeoDataFrame debe tener columna 'cod_manzana'."
    )

    if output_path is None:
        output_path = Path("data/raw/gee") / f"ndvi_{year}.csv"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import ee
    except ImportError as exc:
        raise ImportError("[gee] Instala earthengine-api: pip install earthengine-api") from exc

    print(f"[gee] Descargando NDVI Sentinel-2 para {year}...")

    start_date = f"{year}-01-01"
    end_date   = f"{year}-12-31"

    # Máscara de nubes con SCL (valores 4=vegetación, 5=suelo, 6=agua, 11=nieve válidos)
    def mask_clouds_s2(image):
        scl = image.select("SCL")
        mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(11))
        return image.updateMask(mask)

    def add_ndvi(image):
        ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
        return image.addBands(ndvi)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
        .map(mask_clouds_s2)
        .map(add_ndvi)
        .select("NDVI")
    )

    ndvi_median = collection.median()
    ndvi_std_img = collection.reduce(ee.Reducer.stdDev()).rename("NDVI_stdDev")
    ndvi_composite = ndvi_median.addBands(ndvi_std_img)

    fc = _gdf_to_ee_fc(manzanas)

    # Filtrar colección a la región de interés
    region = fc.geometry().bounds()
    ndvi_composite = ndvi_composite.clip(region)

    print("[gee]   Calculando zonal statistics por manzana (puede tardar varios minutos)...")

    def zonal_stats_feature(feature):
        stats = ndvi_composite.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True),
            geometry=feature.geometry(),
            scale=10,
            maxPixels=1e9,
        )
        return feature.set(stats)

    fc_with_stats = fc.map(zonal_stats_feature)

    # Exportar a local via getInfo (para datasets medianos; para grandes usar Export.table)
    features = fc_with_stats.getInfo()["features"]

    records = []
    for feat in features:
        props = feat["properties"]
        records.append({
            "cod_manzana": str(props.get("cod_manzana", "")),
            "ndvi_mean":   props.get("NDVI_mean", None),
            "ndvi_std":    props.get("NDVI_stdDev", None),
        })

    df = pd.DataFrame(records)
    df["cod_manzana"] = df["cod_manzana"].astype(str)
    df = df.dropna(subset=["ndvi_mean"])

    df.to_csv(output_path, index=False)
    print(f"[gee] NDVI guardado en {output_path} ({len(df)} manzanas).")
    return output_path


def download_lst(
    manzanas: gpd.GeoDataFrame,
    year: int = 2023,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Descarga Land Surface Temperature (LST) desde Landsat 8 C2 L2 por manzana.

    La banda ST_B10 se convierte de DN a Kelvin con la fórmula oficial USGS:
        LST_K = DN * 0.00341802 + 149.0
    Luego a Celsius: LST_C = LST_K - 273.15

    Se calculan estadísticas para dos periodos climáticos colombianos:
      - Cálido: dic–mar (meses 12, 1, 2, 3)
      - Frío:   may–oct (meses 5, 6, 7, 8, 9, 10)

    Args:
        manzanas:    GeoDataFrame con columnas 'cod_manzana' y 'geometry'.
        year:        Año base (el periodo cálido incluye dic del año anterior).
        output_path: Ruta donde guardar el CSV.
                     Default: data/raw/gee/lst_{year}.csv

    Returns:
        Path al CSV con columnas:
            cod_manzana, lst_calido_mean, lst_frio_mean, amplitud_termica

    Raises:
        AssertionError: si 'cod_manzana' no está en el GeoDataFrame.
        RuntimeError:   si falla la descarga o el procesamiento GEE.
    """
    assert "cod_manzana" in manzanas.columns, (
        "[gee] El GeoDataFrame debe tener columna 'cod_manzana'."
    )

    if output_path is None:
        output_path = Path("data/raw/gee") / f"lst_{year}.csv"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import ee
    except ImportError as exc:
        raise ImportError("[gee] Instala earthengine-api: pip install earthengine-api") from exc

    print(f"[gee] Descargando LST Landsat 8 para {year}...")

    def mask_clouds_l8(image):
        qa = image.select("QA_PIXEL")
        # Bit 3 = Cloud, Bit 4 = Cloud Shadow
        cloud_mask = qa.bitwiseAnd(1 << 3).eq(0).And(
            qa.bitwiseAnd(1 << 4).eq(0)
        )
        return image.updateMask(cloud_mask)

    def apply_lst_scale(image):
        lst = (
            image.select("ST_B10")
            .multiply(LST_SCALE)
            .add(LST_OFFSET)
            .subtract(KELVIN_TO_CELSIUS)
            .rename("LST_C")
        )
        return image.addBands(lst)

    # Periodo cálido: dic año-1 + ene–mar año
    calido_start = f"{year - 1}-12-01"
    calido_end   = f"{year}-03-31"
    # Periodo frío: may–oct año
    frio_start   = f"{year}-05-01"
    frio_end     = f"{year}-10-31"

    collection_base = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filter(ee.Filter.lt("CLOUD_COVER", 30))
        .map(mask_clouds_l8)
        .map(apply_lst_scale)
        .select("LST_C")
    )

    lst_calido = collection_base.filterDate(calido_start, calido_end).mean().rename("LST_calido")
    lst_frio   = collection_base.filterDate(frio_start,   frio_end).mean().rename("LST_frio")
    lst_composite = lst_calido.addBands(lst_frio)

    fc = _gdf_to_ee_fc(manzanas)
    region = fc.geometry().bounds()
    lst_composite = lst_composite.clip(region)

    print("[gee]   Calculando zonal statistics LST por manzana...")

    def zonal_stats_feature(feature):
        stats = lst_composite.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=feature.geometry(),
            scale=30,
            maxPixels=1e9,
        )
        return feature.set(stats)

    fc_with_stats = fc.map(zonal_stats_feature)
    features = fc_with_stats.getInfo()["features"]

    records = []
    for feat in features:
        props = feat["properties"]
        lst_cal  = props.get("LST_calido", None)
        lst_fr   = props.get("LST_frio", None)
        amplitud = (lst_cal - lst_fr) if (lst_cal is not None and lst_fr is not None) else None
        records.append({
            "cod_manzana":       str(props.get("cod_manzana", "")),
            "lst_calido_mean":   lst_cal,
            "lst_frio_mean":     lst_fr,
            "amplitud_termica":  amplitud,
        })

    df = pd.DataFrame(records)
    df["cod_manzana"] = df["cod_manzana"].astype(str)
    df = df.dropna(subset=["lst_calido_mean", "lst_frio_mean"])

    df.to_csv(output_path, index=False)
    print(f"[gee] LST guardado en {output_path} ({len(df)} manzanas).")
    return output_path
