"""
Indicadores de Empleo — Dimensión Socioeconómica.

Fuente: CNPV 2018 DANE, agregado a nivel manzana.

IndicadorEmpleo (IEM):
    Mide la tasa de ocupación sobre la Población Económicamente Activa (PEA)
    en cada manzana. Captura la capacidad del mercado laboral local para
    absorber la fuerza de trabajo disponible. Una tasa alta indica menor
    desempleo y mayor estabilidad económica del hogar.

    Adaptado del componente "empleo e ingresos" de la Matriz BHT chilena.
    En el Urabá antioqueño, donde economías informales agropecuarias y
    portuarias dominan, este indicador refleja la integración al mercado
    laboral formal e informal con ingresos declarados.

    Interpretación: 0 = menor ocupación (más desempleo, peor),
                    1 = mayor ocupación (menos desempleo, mejor).
    invert=False porque tasa alta de ocupación es mejor situación.

IndicadorParticipacionJuvenil (IPJ):
    Mide el porcentaje de jóvenes entre 15 y 24 años que trabajan o estudian
    en cada manzana. Identifica la proporción de juventud "activa" versus
    los que no trabajan, no estudian ni se capacitan (NINI). Un valor bajo
    señala riesgo de exclusión social y reproductividad de la pobreza.

    Adaptado del componente "capital humano joven" de la Matriz BHT.
    En contextos de posconflicto como el Urabá, la desvinculación juvenil
    es un factor de riesgo para la reincorporación a economías ilícitas.

    Interpretación: 0 = menor participación juvenil (más exclusión, peor),
                    1 = mayor participación juvenil (menos exclusión, mejor).
    invert=False porque porcentaje alto de participación es mejor situación.
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from src.indicators.base import Indicator


class IndicadorEmpleo(Indicator):
    """IEM — Tasa de ocupación sobre la PEA por manzana."""

    name = "IEM"
    dimension = "socioeconomico"
    unit = "tasa de ocupación (0-1) sobre PEA"
    invert = False  # tasa alta = mejor → no invertir

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con columna 'tasa_ocupacion' proveniente
                      del enriquecimiento CNPV 2018. Representa la proporción
                      de personas ocupadas sobre el total de la PEA en la manzana.
        """
        super().__init__(manzanas)

    def calculate(self) -> pd.Series:
        """
        Retorna la tasa de ocupación sobre la PEA por manzana.
        Los NaN se imputan con la mediana del conjunto antes de normalizar.
        """
        serie = self.manzanas.set_index("cod_manzana")["tasa_ocupacion"].copy()
        serie = serie.fillna(serie.median())
        return serie.rename(self.name)


class IndicadorParticipacionJuvenil(Indicator):
    """IPJ — Porcentaje de jóvenes 15-24 que trabajan o estudian por manzana."""

    name = "IPJ"
    dimension = "socioeconomico"
    unit = "% jóvenes 15-24 que trabajan o estudian"
    invert = False  # porcentaje alto = mejor → no invertir

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con columna 'pct_jovenes_activos' proveniente
                      del enriquecimiento CNPV 2018. Representa el porcentaje de
                      jóvenes entre 15 y 24 años que declararon estar empleados
                      o matriculados en algún nivel educativo en la manzana.
        """
        super().__init__(manzanas)

    def calculate(self) -> pd.Series:
        """
        Retorna el porcentaje de jóvenes activos (trabajan o estudian) por manzana.
        Los NaN se imputan con la mediana del conjunto antes de normalizar.
        """
        serie = self.manzanas.set_index("cod_manzana")["pct_jovenes_activos"].copy()
        serie = serie.fillna(serie.median())
        return serie.rename(self.name)
