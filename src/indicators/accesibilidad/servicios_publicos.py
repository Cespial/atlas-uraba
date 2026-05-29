"""
Indicador de Servicios Públicos (ISER) — Dimensión Accesibilidad.
Mide la tasa de establecimientos de servicios públicos por cada 1000 habitantes
accesibles desde cada manzana dentro de un radio de 1500m.

Tags OSM considerados:
  amenity: police, fire_station, post_office, townhall, courthouse, bank

A diferencia de los indicadores de área verde, salud y cultura, este indicador
usa conteo de establecimientos (no m²), dado que la superficie construida de una
comisaría o alcaldía no es la unidad relevante de servicio — sí lo es su presencia.
"""
import geopandas as gpd
import pandas as pd
import osmnx as ox

from src.indicators.base import Indicator


class IndicadorServiciosPublicos(Indicator):
    """Tasa de servicios públicos accesibles por cada 1000 hab (radio 1500m)."""

    name = "ISER"
    dimension = "accesibilidad"
    unit = "establecimientos de servicio público por 1000 habitantes"
    invert = False  # más servicios = mejor → no invertir

    OSM_TAGS = {
        "amenity": ["police", "fire_station", "post_office", "townhall", "courthouse", "bank"]
    }

    def __init__(self, manzanas: gpd.GeoDataFrame, radio_m: int = 1500):
        """
        Args:
            manzanas: GeoDataFrame con 'cod_manzana' y opcionalmente 'poblacion'.
            radio_m:  radio de acceso en metros (default 1500m, escala intercomunal).
        """
        super().__init__(manzanas)
        self.radio_m = radio_m

    def calculate(self) -> pd.Series:
        """
        Cuenta establecimientos de servicios públicos dentro del radio desde el
        centroide de cada manzana y divide por (poblacion / 1000).

        Los equipamientos se representan como centroides para el sjoin, ya que
        OSM puede mapearlos como puntos o polígonos indistintamente.
        """
        bbox = self.manzanas.total_bounds
        try:
            servicios = ox.features_from_bbox(
                bbox=(bbox[3], bbox[1], bbox[2], bbox[0]),
                tags=self.OSM_TAGS,
            ).to_crs("EPSG:3116")

            # Convertir a centroides para un sjoin homogéneo (punto-en-buffer)
            servicios = servicios.copy()
            servicios["geometry"] = servicios.geometry.centroid
            servicios = servicios.reset_index(drop=True)
            servicios["_srv_id"] = servicios.index
            servicios = gpd.GeoDataFrame(
                servicios[["_srv_id", "geometry"]], crs="EPSG:3116"
            )
        except Exception:
            servicios = gpd.GeoDataFrame(
                columns=["_srv_id", "geometry"],
                geometry="geometry",
                crs="EPSG:3116",
            )

        manzanas_proj = self.manzanas.to_crs("EPSG:3116")
        centroides = manzanas_proj.copy()
        centroides["geometry"] = centroides.geometry.centroid
        buffers = centroides.copy()
        buffers["geometry"] = centroides.geometry.buffer(self.radio_m)

        if servicios.empty:
            return pd.Series(0.0, index=self.manzanas["cod_manzana"])

        joined = gpd.sjoin(
            servicios[["_srv_id", "geometry"]],
            buffers[["cod_manzana", "geometry"]],
            how="right",
            predicate="within",
        )
        conteo_por_manzana = (
            joined.groupby("cod_manzana")["_srv_id"]
            .count()
            .reindex(self.manzanas["cod_manzana"], fill_value=0)
            .astype(float)
        )

        # Tasa por 1000 habitantes
        if "poblacion" in self.manzanas.columns:
            pop = self.manzanas.set_index("cod_manzana")["poblacion"].replace(0, 1)
            return (conteo_por_manzana / (pop / 1000)).rename(self.name)

        # Sin datos de población: retornar conteo bruto
        return conteo_por_manzana.rename(self.name)
