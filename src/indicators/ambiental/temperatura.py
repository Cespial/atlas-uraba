"""
Indicador de Amplitud Térmica Anual (IATA) — Dimensión Ambiental.
Mide la diferencia entre LST media del periodo cálido y LST media del periodo frío
por manzana usando Landsat 8 vía Google Earth Engine.

Mayor amplitud térmica implica mayor estrés térmico → invert=True.
"""
import logging
import warnings

import geopandas as gpd
import pandas as pd

from src.indicators.base import Indicator

logger = logging.getLogger(__name__)


class IndicadorAmplitudTermica(Indicator):
    """
    Amplitud térmica anual (LST_calido - LST_frio) por manzana.

    Para Colombia:
      - Periodo cálido (seco):  diciembre–marzo
      - Periodo frío (lluvias): mayo–octubre

    Fuente: LANDSAT/LC08/C02/T1_L2, banda ST_B10.
    Conversión: LST_C = ST_B10 * 0.00341802 + 149.0 - 273.15
    """

    name = "IATA"
    dimension = "ambiental"
    unit = "°C (amplitud térmica anual)"
    invert = True  # mayor amplitud = mayor estrés térmico = peor

    GEE_COLLECTION = "LANDSAT/LC08/C02/T1_L2"

    # Meses secos (cálidos) y de lluvia (fríos) para Colombia
    _MESES_CALIDO = [12, 1, 2, 3]
    _MESES_FRIO = [5, 6, 7, 8, 9, 10]

    def __init__(
        self,
        manzanas: gpd.GeoDataFrame,
        year: int = 2023,
        cloud_pct: float = 30.0,
    ):
        """
        Args:
            manzanas:   GeoDataFrame con columna 'cod_manzana' como ID único.
            year:       Año de referencia. Diciembre se toma del año anterior.
            cloud_pct:  Porcentaje máximo de nubosidad permitido.
        """
        super().__init__(manzanas)
        self.year = year
        self.cloud_pct = cloud_pct

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _lst_celsius(self, image):
        """Convierte ST_B10 a Celsius y la agrega como banda 'LST_C'."""
        import ee  # importación local para no fallar en ausencia de GEE

        lst = (
            image.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .rename("LST_C")
        )
        return image.addBands(lst)

    def _build_collection(self, start: str, end: str):
        """Construye ImageCollection filtrada por fecha y nubosidad."""
        import ee

        return (
            ee.ImageCollection(self.GEE_COLLECTION)
            .filterDate(start, end)
            .filter(ee.Filter.lt("CLOUD_COVER", self.cloud_pct))
            .map(self._lst_celsius)
            .select("LST_C")
        )

    def _lst_media_por_manzana(self, lst_image, manzanas_wgs: gpd.GeoDataFrame) -> dict:
        """Calcula LST media de una imagen compuesta para cada manzana."""
        import ee

        results = {}
        for _, row in manzanas_wgs.iterrows():
            cod = row["cod_manzana"]
            geom = ee.Geometry(row.geometry.__geo_interface__)
            val = lst_image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom,
                scale=30,          # resolución Landsat 8 térmica resampled
                maxPixels=1e8,
            ).get("LST_C")
            info = val.getInfo()
            results[cod] = float(info) if info is not None else float("nan")
        return results

    # ------------------------------------------------------------------
    # Método principal
    # ------------------------------------------------------------------

    def calculate(self) -> pd.Series:
        """
        Calcula la amplitud térmica anual (°C) por manzana.

        Requiere autenticación previa:
            import ee
            ee.Authenticate()
            ee.Initialize()

        Returns:
            pd.Series indexada por 'cod_manzana' con la amplitud en °C.
            Si GEE no está disponible retorna Series de NaN con advertencia.
        """
        try:
            import ee  # noqa: F401
        except ImportError:
            warnings.warn(
                "earthengine-api no instalado. Instala con: pip install earthengine-api. "
                "Retornando Series de NaN.",
                RuntimeWarning,
                stacklevel=2,
            )
            return pd.Series(
                float("nan"),
                index=self.manzanas["cod_manzana"],
                name=self.name,
            )

        try:
            # Verificar que GEE esté inicializado intentando una operación trivial
            ee.Number(1).getInfo()
        except Exception as exc:
            warnings.warn(
                f"GEE no autenticado/inicializado ({exc}). "
                "Ejecuta ee.Authenticate() y ee.Initialize() antes de usar este indicador. "
                "Retornando Series de NaN.",
                RuntimeWarning,
                stacklevel=2,
            )
            return pd.Series(
                float("nan"),
                index=self.manzanas["cod_manzana"],
                name=self.name,
            )

        manzanas_wgs = self.manzanas.to_crs("EPSG:4326")
        year = self.year

        # ---- Periodo cálido (diciembre año-1 a marzo año) ----
        # Diciembre del año anterior + enero-marzo del año actual
        start_calido = f"{year - 1}-12-01"
        end_calido = f"{year}-03-31"

        # ---- Periodo frío (mayo–octubre del año) ----
        start_frio = f"{year}-05-01"
        end_frio = f"{year}-10-31"

        logger.info(
            "IATA | Descargando LST Landsat 8 "
            "cálido=%s→%s  frío=%s→%s  nubosidad<%.0f%%",
            start_calido, end_calido, start_frio, end_frio, self.cloud_pct,
        )

        col_calido = self._build_collection(start_calido, end_calido)
        col_frio = self._build_collection(start_frio, end_frio)

        lst_calido_img = col_calido.mean()
        lst_frio_img = col_frio.mean()

        logger.info("IATA | Extrayendo LST media periodo cálido por manzana …")
        vals_calido = self._lst_media_por_manzana(lst_calido_img, manzanas_wgs)

        logger.info("IATA | Extrayendo LST media periodo frío por manzana …")
        vals_frio = self._lst_media_por_manzana(lst_frio_img, manzanas_wgs)

        # Amplitud = LST_calido - LST_frio
        s_calido = pd.Series(vals_calido, name="lst_calido")
        s_frio = pd.Series(vals_frio, name="lst_frio")
        amplitud = (s_calido - s_frio).rename(self.name)

        n_nan = amplitud.isna().sum()
        if n_nan > 0:
            logger.warning(
                "IATA | %d manzanas sin datos LST (posiblemente sin escenas válidas "
                "para ese periodo/nubosidad).",
                n_nan,
            )

        return amplitud
