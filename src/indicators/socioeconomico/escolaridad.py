"""
Indicador de Escolaridad — Dimensión Socioeconómica.

Fuente: CNPV 2018 DANE, agregado a nivel manzana.

IndicadorEscolaridadJefeHogar (IEJ):
    Mide el promedio de años de escolaridad del jefe o jefa de hogar en cada
    manzana. Es un proxy de capital humano del hogar y predictor de movilidad
    social. Adaptado del componente "educación" de la Matriz BHT chilena
    (Ministerio de Vivienda y Urbanismo de Chile), que utiliza años de
    escolaridad del jefe de hogar como indicador de rezago educativo.

    A diferencia de Colombia donde se usa el CNPV 2018, la BHT chilena usa
    la Encuesta CASEN. Ambas capturan el mismo constructo: capital educativo
    del hogar como determinante de la vulnerabilidad.

    Interpretación: 0 = menor escolaridad (más vulnerable),
                    1 = mayor escolaridad (menos vulnerable).
    invert=False porque más escolaridad es mejor situación.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.indicators.base import Indicator


class IndicadorEscolaridadJefeHogar(Indicator):
    """IEJ — Promedio de años de escolaridad del jefe/a de hogar por manzana."""

    name = "IEJ"
    dimension = "socioeconomico"
    unit = "años promedio de escolaridad del jefe de hogar"
    invert = False  # más escolaridad = mejor → no invertir

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con columna 'esc_jefe_hogar' proveniente
                      del enriquecimiento CNPV 2018. Representa el promedio
                      de años de educación formal aprobados por el jefe de
                      hogar en la manzana.
        """
        super().__init__(manzanas)

    def calculate(self) -> pd.Series:
        """
        Retorna el nivel educativo ponderado por manzana.
        Usa 'escolaridad_ponderada' del CNPV 2018 (primaria=1..posgrado=4)
        o 'esc_jefe_hogar' si está disponible.
        """
        mzn = self.manzanas.set_index("cod_manzana")
        col = next(
            (c for c in ["escolaridad_ponderada", "esc_jefe_hogar"] if c in mzn.columns),
            None,
        )
        if col is None:
            raise KeyError(
                "Se requiere 'escolaridad_ponderada' o 'esc_jefe_hogar'. "
                "Ejecutar cnpv_enricher.enriquecer_manzanas() primero."
            )
        serie = mzn[col].copy().fillna(mzn[col].median())
        return serie.rename(self.name)
