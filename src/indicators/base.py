"""
Clase base para todos los indicadores de Atlas Urabá.
Inspirado en la arquitectura Indicator/CompositeIndicator de CityScope (MIT Media Lab).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import geopandas as gpd
import pandas as pd
import numpy as np


class Indicator(ABC):
    """Clase base. Cada indicador concreto subclasifica e implementa `calculate`."""

    name: str = ""
    dimension: str = ""         # accesibilidad | ambiental | socioeconomico | seguridad
    unit: str = ""              # descripción de la unidad del valor raw
    invert: bool = False        # True si valor alto = peor (se invierte en normalización)

    def __init__(self, manzanas: gpd.GeoDataFrame):
        """
        Args:
            manzanas: GeoDataFrame con geometrías de manzanas (EPSG:4326 o proyectado).
                      Debe tener columna 'cod_manzana' como identificador único.
        """
        self.manzanas = manzanas

    @abstractmethod
    def calculate(self) -> pd.Series:
        """Retorna una Series indexada por 'cod_manzana' con el valor raw del indicador."""

    def normalize(self, series: pd.Series) -> pd.Series:
        """Normaliza a 0-1. Si invert=True, 1 = valor más bajo (mejor)."""
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series(0.5, index=series.index)
        normalized = (series - mn) / (mx - mn)
        return (1 - normalized) if self.invert else normalized

    def run(self) -> pd.Series:
        """Calcula y normaliza. Retorna Series 0-1 indexada por cod_manzana."""
        raw = self.calculate()
        return self.normalize(raw).rename(self.name)


class CompositeIndicator:
    """
    Agrega múltiples indicadores en un índice compuesto.
    Soporta pesos iguales o personalizados, y PCA como método alternativo.
    """

    def __init__(
        self,
        indicators: list[Indicator],
        weights: Optional[list[float]] = None,
        name: str = "composite",
    ):
        self.indicators = indicators
        self.weights = weights or [1.0 / len(indicators)] * len(indicators)
        self.name = name
        assert len(self.weights) == len(self.indicators), "Pesos e indicadores deben tener la misma longitud"
        assert abs(sum(self.weights) - 1.0) < 1e-6, "Los pesos deben sumar 1"

    def run(self) -> pd.Series:
        """Retorna el índice compuesto normalizado 0-1 por manzana."""
        scores = pd.DataFrame({ind.name: ind.run() for ind in self.indicators})
        composite = sum(scores[ind.name] * w for ind, w in zip(self.indicators, self.weights))
        mn, mx = composite.min(), composite.max()
        if mx == mn:
            return pd.Series(0.5, index=composite.index, name=self.name)
        return ((composite - mn) / (mx - mn)).rename(self.name)
