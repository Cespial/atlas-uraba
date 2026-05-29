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
        Usa 'pct_mat_inadecuada' del CNPV 2018 (% sin acueducto + alcantarillado + energía)
        o calcula desde columnas componentes si están disponibles.
        """
        mzn = self.manzanas.set_index("cod_manzana")

        if "pct_mat_inadecuada" in mzn.columns:
            serie = mzn["pct_mat_inadecuada"].copy()
        elif all(c in mzn.columns for c in ["pct_sin_acueducto", "pct_sin_alcantarillado", "pct_sin_energia"]):
            serie = (
                mzn["pct_sin_acueducto"]
                + mzn["pct_sin_alcantarillado"]
                + mzn["pct_sin_energia"]
            ) / 3.0
        else:
            raise KeyError(
                "Se requiere 'pct_mat_inadecuada' o las tres columnas "
                "'pct_sin_acueducto', 'pct_sin_alcantarillado', 'pct_sin_energia' "
                "en el GeoDataFrame. Ejecutar cnpv_enricher.enriquecer_manzanas() primero."
            )

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
        Usa datos CNPV 2018: pct_hacinamiento = personas/hogar/3 y
        pct_hacinamiento_severo = personas/hogar/5, ambos normalizados a [0,1].
        """
        mzn = self.manzanas.set_index("cod_manzana")

        # Calcular hacinamiento desde personas_por_hogar si no vienen directos
        if "personas_por_hogar" in mzn.columns and "pct_hacinamiento" not in mzn.columns:
            mzn = mzn.copy()
            mzn["pct_hacinamiento"] = (mzn["personas_por_hogar"] / 3.0).clip(upper=1.0)
            mzn["pct_hacinamiento_severo"] = (mzn["personas_por_hogar"] / 5.0).clip(upper=1.0)

        df = mzn[["pct_hacinamiento", "pct_hacinamiento_severo"]].copy()

        df["pct_hacinamiento"] = df["pct_hacinamiento"].fillna(df["pct_hacinamiento"].median())
        df["pct_hacinamiento_severo"] = df["pct_hacinamiento_severo"].fillna(
            df["pct_hacinamiento_severo"].median()
        )

        serie = (
            df["pct_hacinamiento"] * self.PESO_HACINAMIENTO
            + df["pct_hacinamiento_severo"] * self.PESO_SEVERO
        )
        return serie.rename(self.name)
