"""
Carga de datos del SIMAT (Sistema de Información de Matrícula) del Ministerio de Educación.

Fuente:
  - MEN — SIMAT: https://www.mineducacion.gov.co/
  - Descarga: https://www.datos.gov.co/  (buscar "Establecimientos educativos SIMAT")
  - Alternativa: Consulta directa SIMAT con usuario institucional.

Columnas clave esperadas en el CSV del SIMAT:
  codigo_establecimiento → Código DANE del establecimiento (12 dígitos)
  nombre                 → Nombre del establecimiento
  municipio_codigo       → Código DIVIPOLA del municipio (5 dígitos)
  latitud                → Latitud WGS84 decimal
  longitud               → Longitud WGS84 decimal
  matricula_total        → Total de estudiantes matriculados
  preescolar             → Matrícula en preescolar (transición + prejardín)
  primaria               → Matrícula en primaria (grados 1–5)
  secundaria             → Matrícula en secundaria (grados 6–9)
  media                  → Matrícula en media (grados 10–11)

Grupos de edad cubiertos por nivel (referencia Ley 115):
  Preescolar:  3–5  años
  Primaria:    6–10 años
  Secundaria: 11–14 años
  Media:      15–17 años
  → Rango combinado para accesibilidad educativa: 4–18 años
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

DIVIPOLA_URABA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]

# Alias de columnas por si el SIMAT cambia encabezados entre versiones
_ALIAS_CODIGO    = ["codigo_establecimiento", "codigo_dane", "codigo", "cod_dane_establecimiento"]
_ALIAS_NOMBRE    = ["nombre", "nombre_establecimiento", "nombre_sede", "institucion"]
_ALIAS_MUNICIPIO = ["municipio_codigo", "codigo_municipio", "cod_municipio", "cod_dane_municipio"]
_ALIAS_LAT       = ["latitud", "lat", "latitude", "geo_latitud"]
_ALIAS_LON       = ["longitud", "lon", "lng", "longitude", "geo_longitud"]
_ALIAS_TOTAL     = ["matricula_total", "total_matricula", "total", "total_estudiantes"]
_ALIAS_PREESCOLAR  = ["preescolar", "matricula_preescolar"]
_ALIAS_PRIMARIA    = ["primaria", "matricula_primaria"]
_ALIAS_SECUNDARIA  = ["secundaria", "matricula_secundaria"]
_ALIAS_MEDIA       = ["media", "matricula_media"]

COLS_REQUERIDAS = {"codigo_establecimiento", "nombre", "municipio_codigo", "latitud", "longitud"}

# Niveles educativos válidos para el cálculo de matrícula 4-18 años
NIVELES_VALIDOS = ["preescolar", "primaria", "secundaria", "media"]


def cargar_simat(path: Path) -> gpd.GeoDataFrame:
    """
    Lee el CSV del SIMAT, filtra por municipios de Urabá y geocodifica establecimientos.

    Normaliza nombres de columna, descarta registros sin coordenadas válidas y
    crea geometrías Point(lon, lat) para cada establecimiento.

    Args:
        path: Ruta al CSV del SIMAT descargado del MEN o datos.gov.co.

    Returns:
        GeoDataFrame con columnas:
            codigo_establecimiento, nombre, municipio_codigo, latitud, longitud,
            matricula_total, preescolar, primaria, secundaria, media, geometry
        CRS: EPSG:4326.
        Columnas de matrícula por nivel rellenadas con 0 si no están presentes.

    Raises:
        FileNotFoundError: si el archivo no existe.
        AssertionError:    si faltan columnas mínimas requeridas.
        ValueError:        si no hay registros para Urabá.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[men] Archivo SIMAT no encontrado: {path}\n"
            "Descarga el CSV desde https://www.datos.gov.co/ "
            "buscando 'Establecimientos educativos SIMAT Antioquia'."
        )

    print(f"[men] Cargando SIMAT desde {path}...")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Normalizar columnas principales
    df = _renombrar_alias(df, _ALIAS_CODIGO,     "codigo_establecimiento")
    df = _renombrar_alias(df, _ALIAS_NOMBRE,     "nombre")
    df = _renombrar_alias(df, _ALIAS_MUNICIPIO,  "municipio_codigo")
    df = _renombrar_alias(df, _ALIAS_LAT,        "latitud")
    df = _renombrar_alias(df, _ALIAS_LON,        "longitud")
    df = _renombrar_alias(df, _ALIAS_TOTAL,      "matricula_total")
    df = _renombrar_alias(df, _ALIAS_PREESCOLAR, "preescolar")
    df = _renombrar_alias(df, _ALIAS_PRIMARIA,   "primaria")
    df = _renombrar_alias(df, _ALIAS_SECUNDARIA, "secundaria")
    df = _renombrar_alias(df, _ALIAS_MEDIA,      "media")

    cols_faltantes = COLS_REQUERIDAS - set(df.columns)
    assert not cols_faltantes, (
        f"[men] Faltan columnas mínimas en el CSV: {cols_faltantes}. "
        f"Columnas disponibles: {list(df.columns)}"
    )

    # Filtrar por municipios de Urabá
    df["municipio_codigo"] = df["municipio_codigo"].astype(str).str.zfill(5)
    df_uraba = df[df["municipio_codigo"].isin(DIVIPOLA_URABA)].copy()

    if df_uraba.empty:
        raise ValueError(
            "[men] No se encontraron establecimientos para los municipios de Urabá. "
            f"Verifica municipio_codigo. Esperados: {DIVIPOLA_URABA}"
        )

    # Geocodificar
    df_uraba["latitud"]  = pd.to_numeric(df_uraba["latitud"],  errors="coerce")
    df_uraba["longitud"] = pd.to_numeric(df_uraba["longitud"], errors="coerce")

    n_antes = len(df_uraba)
    df_uraba = df_uraba.dropna(subset=["latitud", "longitud"])
    n_descartados = n_antes - len(df_uraba)
    if n_descartados:
        print(
            f"[men]   ADVERTENCIA: {n_descartados} establecimientos sin coordenadas válidas "
            "fueron descartados."
        )

    # Rellenar columnas de nivel con 0 si no están en el CSV
    for nivel in NIVELES_VALIDOS:
        if nivel not in df_uraba.columns:
            print(f"[men]   ADVERTENCIA: columna '{nivel}' no encontrada. Se asigna 0.")
            df_uraba[nivel] = 0
        else:
            df_uraba[nivel] = pd.to_numeric(df_uraba[nivel], errors="coerce").fillna(0).astype(int)

    if "matricula_total" not in df_uraba.columns:
        df_uraba["matricula_total"] = (
            df_uraba["preescolar"] + df_uraba["primaria"]
            + df_uraba["secundaria"] + df_uraba["media"]
        )
    else:
        df_uraba["matricula_total"] = (
            pd.to_numeric(df_uraba["matricula_total"], errors="coerce")
            .fillna(0).astype(int)
        )

    geometrias = [
        Point(lon, lat)
        for lon, lat in zip(df_uraba["longitud"], df_uraba["latitud"])
    ]
    gdf = gpd.GeoDataFrame(df_uraba, geometry=geometrias, crs="EPSG:4326")

    print(
        f"[men] {len(gdf)} establecimientos cargados para Urabá. "
        f"Matrícula total: {gdf['matricula_total'].sum():,} estudiantes."
    )
    return gdf


def calcular_matriculas_por_nivel(
    gdf: gpd.GeoDataFrame,
    niveles: Optional[list[str]] = None,
) -> gpd.GeoDataFrame:
    """
    Suma matrícula para los niveles educativos que cubren 4–18 años.

    El rango 4–18 años corresponde a: preescolar + primaria + secundaria + media.
    Se puede especificar un subconjunto de niveles si se requiere un corte diferente.

    Args:
        gdf:    GeoDataFrame retornado por cargar_simat().
        niveles: Lista de niveles a sumar. Default: todos los 4 niveles.
                 Valores válidos: 'preescolar', 'primaria', 'secundaria', 'media'.

    Returns:
        El mismo GeoDataFrame con columnas adicionales:
            matricula_4_18        → suma de matrícula en los niveles seleccionados
            pct_preescolar        → % de matrícula en preescolar sobre total del establecimiento
            pct_primaria          → % de matrícula en primaria
            pct_secundaria        → % de matrícula en secundaria
            pct_media             → % de matrícula en media

    Raises:
        AssertionError: si algún nivel solicitado no está en el GeoDataFrame.
        ValueError:     si la lista de niveles está vacía.
    """
    if niveles is None:
        niveles = NIVELES_VALIDOS

    if not niveles:
        raise ValueError("[men] La lista de niveles no puede estar vacía.")

    cols_invalidas = set(niveles) - set(NIVELES_VALIDOS)
    if cols_invalidas:
        raise ValueError(
            f"[men] Niveles no válidos: {cols_invalidas}. "
            f"Valores aceptados: {NIVELES_VALIDOS}"
        )

    cols_faltantes = set(niveles) - set(gdf.columns)
    assert not cols_faltantes, (
        f"[men] El GeoDataFrame no tiene las columnas de nivel: {cols_faltantes}. "
        "Usa cargar_simat() primero."
    )

    gdf = gdf.copy()
    gdf["matricula_4_18"] = gdf[niveles].sum(axis=1).astype(int)

    # Calcular porcentajes sobre matricula_total (evitar división por cero)
    total = gdf["matricula_total"].replace(0, pd.NA)
    for nivel in NIVELES_VALIDOS:
        if nivel in gdf.columns:
            gdf[f"pct_{nivel}"] = (gdf[nivel] / total * 100).round(2)
        else:
            gdf[f"pct_{nivel}"] = 0.0

    print(
        f"[men] Matrícula 4-18 años calculada: {gdf['matricula_4_18'].sum():,} estudiantes "
        f"en {len(gdf)} establecimientos."
    )
    return gdf


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _renombrar_alias(
    df: pd.DataFrame,
    alias: list[str],
    nombre_estandar: str,
) -> pd.DataFrame:
    """
    Renombra la primera columna que coincida con algún alias al nombre estándar.
    Si el nombre estándar ya existe, no hace nada.
    """
    if nombre_estandar in df.columns:
        return df
    for a in alias:
        if a in df.columns:
            return df.rename(columns={a: nombre_estandar})
    return df
