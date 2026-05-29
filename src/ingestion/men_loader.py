"""
Carga de datos del SIMAT (Sistema de Información de Matrícula) del Ministerio de Educación.

Fuente:
  - MEN — SIMAT: https://www.mineducacion.gov.co/
  - Descarga: https://www.datos.gov.co/api/views/upkm-vdjb/rows.csv?accessType=DOWNLOAD
  - Geocodificado: data/processed/equipamientos/simat_uraba_geo.gpkg

Columnas reales del CSV SIMAT (confirmadas en descarga):
  año                  → Año del registro (ej: 2016)
  codigomunicipio      → Código DIVIPOLA del municipio (entero o string, zfill a 5)
  nombreestablecimiento→ Nombre del establecimiento educativo
  zona                 → 'Urbana' o 'Rural'
  direccion            → Dirección postal del establecimiento
  niveles              → Niveles que ofrece (texto libre: "Primaria, Secundaria, etc.")
  matricula_Contratada → Matrícula contratada (puede ser NaN)

Cobertura Urabá verificada: 180 establecimientos (datos 2016)

NOTA: el SIMAT NO incluye coordenadas geográficas. Los 180 establecimientos de Urabá
fueron geocodificados por dirección y guardados en simat_uraba_geo.gpkg.

NOTA 2: El CSV no contiene columnas de matrícula desagregada por nivel educativo
(preescolar, primaria, secundaria, media). Solo 'matricula_Contratada' como proxy.

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

# Rutas procesadas (relativas a la raíz del proyecto)
_SIMAT_GEO_GPKG = "data/processed/equipamientos/simat_uraba_geo.gpkg"

# Alias de columnas — columnas reales SIMAT primero, luego variantes legado
# Columna real de código municipal: 'codigomunicipio' (sin guion bajo)
_ALIAS_CODIGO    = ["nombreestablecimiento", "codigo_establecimiento", "codigo_dane",
                    "codigo", "cod_dane_establecimiento"]
_ALIAS_NOMBRE    = ["nombreestablecimiento", "nombre", "nombre_establecimiento",
                    "nombre_sede", "institucion"]
_ALIAS_MUNICIPIO = ["codigomunicipio", "municipio_codigo", "codigo_municipio",
                    "cod_municipio", "cod_dane_municipio"]
_ALIAS_ZONA      = ["zona"]
_ALIAS_DIRECCION = ["direccion"]
_ALIAS_NIVELES   = ["niveles"]
_ALIAS_LAT       = ["latitud", "lat", "latitude", "geo_latitud"]
_ALIAS_LON       = ["longitud", "lon", "lng", "longitude", "geo_longitud"]
_ALIAS_TOTAL     = ["matricula_contratada", "matricula_total", "total_matricula",
                    "total", "total_estudiantes"]
_ALIAS_PREESCOLAR  = ["preescolar", "matricula_preescolar"]
_ALIAS_PRIMARIA    = ["primaria", "matricula_primaria"]
_ALIAS_SECUNDARIA  = ["secundaria", "matricula_secundaria"]
_ALIAS_MEDIA       = ["media", "matricula_media"]

# Columnas mínimas requeridas (sin coordenadas, se geocodifica aparte)
COLS_REQUERIDAS = {"nombre", "municipio_codigo"}

# Niveles educativos válidos para el cálculo de matrícula 4-18 años
NIVELES_VALIDOS = ["preescolar", "primaria", "secundaria", "media"]


def cargar_simat(path: Path) -> pd.DataFrame:
    """
    Lee el CSV del SIMAT, filtra por municipios de Urabá y normaliza columnas.

    Columnas reales del SIMAT (descarga datos.gov.co):
      año, codigomunicipio, nombreestablecimiento, zona, direccion,
      niveles, matricula_Contratada

    La columna de código municipal real es 'codigomunicipio' (sin guion bajo).
    Se filtra con zfill(5) para obtener código DIVIPOLA de 5 dígitos.

    NOTA: el SIMAT NO incluye coordenadas. Usar cargar_simat_geocodificado()
    para obtener el GeoDataFrame con geometrías.
    NOTA 2: no hay columnas de matrícula desagregada por nivel; solo
    'matricula_Contratada' como proxy del tamaño del establecimiento.

    Args:
        path: Ruta al CSV del SIMAT descargado del MEN o datos.gov.co.

    Returns:
        DataFrame con 180 establecimientos de Urabá y columnas normalizadas:
            nombre, municipio_codigo, zona, direccion, niveles, matricula_total
        Columnas de nivel (preescolar, primaria, secundaria, media) = 0 si ausentes.

    Raises:
        FileNotFoundError: si el archivo no existe.
        AssertionError:    si faltan columnas mínimas requeridas.
        ValueError:        si no hay registros para Urabá.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[men] Archivo SIMAT no encontrado: {path}\n"
            "Descarga: wget 'https://www.datos.gov.co/api/views/upkm-vdjb/rows.csv?accessType=DOWNLOAD'"
        )

    print(f"[men] Cargando SIMAT desde {path}...")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    # Normalizar encabezados (strip + lowercase) para detectar alias
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Mapear columnas reales del SIMAT a nombres estándar
    df = _renombrar_alias(df, _ALIAS_NOMBRE,     "nombre")
    df = _renombrar_alias(df, _ALIAS_MUNICIPIO,  "municipio_codigo")   # codigomunicipio → municipio_codigo
    df = _renombrar_alias(df, _ALIAS_ZONA,       "zona")
    df = _renombrar_alias(df, _ALIAS_DIRECCION,  "direccion")
    df = _renombrar_alias(df, _ALIAS_NIVELES,    "niveles")
    df = _renombrar_alias(df, _ALIAS_TOTAL,      "matricula_total")    # matricula_contratada → matricula_total
    df = _renombrar_alias(df, _ALIAS_PREESCOLAR, "preescolar")
    df = _renombrar_alias(df, _ALIAS_PRIMARIA,   "primaria")
    df = _renombrar_alias(df, _ALIAS_SECUNDARIA, "secundaria")
    df = _renombrar_alias(df, _ALIAS_MEDIA,      "media")

    cols_faltantes = COLS_REQUERIDAS - set(df.columns)
    assert not cols_faltantes, (
        f"[men] Faltan columnas mínimas en el CSV: {cols_faltantes}. "
        f"Columnas disponibles: {list(df.columns)}"
    )

    # Filtrar por municipios de Urabá — 'codigomunicipio' puede ser int, zfill a 5
    df["municipio_codigo"] = df["municipio_codigo"].astype(str).str.zfill(5)
    df_uraba = df[df["municipio_codigo"].isin(DIVIPOLA_URABA)].copy()

    if df_uraba.empty:
        raise ValueError(
            "[men] No se encontraron establecimientos para los municipios de Urabá. "
            f"Verifica 'codigomunicipio'. Esperados: {DIVIPOLA_URABA}"
        )

    # Rellenar columnas de nivel con 0 (el SIMAT no las desagrega por nivel)
    for nivel in NIVELES_VALIDOS:
        if nivel not in df_uraba.columns:
            df_uraba[nivel] = 0
        else:
            df_uraba[nivel] = pd.to_numeric(df_uraba[nivel], errors="coerce").fillna(0).astype(int)

    if "matricula_total" not in df_uraba.columns:
        df_uraba["matricula_total"] = 0
    else:
        df_uraba["matricula_total"] = (
            pd.to_numeric(df_uraba["matricula_total"], errors="coerce").fillna(0).astype(int)
        )

    print(f"[men] {len(df_uraba)} establecimientos SIMAT cargados para Urabá.")
    return df_uraba


def cargar_simat_geocodificado(path: Optional[Path] = None) -> gpd.GeoDataFrame:
    """
    Lee el GeoPackage del SIMAT ya geocodificado por dirección para Urabá.

    El archivo simat_uraba_geo.gpkg contiene los 180 establecimientos de Urabá
    con coordenadas obtenidas mediante geocodificación por dirección postal.

    Args:
        path: Ruta al GeoPackage. Si es None usa _SIMAT_GEO_GPKG.

    Returns:
        GeoDataFrame con 180 establecimientos y columna geometry (Point).
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
    """
    if path is None:
        path = Path(_SIMAT_GEO_GPKG)
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[men] GeoPackage SIMAT geocodificado no encontrado: {path}\n"
            "Ejecuta: python scripts/geocode_equipamientos.py simat"
        )

    print(f"[men] Cargando SIMAT geocodificado desde {path}...")
    gdf = gpd.read_file(path)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    print(f"[men] {len(gdf)} establecimientos geocodificados cargados.")
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
