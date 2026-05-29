"""
Carga del REPS (Registro Especial de Prestadores de Servicios de Salud) de MinSalud.

Fuente:
  - Ministerio de Salud y Protección Social — REPS
  - Descarga: https://www.sispro.gov.co/Pages/Home.aspx  (Sección REPS)
  - Alternativa datos.gov.co: https://www.datos.gov.co/

Columnas clave esperadas en el CSV del REPS:
  nombre_prestador    → Nombre del establecimiento de salud
  codigo_municipio    → Código DIVIPOLA del municipio (puede ser 5 dígitos)
  departamento        → Nombre del departamento (para filtrar Antioquia)
  latitud             → Latitud WGS84 (decimal)
  longitud            → Longitud WGS84 (decimal)
  nivel_atencion      → Nivel de complejidad: '1', '2' o '3'

Niveles de atención:
  1 = Primario  (puestos de salud, centros de salud sin internación)
  2 = Secundario (hospitales con internación, especialidades básicas)
  3 = Terciario  (hospitales de alta complejidad, clínicas especializadas)

Estimación de capacidad en m² (proxy para indicador de accesibilidad):
  Primario:    200 m²
  Secundario:  800 m²
  Terciario: 3 000 m²
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

DIVIPOLA_URABA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]

# Nombres de columna aceptados (REPS cambia encabezados entre versiones)
_ALIAS_NOMBRE    = ["nombre_prestador", "nombre_sede", "nombre_ips", "razon_social"]
_ALIAS_MUNICIPIO = ["codigo_municipio", "cod_municipio", "municipio_codigo", "mpio_cdpmp", "divipola"]
_ALIAS_DEPTO     = ["departamento", "nombre_departamento", "depto"]
_ALIAS_LAT       = ["latitud", "lat", "latitude"]
_ALIAS_LON       = ["longitud", "lon", "lng", "longitude"]
_ALIAS_NIVEL     = ["nivel_atencion", "nivel", "nivel_complejidad"]

# m² estimados por nivel de atención
CAPACIDAD_M2 = {
    "1": 200,
    "2": 800,
    "3": 3000,
}

COLS_REQUERIDAS = {"nombre_prestador", "codigo_municipio", "latitud", "longitud", "nivel_atencion"}


def cargar_reps(path: Path) -> gpd.GeoDataFrame:
    """
    Lee el CSV del REPS, filtra por Antioquia y municipios de Urabá, y geocodifica.

    Estandariza los nombres de columna usando alias conocidos, filtra registros
    sin coordenadas válidas y crea geometrías Point (lon, lat).

    Args:
        path: Ruta al CSV del REPS descargado de MinSalud / datos.gov.co.

    Returns:
        GeoDataFrame con columnas:
            nombre_prestador, codigo_municipio, latitud, longitud,
            nivel_atencion, geometry
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
        AssertionError:    si faltan columnas requeridas tras normalización.
        ValueError:        si no hay registros para Urabá.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[minsal] Archivo REPS no encontrado: {path}\n"
            "Descarga el CSV del REPS desde https://www.sispro.gov.co/"
        )

    print(f"[minsal] Cargando REPS desde {path}...")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    # Normalizar encabezados
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = _renombrar_alias(df, _ALIAS_NOMBRE,    "nombre_prestador")
    df = _renombrar_alias(df, _ALIAS_MUNICIPIO, "codigo_municipio")
    df = _renombrar_alias(df, _ALIAS_DEPTO,     "departamento")
    df = _renombrar_alias(df, _ALIAS_LAT,       "latitud")
    df = _renombrar_alias(df, _ALIAS_LON,       "longitud")
    df = _renombrar_alias(df, _ALIAS_NIVEL,     "nivel_atencion")

    cols_faltantes = COLS_REQUERIDAS - set(df.columns)
    assert not cols_faltantes, (
        f"[minsal] Faltan columnas en el CSV: {cols_faltantes}. "
        f"Columnas disponibles: {list(df.columns)}"
    )

    # Filtrar por departamento Antioquia (si la columna existe)
    if "departamento" in df.columns:
        df = df[df["departamento"].str.upper().str.contains("ANTIOQUIA", na=False)]
        print(f"[minsal]   {len(df)} registros en Antioquia.")

    # Filtrar por municipios de Urabá
    df["codigo_municipio"] = df["codigo_municipio"].astype(str).str.zfill(5)
    df_uraba = df[df["codigo_municipio"].isin(DIVIPOLA_URABA)].copy()

    if df_uraba.empty:
        raise ValueError(
            "[minsal] No se encontraron prestadores para los municipios de Urabá. "
            f"Verifica codigo_municipio. Esperados: {DIVIPOLA_URABA}"
        )

    # Geocodificar
    df_uraba["latitud"]  = pd.to_numeric(df_uraba["latitud"],  errors="coerce")
    df_uraba["longitud"] = pd.to_numeric(df_uraba["longitud"], errors="coerce")

    n_antes = len(df_uraba)
    df_uraba = df_uraba.dropna(subset=["latitud", "longitud"])
    n_descartados = n_antes - len(df_uraba)
    if n_descartados:
        print(f"[minsal]   ADVERTENCIA: {n_descartados} registros descartados por coordenadas nulas.")

    geometrias = [Point(lon, lat) for lon, lat in zip(df_uraba["longitud"], df_uraba["latitud"])]
    gdf = gpd.GeoDataFrame(df_uraba, geometry=geometrias, crs="EPSG:4326")

    # Normalizar nivel_atencion a string limpio
    gdf["nivel_atencion"] = gdf["nivel_atencion"].astype(str).str.strip()

    print(f"[minsal] {len(gdf)} prestadores cargados para Urabá.")
    return gdf


def clasificar_nivel(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Agrega la columna 'es_intercomunal' marcando hospitales/clínicas de alta complejidad.

    Un prestador es intercomunal (nivel 3) si tiene nivel_atencion == '3',
    lo que implica que sirve a una población mayor que el municipio donde se ubica.

    Args:
        gdf: GeoDataFrame retornado por cargar_reps().

    Returns:
        El mismo GeoDataFrame con columna adicional:
            es_intercomunal → bool (True si nivel_atencion == '3')

    Raises:
        AssertionError: si 'nivel_atencion' no está en el GeoDataFrame.
    """
    assert "nivel_atencion" in gdf.columns, (
        "[minsal] El GeoDataFrame debe tener columna 'nivel_atencion'. "
        "Usa cargar_reps() primero."
    )

    gdf = gdf.copy()
    gdf["es_intercomunal"] = gdf["nivel_atencion"].astype(str).str.strip() == "3"
    n_intercomunal = gdf["es_intercomunal"].sum()
    print(f"[minsal] {n_intercomunal} prestadores nivel 3 (intercomunal) identificados.")
    return gdf


def calcular_capacidad_m2(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Agrega columna 'capacidad_m2' con estimación de área física por tipo de prestador.

    Estimaciones estándar para dasymetría de accesibilidad:
      Nivel 1 (primario):    200 m²
      Nivel 2 (secundario):  800 m²
      Nivel 3 (terciario): 3 000 m²

    Si el nivel no corresponde a 1, 2 o 3, se asigna 200 m² (mínimo).

    Args:
        gdf: GeoDataFrame retornado por cargar_reps() (con columna nivel_atencion).

    Returns:
        El mismo GeoDataFrame con columna adicional:
            capacidad_m2 → int, área estimada en m²

    Raises:
        AssertionError: si 'nivel_atencion' no está en el GeoDataFrame.
    """
    assert "nivel_atencion" in gdf.columns, (
        "[minsal] El GeoDataFrame debe tener columna 'nivel_atencion'."
    )

    gdf = gdf.copy()
    gdf["capacidad_m2"] = (
        gdf["nivel_atencion"]
        .astype(str)
        .str.strip()
        .map(CAPACIDAD_M2)
        .fillna(200)
        .astype(int)
    )

    resumen = gdf.groupby("nivel_atencion")["capacidad_m2"].agg(["count", "sum"])
    print("[minsal] Capacidad estimada por nivel:")
    for nivel, row in resumen.iterrows():
        print(f"         Nivel {nivel}: {int(row['count'])} prestadores → {int(row['sum']):,} m² totales")

    return gdf


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _renombrar_alias(df: pd.DataFrame, alias: list[str], nombre_estandar: str) -> pd.DataFrame:
    """
    Renombra la primera columna que coincida con algún alias al nombre estándar.
    Si ya existe el nombre estándar, no hace nada.
    """
    if nombre_estandar in df.columns:
        return df
    for a in alias:
        if a in df.columns:
            return df.rename(columns={a: nombre_estandar})
    return df  # sin columna → se detectará en el assert posterior
