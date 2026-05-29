"""
Carga del REPS (Registro Especial de Prestadores de Servicios de Salud) de MinSalud.

Fuente:
  - Ministerio de Salud y Protección Social — REPS
  - Descarga: https://www.datos.gov.co/resource/c36g-9fc2.csv
  - Filtrado Urabá ya procesado: data/processed/equipamientos/reps_uraba.csv
  - Geocodificado: data/processed/equipamientos/reps_uraba_geo.gpkg

Columnas reales del CSV REPS (confirmadas en descarga):
  CodigoPrestador          → ID único del prestador
  NombrePrestador          → Nombre del prestador/institución
  NombreSede               → Nombre de la sede
  MunicipioPrestador       → Código DIVIPOLA del municipio (5 dígitos string)
  DepartamentoPrestadorDesc→ Nombre del departamento
  DireccionPrestador       → Dirección postal
  ClasePrestador           → Clase: IPS, Profesional independiente, etc.
  NivelAtencion            → Nivel de complejidad: '1', '2' o '3' (o texto)

Cobertura Urabá verificada: 339 prestadores
  Apartadó: 196 · Turbo: 79 · Chigorodó: 32 · resto: ~32

Nota: el REPS NO incluye coordenadas geográficas. Los 339 prestadores de Urabá
fueron geocodificados por dirección y guardados en reps_uraba_geo.gpkg.

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

# Rutas procesadas (relativas a la raíz del proyecto)
_REPS_CSV_PROCESADO = "data/processed/equipamientos/reps_uraba.csv"
_REPS_GEO_GPKG      = "data/processed/equipamientos/reps_uraba_geo.gpkg"

# Nombres de columna aceptados (REPS cambia encabezados entre versiones)
# Columnas reales REPS descarga MinSalud: CodigoPrestador, NombrePrestador,
# NombreSede, MunicipioPrestador, DepartamentoPrestadorDesc,
# DireccionPrestador, ClasePrestador, NivelAtencion
_ALIAS_ID        = ["codigoprestador", "codigo_prestador", "id_prestador"]
_ALIAS_NOMBRE    = ["nombreprestador", "nombre_prestador", "nombresede", "nombre_sede",
                    "nombre_ips", "razon_social"]
_ALIAS_SEDE      = ["nombresede", "nombre_sede"]
_ALIAS_MUNICIPIO = ["municipioprestador", "codigo_municipio", "cod_municipio",
                    "municipio_codigo", "mpio_cdpmp", "divipola"]
_ALIAS_DEPTO     = ["departamentoprestadordesc", "departamento", "nombre_departamento", "depto"]
_ALIAS_DIRECCION = ["direccionprestador", "direccion", "direccion_prestador"]
_ALIAS_CLASE     = ["claseprestador", "clase_prestador", "tipo_prestador"]
_ALIAS_NIVEL     = ["nivelatencion", "nivel_atencion", "nivel", "nivel_complejidad"]
_ALIAS_LAT       = ["latitud", "lat", "latitude"]
_ALIAS_LON       = ["longitud", "lon", "lng", "longitude"]

# m² estimados por nivel de atención
CAPACIDAD_M2 = {
    "1": 200,
    "2": 800,
    "3": 3000,
}

# Columnas mínimas requeridas para el flujo de datos (sin coordenadas, se geocodifica aparte)
COLS_REQUERIDAS_CSV = {"nombre_prestador", "codigo_municipio"}
COLS_REQUERIDAS_GEO = {"nombre_prestador", "codigo_municipio", "latitud", "longitud"}


def cargar_reps(path: Optional[Path] = None) -> pd.DataFrame:
    """
    Lee el CSV del REPS ya filtrado para Urabá (339 prestadores).

    Usa preferentemente el archivo procesado en data/processed/equipamientos/reps_uraba.csv
    que ya contiene solo los prestadores de Urabá. Si se pasa 'path' al CSV nacional
    completo, filtra por municipios de Urabá y normaliza columnas.

    Columnas reales del REPS MinSalud:
      CodigoPrestador, NombrePrestador, NombreSede, MunicipioPrestador (5d),
      DepartamentoPrestadorDesc, DireccionPrestador, ClasePrestador, NivelAtencion

    Tras normalización devuelve columnas estandarizadas:
      codigo_prestador, nombre_prestador, nombre_sede, codigo_municipio,
      departamento, direccion, clase_prestador, nivel_atencion

    NOTA: El REPS no incluye coordenadas. Usar cargar_reps_geocodificado() para
    obtener el GeoDataFrame con geometrías.

    Args:
        path: Ruta al CSV del REPS (nacional o pre-filtrado Urabá).
              Si es None usa _REPS_CSV_PROCESADO.

    Returns:
        DataFrame con 339 prestadores de Urabá y columnas normalizadas.

    Raises:
        FileNotFoundError: si el archivo no existe.
        ValueError:        si no hay registros para Urabá.
    """
    if path is None:
        path = Path(_REPS_CSV_PROCESADO)
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[minsal] Archivo REPS no encontrado: {path}\n"
            "CSV procesado esperado en data/processed/equipamientos/reps_uraba.csv\n"
            "Descarga nacional: wget 'https://www.datos.gov.co/api/views/c36g-9fc2/rows.csv?accessType=DOWNLOAD'"
        )

    print(f"[minsal] Cargando REPS desde {path}...")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)

    # Normalizar encabezados (strip + lowercase para detectar alias)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Mapear columnas reales del REPS a nombres estándar
    df = _renombrar_alias(df, _ALIAS_ID,        "codigo_prestador")
    df = _renombrar_alias(df, _ALIAS_NOMBRE,     "nombre_prestador")
    df = _renombrar_alias(df, _ALIAS_SEDE,       "nombre_sede")
    df = _renombrar_alias(df, _ALIAS_MUNICIPIO,  "codigo_municipio")
    df = _renombrar_alias(df, _ALIAS_DEPTO,      "departamento")
    df = _renombrar_alias(df, _ALIAS_DIRECCION,  "direccion")
    df = _renombrar_alias(df, _ALIAS_CLASE,      "clase_prestador")
    df = _renombrar_alias(df, _ALIAS_NIVEL,      "nivel_atencion")

    cols_faltantes = COLS_REQUERIDAS_CSV - set(df.columns)
    assert not cols_faltantes, (
        f"[minsal] Faltan columnas en el CSV: {cols_faltantes}. "
        f"Columnas disponibles: {list(df.columns)}"
    )

    # Filtrar por municipios de Urabá (solo si el CSV es el nacional completo)
    df["codigo_municipio"] = df["codigo_municipio"].astype(str).str.zfill(5)
    df_uraba = df[df["codigo_municipio"].isin(DIVIPOLA_URABA)].copy()

    if df_uraba.empty:
        raise ValueError(
            "[minsal] No se encontraron prestadores para los municipios de Urabá. "
            f"Verifica MunicipioPrestador/codigo_municipio. Esperados: {DIVIPOLA_URABA}"
        )

    print(f"[minsal] {len(df_uraba)} prestadores REPS cargados para Urabá.")
    return df_uraba


def cargar_reps_geocodificado(path: Optional[Path] = None) -> gpd.GeoDataFrame:
    """
    Lee el GeoPackage del REPS ya geocodificado por dirección para Urabá.

    El archivo reps_uraba_geo.gpkg contiene los 339 prestadores de Urabá con
    coordenadas obtenidas mediante geocodificación por dirección postal.

    Args:
        path: Ruta al GeoPackage. Si es None usa _REPS_GEO_GPKG.

    Returns:
        GeoDataFrame con 339 prestadores y columna geometry (Point).
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
    """
    if path is None:
        path = Path(_REPS_GEO_GPKG)
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[minsal] GeoPackage REPS geocodificado no encontrado: {path}\n"
            "Ejecuta: python scripts/geocode_equipamientos.py reps"
        )

    print(f"[minsal] Cargando REPS geocodificado desde {path}...")
    gdf = gpd.read_file(path)

    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    print(f"[minsal] {len(gdf)} prestadores geocodificados cargados.")
    return gdf


def clasificar_nivel(df: "pd.DataFrame | gpd.GeoDataFrame") -> "pd.DataFrame | gpd.GeoDataFrame":
    """
    Agrega la columna 'es_intercomunal' marcando prestadores de alta complejidad.

    Un prestador es intercomunal (nivel 3) si NivelAtencion == '3' o si
    ClasePrestador indica alta complejidad. Se acepta tanto DataFrame como
    GeoDataFrame (retornados por cargar_reps() o cargar_reps_geocodificado()).

    Columnas consultadas (por orden de prioridad):
      1. 'nivel_atencion'  → valor '3' = alta complejidad
      2. 'clase_prestador' → texto libre (fallback si no hay nivel_atencion)

    Args:
        df: DataFrame o GeoDataFrame con columna 'nivel_atencion' y/o 'clase_prestador'.

    Returns:
        El mismo objeto con columna adicional:
            es_intercomunal → bool (True si nivel 3 / alta complejidad)

    Raises:
        AssertionError: si no existe ninguna de las columnas consultadas.
    """
    tiene_nivel = "nivel_atencion" in df.columns
    tiene_clase = "clase_prestador" in df.columns
    assert tiene_nivel or tiene_clase, (
        "[minsal] Se requiere columna 'nivel_atencion' o 'clase_prestador'. "
        "Usa cargar_reps() o cargar_reps_geocodificado() primero."
    )

    df = df.copy()
    if tiene_nivel:
        df["es_intercomunal"] = df["nivel_atencion"].astype(str).str.strip() == "3"
    else:
        # Fallback: buscar indicadores de alta complejidad en clase_prestador
        df["es_intercomunal"] = df["clase_prestador"].astype(str).str.upper().str.contains(
            "HOSPITAL|CLINICA|ALTA COMPLEJIDAD", na=False
        )

    n_intercomunal = df["es_intercomunal"].sum()
    print(f"[minsal] {n_intercomunal} prestadores nivel 3 (intercomunal) identificados.")
    return df


def calcular_capacidad_m2(df: "pd.DataFrame | gpd.GeoDataFrame") -> "pd.DataFrame | gpd.GeoDataFrame":
    """
    Agrega columna 'capacidad_m2' con estimación de área física por tipo de prestador.

    Estimaciones estándar para dasymetría de accesibilidad:
      Nivel 1 (primario):    200 m²
      Nivel 2 (secundario):  800 m²
      Nivel 3 (terciario): 3 000 m²

    Si el nivel no corresponde a 1, 2 o 3, se asigna 200 m² (mínimo).
    Acepta tanto DataFrame (cargar_reps) como GeoDataFrame (cargar_reps_geocodificado).

    Args:
        df: DataFrame o GeoDataFrame con columna 'nivel_atencion'.

    Returns:
        El mismo objeto con columna adicional:
            capacidad_m2 → int, área estimada en m²

    Raises:
        AssertionError: si 'nivel_atencion' no está en el objeto.
    """
    assert "nivel_atencion" in df.columns, (
        "[minsal] Se requiere columna 'nivel_atencion'. "
        "Usa cargar_reps() o cargar_reps_geocodificado() primero."
    )

    df = df.copy()
    df["capacidad_m2"] = (
        df["nivel_atencion"]
        .astype(str)
        .str.strip()
        .map(CAPACIDAD_M2)
        .fillna(200)
        .astype(int)
    )

    resumen = df.groupby("nivel_atencion")["capacidad_m2"].agg(["count", "sum"])
    print("[minsal] Capacidad estimada por nivel:")
    for nivel, row in resumen.iterrows():
        print(f"         Nivel {nivel}: {int(row['count'])} prestadores → {int(row['sum']):,} m² totales")

    return df


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
