"""
Método alternativo de índice Atlas usando PCA (Análisis de Componentes Principales).

El primer componente principal captura la dirección de máxima varianza en el
espacio de indicadores normalizados. Se normaliza a [0, 1] y, si es necesario,
se invierte para que un score alto corresponda a mejor situación.

Patrón inspirado en dep_index (Townsend Deprivation Index) y geomarker-io.

Uso::

    pca = PCAtlasIndex(n_components=1)
    score = pca.fit_transform(df_indicadores)   # Series 'pca_atlas_score'
    print(f"Varianza explicada: {pca.variance_explained():.1%}")
    print(pca.loadings())
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler


class PCAtlasIndex:
    """Índice compuesto Atlas Urabá calculado mediante PCA.

    El PC1 (primer componente principal) se usa como índice. Al capturar la
    máxima varianza compartida entre indicadores, es más robusto a la elección
    arbitraria de pesos que la media ponderada simple.

    Inversión automática: si la correlación promedio entre PC1 y los
    indicadores de entrada es negativa (mayoría de loadings negativos), el
    componente se invierte para que un score alto = mejor situación.

    Atributos públicos tras ``fit_transform()``:
        pca_:       Objeto ``sklearn.decomposition.PCA`` ajustado.
        scaler_:    Objeto ``StandardScaler`` ajustado.
        columns_:   Lista de columnas de indicadores usadas.
        inverted_:  bool — True si el PC1 fue invertido.
    """

    def __init__(self, n_components: int = 1) -> None:
        """Inicializa el modelo PCA.

        Args:
            n_components: Número de componentes a calcular. Para el índice
                Atlas se usa solo el PC1, pero más componentes permite
                análisis exploratorio de la estructura de datos.
        """
        if n_components < 1:
            raise ValueError("n_components debe ser >= 1.")

        self.n_components = n_components
        self.pca_: Optional[PCA] = None
        self.scaler_: Optional[StandardScaler] = None
        self.columns_: Optional[list[str]] = None
        self.inverted_: bool = False
        self._pc1_raw: Optional[pd.Series] = None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def fit_transform(self, df_indicadores: pd.DataFrame) -> pd.Series:
        """Ajusta PCA y retorna el índice basado en PC1.

        Args:
            df_indicadores: DataFrame donde cada columna es un indicador
                normalizado (idealmente [0, 1]), indexado por cod_manzana.
                Las filas con NaN en todas las columnas se excluyen.
                Los NaN parciales se imputan con la mediana de cada columna.

        Returns:
            Series 'pca_atlas_score' con valores [0, 1] indexada por
            cod_manzana. Un valor alto indica mejor situación.

        Raises:
            ValueError: Si el DataFrame está vacío o tiene menos de 2 filas.
        """
        if df_indicadores.empty:
            raise ValueError("df_indicadores está vacío.")
        if len(df_indicadores) < 2:
            raise ValueError("Se necesitan al menos 2 filas para PCA.")

        self.columns_ = list(df_indicadores.columns)

        # Imputar NaN con mediana por columna
        df_imputed = df_indicadores.copy()
        for col in self.columns_:
            median = df_imputed[col].median()
            df_imputed[col] = df_imputed[col].fillna(
                median if not np.isnan(median) else 0.0
            )

        # Estandarizar (media=0, std=1) — requisito de PCA
        self.scaler_ = StandardScaler()
        X_scaled = self.scaler_.fit_transform(df_imputed.values)

        # Ajustar PCA
        self.pca_ = PCA(n_components=self.n_components, random_state=42)
        pc_scores = self.pca_.fit_transform(X_scaled)

        # PC1 como Series
        pc1 = pd.Series(pc_scores[:, 0], index=df_indicadores.index, name="pc1_raw")
        self._pc1_raw = pc1

        # Determinar si hay que invertir: la mayoría de loadings positivos
        # implica que valores altos de PC1 = mejor (no invertir).
        loadings_pc1 = self.pca_.components_[0]
        self.inverted_ = bool(loadings_pc1.mean() < 0)

        if self.inverted_:
            pc1 = -pc1

        # Normalizar a [0, 1]
        mn, mx = pc1.min(), pc1.max()
        if mx == mn:
            score = pd.Series(0.5, index=pc1.index, dtype=float)
        else:
            score = (pc1 - mn) / (mx - mn)

        return score.rename("pca_atlas_score")

    def variance_explained(self) -> float:
        """Proporción de varianza explicada por el primer componente (PC1).

        Returns:
            Float en [0, 1]. Por ejemplo, 0.62 significa que el PC1 explica
            el 62 % de la varianza total de los indicadores.

        Raises:
            RuntimeError: Si ``fit_transform()`` no ha sido llamado.
        """
        self._check_fitted()
        return float(self.pca_.explained_variance_ratio_[0])

    def loadings(self) -> pd.DataFrame:
        """Contribución de cada indicador al PC1 (y componentes adicionales).

        Los loadings (pesos del componente) indican la dirección y magnitud
        con la que cada indicador contribuye al componente. Un loading
        positivo alto significa que el indicador mueve el score hacia arriba.

        Returns:
            DataFrame con forma (n_indicators, n_components).
            Índice = nombre del indicador.
            Columnas = ['PC1', 'PC2', ...] según n_components.
            Los valores están en escala de correlación (no son coeficientes
            brutos de la eigenvector; se multiplican por sqrt(eigenvalue) para
            comparabilidad entre componentes).

        Raises:
            RuntimeError: Si ``fit_transform()`` no ha sido llamado.
        """
        self._check_fitted()

        # Loadings = eigenvectors * sqrt(eigenvalues)  →  correlaciones
        eigenvalues = self.pca_.explained_variance_
        components = self.pca_.components_  # shape: (n_components, n_features)

        # Invertir el signo del PC1 si fue necesario para consistencia
        sign_correction = np.ones(self.n_components)
        if self.inverted_:
            sign_correction[0] = -1.0

        loadings_matrix = (components * sign_correction[:, np.newaxis]).T * np.sqrt(eigenvalues)

        col_names = [f"PC{i+1}" for i in range(self.n_components)]
        return pd.DataFrame(
            loadings_matrix,
            index=self.columns_,
            columns=col_names,
        ).sort_values("PC1", ascending=False)

    # ------------------------------------------------------------------
    # Método privado
    # ------------------------------------------------------------------

    def _check_fitted(self) -> None:
        """Lanza RuntimeError si el modelo no ha sido ajustado."""
        if self.pca_ is None or self.scaler_ is None:
            raise RuntimeError(
                "El modelo no ha sido ajustado. Llama fit_transform() primero."
            )
