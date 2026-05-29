"""
Tests para src/processing/disaggregate.py

Verifica que la interpolación areal conserva propiedades clave:
- Variables extensivas (conteos): conservación de totales.
- Variables intensivas (tasas): conservación del rango.
- Manejo de GeoDataFrame fuente vacío.
"""
from __future__ import annotations

import numpy as np
import pytest
import geopandas as gpd
from shapely.geometry import box

from src.processing.disaggregate import disaggregate_simple


# ---------------------------------------------------------------------------
# Fixtures auxiliares
# ---------------------------------------------------------------------------

def _make_sectores() -> gpd.GeoDataFrame:
    """
    3 sectores censales rectangulares, dispuestos en columna vertical.
    Cada sector tiene 3 manzanas (9 en total).

    Layout (coordenadas EPSG:3116, metros):
        Sector 0: y 0..300
        Sector 1: y 300..600
        Sector 2: y 600..900
    """
    geometrias = [
        box(0, 0, 300, 300),
        box(0, 300, 300, 600),
        box(0, 600, 300, 900),
    ]
    return gpd.GeoDataFrame(
        {
            "id_sector": ["S0", "S1", "S2"],
            "poblacion": [1000.0, 2000.0, 3000.0],
            "tasa_hacinamiento": [0.10, 0.25, 0.40],  # variable intensiva (%)
        },
        geometry=geometrias,
        crs="EPSG:3116",
    )


def _make_manzanas() -> gpd.GeoDataFrame:
    """
    9 manzanas de 100x100 m, 3 dentro de cada sector.
    """
    geometrias = []
    ids = []
    for fila in range(3):        # sectores
        for col in range(3):     # manzanas por sector
            x0 = col * 100
            y0 = fila * 300
            geometrias.append(box(x0, y0, x0 + 100, y0 + 100))
            ids.append(f"MZ_{fila}_{col}")

    return gpd.GeoDataFrame(
        {"cod_manzana": ids},
        geometry=geometrias,
        crs="EPSG:3116",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAreaInterpolate:
    """Grupo de tests para disaggregate_simple."""

    def test_area_interpolate_conserva_poblacion_total(self):
        """
        Variables extensivas (conteos) deben conservar el total poblacional
        con una tolerancia del 5% respecto al total de la fuente.
        """
        sectores = _make_sectores()
        manzanas = _make_manzanas()

        resultado = disaggregate_simple(
            source=sectores,
            target=manzanas,
            extensive_vars=["poblacion"],
            intensive_vars=[],
        )

        total_original = sectores["poblacion"].sum()          # 6000
        total_disagregado = resultado["poblacion"].sum()

        tolerancia = 0.05 * total_original
        assert abs(total_disagregado - total_original) <= tolerancia, (
            f"Total disagregado {total_disagregado:.1f} difiere del original "
            f"{total_original:.1f} en más del 5%."
        )

    def test_disaggregate_intensivas_rango(self):
        """
        Las variables intensivas (tasas/promedios) disagregadas deben
        permanecer dentro del rango [min, max] de la fuente original.
        """
        sectores = _make_sectores()
        manzanas = _make_manzanas()

        resultado = disaggregate_simple(
            source=sectores,
            target=manzanas,
            extensive_vars=[],
            intensive_vars=["tasa_hacinamiento"],
        )

        min_orig = sectores["tasa_hacinamiento"].min()
        max_orig = sectores["tasa_hacinamiento"].max()

        valores = resultado["tasa_hacinamiento"].dropna()
        assert len(valores) > 0, "No se disagregó ninguna manzana."

        assert valores.min() >= min_orig - 1e-6, (
            f"Valor mínimo disagregado {valores.min():.4f} < mínimo original {min_orig:.4f}."
        )
        assert valores.max() <= max_orig + 1e-6, (
            f"Valor máximo disagregado {valores.max():.4f} > máximo original {max_orig:.4f}."
        )

    def test_empty_source(self):
        """
        Si el GeoDataFrame fuente está vacío, el resultado debe devolver
        las manzanas target con NaN en las columnas disagregadas.
        """
        sectores_vacios = gpd.GeoDataFrame(
            columns=["id_sector", "poblacion", "geometry"],
            geometry="geometry",
            crs="EPSG:3116",
        )
        manzanas = _make_manzanas()

        resultado = disaggregate_simple(
            source=sectores_vacios,
            target=manzanas,
            extensive_vars=["poblacion"],
            intensive_vars=[],
        )

        # El resultado debe tener el mismo número de filas que el target
        assert len(resultado) == len(manzanas), (
            "El resultado debe preservar el número de manzanas del target."
        )

        # La columna disagregada debe existir y ser NaN (sin fuente que interpolar)
        assert "poblacion" in resultado.columns, (
            "La columna 'poblacion' debe existir aunque la fuente esté vacía."
        )
        assert resultado["poblacion"].isna().all(), (
            "Con fuente vacía, todos los valores de 'poblacion' deben ser NaN."
        )
