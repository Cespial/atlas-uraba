"""
Indicadores de Vivienda — Dimensión Socioeconómica.

Fuente: CNPV 2018 DANE, agregado a nivel manzana.

IndicadorCalidadVivienda (IVI):
    Mide el porcentaje de viviendas con materiales inadecuados en paredes,
    piso o techo. Un valor alto indica precariedad estructural del parque
    habitacional. Adaptado del componente "calidad de la vivienda" de la
    Matriz BHT chilena (Ministerio de Vivienda y Urbanismo).
    Interpretación: 0 = mejor calidad (menos inadecuadas), 1 = peor.

IndicadorSuficienciaVivienda (ISV):
    Mide el nivel de hacinamiento combinando hacinamiento moderado y severo
    mediante un promedio ponderado (0.6 hacinamiento + 0.4 severo). Captura
    tanto la extensión como la intensidad del problema de sobrepoblación en
    el hogar. Adaptado del componente "hacinamiento" de la Matriz BHT.
    Interpretación: 0 = sin hacinamiento, 1 = hacinamiento máximo.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.indicators.base import Indicator


class IndicadorCalidadVivienda(Indicator):
    """IVI — Porcentaje de viviendas con materiales inadecuados (paredes/piso/techo)."""

    name = "IVI"
    dimension = "socioeconomico"
    unit = "% viviendas con materiales inadecuados"
    invert = True  # valor alto = peor situación → invertir en normalización

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con columna 'pct_mat_inadecuada' proveniente
                      del enriquecimiento CNPV 2018.
        """
        super().__init__(manzanas)

    def calculate(self) -> pd.Series:
        """
        Retorna el porcentaje de viviendas con materiales inadecuados por manzana.
        Los NaN se imputan con la mediana del conjunto antes de normalizar.
        """
        serie = self.manzanas.set_index("cod_manzana")["pct_mat_inadecuada"].copy()
        serie = serie.fillna(serie.median())
        return serie.rename(self.name)


class IndicadorSuficienciaVivienda(Indicator):
    """ISV — Índice de hacinamiento ponderado (moderado 0.6 + severo 0.4)."""

    name = "ISV"
    dimension = "socioeconomico"
    unit = "índice ponderado de hacinamiento (0-100)"
    invert = True  # valor alto = peor situación → invertir en normalización

    # Pesos del promedio ponderado
    PESO_HACINAMIENTO = 0.6
    PESO_SEVERO = 0.4

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con columnas 'pct_hacinamiento' y
                      'pct_hacinamiento_severo' provenientes del enriquecimiento
                      CNPV 2018.
        """
        super().__init__(manzanas)

    def calculate(self) -> pd.Series:
        """
        Calcula promedio ponderado entre hacinamiento moderado (60%) y severo (40%).
        Los NaN en cada columna se imputan con la mediana de esa columna.
        """
        df = self.manzanas.set_index("cod_manzana")[
            ["pct_hacinamiento", "pct_hacinamiento_severo"]
        ].copy()

        df["pct_hacinamiento"] = df["pct_hacinamiento"].fillna(df["pct_hacinamiento"].median())
        df["pct_hacinamiento_severo"] = df["pct_hacinamiento_severo"].fillna(
            df["pct_hacinamiento_severo"].median()
        )

        serie = (
            df["pct_hacinamiento"] * self.PESO_HACINAMIENTO
            + df["pct_hacinamiento_severo"] * self.PESO_SEVERO
        )
        return serie.rename(self.name)
