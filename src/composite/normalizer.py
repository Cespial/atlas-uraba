"""
Funciones de normalización para el pipeline Atlas Urabá.

Patrón: winsorize → normalize_minmax → normalize_all_indicators.
Diseñado para integrarse con AtlasAggregator y PCAtlasIndex.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats.mstats import winsorize as _scipy_winsorize


def winsorize(
    series: pd.Series,
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.Series:
    """Winsoriza una Serie para mitigar outliers antes de normalizar.

    Recorta los valores por debajo del percentil ``lower`` y por encima del
    percentil ``upper``, reemplazándolos por el valor del percentil límite.

    Args:
        series: Serie numérica indexada por cod_manzana.
        lower: Percentil inferior de recorte (0–1). Default 0.01 (1 %).
        upper: Percentil superior de recorte (0–1). Default 0.99 (99 %).

    Returns:
        Serie winsorizada con el mismo índice. Los NaN se conservan sin tocar.
    """
    if series.empty:
        return series.copy()

    mask_notna = series.notna()
    result = series.copy()

    if mask_notna.sum() < 2:
        # No hay suficientes valores para winsorizar
        return result

    vals = series[mask_notna].values.astype(float)
    # scipy.stats.mstats.winsorize usa limits=(lower_frac, upper_frac)
    winsorized = _scipy_winsorize(vals, limits=(lower, 1.0 - upper))
    result[mask_notna] = np.array(winsorized)
    return result


def normalize_minmax(
    series: pd.Series,
    invert: bool = False,
) -> pd.Series:
    """Normaliza una Serie a rango [0, 1] usando min-max scaling.

    Manejo de casos especiales:
    - NaN: se imputan con la mediana de la serie antes de escalar.
    - Serie constante (min == max): se retorna 0.5 para todas las entradas.

    Args:
        series: Serie numérica indexada por cod_manzana.
        invert: Si True, invierte la normalización (1 = valor mínimo = mejor).
                Útil para indicadores donde un valor alto implica peor condición.

    Returns:
        Serie normalizada [0, 1] con el mismo índice y nombre.
    """
    if series.empty:
        return series.copy()

    # Imputar NaN con mediana
    median = series.median()
    filled = series.fillna(median if not np.isnan(median) else 0.0)

    mn = filled.min()
    mx = filled.max()

    if mx == mn:
        return pd.Series(0.5, index=series.index, name=series.name, dtype=float)

    normalized = (filled - mn) / (mx - mn)

    if invert:
        normalized = 1.0 - normalized

    return normalized.rename(series.name)


def normalize_all_indicators(
    df: pd.DataFrame,
    invert_cols: list[str],
) -> pd.DataFrame:
    """Normaliza todas las columnas de un DataFrame de indicadores.

    Aplica ``normalize_minmax`` columna a columna. Las columnas en
    ``invert_cols`` se normalizan con ``invert=True``.

    Args:
        df: DataFrame donde cada columna es un indicador raw, indexado por
            cod_manzana.
        invert_cols: Lista de nombres de columnas que deben invertirse porque
            un valor alto representa peor situación (p. ej. IVI, IGPE).

    Returns:
        DataFrame con las mismas columnas y dimensiones, valores en [0, 1].

    Raises:
        ValueError: Si algún elemento de ``invert_cols`` no existe en ``df``.
    """
    unknown = [c for c in invert_cols if c not in df.columns]
    if unknown:
        raise ValueError(
            f"Columnas en invert_cols no encontradas en df: {unknown}. "
            f"Columnas disponibles: {list(df.columns)}"
        )

    result = pd.DataFrame(index=df.index)

    for col in df.columns:
        should_invert = col in invert_cols
        result[col] = normalize_minmax(df[col], invert=should_invert)

    return result
