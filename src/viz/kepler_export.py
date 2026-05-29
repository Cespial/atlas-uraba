"""
Exportación de resultados Atlas Urabá a Kepler.gl y formatos web.

Genera visualizaciones interactivas del índice de bienestar humano territorial
listas para publicación en web o exploración interna.
"""
from __future__ import annotations

import json
import subprocess
import shutil
from pathlib import Path

import geopandas as gpd
import pandas as pd


# ---------------------------------------------------------------------------
# Constantes de configuración visual
# ---------------------------------------------------------------------------

_KEPLER_CONFIG = {
    "version": "v1",
    "config": {
        "visState": {
            "layers": [
                {
                    "id": "atlas-score-layer",
                    "type": "geojson",
                    "config": {
                        "dataId": "atlas_manzanas",
                        "label": "Atlas Score — Bienestar",
                        "color": [255, 153, 31],
                        "highlightColor": [252, 242, 26, 255],
                        "columns": {"geojson": "_geojson"},
                        "isVisible": True,
                        "visConfig": {
                            "opacity": 0.8,
                            "strokeOpacity": 0.2,
                            "thickness": 0.5,
                            "strokeColor": [255, 255, 255],
                            "colorRange": {
                                "name": "Divergente Bienestar",
                                "type": "diverging",
                                "category": "Custom",
                                "colors": [
                                    "#d73027",  # rojo — bajo bienestar
                                    "#f46d43",
                                    "#fdae61",
                                    "#fee08b",
                                    "#d9ef8b",
                                    "#a6d96a",
                                    "#66bd63",
                                    "#1a9850",  # verde — alto bienestar
                                ],
                            },
                            "strokeColorRange": {
                                "name": "Global Warming",
                                "type": "sequential",
                                "category": "Uber",
                                "colors": ["#5A1846", "#900C3F", "#C70039", "#E3611C", "#F1920E", "#FFC300"],
                            },
                            "radius": 10,
                            "sizeRange": [0, 10],
                            "radiusRange": [0, 50],
                            "heightRange": [0, 500],
                            "elevationScale": 5,
                            "enableElevationZoomFactor": True,
                            "stroked": True,
                            "filled": True,
                            "enable3d": False,
                            "wireframe": False,
                        },
                        "colorField": {
                            "name": "atlas_score",
                            "type": "real",
                        },
                        "colorScale": "quantize",
                    },
                    "visualChannels": {
                        "colorField": {"name": "atlas_score", "type": "real"},
                        "colorScale": "quantize",
                        "strokeColorField": None,
                        "strokeColorScale": "quantile",
                        "sizeField": None,
                        "sizeScale": "linear",
                        "heightField": None,
                        "heightScale": "linear",
                        "radiusField": None,
                        "radiusScale": "linear",
                    },
                }
            ],
            "interactionConfig": {
                "tooltip": {
                    "fieldsToShow": {
                        "atlas_manzanas": [
                            {"name": "cod_manzana", "format": None},
                            {"name": "municipio_nombre", "format": None},
                            {"name": "atlas_score", "format": ".3f"},
                            {"name": "zona_atlas", "format": None},
                            {"name": "score_accesibilidad", "format": ".3f"},
                            {"name": "score_ambiental", "format": ".3f"},
                            {"name": "score_socioeconomico", "format": ".3f"},
                            {"name": "score_seguridad", "format": ".3f"},
                        ]
                    },
                    "compareMode": False,
                    "compareType": "absolute",
                    "enabled": True,
                },
                "geocoder": {"enabled": False},
                "brush": {"size": 0.5, "enabled": False},
                "coordinate": {"enabled": False},
            },
            "layerBlending": "normal",
        },
        "mapState": {
            "bearing": 0,
            "dragRotate": False,
            "latitude": 7.88,
            "longitude": -76.65,
            "pitch": 0,
            "zoom": 9,
            "isSplit": False,
        },
        "mapStyle": {
            "styleType": "dark",
            "topLayerGroups": {},
            "visibleLayerGroups": {
                "label": True,
                "road": True,
                "border": False,
                "building": True,
                "water": True,
                "land": True,
                "3d building": False,
            },
        },
    },
}

_ZONA_ATLAS_CONFIG = {
    "id": "zona-atlas-layer",
    "type": "geojson",
    "config": {
        "dataId": "atlas_manzanas",
        "label": "Zonas Atlas (LISA)",
        "isVisible": False,
        "visConfig": {
            "opacity": 0.75,
            "stroked": True,
            "filled": True,
            "strokeOpacity": 0.3,
            "thickness": 0.5,
            "colorRange": {
                "name": "Zonas Atlas",
                "type": "qualitative",
                "category": "Custom",
                "colors": {
                    "HH": "#1a9850",
                    "LL": "#d73027",
                    "HL": "#fee08b",
                    "LH": "#4575b4",
                    "NS": "#aaaaaa",
                },
            },
        },
        "colorField": {"name": "zona_atlas", "type": "string"},
        "colorScale": "ordinal",
    },
    "visualChannels": {
        "colorField": {"name": "zona_atlas", "type": "string"},
        "colorScale": "ordinal",
    },
}

# Columnas que se exportan en el GeoJSON ligero para web
_COLS_WEB = [
    "cod_manzana",
    "atlas_score",
    "zona_atlas",
    "score_accesibilidad",
    "score_ambiental",
    "score_socioeconomico",
    "score_seguridad",
    "municipio_nombre",
]


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------


def exportar_kepler(
    manzanas_atlas: gpd.GeoDataFrame,
    output_html: Path,
    titulo: str = "Atlas Urabá — Bienestar Humano Territorial",
) -> None:
    """
    Genera un HTML interactivo de Kepler.gl con el índice Atlas.

    La capa principal colorea cada manzana según atlas_score (0-1) usando
    una paleta divergente rojo→verde (rojo = bajo bienestar, verde = alto).
    Opacidad 0.8. Si existe la columna 'zona_atlas', se agrega una segunda
    capa de Zonas Atlas (HH/LL/HL/LH/NS) oculta por defecto.

    Args:
        manzanas_atlas: GeoDataFrame con columnas atlas_score y geometría.
        output_html: Ruta de salida del archivo .html.
        titulo: Título del mapa mostrado en la interfaz.
    """
    try:
        from keplergl import KeplerGl
    except ImportError:
        raise ImportError(
            "keplergl no está instalado. Instala con: pip install keplergl"
        )

    output_html = Path(output_html)
    output_html.parent.mkdir(parents=True, exist_ok=True)

    # Proyectar a WGS84 para Kepler
    gdf = manzanas_atlas.to_crs("EPSG:4326").copy()

    # Asegurar columnas requeridas
    if "atlas_score" not in gdf.columns:
        raise ValueError("El GeoDataFrame debe tener la columna 'atlas_score'.")

    # Construir config: agregar capa zona_atlas si existe
    config = json.loads(json.dumps(_KEPLER_CONFIG))  # deep copy
    if "zona_atlas" in gdf.columns:
        config["config"]["visState"]["layers"].append(_ZONA_ATLAS_CONFIG)

    # Seleccionar columnas disponibles para exportar
    cols_disponibles = [c for c in _COLS_WEB if c in gdf.columns] + ["geometry"]
    gdf_export = gdf[cols_disponibles]

    # Serializar geometría como GeoJSON para keplergl
    geojson_data = json.loads(gdf_export.to_json())

    mapa = KeplerGl(height=700, config=config)
    mapa.add_data(data=geojson_data, name="atlas_manzanas")

    mapa.save_to_html(file_name=str(output_html), center_map=True, read_only=False)
    print(f"[kepler_export] HTML generado: {output_html}")


def exportar_geojson(
    manzanas_atlas: gpd.GeoDataFrame,
    output_path: Path,
) -> None:
    """
    Exporta GeoJSON ligero para visualización web.

    Solo incluye las columnas necesarias:
    cod_manzana, atlas_score, zona_atlas, score_accesibilidad,
    score_ambiental, score_socioeconomico, score_seguridad, municipio_nombre.
    Las columnas ausentes se omiten sin error.

    Args:
        manzanas_atlas: GeoDataFrame con resultados del índice Atlas.
        output_path: Ruta de salida del archivo .geojson.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    gdf = manzanas_atlas.to_crs("EPSG:4326").copy()

    cols_disponibles = [c for c in _COLS_WEB if c in gdf.columns]
    if not cols_disponibles:
        raise ValueError(
            "El GeoDataFrame no contiene ninguna de las columnas esperadas para exportación web."
        )

    gdf_export = gdf[cols_disponibles + ["geometry"]]

    # Redondear scores a 4 decimales para reducir tamaño
    score_cols = [c for c in cols_disponibles if c.startswith("score") or c == "atlas_score"]
    for col in score_cols:
        gdf_export[col] = gdf_export[col].round(4)

    gdf_export.to_file(str(output_path), driver="GeoJSON")
    size_kb = output_path.stat().st_size / 1024
    print(f"[kepler_export] GeoJSON exportado: {output_path} ({size_kb:.1f} KB)")


def exportar_pmtiles(geojson_path: Path, output_path: Path) -> None:
    """
    Convierte GeoJSON a PMTiles usando tippecanoe.

    PMTiles es un formato de teselas vectoriales de archivo único, ideal
    para publicación estática en S3/Cloudflare R2 sin servidor de tiles.

    Si tippecanoe no está instalado, imprime instrucciones y omite la
    conversión sin lanzar excepción.

    Args:
        geojson_path: Ruta al archivo .geojson de entrada.
        output_path: Ruta de salida del archivo .pmtiles.
    """
    geojson_path = Path(geojson_path)
    output_path = Path(output_path)

    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON no encontrado: {geojson_path}")

    tippecanoe_bin = shutil.which("tippecanoe")
    if tippecanoe_bin is None:
        print(
            "[kepler_export] tippecanoe no encontrado. Para instalar:\n"
            "  macOS:  brew install tippecanoe\n"
            "  Ubuntu: apt-get install tippecanoe\n"
            "  Docker: docker run --rm -v $(pwd):/data ghcr.io/felt/tippecanoe ...\n"
            "  Alternativa: https://github.com/felt/tippecanoe\n"
            "[kepler_export] Conversión a PMTiles omitida."
        )
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        tippecanoe_bin,
        "--output", str(output_path),
        "--layer", "atlas_manzanas",
        "--minimum-zoom", "8",
        "--maximum-zoom", "16",
        "--coalesce-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--force",  # sobreescribir si existe
        str(geojson_path),
    ]

    print(f"[kepler_export] Generando PMTiles: {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"tippecanoe falló con código {result.returncode}:\n{result.stderr}"
        )

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[kepler_export] PMTiles generado: {output_path} ({size_mb:.2f} MB)")
