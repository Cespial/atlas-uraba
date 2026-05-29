# Fuentes de datos — Atlas Urabá

## Geometría base

| Dataset | URL | Formato | Actualización |
|---------|-----|---------|---------------|
| MGN 2024 — Manzana Censal | https://www.arcgis.com/home/item.html?id=da6856c2040c4098831605384715d35b | Shapefile | 2024 |
| CNPV 2018 Geovisor Detallado | https://geoportal.dane.gov.co/geovisores/sociedad/cnpv2018-detallado/ | Shapefile + CSV | 2018 |
| IGAC Catastro Multipropósito | https://geoportal.igac.gov.co/contenido/datos-abiertos-catastro | Shapefile | 2024-2025 |
| ICDE — MGN oct 2024 | https://datos.icde.gov.co/datasets/0c133b73f9e644588768b76a2dda96b3 | SHP ZIP | Oct 2024 |

**Municipios Urabá actualizados (catastro multipropósito 2024):**
Apartadó · Chigorodó · Carepa · San Pedro de Urabá · Necoclí · San Juan de Urabá · Arboletes

## Datos censales socioeconómicos

| Dataset | URL | Nivel | Variables clave |
|---------|-----|-------|-----------------|
| CNPV 2018 Microdatos | https://microdatos.dane.gov.co/index.php/catalog/643 | Persona/hogar/vivienda | Materiales, hacinamiento, escolaridad, empleo |
| CNPV 2018 variables por manzana | https://geoportal.dane.gov.co/geovisores/sociedad/cnpv2018-detallado/ | Manzana censal | Población, hogares, vivienda |

**Códigos DIVIPOLA Urabá:**
- 05045 Apartadó
- 05147 Chigorodó
- 05120 Carepa
- 05837 Turbo
- 05544 Necoclí
- 05665 San Pedro de Urabá
- 05659 San Juan de Urabá
- 05051 Arboletes

## Equipamientos y servicios

| Dataset | URL | Uso |
|---------|-----|-----|
| REPS MinSalud | https://www.datos.gov.co (buscar "REPS") | Establecimientos de salud geocodificados |
| SIMAT MEN | https://www.datos.gov.co (buscar "SIMAT") | Establecimientos educativos + matrícula |
| OpenStreetMap Colombia | https://download.geofabrik.de/south-america/colombia.html | Red vial, amenities, edificaciones |
| Colombia en Mapas (IGAC) | https://www.colombiaenmapas.gov.co | Cartografía oficial |

## Ambiental (satélite)

| Dataset | Plataforma | Resolución | Uso |
|---------|-----------|------------|-----|
| Sentinel-2 SR | Google Earth Engine `COPERNICUS/S2_SR_HARMONIZED` | 10m | NDVI, cobertura vegetal |
| Landsat 8/9 | Google Earth Engine `LANDSAT/LC08/C02/T1_L2` | 30m | LST, amplitud térmica |
| Global Forest Watch | https://globalforestwatch.org | Variable | Deforestación, bosque húmedo |

## Seguridad

| Dataset | URL | Cobertura |
|---------|-----|-----------|
| SIEDCO Policía Nacional | https://www.datos.gov.co (buscar "SIEDCO") | Nacional por municipio |
| Homicidios georeferenciados | https://www.datos.gov.co/Seguridad-y-Defensa | Colombia |
| UARIV — Desplazamiento | https://www.unidadvictimas.gov.co/es/reportes | Por municipio |
| OCHA Colombia | https://www.unocha.org/colombia | Humanitario |

## Data-lakes propios (por inventariar en Sprint 1)

- [ ] Data-lake Urabá (inventariar capas disponibles, formatos, fechas)
- [ ] Gemelo digital de Urabá (documentar API, formatos de exportación, geometrías disponibles)
