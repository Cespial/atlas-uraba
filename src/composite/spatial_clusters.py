"""
Clustering espacial para generar "Zonas Atlas".

Usa autocorrelación espacial local (LISA - Local Indicators of Spatial Association)
para agrupar manzanas vecinas con niveles similares de bienestar.

Equivalente a las "Zonas BHT" de la MBHT chilena.
Referencia: PySAL-esda — https://pysal.org/esda/
"""
import geopandas as gpd
import pandas as pd
import numpy as np
from libpysal.weights import Queen, Rook
from esda.moran import Moran, Moran_Local


def calcular_zonas_atlas(
    manzanas: gpd.GeoDataFrame,
    col_indice: str = "atlas_score",
    metodo: str = "queen",
    significance: float = 0.05,
) -> gpd.GeoDataFrame:
    """
    Calcula el índice de Moran global y LISA local por manzana.
    Clasifica cada manzana en una de las 4 zonas de bienestar:

        HH — Alto-Alto: manzana de alto bienestar rodeada de alto bienestar (zona próspera)
        LL — Bajo-Bajo: manzana de bajo bienestar rodeada de bajo bienestar (zona crítica)
        HL — Alto-Bajo: outlier positivo (isla de bienestar)
        LH — Bajo-Alto: outlier negativo (rezago en zona próspera)
        NS — No significativo

    Args:
        manzanas: GeoDataFrame con columna del índice compuesto.
        col_indice: Nombre de la columna con el puntaje Atlas (0-1).
        metodo: 'queen' o 'rook' para construir la matriz de pesos espaciales.
        significance: Nivel de significancia para filtrar LISA (default 0.05).

    Returns:
        GeoDataFrame con columnas añadidas: moran_i, lisa_q, zona_atlas.
    """
    manzanas_proj = manzanas.to_crs("EPSG:3116").copy()
    y = manzanas_proj[col_indice].fillna(manzanas_proj[col_indice].mean()).values

    W = Queen.from_dataframe(manzanas_proj) if metodo == "queen" else Rook.from_dataframe(manzanas_proj)
    W.transform = "r"  # estandarización por fila

    # Moran global
    moran = Moran(y, W)

    # LISA local
    lisa = Moran_Local(y, W)

    quadrant_map = {1: "HH", 2: "LH", 3: "LL", 4: "HL"}
    manzanas_proj["moran_i"] = round(moran.I, 4)
    manzanas_proj["lisa_q"] = lisa.q
    manzanas_proj["lisa_p"] = lisa.p_sim
    manzanas_proj["zona_atlas"] = np.where(
        lisa.p_sim < significance,
        [quadrant_map.get(q, "NS") for q in lisa.q],
        "NS",
    )

    return manzanas_proj.to_crs(manzanas.crs)
