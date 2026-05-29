"""
Indicadores de Seguridad (Delitos) — Dimensión Seguridad.

Metodología MBHT: Kernel Density Estimation (KDE) con scipy.stats.gaussian_kde
sobre coordenadas proyectadas (EPSG:3116 MAGNA-SIRGAS Colombia Bogotá).
El KDE se evalúa en el centroide de cada manzana.

Categorías de eventos (columna 'categoria' del GeoDataFrame de puntos):
    - 'grave_persona'   : homicidios, violaciones, lesiones graves, tráfico drogas, armas
    - 'grave_propiedad' : robo vehículos, robo con violencia, robo habitado
    - 'leve_persona'    : amenazas, riñas, VIF, lesiones leves, ebriedad
    - 'leve_propiedad'  : hurtos, robo desde vehículos, robo no habitado

Convención invert=True: más delitos → KDE alto → valor alto → normalización invierte → score bajo.

Referencias:
    - MBHT (Metodología de Bienestar Humano Territorial), MINVU Chile, 2022.
    - Silverman, B.W. (1986). Density Estimation for Statistics and Data Analysis.
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.stats import gaussian_kde

from src.indicators.base import Indicator


# ---------------------------------------------------------------------------
# Helper function
# ---------------------------------------------------------------------------

def calcular_kde_puntos(
    puntos: gpd.GeoDataFrame,
    manzanas: gpd.GeoDataFrame,
    bandwidth_m: int = 500,
) -> pd.Series:
    """
    Aplica KDE sobre un conjunto de puntos de delitos y lo evalúa en el centroide
    de cada manzana. Retorna una Series indexada por 'cod_manzana'.

    El cálculo se realiza en EPSG:3116 (MAGNA-SIRGAS / Colombia Bogotá) para
    garantizar que el bandwidth esté en metros reales.

    Fallback: si no hay puntos (municipio rural sin datos o capa vacía),
    retorna Series de 1.0 para todas las manzanas (seguridad máxima),
    de modo que el indicador no penalice áreas sin registros.

    Args:
        puntos:       GeoDataFrame de eventos con geometría de puntos. Puede estar
                      en cualquier CRS compatible; se reproyecta internamente a 3116.
        manzanas:     GeoDataFrame de manzanas con columna 'cod_manzana' como ID único.
                      Puede estar en cualquier CRS compatible.
        bandwidth_m:  Ancho de banda del kernel en metros (default 500 m, escala MBHT).

    Returns:
        pd.Series indexada por 'cod_manzana' con la densidad KDE cruda en cada centroide.
        Valores entre 0 y ~inf (densidad de probabilidad escalada por número de puntos).
    """
    cod_manzana = manzanas["cod_manzana"]

    # --- Fallback: sin eventos ---
    if puntos is None or len(puntos) == 0:
        warnings.warn(
            "calcular_kde_puntos: no hay eventos en la capa. "
            "Retornando seguridad máxima (1.0) para todas las manzanas.",
            UserWarning,
            stacklevel=2,
        )
        return pd.Series(1.0, index=cod_manzana, name="kde_density")

    # --- Proyectar todo a EPSG:3116 para trabajar en metros ---
    try:
        puntos_proj = puntos.to_crs("EPSG:3116")
    except Exception as exc:
        warnings.warn(
            f"calcular_kde_puntos: no se pudo reproyectar puntos a EPSG:3116 ({exc}). "
            "Retornando seguridad máxima (1.0).",
            UserWarning,
            stacklevel=2,
        )
        return pd.Series(1.0, index=cod_manzana, name="kde_density")

    try:
        manzanas_proj = manzanas.to_crs("EPSG:3116")
    except Exception as exc:
        warnings.warn(
            f"calcular_kde_puntos: no se pudo reproyectar manzanas a EPSG:3116 ({exc}). "
            "Retornando seguridad máxima (1.0).",
            UserWarning,
            stacklevel=2,
        )
        return pd.Series(1.0, index=cod_manzana, name="kde_density")

    # --- Extraer coordenadas de eventos ---
    coords_x = puntos_proj.geometry.x.values
    coords_y = puntos_proj.geometry.y.values

    # Eliminar NaN/Inf que romperían el KDE
    mask_valid = np.isfinite(coords_x) & np.isfinite(coords_y)
    coords_x = coords_x[mask_valid]
    coords_y = coords_y[mask_valid]

    if len(coords_x) < 2:
        # Con un solo punto el KDE no es significativo
        warnings.warn(
            f"calcular_kde_puntos: solo {len(coords_x)} evento(s) válido(s). "
            "Retornando seguridad máxima (1.0).",
            UserWarning,
            stacklevel=2,
        )
        return pd.Series(1.0, index=cod_manzana, name="kde_density")

    # --- Construir KDE con bandwidth en metros ---
    # scipy.stats.gaussian_kde usa el factor de Scott por defecto.
    # Para imponer bandwidth_m en metros, calculamos el factor de escala:
    #   bw_factor = bandwidth_m / std(datos)
    # y lo pasamos como bw_method al KDE.
    std_x = np.std(coords_x)
    std_y = np.std(coords_y)
    std_mean = (std_x + std_y) / 2.0

    if std_mean < 1e-3:
        # Todos los puntos están prácticamente en el mismo lugar
        warnings.warn(
            "calcular_kde_puntos: varianza de coordenadas casi nula. "
            "Usando bandwidth mínimo de 100 m para evitar singularidad.",
            UserWarning,
            stacklevel=2,
        )
        std_mean = max(std_mean, 100.0)

    bw_factor = bandwidth_m / std_mean

    try:
        kde = gaussian_kde(
            dataset=np.vstack([coords_x, coords_y]),
            bw_method=bw_factor,
        )
    except np.linalg.LinAlgError as exc:
        warnings.warn(
            f"calcular_kde_puntos: KDE falló ({exc}). "
            "Retornando seguridad máxima (1.0).",
            UserWarning,
            stacklevel=2,
        )
        return pd.Series(1.0, index=cod_manzana, name="kde_density")

    # --- Evaluar KDE en centroides de manzanas ---
    centroides = manzanas_proj.geometry.centroid
    cx = centroides.x.values
    cy = centroides.y.values

    eval_points = np.vstack([cx, cy])
    densidades = kde.evaluate(eval_points)

    # Escalar por número de eventos para que la magnitud refleje intensidad absoluta
    densidades = densidades * len(coords_x)

    result = pd.Series(densidades, index=cod_manzana, name="kde_density")
    return result


# ---------------------------------------------------------------------------
# Indicadores concretos
# ---------------------------------------------------------------------------

class _IndicadorDelitosBase(Indicator):
    """
    Clase base interna para indicadores de delitos.
    No instanciar directamente; usar las subclases específicas.
    """

    name: str = ""
    dimension: str = "seguridad"
    unit: str = "densidad KDE (eventos / m²)"
    invert: bool = True          # más delitos = KDE alto = peor → invert=True

    #: Valor de 'categoria' que filtra este indicador. Definido en cada subclase.
    _categoria: str = ""

    def __init__(
        self,
        manzanas: gpd.GeoDataFrame,
        eventos: gpd.GeoDataFrame,
        bandwidth_m: int = 500,
    ):
        """
        Args:
            manzanas:    GeoDataFrame de manzanas con columna 'cod_manzana'.
            eventos:     GeoDataFrame de puntos de delitos con columna 'categoria'.
                         Categorías válidas: 'grave_persona', 'grave_propiedad',
                         'leve_persona', 'leve_propiedad'.
            bandwidth_m: Ancho de banda del kernel en metros (default 500 m, escala MBHT).
                         Valores mayores → suavizado más amplio; menores → más localizado.
        """
        super().__init__(manzanas)
        self.eventos = eventos
        self.bandwidth_m = bandwidth_m

    def calculate(self) -> pd.Series:
        """
        Filtra eventos por la categoría de esta subclase y aplica KDE sobre
        los puntos resultantes, evaluado en el centroide de cada manzana.

        Returns:
            pd.Series indexada por 'cod_manzana' con la densidad KDE cruda.
            Si no hay eventos de la categoría, retorna 1.0 para todas las manzanas
            (seguridad máxima — no se penaliza ausencia de datos).
        """
        # --- Validar que 'categoria' existe ---
        if self.eventos is None or len(self.eventos) == 0:
            warnings.warn(
                f"{self.__class__.__name__}.calculate: GeoDataFrame de eventos vacío. "
                "Retornando seguridad máxima (1.0).",
                UserWarning,
                stacklevel=2,
            )
            return pd.Series(1.0, index=self.manzanas["cod_manzana"], name=self.name)

        if "categoria" not in self.eventos.columns:
            raise ValueError(
                f"{self.__class__.__name__}: el GeoDataFrame de eventos debe tener "
                "columna 'categoria' con valores: 'grave_persona', 'grave_propiedad', "
                "'leve_persona', 'leve_propiedad'."
            )

        # --- Filtrar por categoría ---
        puntos_categoria = self.eventos[self.eventos["categoria"] == self._categoria].copy()

        if len(puntos_categoria) == 0:
            warnings.warn(
                f"{self.__class__.__name__}.calculate: sin eventos de categoría "
                f"'{self._categoria}'. Retornando seguridad máxima (1.0).",
                UserWarning,
                stacklevel=2,
            )
            return pd.Series(1.0, index=self.manzanas["cod_manzana"], name=self.name)

        # --- Calcular KDE ---
        densidades = calcular_kde_puntos(
            puntos=puntos_categoria,
            manzanas=self.manzanas,
            bandwidth_m=self.bandwidth_m,
        )

        return densidades.rename(self.name)


class IndicadorDelitosGravesPersonas(_IndicadorDelitosBase):
    """
    IGPE — Indicador de Delitos Graves contra las Personas.

    Categoría: 'grave_persona' (homicidios, violaciones, lesiones graves,
    tráfico de drogas, porte ilegal de armas).

    Metodología: KDE con bandwidth 500 m (configurable) sobre coordenadas
    proyectadas EPSG:3116. Valor alto = mayor densidad de delitos = peor situación
    (invert=True en normalización).

    Interpretación del score normalizado:
        0.0 → zona con mayor concentración de delitos graves contra personas
        1.0 → zona con menor concentración (o sin eventos registrados)
    """

    name = "IGPE"
    _categoria = "grave_persona"


class IndicadorDelitosGravesPropiedad(_IndicadorDelitosBase):
    """
    IGPR — Indicador de Delitos Graves contra la Propiedad.

    Categoría: 'grave_propiedad' (robo de vehículos, robo con violencia,
    robo a residencia habitada).

    Metodología y convención de invert idénticas a IGPE.

    Interpretación del score normalizado:
        0.0 → zona con mayor concentración de delitos graves contra la propiedad
        1.0 → zona con menor concentración (o sin eventos registrados)
    """

    name = "IGPR"
    _categoria = "grave_propiedad"


class IndicadorDelitosLevesPersonas(_IndicadorDelitosBase):
    """
    ILPE — Indicador de Delitos Leves contra las Personas.

    Categoría: 'leve_persona' (amenazas, riñas, violencia intrafamiliar,
    lesiones leves, ebriedad en vía pública).

    Metodología y convención de invert idénticas a IGPE.

    Interpretación del score normalizado:
        0.0 → zona con mayor concentración de delitos leves contra personas
        1.0 → zona con menor concentración (o sin eventos registrados)
    """

    name = "ILPE"
    _categoria = "leve_persona"


class IndicadorDelitosLevesPropiedad(_IndicadorDelitosBase):
    """
    ILPR — Indicador de Delitos Leves contra la Propiedad.

    Categoría: 'leve_propiedad' (hurtos, robo desde vehículos,
    robo a residencia no habitada).

    Metodología y convención de invert idénticas a IGPE.

    Interpretación del score normalizado:
        0.0 → zona con mayor concentración de delitos leves contra la propiedad
        1.0 → zona con menor concentración (o sin eventos registrados)
    """

    name = "ILPR"
    _categoria = "leve_propiedad"
