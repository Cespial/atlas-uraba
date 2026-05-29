"""
Indicador de Equipamientos Deportivos (IDEP) — Dimensión Accesibilidad.
Mide m² de equipamiento deportivo accesible por habitante desde cada manzana.

Radios diferenciados por escala:
- Canchas / pitch (escala local):     600m (~7 min caminando)
- Estadios / stadium (intercomunal): 2000m (acceso vehicular o transporte)
Los demás equipamientos (sports_centre, swimming_pool, fitness_centre) usan 1000m.
"""
import geopandas as gpd
import pandas as pd
import osmnx as ox

from src.indicators.base import Indicator


# Equipamientos agrupados por radio de servicio (metros)
_TAGS_LOCAL = {"leisure": ["pitch"]}
_TAGS_INTERCOMUNAL = {"leisure": ["stadium"]}
_TAGS_MEDIO = {"leisure": ["sports_centre", "swimming_pool", "fitness_centre"]}

# Tags combinados para la consulta OSM única
_OSM_TAGS_ALL = {
    "leisure": ["sports_centre", "pitch", "stadium", "swimming_pool", "fitness_centre"]
}

_RADIO_LOCAL = 600
_RADIO_INTERCOMUNAL = 2000
_RADIO_MEDIO = 1000


class IndicadorDeportivos(Indicator):
    """m² de equipamiento deportivo accesible por habitante (radios diferenciados por escala)."""

    name = "IDEP"
    dimension = "accesibilidad"
    unit = "m² de equipamiento deportivo por habitante"
    invert = False  # más área deportiva = mejor → no invertir

    OSM_TAGS = _OSM_TAGS_ALL

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con 'cod_manzana' y opcionalmente 'poblacion'.
        """
        super().__init__(manzanas)

    def _fetch_features(self) -> gpd.GeoDataFrame:
        """Descarga todos los equipamientos deportivos OSM para el bbox de las manzanas."""
        bbox = self.manzanas.total_bounds
        try:
            feats = ox.features_from_bbox(
                bbox=(bbox[3], bbox[1], bbox[2], bbox[0]),
                tags=self.OSM_TAGS,
            ).to_crs("EPSG:3116")
            feats = feats[feats.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
            feats["area_m2"] = feats.geometry.area
            # Normalizar tag 'leisure' para clasificación
            if "leisure" in feats.columns:
                feats["_leisure"] = feats["leisure"].fillna("").astype(str)
            else:
                feats["_leisure"] = ""
            return feats
        except Exception:
            return gpd.GeoDataFrame(
                columns=["area_m2", "_leisure", "geometry"],
                geometry="geometry",
                crs="EPSG:3116",
            )

    def _area_accesible(
        self,
        feats: gpd.GeoDataFrame,
        buffers: gpd.GeoDataFrame,
        subset_tag: str | None,
        radio_m: int,
    ) -> pd.Series:
        """
        Calcula m² accesibles para un subconjunto de equipamientos y un radio dado.
        subset_tag: valor de '_leisure' a filtrar; None = todos los equipamientos.
        """
        if subset_tag is not None:
            sub = feats[feats["_leisure"] == subset_tag]
        else:
            sub = feats

        if sub.empty:
            return pd.Series(
                0.0, index=buffers["cod_manzana"], name="area_m2"
            )

        # Buffer ya construido con el radio correcto
        joined = gpd.sjoin(
            sub[["area_m2", "geometry"]],
            buffers[["cod_manzana", "geometry"]],
            how="right",
            predicate="intersects",
        )
        return (
            joined.groupby("cod_manzana")["area_m2"]
            .sum()
            .reindex(buffers["cod_manzana"], fill_value=0.0)
        )

    def _make_buffers(self, manzanas_proj: gpd.GeoDataFrame, radio_m: int) -> gpd.GeoDataFrame:
        centroides = manzanas_proj.copy()
        centroides["geometry"] = centroides.geometry.centroid
        buffers = centroides.copy()
        buffers["geometry"] = centroides.geometry.buffer(radio_m)
        return buffers

    def calculate(self) -> pd.Series:
        """
        Agrega m² deportivos accesibles por manzana sumando los tres tramos de radio.
        Divide por 'poblacion' si la columna está disponible.
        """
        feats = self._fetch_features()
        manzanas_proj = self.manzanas.to_crs("EPSG:3116")

        if feats.empty:
            return pd.Series(0.0, index=self.manzanas["cod_manzana"])

        # Tramo local: canchas (pitch) a 600m
        buf_local = self._make_buffers(manzanas_proj, _RADIO_LOCAL)
        area_local = self._area_accesible(feats, buf_local, "pitch", _RADIO_LOCAL)

        # Tramo intercomunal: estadios a 2000m
        buf_inter = self._make_buffers(manzanas_proj, _RADIO_INTERCOMUNAL)
        area_inter = self._area_accesible(feats, buf_inter, "stadium", _RADIO_INTERCOMUNAL)

        # Tramo medio: centros deportivos, piscinas, gimnasios a 1000m
        buf_medio = self._make_buffers(manzanas_proj, _RADIO_MEDIO)
        tags_medios = ["sports_centre", "swimming_pool", "fitness_centre"]
        feats_medios = feats[feats["_leisure"].isin(tags_medios)]
        if feats_medios.empty:
            area_medio = pd.Series(0.0, index=self.manzanas["cod_manzana"])
        else:
            joined_medio = gpd.sjoin(
                feats_medios[["area_m2", "geometry"]],
                buf_medio[["cod_manzana", "geometry"]],
                how="right",
                predicate="intersects",
            )
            area_medio = (
                joined_medio.groupby("cod_manzana")["area_m2"]
                .sum()
                .reindex(self.manzanas["cod_manzana"], fill_value=0.0)
            )

        total_area = (
            area_local.reindex(self.manzanas["cod_manzana"], fill_value=0.0)
            + area_inter.reindex(self.manzanas["cod_manzana"], fill_value=0.0)
            + area_medio.reindex(self.manzanas["cod_manzana"], fill_value=0.0)
        )

        if "poblacion" in self.manzanas.columns:
            pop = self.manzanas.set_index("cod_manzana")["poblacion"].replace(0, 1)
            return (total_area / pop).rename(self.name)

        return total_area.rename(self.name)
