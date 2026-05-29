"""
Carga de datos de la Base Catastral Pública IGAC 2026 para Urabá.

Fuente:
  - IGAC Base Catastral 2026: https://datos.icde.gov.co/datasets/2e26ee016ce14c359a5037231da25a86
  - Descarga: wget -L '<url_arcgis_rest>' -O CatastroPublicoIGAC_2026.zip

ADVERTENCIA — CATASTRO DESCENTRALIZADO:
  Antioquia (y Bogotá, Medellín, Cali) maneja su propio catastro descentralizado
  y NO está incluido en la descarga nacional del IGAC. La capa IGAC 2026 cubre
  únicamente los departamentos bajo jurisdicción directa del IGAC.
  Para Urabá/Antioquia se requiere catastro de la Gobernación de Antioquia o
  del municipio (Lonja de Propiedad Raíz / CATASTRO ANTIOQUIA).

Capas disponibles en la descarga IGAC 2026:
  U_MANZANA      → Manzanas urbanas (polígonos)
  U_TERRENO      → Terrenos urbanos / predios urbanos (polígonos)
  U_CONSTRUCCION → Construcciones urbanas (polígonos)
  R_VEREDA       → Veredas rurales (polígonos)
  R_TERRENO      → Terrenos rurales / predios rurales (polígonos)
  R_SECTOR       → Sectores rurales (polígonos)

Columnas reales confirmadas (Base Catastral 2026):
  codigo_mun  → Código DIVIPOLA del municipio (string 5 dígitos, ej: "05045")
  (U_TERRENO) → columnas específicas de terreno; ver _COLS_U_TERRENO
  (U_MANZANA) → columnas específicas de manzana; ver _COLS_U_MANZANA

Columnas clave esperadas en la capa de edificaciones (U_CONSTRUCCION):
  NUPRE       → Número predial para join con predios
  AREA_CONST  → Área construida en m²
  PISOS       → Número de pisos
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

DIVIPOLA_URABA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]

# Columna de código municipal real en la Base Catastral IGAC 2026
_COL_MUNICIPIO_IGAC = "codigo_mun"  # string 5 dígitos, ej: "05045"

# Columnas mínimas requeridas por capa
_COLS_U_TERRENO    = {_COL_MUNICIPIO_IGAC}          # mínimo; hay más según versión
_COLS_U_MANZANA    = {_COL_MUNICIPIO_IGAC}          # mínimo
COLS_PREDIOS       = {"NUPRE", "AREA_TERR", "USO_SUELO", "MUNICIPIO_CODIGO"}  # esquema legado
COLS_EDIFICACIONES = {"NUPRE", "AREA_CONST", "PISOS"}


def cargar_predios(path: Path, capa: str = "U_TERRENO") -> gpd.GeoDataFrame:
    """
    Lee la capa U_TERRENO (predios urbanos) de la Base Catastral IGAC 2026 y filtra
    por municipios de Urabá.

    NOTA: Antioquia NO está incluida en la descarga nacional del IGAC (catastro
    descentralizado). Esta función es funcional para los departamentos bajo
    jurisdicción IGAC. Para Urabá/Antioquia se requiere el catastro departamental.

    La columna de código municipal real en IGAC 2026 es 'codigo_mun' (string 5 dígitos).
    Se mapea a 'MUNICIPIO_CODIGO' para compatibilidad con el resto del pipeline.

    Args:
        path: Ruta al shapefile (.shp) o GeoPackage (.gpkg) de la Base Catastral IGAC.
        capa: Nombre de la capa a leer si el archivo es multi-capa (default: 'U_TERRENO').

    Returns:
        GeoDataFrame de predios/terrenos de Urabá con columna 'MUNICIPIO_CODIGO' (5d).
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError:        si el GeoDataFrame queda vacío tras filtrar por Urabá.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[igac] Archivo de predios no encontrado: {path}\n"
            "IMPORTANTE: Antioquia tiene catastro descentralizado y NO está en la\n"
            "descarga nacional IGAC. Ver docs/metodologia/fuentes_verificadas.md\n"
            "sección 'IGAC: Antioquia requiere catastro departamental'."
        )

    print(f"[igac] Cargando capa '{capa}' desde {path}...")
    try:
        gdf = gpd.read_file(path, layer=capa)
    except Exception:
        # Si el archivo no es multi-capa (shapefile simple), leer sin especificar capa
        gdf = gpd.read_file(path)

    # La columna real en IGAC 2026 es 'codigo_mun' (minúsculas, string 5d)
    col_mun = _detectar_columna_municipio(gdf)
    if col_mun != "MUNICIPIO_CODIGO":
        gdf = gdf.rename(columns={col_mun: "MUNICIPIO_CODIGO"})

    gdf["MUNICIPIO_CODIGO"] = gdf["MUNICIPIO_CODIGO"].astype(str).str.zfill(5)

    gdf_uraba = gdf[gdf["MUNICIPIO_CODIGO"].isin(DIVIPOLA_URABA)].copy()

    if gdf_uraba.empty:
        raise ValueError(
            "[igac] No se encontraron predios para los municipios de Urabá. "
            f"Verifica que 'codigo_mun' contenga códigos DIVIPOLA: {DIVIPOLA_URABA}\n"
            "RECORDATORIO: Antioquia no está en la descarga nacional IGAC."
        )

    print(f"[igac] {len(gdf_uraba)} registros ({capa}) cargados para Urabá.")

    if gdf_uraba.crs is None:
        print("[igac] ADVERTENCIA: shapefile sin CRS. Asumiendo EPSG:4326.")
        gdf_uraba = gdf_uraba.set_crs("EPSG:4326")
    else:
        gdf_uraba = gdf_uraba.to_crs("EPSG:4326")

    return gdf_uraba


def cargar_manzanas_igac(path: Path) -> gpd.GeoDataFrame:
    """
    Lee la capa U_MANZANA de la Base Catastral IGAC 2026 y filtra por Urabá.

    La capa U_MANZANA contiene polígonos de manzanas urbanas con columna
    'codigo_mun' (string 5 dígitos) como identificador municipal.

    NOTA: Antioquia NO está incluida en la descarga nacional del IGAC.
    Esta función aplica solo a departamentos bajo jurisdicción IGAC directa.

    Args:
        path: Ruta al shapefile (.shp) o GeoPackage (.gpkg) de la Base Catastral IGAC.

    Returns:
        GeoDataFrame de manzanas urbanas de Urabá con columna 'MUNICIPIO_CODIGO'.
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError:        si no hay manzanas para Urabá.
    """
    return cargar_predios(path, capa="U_MANZANA")


def cargar_edificaciones(path: Path) -> gpd.GeoDataFrame:
    """
    Lee la capa de construcciones del IGAC para uso en dasymetría de Tobler.

    Esta capa es necesaria para redistribuir población desde unidades
    administrativas hacia manzanas ponderando por área construida.

    Args:
        path: Ruta al shapefile o GeoPackage de edificaciones IGAC.

    Returns:
        GeoDataFrame con columnas: NUPRE, AREA_CONST, PISOS, geometry
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
        AssertionError:    si faltan columnas requeridas.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[igac] Archivo de edificaciones no encontrado: {path}\n"
            "Descarga la capa de construcciones desde el portal IGAC."
        )

    print(f"[igac] Cargando edificaciones desde {path}...")
    gdf = gpd.read_file(path)
    gdf.columns = [c.upper() for c in gdf.columns]

    cols_faltantes = COLS_EDIFICACIONES - set(gdf.columns)
    assert not cols_faltantes, (
        f"[igac] Faltan columnas en edificaciones: {cols_faltantes}. "
        f"Columnas disponibles: {list(gdf.columns)}"
    )

    gdf["AREA_CONST"] = pd.to_numeric(gdf["AREA_CONST"], errors="coerce").fillna(0.0)
    gdf["PISOS"]      = pd.to_numeric(gdf["PISOS"],      errors="coerce").fillna(1).astype(int)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    print(f"[igac] {len(gdf)} edificaciones cargadas.")
    return gdf


def join_predios_manzanas(
    predios: gpd.GeoDataFrame,
    manzanas: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Agrega predios por manzana mediante spatial join y groupby.

    Hace un sjoin de predios (puntos o polígonos) dentro de cada manzana
    y calcula estadísticas agregadas de construcción.

    Args:
        predios:  GeoDataFrame de predios con columnas NUPRE, AREA_CONST (opcional),
                  AREA_TERR, USO_SUELO. CRS debe coincidir con manzanas.
        manzanas: GeoDataFrame con columna 'cod_manzana' y geometrías de manzanas.

    Returns:
        GeoDataFrame de manzanas con columnas adicionales:
            count_predios         → número de predios dentro de la manzana
            area_construida_total → suma de AREA_CONST (m²); 0 si columna ausente
            area_construida_media → media de AREA_CONST (m²); 0 si columna ausente

    Raises:
        AssertionError: si falta 'cod_manzana' en manzanas o 'NUPRE' en predios.
    """
    assert "cod_manzana" in manzanas.columns, (
        "[igac] El GeoDataFrame de manzanas debe tener columna 'cod_manzana'."
    )
    assert "NUPRE" in predios.columns, (
        "[igac] El GeoDataFrame de predios debe tener columna 'NUPRE'."
    )

    print("[igac] Realizando spatial join predios → manzanas...")

    # Asegurar mismo CRS
    predios_proj  = predios.to_crs(manzanas.crs)

    # Si la geometría de predios es polígono, usar centroide para el join
    if predios_proj.geometry.geom_type.iloc[0] in ("Polygon", "MultiPolygon"):
        predios_puntos = predios_proj.copy()
        predios_puntos["geometry"] = predios_proj.geometry.centroid
    else:
        predios_puntos = predios_proj

    joined = gpd.sjoin(
        predios_puntos[["NUPRE", "geometry"] + (["AREA_CONST"] if "AREA_CONST" in predios_proj.columns else [])],
        manzanas[["cod_manzana", "geometry"]],
        how="left",
        predicate="within",
    )

    tiene_area_const = "AREA_CONST" in joined.columns

    agg_dict: dict = {"NUPRE": "count"}
    if tiene_area_const:
        agg_dict["AREA_CONST"] = ["sum", "mean"]

    grouped = joined.groupby("cod_manzana").agg(agg_dict)

    if tiene_area_const:
        grouped.columns = ["count_predios", "area_construida_total", "area_construida_media"]
    else:
        grouped.columns = ["count_predios"]
        grouped["area_construida_total"] = 0.0
        grouped["area_construida_media"] = 0.0

    grouped = grouped.reset_index()

    result = manzanas.merge(grouped, on="cod_manzana", how="left")
    result["count_predios"]          = result["count_predios"].fillna(0).astype(int)
    result["area_construida_total"]  = result["area_construida_total"].fillna(0.0)
    result["area_construida_media"]  = result["area_construida_media"].fillna(0.0)

    print(
        f"[igac] Join completado: {result['count_predios'].sum()} predios "
        f"asignados a {len(result)} manzanas."
    )
    return result


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _detectar_columna_municipio(gdf: gpd.GeoDataFrame) -> str:
    """
    Detecta el nombre de la columna de código municipal entre variantes comunes.

    En la Base Catastral IGAC 2026 la columna real es 'codigo_mun' (minúsculas).
    Se incluye primero en la lista de candidatos.
    """
    candidatos = [
        # IGAC 2026 real (minúsculas)
        "codigo_mun",
        # Variantes en mayúsculas / legado
        "MUNICIPIO_CODIGO", "COD_MPIO", "MPIO_CDPMP", "COD_MUNICIPIO",
        "DIVIPOLA", "CODIGO_MUNICIPIO", "MUNICIPIO",
    ]
    # Buscar en columnas originales (case-sensitive) y también en minúsculas
    cols_lower = {c.lower(): c for c in gdf.columns}
    for c in candidatos:
        if c in gdf.columns:
            return c
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]
    raise KeyError(
        f"[igac] No se encontró columna de código municipal. "
        f"Columnas disponibles: {list(gdf.columns)}. "
        f"Se esperaba una de: {candidatos}"
    )
