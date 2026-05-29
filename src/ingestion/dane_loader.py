"""
Carga y preprocesamiento de datos DANE para Urabá.

Fuentes:
  - MGN 2024 (manzanas censales): https://www.arcgis.com/home/item.html?id=da6856c2040c4098831605384715d35b
  - CNPV 2018 Geovisor detallado: https://geoportal.dane.gov.co/geovisores/sociedad/cnpv2018-detallado/
  - Microdatos CNPV 2018: https://microdatos.dane.gov.co/index.php/catalog/643

Códigos DIVIPOLA de municipios de Urabá (Antioquia = 05):
  05045 Apartadó | 05147 Chigorodó | 05120 Carepa | 05837 Turbo
  05544 Necoclí   | 05665 San Pedro de Urabá | 05659 San Juan de Urabá | 05051 Arboletes
"""
import geopandas as gpd
import pandas as pd
from pathlib import Path

DIVIPOLA_URABA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]
RAW_DIR = Path("data/raw/dane")
PROCESSED_DIR = Path("data/processed/manzanas")


def cargar_mgn_manzanas(path: Path) -> gpd.GeoDataFrame:
    """
    Carga el shapefile de manzanas censales del MGN y filtra por municipios de Urabá.

    Args:
        path: Ruta al shapefile del MGN descargado.

    Returns:
        GeoDataFrame de manzanas de Urabá con columna 'cod_manzana' estandarizada.
    """
    gdf = gpd.read_file(path)
    # El MGN usa MPIO_CDPMP (5 dígitos) como código municipal
    col_mpio = next(c for c in gdf.columns if "MPIO" in c.upper() and "CD" in c.upper())
    manzanas = gdf[gdf[col_mpio].isin(DIVIPOLA_URABA)].copy()
    manzanas["cod_manzana"] = manzanas[col_mpio] + manzanas.index.astype(str).str.zfill(8)
    print(f"[dane] {len(manzanas)} manzanas cargadas para Urabá")
    return manzanas.to_crs("EPSG:4326")


def cargar_variables_socioeconomicas(path_csv: Path) -> pd.DataFrame:
    """
    Carga las variables socioeconómicas del CNPV 2018 a nivel de manzana.
    El CSV debe ser exportado desde el Geovisor Detallado del DANE o desde
    los microdatos con agregación por manzana.

    Variables esperadas (nombres pueden variar según exportación DANE):
      - cod_manzana, poblacion, hogares
      - pct_vivienda_inadecuada (materiales insuficientes paredes/piso/techo)
      - pct_hacinamiento
      - pct_hacinamiento_severo
      - esc_promedio_jefe (años de escolaridad promedio jefe de hogar)
      - pct_hogares_monoparentales
      - pct_ocupados (sobre PEA)
      - pct_jovenes_15_24_en_actividad

    Returns:
        DataFrame indexado por cod_manzana.
    """
    df = pd.read_csv(path_csv, dtype={"cod_manzana": str})
    df = df.set_index("cod_manzana")
    print(f"[dane] {len(df)} manzanas cargadas con variables socioeconómicas")
    print(f"       Columnas: {list(df.columns)}")
    return df
