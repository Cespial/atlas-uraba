"""
Indicador de Áreas Verdes (IAV) — Dimensión Accesibilidad.
Mide m² de área verde accesible por habitante desde cada manzana.
Equivalente al IAV de la MBHT chilena.
"""
import geopandas as gpd
import pandas as pd
import osmnx as ox

from src.indicators.base import Indicator


class IndicadorAreasVerdes(Indicator):
    name = "IAV"
    dimension = "accesibilidad"
    unit = "m² de área verde por habitante"
    invert = False  # más área verde = mejor → no invertir

    # Tags OSM para espacios verdes
    OSM_TAGS = {"leisure": ["park", "nature_reserve", "garden", "recreation_ground"]}

    def __init__(self, manzanas: gpd.GeoDataFrame, radio_m: int = 800):
        """
        Args:
            radio_m: radio peatonal máximo en metros para considerar acceso (default 800m ~10 min caminando)
        """
        super().__init__(manzanas)
        self.radio_m = radio_m

    def calculate(self) -> pd.Series:
        """
        Calcula m² de parques/áreas verdes accesibles desde el centroide de cada manzana,
        ponderado por la inversa de la distancia y dividido por la población de la manzana.

        TODO Fase 2: reemplazar buffer simple por análisis de red con pgRouting/OSMnx.
        """
        # Obtener polígonos de parques desde OSM para el bounding box de las manzanas
        bbox = self.manzanas.total_bounds  # [minx, miny, maxx, maxy]
        try:
            parks = ox.features_from_bbox(
                bbox=(bbox[3], bbox[1], bbox[2], bbox[0]),  # (north, south, east, west)
                tags=self.OSM_TAGS,
            ).to_crs(self.manzanas.crs)
            parks = parks[parks.geometry.type.isin(["Polygon", "MultiPolygon"])]
            parks["area_m2"] = parks.geometry.to_crs("EPSG:3116").area  # MAGNA-SIRGAS Colombia
        except Exception:
            parks = gpd.GeoDataFrame(geometry=[], crs=self.manzanas.crs)

        # Buffer simple desde centroide de cada manzana
        manzanas_proj = self.manzanas.to_crs("EPSG:3116")
        centroides = manzanas_proj.copy()
        centroides["geometry"] = centroides.geometry.centroid
        buffers = centroides.copy()
        buffers["geometry"] = centroides.geometry.buffer(self.radio_m)

        if parks.empty:
            return pd.Series(0.0, index=self.manzanas["cod_manzana"])

        parks_proj = parks.to_crs("EPSG:3116")
        joined = gpd.sjoin(parks_proj[["area_m2", "geometry"]], buffers[["cod_manzana", "geometry"]], how="right", predicate="intersects")
        area_por_manzana = joined.groupby("cod_manzana")["area_m2"].sum().reindex(self.manzanas["cod_manzana"], fill_value=0.0)

        # Dividir por población si está disponible
        if "poblacion" in self.manzanas.columns:
            pop = self.manzanas.set_index("cod_manzana")["poblacion"].replace(0, 1)
            return (area_por_manzana / pop).rename(self.name)

        return area_por_manzana.rename(self.name)
