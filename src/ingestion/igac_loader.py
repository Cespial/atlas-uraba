"""
Carga de datos del catastro multipropósito IGAC para Urabá.

Fuente:
  - IGAC Catastro Multipropósito: https://www.igac.gov.co/es/contenido/areas-estrategicas/catastro-multiproposito
  - Descarga manual de shapefiles por municipio (predios y edificaciones).

Columnas clave esperadas en el shapefile de predios IGAC:
  NUPRE            → Número predial único (string 30 dígitos)
  AREA_TERR        → Área de terreno en m²
  USO_SUELO        → Código de uso del suelo (residencial, comercial, etc.)
  MUNICIPIO_CODIGO → Código DIVIPOLA del municipio (5 dígitos)

Columnas clave esperadas en la capa de edificaciones:
  NUPRE            → Número predial para join con predios
  AREA_CONST       → Área construida en m²
  PISOS            → Número de pisos
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

DIVIPOLA_URABA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]

# Columnas mínimas requeridas
COLS_PREDIOS      = {"NUPRE", "AREA_TERR", "USO_SUELO", "MUNICIPIO_CODIGO"}
COLS_EDIFICACIONES = {"NUPRE", "AREA_CONST", "PISOS"}


def cargar_predios(path: Path) -> gpd.GeoDataFrame:
    """
    Lee el shapefile de predios IGAC y filtra por municipios de Urabá.

    Estandariza los nombres de columna a mayúsculas y verifica que estén
    presentes las columnas requeridas. Retorna en CRS EPSG:4326.

    Args:
        path: Ruta al shapefile (.shp) o GeoPackage (.gpkg) de predios IGAC.

    Returns:
        GeoDataFrame de predios de Urabá con columnas:
            NUPRE, AREA_TERR, USO_SUELO, MUNICIPIO_CODIGO, geometry
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
        AssertionError:    si faltan columnas requeridas.
        ValueError:        si el GeoDataFrame queda vacío tras filtrar por Urabá.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[igac] Archivo de predios no encontrado: {path}\n"
            "Descarga el shapefile desde el portal de IGAC Catastro Multipropósito."
        )

    print(f"[igac] Cargando predios desde {path}...")
    gdf = gpd.read_file(path)

    # Normalizar columnas a mayúsculas
    gdf.columns = [c.upper() for c in gdf.columns]

    # Detectar columna de código municipal (puede llamarse diferente)
    col_municipio = _detectar_columna_municipio(gdf)
    if col_municipio != "MUNICIPIO_CODIGO":
        gdf = gdf.rename(columns={col_municipio: "MUNICIPIO_CODIGO"})

    gdf["MUNICIPIO_CODIGO"] = gdf["MUNICIPIO_CODIGO"].astype(str).str.zfill(5)

    cols_faltantes = COLS_PREDIOS - set(gdf.columns)
    assert not cols_faltantes, (
        f"[igac] Faltan columnas en predios: {cols_faltantes}. "
        f"Columnas disponibles: {list(gdf.columns)}"
    )

    gdf_uraba = gdf[gdf["MUNICIPIO_CODIGO"].isin(DIVIPOLA_URABA)].copy()

    if gdf_uraba.empty:
        raise ValueError(
            "[igac] No se encontraron predios para los municipios de Urabá. "
            f"Verifica que MUNICIPIO_CODIGO contenga códigos DIVIPOLA: {DIVIPOLA_URABA}"
        )

    print(f"[igac] {len(gdf_uraba)} predios cargados para Urabá.")

    if gdf_uraba.crs is None:
        print("[igac] ADVERTENCIA: shapefile sin CRS. Asumiendo EPSG:4326.")
        gdf_uraba = gdf_uraba.set_crs("EPSG:4326")
    else:
        gdf_uraba = gdf_uraba.to_crs("EPSG:4326")

    return gdf_uraba


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
    """
    candidatos = [
        "MUNICIPIO_CODIGO", "COD_MPIO", "MPIO_CDPMP", "COD_MUNICIPIO",
        "DIVIPOLA", "CODIGO_MUNICIPIO", "MUNICIPIO",
    ]
    for c in candidatos:
        if c in gdf.columns:
            return c
    raise KeyError(
        f"[igac] No se encontró columna de código municipal. "
        f"Columnas disponibles: {list(gdf.columns)}. "
        f"Se esperaba una de: {candidatos}"
    )
