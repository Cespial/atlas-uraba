"""
Tests para src/composite/spatial_clusters.py

Verifica que el cálculo de Zonas Atlas (LISA) cumple:
- Las categorías asignadas son siempre válidas {'HH','LL','HL','LH','NS'}.
- El índice de Moran global está en el rango teórico (-1, 1).
- Un cluster perfecto clasifica correctamente (HH para alta puntuación,
  LL para baja, o NS si no alcanza significancia estadística).
"""
from __future__ import annotations

import numpy as np
import pytest
import geopandas as gpd
from shapely.geometry import box

from src.composite.spatial_clusters import calcular_zonas_atlas


# ---------------------------------------------------------------------------
# Fixture: manzanas sintéticas en grid regular
# ---------------------------------------------------------------------------

def _make_grid(
    n_filas: int = 3,
    n_cols: int = 3,
    lado: float = 100.0,
    scores: list[float] | None = None,
) -> gpd.GeoDataFrame:
    """
    Crea un GeoDataFrame de polígonos cuadrados en grid regular (EPSG:3116).

    Args:
        n_filas: Número de filas del grid.
        n_cols: Número de columnas del grid.
        lado: Lado de cada cuadrado en metros.
        scores: Lista de atlas_score para cada celda (longitud n_filas*n_cols).
                Si None, asigna valores aleatorios en [0, 1].
    """
    n = n_filas * n_cols
    if scores is None:
        rng = np.random.default_rng(42)
        scores = rng.random(n).tolist()

    assert len(scores) == n, f"scores debe tener longitud {n}, tiene {len(scores)}."

    geometrias = []
    ids = []
    for fila in range(n_filas):
        for col in range(n_cols):
            x0 = col * lado
            y0 = fila * lado
            geometrias.append(box(x0, y0, x0 + lado, y0 + lado))
            ids.append(f"MZ_{fila}_{col}")

    return gpd.GeoDataFrame(
        {
            "cod_manzana": ids,
            "atlas_score": scores,
        },
        geometry=geometrias,
        crs="EPSG:3116",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

ZONAS_VALIDAS = {"HH", "LL", "HL", "LH", "NS"}


class TestZonasAtlas:
    """Grupo de tests para calcular_zonas_atlas."""

    def test_zonas_atlas_categorias_validas(self):
        """
        Las zonas asignadas deben pertenecer al conjunto {'HH','LL','HL','LH','NS'}.
        """
        manzanas = _make_grid(n_filas=3, n_cols=3)
        resultado = calcular_zonas_atlas(manzanas, col_indice="atlas_score")

        assert "zona_atlas" in resultado.columns, "Debe existir la columna 'zona_atlas'."

        categorias_resultado = set(resultado["zona_atlas"].unique())
        invalidas = categorias_resultado - ZONAS_VALIDAS
        assert not invalidas, (
            f"Se encontraron categorías inválidas en zona_atlas: {invalidas}. "
            f"Solo se permiten: {ZONAS_VALIDAS}."
        )

    def test_moran_i_rango(self):
        """
        El índice de Moran global (I) debe estar dentro del rango teórico (-1, 1).

        Nota: en casos extremos teóricos puede superar ligeramente -1,
        pero en datos reales siempre está en (-1, 1).
        """
        # Grid 4x4 con scores variados para un Moran no trivial
        scores = [0.1, 0.9, 0.2, 0.8,
                  0.85, 0.15, 0.75, 0.25,
                  0.3, 0.7, 0.4, 0.6,
                  0.65, 0.35, 0.55, 0.45]
        manzanas = _make_grid(n_filas=4, n_cols=4, scores=scores)
        resultado = calcular_zonas_atlas(manzanas, col_indice="atlas_score")

        assert "moran_i" in resultado.columns, "Debe existir la columna 'moran_i'."
        moran_i = resultado["moran_i"].iloc[0]

        assert -1.0 < moran_i < 1.0, (
            f"El índice de Moran I = {moran_i:.4f} está fuera del rango teórico (-1, 1)."
        )

    def test_cluster_perfecto(self):
        """
        En un cluster espacial perfecto:
        - Mitad superior del grid (fila 1): atlas_score = 1.0
        - Mitad inferior del grid (fila 0): atlas_score = 0.0

        Las manzanas con score = 1.0 deben clasificarse como HH o NS.
        Las manzanas con score = 0.0 deben clasificarse como LL o NS.

        'NS' es aceptable si la muestra es pequeña y no hay significancia estadística.
        No deben aparecer zonas cruzadas (HL o LH) para los clusters homogéneos.
        """
        # Grid 2x3: fila 0 = score 0.0 (cluster bajo), fila 1 = score 1.0 (cluster alto)
        scores_perfectos = [
            0.0, 0.0, 0.0,  # fila 0 — bajo
            1.0, 1.0, 1.0,  # fila 1 — alto
        ]
        manzanas = _make_grid(n_filas=2, n_cols=3, scores=scores_perfectos)
        resultado = calcular_zonas_atlas(
            manzanas,
            col_indice="atlas_score",
            significance=0.1,  # umbral más permisivo para muestra pequeña
        )

        # Manzanas con score alto
        mask_alto = resultado["atlas_score"] == 1.0
        zonas_alto = set(resultado.loc[mask_alto, "zona_atlas"].unique())

        # Manzanas con score bajo
        mask_bajo = resultado["atlas_score"] == 0.0
        zonas_bajo = set(resultado.loc[mask_bajo, "zona_atlas"].unique())

        zonas_permitidas_alto = {"HH", "NS"}
        zonas_permitidas_bajo = {"LL", "NS"}

        assert zonas_alto <= zonas_permitidas_alto, (
            f"Las manzanas de score=1.0 clasificaron como {zonas_alto}, "
            f"se esperaba un subconjunto de {zonas_permitidas_alto}."
        )
        assert zonas_bajo <= zonas_permitidas_bajo, (
            f"Las manzanas de score=0.0 clasificaron como {zonas_bajo}, "
            f"se esperaba un subconjunto de {zonas_permitidas_bajo}."
        )

    def test_columnas_requeridas_presentes(self):
        """
        El resultado siempre debe contener moran_i, lisa_q, lisa_p y zona_atlas.
        """
        manzanas = _make_grid(n_filas=3, n_cols=3)
        resultado = calcular_zonas_atlas(manzanas)

        for col in ("moran_i", "lisa_q", "lisa_p", "zona_atlas"):
            assert col in resultado.columns, (
                f"La columna requerida '{col}' no está en el resultado."
            )

    def test_crs_preservado(self):
        """
        El CRS del GeoDataFrame de entrada debe preservarse en el resultado.
        """
        manzanas = _make_grid(n_filas=3, n_cols=3)
        crs_original = manzanas.crs
        resultado = calcular_zonas_atlas(manzanas)

        assert resultado.crs == crs_original, (
            f"CRS del resultado {resultado.crs} difiere del original {crs_original}."
        )
