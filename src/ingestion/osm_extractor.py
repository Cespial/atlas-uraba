"""
Extracción de datos OpenStreetMap para los municipios de Urabá.

Descarga vía OSMnx: red vial, equipamientos (amenities), edificaciones.
Municipios cubiertos: Apartadó, Chigorodó, Carepa, Turbo, Necoclí,
                      San Pedro de Urabá, San Juan de Urabá, Arboletes.
"""
import osmnx as ox
import geopandas as gpd
from pathlib import Path

MUNICIPIOS_URABA = [
    "Apartadó, Antioquia, Colombia",
    "Chigorodó, Antioquia, Colombia",
    "Carepa, Antioquia, Colombia",
    "Turbo, Antioquia, Colombia",
    "Necoclí, Antioquia, Colombia",
    "San Pedro de Urabá, Antioquia, Colombia",
    "San Juan de Urabá, Antioquia, Colombia",
    "Arboletes, Antioquia, Colombia",
]

AMENITY_TAGS = {
    "amenity": ["hospital", "clinic", "health_post", "school", "university",
                "college", "kindergarten", "library", "community_centre",
                "police", "fire_station"],
    "leisure": ["park", "nature_reserve", "garden", "sports_centre",
                "pitch", "stadium"],
    "shop": ["supermarket", "marketplace"],
}

OUTPUT_DIR = Path("data/raw/osm")


def descargar_red_vial(municipio: str, network_type: str = "walk") -> None:
    """Descarga red vial peatonal/vehicular para un municipio y guarda como GeoPackage."""
    slug = municipio.split(",")[0].lower().replace(" ", "_")
    out = OUTPUT_DIR / f"{slug}_red_{network_type}.gpkg"
    if out.exists():
        print(f"[skip] {out} ya existe")
        return
    G = ox.graph_from_place(municipio, network_type=network_type)
    nodes, edges = ox.graph_to_gdfs(G)
    edges.to_file(out, layer="edges", driver="GPKG")
    nodes.to_file(out, layer="nodes", driver="GPKG")
    print(f"[ok] red vial guardada: {out}")


def descargar_equipamientos(municipio: str) -> gpd.GeoDataFrame:
    """Descarga equipamientos (amenities, leisure, shops) de un municipio."""
    slug = municipio.split(",")[0].lower().replace(" ", "_")
    out = OUTPUT_DIR / f"{slug}_equipamientos.gpkg"
    if out.exists():
        print(f"[skip] {out} ya existe")
        return gpd.read_file(out)
    features = ox.features_from_place(municipio, tags=AMENITY_TAGS)
    features.to_file(out, driver="GPKG")
    print(f"[ok] equipamientos guardados: {out} ({len(features)} features)")
    return features


def auditar_cobertura_osm(municipio: str) -> dict:
    """
    Audita la cobertura de OSM para un municipio.
    Retorna métricas básicas de red y conteo de equipamientos.
    """
    G = ox.graph_from_place(municipio, network_type="walk")
    stats = ox.basic_stats(G)
    equipamientos = descargar_equipamientos(municipio)
    return {
        "municipio": municipio,
        "nodos": stats["n"],
        "aristas": stats["m"],
        "longitud_total_km": round(stats["edge_length_total"] / 1000, 1),
        "densidad_intersecciones": round(stats["intersection_density_km"], 2),
        "equipamientos_osm": len(equipamientos),
    }


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("=== Auditoría de cobertura OSM — Urabá ===")
    for municipio in MUNICIPIOS_URABA:
        try:
            reporte = auditar_cobertura_osm(municipio)
            print(reporte)
        except Exception as e:
            print(f"[error] {municipio}: {e}")
