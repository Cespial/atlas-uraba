"""
Carga de datos delictivos del SIEDCO (Sistema de Información Estadístico, Delincuencial,
Contravencional y Operativo) de la Policía Nacional de Colombia.

Fuentes:
  - Portal SIEDCO (acceso institucional): https://www.policia.gov.co/siedco
  - datos.gov.co: https://www.datos.gov.co/ (buscar "criminalidad Policía Nacional")
  - Informe de criminalidad DIJIN: disponible por municipio y año.

Columnas esperadas en el CSV exportado de SIEDCO / datos.gov.co:
  fecha               → Fecha del evento (formato YYYY-MM-DD o DD/MM/YYYY)
  municipio_codigo    → Código DIVIPOLA del municipio (5 dígitos)
  latitud             → Latitud WGS84 decimal (puede ser vacía en algunos registros)
  longitud            → Longitud WGS84 decimal
  descripcion_conducta → Descripción del delito (ej. "HURTO A PERSONAS")
  grupo_delito        → Clasificación general (ej. "DELITOS CONTRA EL PATRIMONIO ECONÓMICO")

Categorías de delito (para el índice de seguridad):
  grave_persona   → Delitos violentos contra la integridad física (homicidio, lesiones, etc.)
  grave_propiedad → Delitos violentos contra el patrimonio (robo con violencia, extorsión, etc.)
  leve_persona    → Delitos menores contra la persona (amenazas, injurias, etc.)
  leve_propiedad  → Delitos menores contra la propiedad (hurto simple, daño bien ajeno, etc.)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

DIVIPOLA_URABA = ["05045", "05147", "05120", "05837", "05544", "05665", "05659", "05051"]

# Alias de columnas por variaciones en el CSV
_ALIAS_FECHA       = ["fecha", "fecha_hecho", "fecha_evento", "fecha_caso"]
_ALIAS_MUNICIPIO   = ["municipio_codigo", "cod_municipio", "codigo_municipio", "divipola_municipio"]
_ALIAS_LAT         = ["latitud", "lat", "latitude", "geo_latitud", "y"]
_ALIAS_LON         = ["longitud", "lon", "lng", "longitude", "geo_longitud", "x"]
_ALIAS_CONDUCTA    = ["descripcion_conducta", "conducta", "delito", "descripcion_delito", "tipo_delito"]
_ALIAS_GRUPO       = ["grupo_delito", "grupo", "categoria_delito", "bien_juridico"]

COLS_REQUERIDAS = {"fecha", "municipio_codigo", "descripcion_conducta", "grupo_delito"}

# ─────────────────────────────────────────────────────────────────────────────
# Diccionario de categorización de delitos (≥30 tipos)
# Formato: descripcion_conducta (normalizada a MAYÚSCULAS) → categoria
# ─────────────────────────────────────────────────────────────────────────────
CATALOGO_DELITOS: dict[str, str] = {
    # ── GRAVE PERSONA ─────────────────────────────────────────────────────────
    "HOMICIDIO":                            "grave_persona",
    "HOMICIDIO CULPOSO":                    "grave_persona",
    "FEMINICIDIO":                          "grave_persona",
    "LESIONES PERSONALES":                  "grave_persona",
    "LESIONES CULPOSAS":                    "grave_persona",
    "VIOLENCIA INTRAFAMILIAR":              "grave_persona",
    "SECUESTRO":                            "grave_persona",
    "SECUESTRO SIMPLE":                     "grave_persona",
    "SECUESTRO EXTORSIVO":                  "grave_persona",
    "DESAPARICION FORZADA":                 "grave_persona",
    "TORTURA":                              "grave_persona",
    "DELITOS SEXUALES":                     "grave_persona",
    "ACCESO CARNAL VIOLENTO":               "grave_persona",
    "ACTO SEXUAL VIOLENTO":                 "grave_persona",
    "ACOSO SEXUAL":                         "grave_persona",
    "INDUCCION A LA PROSTITUCION":          "grave_persona",
    "TRATA DE PERSONAS":                    "grave_persona",
    "RECLUTAMIENTO ILICITO":                "grave_persona",
    "TERRORISMO":                           "grave_persona",
    "ATENTADO CONTRA SUBSISTENCIA":        "grave_persona",

    # ── GRAVE PROPIEDAD ───────────────────────────────────────────────────────
    "HURTO A PERSONAS":                     "grave_propiedad",
    "HURTO COMERCIO":                       "grave_propiedad",
    "HURTO ENTIDADES FINANCIERAS":          "grave_propiedad",
    "HURTO RESIDENCIAS":                    "grave_propiedad",
    "HURTO AUTOMOTORES":                    "grave_propiedad",
    "HURTO MOTOCICLETAS":                   "grave_propiedad",
    "PIRATERIA TERRESTRE":                  "grave_propiedad",
    "HURTO PIRATAERIA TERRESTRE":           "grave_propiedad",
    "ABIGEATO":                             "grave_propiedad",
    "EXTORSION":                            "grave_propiedad",
    "ESTAFA":                               "grave_propiedad",
    "FRAUDE INFORMATICO":                   "grave_propiedad",
    "LAVADO DE ACTIVOS":                    "grave_propiedad",
    "FABRICACION TRAFICO PORTE ARMAS":      "grave_propiedad",
    "TRAFICO ESTUPEFACIENTES":              "grave_propiedad",
    "CONCIERTO PARA DELINQUIR":             "grave_propiedad",

    # ── LEVE PERSONA ──────────────────────────────────────────────────────────
    "AMENAZAS":                             "leve_persona",
    "INJURIA":                              "leve_persona",
    "CALUMNIA":                             "leve_persona",
    "VIOLACION DE HABITACION AJENA":        "leve_persona",
    "INASISTENCIA ALIMENTARIA":             "leve_persona",
    "MALTRATOS":                            "leve_persona",
    "RIÑA":                                 "leve_persona",

    # ── LEVE PROPIEDAD ────────────────────────────────────────────────────────
    "HURTO SIMPLE":                         "leve_propiedad",
    "HURTO CALIFICADO":                     "leve_propiedad",
    "DANO EN BIEN AJENO":                   "leve_propiedad",
    "DAÑO EN BIEN AJENO":                   "leve_propiedad",
    "INVASION DE TIERRAS":                  "leve_propiedad",
    "USURPACION DE TIERRAS":                "leve_propiedad",
    "PERTURBACION DE LA POSESION":          "leve_propiedad",
    "ABUSO DE CONFIANZA":                   "leve_propiedad",
    "RECEPTACION":                          "leve_propiedad",
    "APROPIACION INDEBIDA":                 "leve_propiedad",
    "INCENDIO":                             "leve_propiedad",
}

# Categoría por defecto cuando el delito no está en el catálogo
CATEGORIA_DEFAULT = "leve_propiedad"


def cargar_eventos(path: Path) -> gpd.GeoDataFrame:
    """
    Lee el CSV de eventos delictivos del SIEDCO, filtra por Urabá y geocodifica.

    Normaliza la columna fecha a datetime, filtra coordenadas inválidas
    (fuera del bounding box de Colombia: lon [-79, -66], lat [-4, 13])
    y crea geometrías Point(lon, lat).

    Args:
        path: Ruta al CSV del SIEDCO o datos.gov.co con eventos delictivos.

    Returns:
        GeoDataFrame con columnas:
            fecha, municipio_codigo, latitud, longitud,
            descripcion_conducta, grupo_delito, geometry
        CRS: EPSG:4326.

    Raises:
        FileNotFoundError: si el archivo no existe.
        AssertionError:    si faltan columnas requeridas.
        ValueError:        si no hay eventos para Urabá.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"[siedco] Archivo no encontrado: {path}\n"
            "Descarga el CSV desde https://www.datos.gov.co/ "
            "buscando 'criminalidad Policía Nacional Antioquia'."
        )

    print(f"[siedco] Cargando eventos delictivos desde {path}...")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Normalizar columnas
    df = _renombrar_alias(df, _ALIAS_FECHA,     "fecha")
    df = _renombrar_alias(df, _ALIAS_MUNICIPIO, "municipio_codigo")
    df = _renombrar_alias(df, _ALIAS_LAT,       "latitud")
    df = _renombrar_alias(df, _ALIAS_LON,       "longitud")
    df = _renombrar_alias(df, _ALIAS_CONDUCTA,  "descripcion_conducta")
    df = _renombrar_alias(df, _ALIAS_GRUPO,     "grupo_delito")

    cols_faltantes = COLS_REQUERIDAS - set(df.columns)
    assert not cols_faltantes, (
        f"[siedco] Faltan columnas en el CSV: {cols_faltantes}. "
        f"Columnas disponibles: {list(df.columns)}"
    )

    # Parsear fecha
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)

    # Filtrar por municipios de Urabá
    df["municipio_codigo"] = df["municipio_codigo"].astype(str).str.zfill(5)
    df_uraba = df[df["municipio_codigo"].isin(DIVIPOLA_URABA)].copy()

    if df_uraba.empty:
        raise ValueError(
            "[siedco] No se encontraron eventos para los municipios de Urabá. "
            f"Verifica municipio_codigo. Esperados: {DIVIPOLA_URABA}"
        )

    print(f"[siedco]   {len(df_uraba)} eventos para Urabá antes de geocodificar.")

    # Geocodificar si las columnas de coordenadas existen
    if "latitud" in df_uraba.columns and "longitud" in df_uraba.columns:
        df_uraba["latitud"]  = pd.to_numeric(df_uraba["latitud"],  errors="coerce")
        df_uraba["longitud"] = pd.to_numeric(df_uraba["longitud"], errors="coerce")

        # Bounding box Colombia
        mask_validas = (
            df_uraba["latitud"].between(-4.0, 13.0) &
            df_uraba["longitud"].between(-79.0, -66.0)
        )
        n_invalidas = (~mask_validas).sum()
        if n_invalidas:
            print(
                f"[siedco]   ADVERTENCIA: {n_invalidas} eventos con coordenadas fuera de "
                "Colombia fueron descartados."
            )
        df_uraba = df_uraba[mask_validas].copy()

        geometrias = [
            Point(lon, lat)
            for lon, lat in zip(df_uraba["longitud"], df_uraba["latitud"])
        ]
        gdf = gpd.GeoDataFrame(df_uraba, geometry=geometrias, crs="EPSG:4326")
    else:
        print(
            "[siedco]   ADVERTENCIA: columnas latitud/longitud no encontradas. "
            "Se retorna GeoDataFrame sin geometría. Geocodifica manualmente."
        )
        gdf = gpd.GeoDataFrame(df_uraba, geometry=gpd.points_from_xy([], []), crs="EPSG:4326")

    # Normalizar descripcion_conducta a mayúsculas sin tildes
    gdf["descripcion_conducta"] = (
        gdf["descripcion_conducta"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    print(f"[siedco] {len(gdf)} eventos cargados con geometría.")
    return gdf


def categorizar_delitos(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Agrega columna 'categoria' clasificando cada evento según el catálogo de delitos.

    Categorías posibles:
      - grave_persona   → delitos violentos contra integridad física
      - grave_propiedad → delitos violentos contra el patrimonio
      - leve_persona    → delitos menores contra la persona
      - leve_propiedad  → delitos menores contra la propiedad (default)

    El mapeo se realiza sobre descripcion_conducta (normalizada a mayúsculas).
    Los delitos no reconocidos en el catálogo se clasifican como 'leve_propiedad'.

    Args:
        gdf: GeoDataFrame retornado por cargar_eventos().

    Returns:
        El mismo GeoDataFrame con columna adicional:
            categoria → str, una de las 4 categorías definidas.

    Raises:
        AssertionError: si 'descripcion_conducta' no está en el GeoDataFrame.
    """
    assert "descripcion_conducta" in gdf.columns, (
        "[siedco] El GeoDataFrame debe tener columna 'descripcion_conducta'. "
        "Usa cargar_eventos() primero."
    )

    gdf = gdf.copy()

    conducta_norm = gdf["descripcion_conducta"].str.upper().str.strip()

    # Intentar mapeo exacto primero
    gdf["categoria"] = conducta_norm.map(CATALOGO_DELITOS)

    # Para no-matches, intentar coincidencia parcial con las keys del catálogo
    mask_sin_cat = gdf["categoria"].isna()
    if mask_sin_cat.any():
        gdf.loc[mask_sin_cat, "categoria"] = (
            conducta_norm[mask_sin_cat]
            .apply(_categorizar_parcial)
        )

    # Rellenar cualquier restante con default
    gdf["categoria"] = gdf["categoria"].fillna(CATEGORIA_DEFAULT)

    resumen = gdf["categoria"].value_counts()
    print("[siedco] Distribución de eventos por categoría:")
    for cat, n in resumen.items():
        print(f"         {cat}: {n:,} ({n/len(gdf)*100:.1f}%)")

    return gdf


def filtrar_periodo(gdf: gpd.GeoDataFrame, year: int) -> gpd.GeoDataFrame:
    """
    Filtra eventos por año calendario.

    Args:
        gdf:  GeoDataFrame retornado por cargar_eventos().
        year: Año de interés (ej. 2022, 2023).

    Returns:
        Subconjunto del GeoDataFrame donde fecha.dt.year == year.

    Raises:
        AssertionError: si la columna 'fecha' no es datetime.
        ValueError:     si no hay eventos en el año especificado.
    """
    assert "fecha" in gdf.columns, (
        "[siedco] El GeoDataFrame debe tener columna 'fecha'."
    )
    assert pd.api.types.is_datetime64_any_dtype(gdf["fecha"]), (
        "[siedco] La columna 'fecha' debe ser tipo datetime. "
        "Verifica que cargar_eventos() parseó la fecha correctamente."
    )

    gdf_filtrado = gdf[gdf["fecha"].dt.year == year].copy()

    if gdf_filtrado.empty:
        raise ValueError(
            f"[siedco] No se encontraron eventos para el año {year}. "
            f"Años disponibles en el dataset: {sorted(gdf['fecha'].dt.year.dropna().unique().tolist())}"
        )

    print(
        f"[siedco] Filtrado a {year}: {len(gdf_filtrado):,} eventos "
        f"({len(gdf_filtrado)/len(gdf)*100:.1f}% del total)."
    )
    return gdf_filtrado


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


def _categorizar_parcial(conducta: str) -> str:
    """
    Intenta categorizar por coincidencia parcial (substring) con el catálogo.
    Si ninguna clave del catálogo es substring de la conducta, retorna el default.
    """
    for key, categoria in CATALOGO_DELITOS.items():
        if key in conducta or conducta in key:
            return categoria
    return CATEGORIA_DEFAULT
