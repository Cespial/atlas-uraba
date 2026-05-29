"""
Indicador de Resiliencia de Hogares — Dimensión Socioeconómica.

Fuente: CNPV 2018 DANE, agregado a nivel manzana.

IndicadorResilienciaHogares (IRH):
    Mide el porcentaje de hogares monoparentales con hijos en cada manzana.
    Los hogares monoparentales, especialmente los encabezados por mujeres,
    enfrentan mayor presión económica y menor capacidad de respuesta ante
    choques externos (desempleo, enfermedad, desastres naturales), lo que
    los hace más vulnerables y con menor resiliencia estructural.

    Adaptado del componente "composición del hogar y vulnerabilidad" de la
    Matriz BHT chilena. En el contexto del Urabá antioqueño, donde la
    presencia histórica de conflicto armado ha fragmentado estructuras
    familiares, este indicador adquiere especial relevancia.

    Interpretación: 0 = menor proporción monoparental (más resiliencia),
                    1 = mayor proporción monoparental (menos resiliencia).
    invert=True porque un porcentaje alto de monoparentalidad
    indica mayor vulnerabilidad (peor situación).
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.indicators.base import Indicator


class IndicadorResilienciaHogares(Indicator):
    """IRH — Porcentaje de hogares monoparentales con hijos por manzana."""

    name = "IRH"
    dimension = "socioeconomico"
    unit = "% hogares monoparentales con hijos"
    invert = True  # valor alto = peor situación (más vulnerabilidad) → invertir

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con columna 'pct_monoparental' proveniente
                      del enriquecimiento CNPV 2018. Representa el porcentaje
                      de hogares con un solo progenitor y al menos un hijo
                      dependiente en la manzana.
        """
        super().__init__(manzanas)

    def calculate(self) -> pd.Series:
        """
        Retorna el porcentaje de hogares monoparentales con hijos por manzana.
        Los NaN se imputan con la mediana del conjunto antes de normalizar.
        """
        serie = self.manzanas.set_index("cod_manzana")["pct_monoparental"].copy()
        serie = serie.fillna(serie.median())
        return serie.rename(self.name)
