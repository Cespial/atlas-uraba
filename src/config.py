"""
Configuración central del proyecto Atlas Urabá.
Todos los módulos deben importar constantes desde aquí para evitar valores dispersos.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_OUTPUTS = ROOT / "data" / "outputs"

# ---------------------------------------------------------------------------
# Sistemas de referencia de coordenadas
# ---------------------------------------------------------------------------
CRS_GEO = "EPSG:4326"           # WGS 84 geográfico
CRS_PROJ = "EPSG:3116"          # MAGNA-SIRGAS / Colombia Bogota (proyectado, metros)

# ---------------------------------------------------------------------------
# Municipios del Urabá antioqueño (DIVIPOLA)
# ---------------------------------------------------------------------------
DIVIPOLA_URABA: dict[str, str] = {
    "05045": "Apartadó",
    "05147": "Chigorodó",
    "05120": "Carepa",
    "05837": "Turbo",
    "05544": "Necoclí",
    "05665": "San Pedro de Urabá",
    "05659": "San Juan de Urabá",
    "05051": "Arboletes",
}

# ---------------------------------------------------------------------------
# Radios de accesibilidad peatonal (metros)
# ---------------------------------------------------------------------------
RADIO_AREAS_VERDES = 800
RADIO_SALUD_LOCAL = 1000
RADIO_SALUD_INTERCOMUNAL = 3000
RADIO_EDUCACION = 1000
RADIO_DEPORTIVOS_LOCAL = 600
RADIO_DEPORTIVOS_INTERCOMUNAL = 2000
RADIO_CULTURALES = 1200
RADIO_SERVICIOS = 1500

# ---------------------------------------------------------------------------
# Parámetros KDE seguridad
# ---------------------------------------------------------------------------
KDE_BANDWIDTH_M = 500
KDE_GRID_SIZE_M = 500

# ---------------------------------------------------------------------------
# Pesos por dimensión (deben sumar 1.0)
# ---------------------------------------------------------------------------
DIMENSION_WEIGHTS: dict[str, float] = {
    "accesibilidad": 0.25,
    "ambiental": 0.25,
    "socioeconomico": 0.25,
    "seguridad": 0.25,
}

assert abs(sum(DIMENSION_WEIGHTS.values()) - 1.0) < 1e-6, (
    "DIMENSION_WEIGHTS debe sumar 1.0"
)
