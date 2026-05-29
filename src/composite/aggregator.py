"""
Motor de agregación del índice Atlas Urabá.

Pipeline:
  1. Winsorización de outliers (percentiles 1–99)
  2. Normalización min-max 0-1 (con inversión donde corresponde)
  3. Promedio simple de indicadores dentro de cada dimensión
  4. Ponderación de dimensiones con DIMENSION_WEIGHTS
  5. Normalización final del atlas_score a [0, 1]
  6. Retorno de GeoDataFrame con scores por dimensión y score global

Uso básico::

    agg = AtlasAggregator(manzanas_gdf)
    agg.add_indicator("IAV", iav_series)
    agg.add_indicator("IVI", ivi_series)
    result_gdf = agg.compute()
    print(agg.summary())
"""
from __future__ import annotations

import warnings
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd

from src.composite.normalizer import normalize_minmax, winsorize

# ---------------------------------------------------------------------------
# Configuración de pesos de dimensión
# ---------------------------------------------------------------------------
# Importar desde src.config cuando esté disponible; si no, usar defaults.
try:
    from src.config import DIMENSION_WEIGHTS  # type: ignore[import]
except ImportError:
    DIMENSION_WEIGHTS: dict[str, float] = {
        "accesibilidad": 0.35,
        "ambiental": 0.20,
        "socioeconomico": 0.30,
        "seguridad": 0.15,
    }

# ---------------------------------------------------------------------------
# Mapeo indicador → dimensión
# ---------------------------------------------------------------------------
INDICATOR_TO_DIMENSION: dict[str, str] = {
    # Accesibilidad
    "IAV": "accesibilidad",
    "IDEP": "accesibilidad",
    "ICUL": "accesibilidad",
    "ISAL": "accesibilidad",
    "ISER": "accesibilidad",
    "ISE": "accesibilidad",
    # Ambiental
    "ICV": "ambiental",
    "IATA": "ambiental",
    # Socioeconómico
    "IVI": "socioeconomico",
    "ISV": "socioeconomico",
    "IEJ": "socioeconomico",
    "IRH": "socioeconomico",
    "IEM": "socioeconomico",
    "IPJ": "socioeconomico",
    # Seguridad
    "IGPE": "seguridad",
    "IGPR": "seguridad",
    "ILPE": "seguridad",
    "ILPR": "seguridad",
}

# Indicadores cuyo valor alto = peor situación (se invierte en normalización)
INVERT_INDICATORS: list[str] = [
    "IVI",   # índice de vulnerabilidad
    "ISV",   # sin vivienda / precariedad
    "IRH",   # riesgo hídrico
    "IATA",  # amenaza ambiental
    "IGPE",  # gravedad de peligro estructural
    "IGPR",  # gravedad de peligro por riesgo
    "ILPE",  # lesividad por peligro estructural
    "ILPR",  # lesividad por peligro de riesgo
]

_KNOWN_DIMENSIONS: tuple[str, ...] = (
    "accesibilidad",
    "ambiental",
    "socioeconomico",
    "seguridad",
)


class AtlasAggregator:
    """Agrega indicadores normalizados en el índice compuesto Atlas Urabá.

    Atributos públicos tras ``compute()``:
        result_gdf:  GeoDataFrame con geometrías y scores.
        df_raw:      DataFrame de indicadores raw antes de normalización.
        df_norm:     DataFrame de indicadores normalizados.
        df_dim:      DataFrame de scores por dimensión (pre-ponderación).
    """

    def __init__(
        self,
        manzanas: gpd.GeoDataFrame,
        dimension_weights: Optional[dict[str, float]] = None,
    ) -> None:
        """Inicializa el agregador.

        Args:
            manzanas: GeoDataFrame de manzanas con columna 'cod_manzana' y
                      geometría. Se usa como base para el resultado final.
            dimension_weights: Diccionario {dimensión: peso}. Los pesos deben
                sumar 1.0. Si None, se usa DIMENSION_WEIGHTS de src.config.

        Raises:
            ValueError: Si 'cod_manzana' no está en manzanas.columns.
        """
        if "cod_manzana" not in manzanas.columns:
            raise ValueError("El GeoDataFrame 'manzanas' debe tener columna 'cod_manzana'.")

        self.manzanas = manzanas.set_index("cod_manzana") if manzanas.index.name != "cod_manzana" else manzanas
        self._weights = dimension_weights or DIMENSION_WEIGHTS
        self._validate_weights(self._weights)

        # Almacén interno: {indicador: pd.Series indexada por cod_manzana}
        self._indicators: dict[str, pd.Series] = {}

        # Artefactos intermedios (disponibles tras compute())
        self.df_raw: Optional[pd.DataFrame] = None
        self.df_norm: Optional[pd.DataFrame] = None
        self.df_dim: Optional[pd.DataFrame] = None
        self.result_gdf: Optional[gpd.GeoDataFrame] = None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def add_indicator(self, indicator_name: str, values: pd.Series) -> None:
        """Añade un indicador raw al agregador.

        Args:
            indicator_name: Clave del indicador (p. ej. "IAV", "IVI").
                Debe existir en INDICATOR_TO_DIMENSION o se lanzará advertencia.
            values: Series indexada por cod_manzana con valores numéricos raw.

        Warns:
            UserWarning: Si el nombre del indicador no está mapeado a ninguna
                dimensión conocida.
        """
        if indicator_name not in INDICATOR_TO_DIMENSION:
            warnings.warn(
                f"Indicador '{indicator_name}' no está en INDICATOR_TO_DIMENSION. "
                "Será ignorado durante la agregación por dimensión.",
                UserWarning,
                stacklevel=2,
            )
        self._indicators[indicator_name] = values.rename(indicator_name)

    def compute(self) -> gpd.GeoDataFrame:
        """Ejecuta el pipeline completo de agregación.

        Pasos:
            1. Ensambla DataFrame de indicadores raw.
            2. Winsoriza outliers (p1–p99).
            3. Normaliza 0-1 (invierte los que corresponde).
            4. Promedia indicadores dentro de cada dimensión (pesos iguales).
            5. Pondera dimensiones con dimension_weights.
            6. Normaliza atlas_score final a 0-1.
            7. Une con geometrías.

        Returns:
            GeoDataFrame con columnas:
                cod_manzana, geometry,
                score_accesibilidad, score_ambiental,
                score_socioeconomico, score_seguridad,
                atlas_score.

        Raises:
            RuntimeError: Si no se han añadido indicadores.
        """
        if not self._indicators:
            raise RuntimeError("No hay indicadores. Usa add_indicator() antes de compute().")

        # 1. Ensamblar raw
        self.df_raw = pd.DataFrame(self._indicators)

        # 2. Winsorizar columna a columna
        df_wins = self.df_raw.apply(lambda s: winsorize(s, lower=0.01, upper=0.99), axis=0)

        # 3. Normalizar (con inversión)
        df_norm_parts = {}
        for col in df_wins.columns:
            invert = col in INVERT_INDICATORS
            df_norm_parts[col] = normalize_minmax(df_wins[col], invert=invert)
        self.df_norm = pd.DataFrame(df_norm_parts)

        # 4. Promediar dentro de cada dimensión
        dim_scores: dict[str, pd.Series] = {}
        for dim in _KNOWN_DIMENSIONS:
            cols_in_dim = [
                c for c in self.df_norm.columns
                if INDICATOR_TO_DIMENSION.get(c) == dim
            ]
            if not cols_in_dim:
                warnings.warn(
                    f"Dimensión '{dim}' no tiene indicadores cargados. "
                    "Su score será NaN y reducirá el atlas_score.",
                    UserWarning,
                    stacklevel=2,
                )
                dim_scores[f"score_{dim}"] = pd.Series(
                    np.nan, index=self.df_norm.index, name=f"score_{dim}"
                )
            else:
                dim_scores[f"score_{dim}"] = self.df_norm[cols_in_dim].mean(axis=1)

        self.df_dim = pd.DataFrame(dim_scores)

        # 5. Ponderar dimensiones → atlas_score raw
        atlas_raw = pd.Series(0.0, index=self.df_norm.index)
        weight_used = 0.0
        for dim in _KNOWN_DIMENSIONS:
            col = f"score_{dim}"
            w = self._weights.get(dim, 0.0)
            dim_vals = self.df_dim[col]
            if dim_vals.isna().all():
                continue
            # Imputar NaN de la dimensión con la mediana de esa dimensión
            dim_filled = dim_vals.fillna(dim_vals.median())
            atlas_raw += w * dim_filled
            weight_used += w

        if weight_used < 1e-9:
            raise RuntimeError("Los pesos de dimensiones suman cero. Revisa dimension_weights.")

        # Re-escalar si no todos los pesos están activos
        if abs(weight_used - 1.0) > 1e-6:
            atlas_raw = atlas_raw / weight_used

        # 6. Normalizar atlas_score a 0-1
        atlas_score = normalize_minmax(atlas_raw, invert=False).rename("atlas_score")

        # 7. Unir con geometrías
        base = self.manzanas[["geometry"]].copy()
        result = base.join(self.df_dim, how="left").join(atlas_score, how="left")
        result.index.name = "cod_manzana"
        self.result_gdf = result.reset_index()

        return self.result_gdf

    def summary(self) -> pd.DataFrame:
        """Estadísticas descriptivas por dimensión y municipio.

        Requiere que ``compute()`` haya sido ejecutado previamente.

        Returns:
            DataFrame con media, desviación estándar, mínimo, p25, mediana,
            p75 y máximo para cada score de dimensión y atlas_score,
            desagregado por municipio si la columna 'cod_municipio' existe
            en el GeoDataFrame base.

        Raises:
            RuntimeError: Si ``compute()`` no ha sido ejecutado.
        """
        if self.result_gdf is None:
            raise RuntimeError("Ejecuta compute() antes de summary().")

        score_cols = [f"score_{d}" for d in _KNOWN_DIMENSIONS] + ["atlas_score"]
        available = [c for c in score_cols if c in self.result_gdf.columns]

        base_df = self.result_gdf[["cod_manzana"] + available].copy()

        # Intentar añadir municipio desde manzanas original
        manzanas_reset = self.manzanas.reset_index()
        if "cod_municipio" in manzanas_reset.columns:
            mun_map = manzanas_reset.set_index("cod_manzana")["cod_municipio"]
            base_df = base_df.set_index("cod_manzana")
            base_df["cod_municipio"] = mun_map
            base_df = base_df.reset_index()
            group_col = "cod_municipio"
        else:
            group_col = None

        percentiles = [0.25, 0.50, 0.75]

        if group_col:
            stats = (
                base_df.groupby(group_col)[available]
                .agg(["mean", "std", "min", *[f"p{int(p*100)}" for p in percentiles], "max"])
            )
            # pd groupby agg con percentiles requiere approach alternativo
            stats_list = []
            for mun, grp in base_df.groupby(group_col):
                row = {"cod_municipio": mun}
                for col in available:
                    s = grp[col].dropna()
                    row.update({
                        f"{col}_mean": s.mean(),
                        f"{col}_std": s.std(),
                        f"{col}_min": s.min(),
                        f"{col}_p25": s.quantile(0.25),
                        f"{col}_p50": s.quantile(0.50),
                        f"{col}_p75": s.quantile(0.75),
                        f"{col}_max": s.max(),
                        f"{col}_n": s.count(),
                    })
                stats_list.append(row)
            return pd.DataFrame(stats_list).set_index("cod_municipio")
        else:
            stats_list = []
            for col in available:
                s = base_df[col].dropna()
                stats_list.append({
                    "score": col,
                    "mean": s.mean(),
                    "std": s.std(),
                    "min": s.min(),
                    "p25": s.quantile(0.25),
                    "p50": s.quantile(0.50),
                    "p75": s.quantile(0.75),
                    "max": s.max(),
                    "n": s.count(),
                })
            return pd.DataFrame(stats_list).set_index("score")

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_weights(weights: dict[str, float]) -> None:
        """Valida que los pesos de dimensiones sumen ~1.0."""
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            warnings.warn(
                f"Los pesos de dimensiones suman {total:.4f}, no 1.0. "
                "El resultado será re-escalado automáticamente.",
                UserWarning,
                stacklevel=3,
            )
        unknown_dims = set(weights) - set(_KNOWN_DIMENSIONS)
        if unknown_dims:
            warnings.warn(
                f"Dimensiones desconocidas en pesos: {unknown_dims}. "
                f"Dimensiones válidas: {_KNOWN_DIMENSIONS}",
                UserWarning,
                stacklevel=3,
            )
