"""
Enriquecimiento de manzanas MGN 2024 con variables del CNPV 2018.

El CNPV 2018 integrado con el MGN tiene coordenadas de centroide por manzana.
Como el marco geoestadístico 2018 y 2024 difieren, se hace un join espacial
por proximidad de centroides (sjoin_nearest) para asignar variables CNPV
a cada manzana del MGN 2024.

Columnas derivadas (usadas por los indicadores):
    pct_sin_acueducto       → IVI (calidad de vivienda)
    pct_sin_alcantarillado  → IVI
    pct_sin_energia         → IVI
    personas_por_hogar      → ISV (suficiencia/hacinamiento)
    escolaridad_ponderada   → IEJ (escolaridad jefe de hogar)
    hogares_por_persona     → IRH (resiliencia hogares)
    pct_edad_productiva     → IEM (empleo, proxy de PEA)
    pct_edu_secundaria_mas  → IPJ (participación juvenil)
"""
from __future__ import annotations

import warnings
import geopandas as gpd
import numpy as np
import pandas as pd
from pathlib import Path

CNPV_PATH = Path("data/processed/manzanas/cnpv2018_uraba.csv")
MGN_PATH = Path("data/processed/manzanas/mgn2024_manzanas_uraba_8mun.gpkg")


def cargar_cnpv(path: Path = CNPV_PATH) -> gpd.GeoDataFrame:
    """Lee el CSV del CNPV 2018 y crea un GeoDataFrame de puntos con los centroides."""
    df = pd.read_csv(path, dtype={"MPIO_CDPMP": str})
    df["MPIO_CDPMP"] = df["MPIO_CDPMP"].astype(str).str.zfill(5)

    # Crear geometría desde coordenadas de centroide por manzana
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["LONGITUD"], df["LATITUD"]),
        crs="EPSG:4326",
    )
    return gdf


def calcular_variables_cnpv(cnpv: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Calcula las variables derivadas que usan los indicadores socioeconómicos.
    Todas las divisiones usan denominadores protegidos con max(..., 1) para evitar NaN.
    """
    df = cnpv.copy()

    total_viv = df["TVIVIENDA"].clip(lower=1)
    total_per = df["TP27_PERSO"].clip(lower=1)
    total_hog = df["TP16_HOG"].clip(lower=1)

    # ── IVI: Calidad de vivienda (servicios básicos) ─────────────────────────
    # Proxy: % viviendas sin servicios básicos (acueducto + alcantarillado + energía)
    df["pct_sin_acueducto"] = df["TP19_ACU_2"] / total_viv
    df["pct_sin_alcantarillado"] = df["TP19_ALC_2"] / total_viv
    df["pct_sin_energia"] = df["TP19_EE_2"] / total_viv
    # IVI compuesto = promedio de las 3 carencias (mayor = peor)
    df["pct_mat_inadecuada"] = (
        df["pct_sin_acueducto"]
        + df["pct_sin_alcantarillado"]
        + df["pct_sin_energia"]
    ) / 3.0

    # ── ISV: Hacinamiento (personas por hogar) ───────────────────────────────
    # Mayor personas/hogar = mayor hacinamiento (valor alto = peor)
    df["personas_por_hogar"] = df["TP27_PERSO"] / total_hog
    # Normalizar como tasa de hacinamiento: ponderado por umbral de 3 personas/hogar
    df["pct_hacinamiento"] = (df["personas_por_hogar"] / 3.0).clip(upper=1.0)
    df["pct_hacinamiento_severo"] = (df["personas_por_hogar"] / 5.0).clip(upper=1.0)

    # ── IEJ: Escolaridad (nivel educativo promedio ponderado) ────────────────
    # Escala: primaria=1, secundaria=2, superior=3, posgrado=4
    edu_total = (
        df["TP51PRIMAR"]
        + df["TP51SECUND"]
        + df["TP51SUPERI"]
        + df["TP51POSTGR"]
    ).clip(lower=1)
    df["escolaridad_ponderada"] = (
        df["TP51PRIMAR"] * 1
        + df["TP51SECUND"] * 2
        + df["TP51SUPERI"] * 3
        + df["TP51POSTGR"] * 4
    ) / edu_total

    # ── IRH: Resiliencia de hogares ──────────────────────────────────────────
    # Proxy: hogares / personas → más pequeños = más vulnerables (monoparental)
    # Inverso: mayor ratio = hogares más pequeños = más riesgo monoparental
    df["hogares_por_persona"] = df["TP16_HOG"] / total_per
    # IRH input: proporción de hogares pequeños (proxy monoparental)
    df["pct_monoparental"] = df["hogares_por_persona"]  # compatible con IndicadorResiliencia

    # ── IEM: Empleo (proxy: % en edad productiva 15-59 años) ─────────────────
    # TP34_x_EDA: grupos etarios (sumados ~15-59 años = TP34_4 a TP34_8)
    edad_productiva = (
        df["TP34_4_EDA"]   # ~15-24 años
        + df["TP34_5_EDA"] # ~25-34 años
        + df["TP34_6_EDA"] # ~35-44 años
        + df["TP34_7_EDA"] # ~45-54 años
        + df["TP34_8_EDA"] # ~55-64 años
    )
    df["pct_edad_productiva"] = edad_productiva / total_per
    df["tasa_ocupacion"] = df["pct_edad_productiva"]  # compatible con IndicadorEmpleo

    # ── IPJ: Participación juvenil (proxy: % con educación secundaria o más) ─
    edu_secundaria_mas = df["TP51SECUND"] + df["TP51SUPERI"] + df["TP51POSTGR"]
    df["pct_edu_secundaria_mas"] = edu_secundaria_mas / total_per
    df["pct_jovenes_activos"] = df["pct_edu_secundaria_mas"]  # compatible con IndicadorParticipacion

    # ── Variables de población base ──────────────────────────────────────────
    df["poblacion_cnpv"] = df["TP27_PERSO"]
    df["hogares_cnpv"] = df["TP16_HOG"]
    df["viviendas_cnpv"] = df["TVIVIENDA"]
    df["densidad_cnpv"] = df["DENSIDAD"]

    return df


def unir_cnpv_a_mgn(
    mgn: gpd.GeoDataFrame,
    cnpv: gpd.GeoDataFrame,
    max_dist_m: float = 500.0,
) -> gpd.GeoDataFrame:
    """
    Une variables del CNPV 2018 al GeoDataFrame de manzanas MGN 2024
    mediante sjoin_nearest por proximidad de centroides.

    Args:
        mgn: GeoDataFrame de manzanas MGN 2024 (polígonos, EPSG:4326).
        cnpv: GeoDataFrame del CNPV 2018 con variables derivadas (puntos, EPSG:4326).
        max_dist_m: Distancia máxima en metros para el join. Manzanas más alejadas
                    quedan con NaN en las columnas CNPV.

    Returns:
        GeoDataFrame de manzanas MGN enriquecido con columnas CNPV.
    """
    mgn_proj = mgn.to_crs("EPSG:3116").copy()
    cnpv_proj = cnpv.to_crs("EPSG:3116").copy()

    # Usar centroide de manzana MGN como punto de join
    mgn_centroids = mgn_proj.copy()
    mgn_centroids["geometry"] = mgn_proj.geometry.centroid

    # Columnas CNPV a transferir
    cols_cnpv = [
        "pct_mat_inadecuada",
        "pct_sin_acueducto", "pct_sin_alcantarillado", "pct_sin_energia",
        "pct_hacinamiento", "pct_hacinamiento_severo",
        "personas_por_hogar",
        "escolaridad_ponderada",
        "pct_monoparental", "hogares_por_persona",
        "pct_edad_productiva", "tasa_ocupacion",
        "pct_edu_secundaria_mas", "pct_jovenes_activos",
        "poblacion_cnpv", "hogares_cnpv", "viviendas_cnpv", "densidad_cnpv",
    ]
    cols_existentes = [c for c in cols_cnpv if c in cnpv_proj.columns]

    joined = gpd.sjoin_nearest(
        mgn_centroids[["cod_manzana", "geometry"]],
        cnpv_proj[cols_existentes + ["geometry"]],
        how="left",
        max_distance=max_dist_m,
        distance_col="_dist_cnpv",
    )

    # Conservar solo la primera coincidencia por manzana (por si hay duplicados)
    joined = joined.drop_duplicates(subset="cod_manzana")

    # Añadir columnas CNPV al MGN original (conservando geometría de polígono)
    mgn_result = mgn.copy()
    for col in cols_existentes:
        if col in joined.columns:
            mapping = joined.set_index("cod_manzana")[col]
            mgn_result[col] = mgn_result["cod_manzana"].map(mapping)

    # Registrar cobertura del join
    n_sin_datos = mgn_result["pct_mat_inadecuada"].isna().sum()
    if n_sin_datos > 0:
        warnings.warn(
            f"{n_sin_datos}/{len(mgn_result)} manzanas sin datos CNPV 2018 "
            f"(distancia > {max_dist_m}m). Se imputará con la mediana.",
            UserWarning,
            stacklevel=2,
        )

    return mgn_result


def enriquecer_manzanas(
    mgn_path: Path = MGN_PATH,
    cnpv_path: Path = CNPV_PATH,
    output_path: Path | None = None,
) -> gpd.GeoDataFrame:
    """
    Pipeline completo: carga MGN + CNPV, calcula variables derivadas y une.

    Args:
        mgn_path: Ruta al GeoPackage de manzanas MGN 2024.
        cnpv_path: Ruta al CSV del CNPV 2018.
        output_path: Si se provee, guarda el resultado como GeoPackage.

    Returns:
        GeoDataFrame de manzanas enriquecidas con variables CNPV.
    """
    print(f"[cnpv] Cargando MGN 2024: {mgn_path}")
    mgn = gpd.read_file(mgn_path)
    print(f"[cnpv] {len(mgn):,} manzanas cargadas")

    print(f"[cnpv] Cargando CNPV 2018: {cnpv_path}")
    cnpv_raw = cargar_cnpv(cnpv_path)
    cnpv_vars = calcular_variables_cnpv(cnpv_raw)
    print(f"[cnpv] {len(cnpv_vars):,} manzanas CNPV con variables calculadas")

    print("[cnpv] Uniendo por proximidad de centroides...")
    mgn_enriquecido = unir_cnpv_a_mgn(mgn, cnpv_vars)

    cobertura = mgn_enriquecido["pct_mat_inadecuada"].notna().mean() * 100
    print(f"[cnpv] Cobertura del join: {cobertura:.1f}%")

    if output_path:
        mgn_enriquecido.to_file(str(output_path), driver="GPKG")
        print(f"[cnpv] Guardado: {output_path}")

    return mgn_enriquecido


if __name__ == "__main__":
    out = Path("data/processed/manzanas/mgn2024_cnpv_uraba.gpkg")
    gdf = enriquecer_manzanas(output_path=out)
    print(gdf[["cod_manzana", "municipio", "pct_mat_inadecuada",
               "pct_hacinamiento", "escolaridad_ponderada",
               "tasa_ocupacion", "pct_jovenes_activos"]].head(10).to_string())
