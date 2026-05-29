"""
Indicador de Salud (ISAL) — Dimensión Accesibilidad.
Mide m² de equipamiento de salud accesible por habitante desde cada manzana.
Radio 1500m (hospitales y clínicas tienen cobertura intercomunal en el Urabá antioqueño).
Nota metodológica: establecimientos primarios/secundarios atienden zonas urbanas locales (<500m);
los terciarios (hospitales) tienen alcance intercomunal, justificando el radio extendido.
"""
import geopandas as gpd
import pandas as pd
import osmnx as ox

from src.indicators.base import Indicator


class IndicadorSalud(Indicator):
    """m² de equipamiento de salud accesible por habitante (radio 1500m)."""

    name = "ISAL"
    dimension = "accesibilidad"
    unit = "m² de equipamiento de salud por habitante"
    invert = False  # más área de salud = mejor → no invertir

    OSM_TAGS = {
        "amenity": ["hospital", "clinic", "doctors", "health_post", "pharmacy"]
    }

    def __init__(self, manzanas: gpd.GeoDataFrame, radio_m: int = 1500):
        """
        Args:
            manzanas: GeoDataFrame con columna 'cod_manzana' y opcionalmente 'poblacion'.
            radio_m:  radio de acceso peatonal/vehicular en metros (default 1500m).
        """
        super().__init__(manzanas)
        self.radio_m = radio_m

    def calculate(self) -> pd.Series:
        """
        Calcula m² de equipamiento de salud dentro del radio desde el centroide
        de cada manzana. Si 'poblacion' está disponible, divide por habitante.
        """
        bbox = self.manzanas.total_bounds  # [minx, miny, maxx, maxy]
        try:
            salud = ox.features_from_bbox(
                bbox=(bbox[3], bbox[1], bbox[2], bbox[0]),  # (north, south, east, west)
                tags=self.OSM_TAGS,
            ).to_crs(self.manzanas.crs)
            salud = salud[salud.geometry.type.isin(["Polygon", "MultiPolygon"])]
            salud["area_m2"] = salud.geometry.to_crs("EPSG:3116").area
        except Exception:
            salud = gpd.GeoDataFrame(geometry=[], crs=self.manzanas.crs)

        manzanas_proj = self.manzanas.to_crs("EPSG:3116")
        centroides = manzanas_proj.copy()
        centroides["geometry"] = centroides.geometry.centroid
        buffers = centroides.copy()
        buffers["geometry"] = centroides.geometry.buffer(self.radio_m)

        if salud.empty:
            return pd.Series(0.0, index=self.manzanas["cod_manzana"])

        salud_proj = salud.to_crs("EPSG:3116")
        joined = gpd.sjoin(
            salud_proj[["area_m2", "geometry"]],
            buffers[["cod_manzana", "geometry"]],
            how="right",
            predicate="intersects",
        )
        area_por_manzana = (
            joined.groupby("cod_manzana")["area_m2"]
            .sum()
            .reindex(self.manzanas["cod_manzana"], fill_value=0.0)
        )

        if "poblacion" in self.manzanas.columns:
            pop = self.manzanas.set_index("cod_manzana")["poblacion"].replace(0, 1)
            return (area_por_manzana / pop).rename(self.name)

        return area_por_manzana.rename(self.name)
