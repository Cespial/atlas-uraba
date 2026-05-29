"""Tests básicos para la arquitectura de indicadores."""
import pytest
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Polygon
from src.indicators.base import Indicator, CompositeIndicator


def _make_manzanas(n: int = 5) -> gpd.GeoDataFrame:
    """GeoDataFrame de prueba con n manzanas cuadradas sintéticas."""
    geoms = [Polygon([(i, 0), (i+1, 0), (i+1, 1), (i, 1)]) for i in range(n)]
    return gpd.GeoDataFrame(
        {"cod_manzana": [f"mzn_{i:03d}" for i in range(n)], "poblacion": [100] * n},
        geometry=geoms,
        crs="EPSG:4326",
    )


class DummyIndicator(Indicator):
    name = "dummy"
    dimension = "test"
    unit = "unidades"
    invert = False

    def __init__(self, manzanas, values):
        super().__init__(manzanas)
        self._values = values

    def calculate(self) -> pd.Series:
        return pd.Series(self._values, index=self.manzanas["cod_manzana"])


def test_normalizacion_rango():
    mzn = _make_manzanas()
    ind = DummyIndicator(mzn, [0, 25, 50, 75, 100])
    result = ind.run()
    assert result.min() == pytest.approx(0.0)
    assert result.max() == pytest.approx(1.0)


def test_normalizacion_invertida():
    mzn = _make_manzanas()
    ind = DummyIndicator(mzn, [0, 25, 50, 75, 100])
    ind.invert = True
    result = ind.run()
    # El valor 0 (el más bajo = mejor) debe dar 1 al invertir
    assert result.iloc[0] == pytest.approx(1.0)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_composite_pesos_iguales():
    mzn = _make_manzanas(3)
    ind1 = DummyIndicator(mzn, [1.0, 0.5, 0.0])
    ind2 = DummyIndicator(mzn, [0.0, 0.5, 1.0])
    composite = CompositeIndicator([ind1, ind2], name="test_composite")
    result = composite.run()
    # Con pesos iguales y valores simétricos, todas las manzanas deben tener el mismo score
    assert result.iloc[0] == pytest.approx(result.iloc[-1], abs=1e-6)


def test_composite_pesos_invalidos():
    mzn = _make_manzanas(2)
    ind = DummyIndicator(mzn, [1.0, 0.0])
    with pytest.raises(AssertionError):
        CompositeIndicator([ind], weights=[0.4, 0.6])  # longitud incorrecta
