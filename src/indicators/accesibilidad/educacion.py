"""
Indicador de Educación (ISE) — Dimensión Accesibilidad.
Mide matrículas disponibles por niño/a en edad escolar (4-18 años) desde cada manzana.

Lógica de cálculo:
- Si 'matriculas_disponibles' existe en el GeoDataFrame → se usa directamente.
- Si no → se cuentan establecimientos educativos OSM accesibles en radio 1000m
  y se estima la capacidad: n_establecimientos × capacidad_estimada (300 cupos/sede).

Para dividir por demanda, se usa 'poblacion_4_18' si está disponible,
luego 'poblacion' (proxy), y si ninguna existe, se retorna el conteo bruto.
"""
import geopandas as gpd
import pandas as pd
import osmnx as ox

from src.indicators.base import Indicator


class IndicadorEducacion(Indicator):
    """Matrículas disponibles por niño/a 4-18 años en radio 1000m."""

    name = "ISE"
    dimension = "accesibilidad"
    unit = "matrículas disponibles por niño/a 4-18 años"
    invert = False  # más oferta educativa = mejor → no invertir

    OSM_TAGS = {
        "amenity": ["school", "kindergarten", "university", "college"]
    }

    CAPACIDAD_ESTIMADA = 300  # cupos promedio estimados por sede cuando no hay datos reales

    def __init__(self, manzanas: gpd.GeoDataFrame, radio_m: int = 1000):
        """
        Args:
            manzanas: GeoDataFrame con 'cod_manzana' y opcionalmente
                      'matriculas_disponibles', 'poblacion_4_18', 'poblacion'.
            radio_m:  radio de acceso en metros (default 1000m).
        """
        super().__init__(manzanas)
        self.radio_m = radio_m

    def calculate(self) -> pd.Series:
        """
        Retorna matrículas disponibles por niño/a indexado por 'cod_manzana'.
        Usa matriculas_disponibles directamente si la columna existe; de lo contrario
        estima a partir de conteo de establecimientos OSM dentro del radio.
        """
        # Ruta 1: datos reales de matrículas en el GeoDataFrame
        if "matriculas_disponibles" in self.manzanas.columns:
            matriculas = self.manzanas.set_index("cod_manzana")["matriculas_disponibles"]
            if "poblacion_4_18" in self.manzanas.columns:
                demanda = self.manzanas.set_index("cod_manzana")["poblacion_4_18"].replace(0, 1)
                return (matriculas / demanda).rename(self.name)
            if "poblacion" in self.manzanas.columns:
                # Proxy: ~28 % de la población es menor de 18 años (estimación Urabá)
                pop = self.manzanas.set_index("cod_manzana")["poblacion"].replace(0, 1)
                return (matriculas / (pop * 0.28)).rename(self.name)
            return matriculas.rename(self.name)

        # Ruta 2: estimar desde OSM
        bbox = self.manzanas.total_bounds  # [minx, miny, maxx, maxy]
        try:
            colegios = ox.features_from_bbox(
                bbox=(bbox[3], bbox[1], bbox[2], bbox[0]),
                tags=self.OSM_TAGS,
            ).to_crs(self.manzanas.crs)
            # Mantener puntos y polígonos (algunas escuelas OSM son polígonos)
            colegios = colegios[
                colegios.geometry.type.isin(
                    ["Point", "Polygon", "MultiPolygon"]
                )
            ].copy()
            # Representar polígonos como centroides para el sjoin por radio
            colegios["geometry"] = colegios.geometry.to_crs("EPSG:3116").centroid.to_crs(
                self.manzanas.crs
            )
        except Exception:
            colegios = gpd.GeoDataFrame(geometry=[], crs=self.manzanas.crs)

        manzanas_proj = self.manzanas.to_crs("EPSG:3116")
        centroides = manzanas_proj.copy()
        centroides["geometry"] = centroides.geometry.centroid
        buffers = centroides.copy()
        buffers["geometry"] = centroides.geometry.buffer(self.radio_m)

        if colegios.empty:
            return pd.Series(0.0, index=self.manzanas["cod_manzana"])

        colegios_proj = colegios.to_crs("EPSG:3116")
        colegios_proj = colegios_proj.reset_index(drop=True)
        colegios_proj["_colegio_id"] = colegios_proj.index

        joined = gpd.sjoin(
            colegios_proj[["_colegio_id", "geometry"]],
            buffers[["cod_manzana", "geometry"]],
            how="right",
            predicate="intersects",
        )
        conteo_por_manzana = (
            joined.groupby("cod_manzana")["_colegio_id"]
            .count()
            .reindex(self.manzanas["cod_manzana"], fill_value=0)
            .astype(float)
        )

        matriculas_estimadas = conteo_por_manzana * self.CAPACIDAD_ESTIMADA

        if "poblacion_4_18" in self.manzanas.columns:
            demanda = self.manzanas.set_index("cod_manzana")["poblacion_4_18"].replace(0, 1)
            return (matriculas_estimadas / demanda).rename(self.name)

        if "poblacion" in self.manzanas.columns:
            pop = self.manzanas.set_index("cod_manzana")["poblacion"].replace(0, 1)
            return (matriculas_estimadas / (pop * 0.28)).rename(self.name)

        return matriculas_estimadas.rename(self.name)
