"""
Indicador de Equipamientos Culturales (ICUL) — Dimensión Accesibilidad.
Mide m² de equipamiento cultural accesible por habitante desde cada manzana.
Radio 1200m (alcance intermedio: escala de barrio ampliado o comunal).

Tags OSM considerados:
  amenity: theatre, cinema, library, community_centre, arts_centre
  tourism: museum
"""
import geopandas as gpd
import pandas as pd
import osmnx as ox

from src.indicators.base import Indicator


class IndicadorCulturales(Indicator):
    """m² de equipamiento cultural accesible por habitante (radio 1200m)."""

    name = "ICUL"
    dimension = "accesibilidad"
    unit = "m² de equipamiento cultural por habitante"
    invert = False  # más oferta cultural = mejor → no invertir

    OSM_TAGS = {
        "amenity": ["theatre", "cinema", "library", "community_centre", "arts_centre"],
        "tourism": ["museum"],
    }

    def __init__(self, manzanas: gpd.GeoDataFrame, radio_m: int = 1200):
        """
        Args:
            manzanas: GeoDataFrame con 'cod_manzana' y opcionalmente 'poblacion'.
            radio_m:  radio de acceso en metros (default 1200m).
        """
        super().__init__(manzanas)
        self.radio_m = radio_m

    def calculate(self) -> pd.Series:
        """
        Calcula m² de equipamiento cultural dentro del radio desde el centroide
        de cada manzana. Divide por 'poblacion' si la columna está disponible.

        Nota: muchos equipamientos culturales en OSM están mapeados como puntos.
        Para puntos se asigna un área estimada estándar de 500 m² (sala polivalente típica).
        """
        bbox = self.manzanas.total_bounds
        try:
            culturales = ox.features_from_bbox(
                bbox=(bbox[3], bbox[1], bbox[2], bbox[0]),
                tags=self.OSM_TAGS,
            ).to_crs("EPSG:3116")

            # Separar polígonos (área real) y puntos (área estimada)
            es_poligono = culturales.geometry.type.isin(["Polygon", "MultiPolygon"])
            poligonos = culturales[es_poligono].copy()
            puntos = culturales[~es_poligono].copy()

            if not poligonos.empty:
                poligonos["area_m2"] = poligonos.geometry.area
            if not puntos.empty:
                # Área estimada para equipamientos sin polígono en OSM
                puntos["area_m2"] = 500.0
                puntos["geometry"] = puntos.geometry.centroid.buffer(1)  # punto → micro-polígono

            culturales_proc = pd.concat(
                [df for df in [poligonos, puntos] if not df.empty],
                ignore_index=True,
            )
            culturales_proc = gpd.GeoDataFrame(
                culturales_proc[["area_m2", "geometry"]], crs="EPSG:3116"
            )
        except Exception:
            culturales_proc = gpd.GeoDataFrame(
                columns=["area_m2", "geometry"],
                geometry="geometry",
                crs="EPSG:3116",
            )

        manzanas_proj = self.manzanas.to_crs("EPSG:3116")
        centroides = manzanas_proj.copy()
        centroides["geometry"] = centroides.geometry.centroid
        buffers = centroides.copy()
        buffers["geometry"] = centroides.geometry.buffer(self.radio_m)

        if culturales_proc.empty:
            return pd.Series(0.0, index=self.manzanas["cod_manzana"])

        joined = gpd.sjoin(
            culturales_proc[["area_m2", "geometry"]],
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
