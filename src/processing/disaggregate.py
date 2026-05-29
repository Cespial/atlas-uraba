"""
Disagregación de datos censales desde sectores/secciones DANE → manzanas.

Usa interpolación areal (tobler) para bajar datos del CNPV 2018 desde
unidades supra-manzana (sector/sección censal) a manzana censal individual.

Referencia metodológica: tobler.area_weighted.area_interpolate
Ver: https://pysal.org/tobler/
"""
from __future__ import annotations
import geopandas as gpd
import pandas as pd
from tobler.area_weighted import area_interpolate
from tobler.dasymetric import masked_area_interpolate


def disaggregate_simple(
    source: gpd.GeoDataFrame,
    target: gpd.GeoDataFrame,
    extensive_vars: list[str],
    intensive_vars: list[str],
) -> gpd.GeoDataFrame:
    """
    Interpolación areal simple ponderada por área.
    Útil como primera aproximación cuando no hay capas auxiliares.

    Args:
        source: GeoDataFrame de unidades fuente (ej. sectores censales DANE).
        target: GeoDataFrame de manzanas destino (MGN).
        extensive_vars: Variables de conteo (población, hogares) — se redistribuyen proporcionalmente.
        intensive_vars: Variables de tasa (%, promedio) — se interpolan directamente.

    Returns:
        GeoDataFrame de manzanas con columnas disagregadas añadidas.
    """
    source_proj = source.to_crs("EPSG:3116")
    target_proj = target.to_crs("EPSG:3116")

    interpolated = area_interpolate(
        source_df=source_proj,
        target_df=target_proj,
        extensive_variables=extensive_vars,
        intensive_variables=intensive_vars,
    )
    return interpolated.to_crs(target.crs)


def disaggregate_dasymetric(
    source: gpd.GeoDataFrame,
    target: gpd.GeoDataFrame,
    mask: gpd.GeoDataFrame,
    extensive_vars: list[str],
) -> gpd.GeoDataFrame:
    """
    Interpolación dasyimétrica ponderada por edificaciones.
    Más precisa que la simple: asume que la población se concentra
    donde hay edificios (capa de edificaciones IGAC o OSM).

    Args:
        source: Sectores censales DANE.
        target: Manzanas MGN destino.
        mask: Polígonos de edificaciones como máscara de distribución real.
        extensive_vars: Variables de conteo a disagregar.

    Returns:
        GeoDataFrame de manzanas con variables disagregadas.
    """
    source_proj = source.to_crs("EPSG:3116")
    target_proj = target.to_crs("EPSG:3116")
    mask_proj = mask.to_crs("EPSG:3116")

    interpolated = masked_area_interpolate(
        source_df=source_proj,
        target_df=target_proj,
        mask=mask_proj,
        extensive_variables=extensive_vars,
    )
    return interpolated.to_crs(target.crs)
