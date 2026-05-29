"""
Indicador de Cobertura Vegetal (ICV) — Dimensión Ambiental.
Calcula el NDVI promedio por manzana usando Sentinel-2 vía Google Earth Engine.
Equivalente al ICV de la MBHT chilena.
"""
import geopandas as gpd
import pandas as pd

from src.indicators.base import Indicator


class IndicadorNDVI(Indicator):
    name = "ICV"
    dimension = "ambiental"
    unit = "NDVI promedio (0-1)"
    invert = False  # más vegetación = mejor

    # Colección GEE
    GEE_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

    def __init__(
        self,
        manzanas: gpd.GeoDataFrame,
        year: int = 2023,
        cloud_pct: float = 20.0,
    ):
        super().__init__(manzanas)
        self.year = year
        self.cloud_pct = cloud_pct

    def calculate(self) -> pd.Series:
        """
        Requiere autenticación previa con GEE: `ee.Authenticate(); ee.Initialize()`.
        Descarga NDVI medio anual por manzana desde Sentinel-2.
        """
        import ee

        manzanas_wgs = self.manzanas.to_crs("EPSG:4326")

        start = f"{self.year}-01-01"
        end = f"{self.year}-12-31"

        collection = (
            ee.ImageCollection(self.GEE_COLLECTION)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", self.cloud_pct))
            .select(["B8", "B4"])  # NIR, Red
            .map(lambda img: img.normalizedDifference(["B8", "B4"]).rename("NDVI"))
        )
        ndvi_mean = collection.mean()

        results = {}
        for _, row in manzanas_wgs.iterrows():
            geom = ee.Geometry(row.geometry.__geo_interface__)
            val = ndvi_mean.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom,
                scale=10,
                maxPixels=1e8,
            ).get("NDVI")
            results[row["cod_manzana"]] = val.getInfo() or 0.0

        return pd.Series(results, name=self.name)
