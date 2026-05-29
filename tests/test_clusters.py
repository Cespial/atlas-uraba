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
        En un cluster espacial con dos bloques bien definidos, las celdas
        del interior de cada bloque (lejos del borde) deben clasificarse como
        HH (alto-alto) o LL (bajo-bajo). Las celdas de borde pueden ser HL/LH
        por el efecto de vecindad entre los dos bloques.

        Se usa un grid 4x4 (2 filas bajas + 2 filas altas) para que las celdas
        de la fila 0 y la fila 3 estén aisladas del borde inter-bloque.
        """
        # Grid 4x4: filas 0-1 = score 0.0, filas 2-3 = score 1.0
        scores_perfectos = [
            0.0, 0.0, 0.0, 0.0,   # fila 0 — bajo (interior)
            0.0, 0.0, 0.0, 0.0,   # fila 1 — bajo (borde)
            1.0, 1.0, 1.0, 1.0,   # fila 2 — alto (borde)
            1.0, 1.0, 1.0, 1.0,   # fila 3 — alto (interior)
        ]
        manzanas = _make_grid(n_filas=4, n_cols=4, scores=scores_perfectos)
        resultado = calcular_zonas_atlas(
            manzanas,
            col_indice="atlas_score",
            significance=0.1,
        )

        # Las celdas interiores (fila 0 y fila 3) deben ser LL/HH/NS
        # Fila 0: índices 0-3 en el GeoDataFrame (y=0..100)
        celdas_interior_bajo = resultado[resultado["cod_manzana"].str.startswith("MZ_0_")]
        zonas_interior_bajo = set(celdas_interior_bajo["zona_atlas"].unique())

        # Fila 3: índices 12-15
        celdas_interior_alto = resultado[resultado["cod_manzana"].str.startswith("MZ_3_")]
        zonas_interior_alto = set(celdas_interior_alto["zona_atlas"].unique())

        assert zonas_interior_bajo <= {"LL", "NS"}, (
            f"Fila interior baja clasificó como {zonas_interior_bajo}, "
            f"esperado subconjunto de {{'LL','NS'}}."
        )
        assert zonas_interior_alto <= {"HH", "NS"}, (
            f"Fila interior alta clasificó como {zonas_interior_alto}, "
            f"esperado subconjunto de {{'HH','NS'}}."
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
