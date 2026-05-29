# Atlas Urabá

**Atlas de Bienestar Humano Territorial para la región de Urabá, Antioquia, Colombia**

Plataforma de indicadores socioespaciales a nivel de manzana, inspirada en la
[Matriz BHT (MBHT)](https://matrizbht.cl) desarrollada por el CIT de la Universidad Adolfo Ibáñez en Chile.

---

## ¿Qué es?

Atlas Urabá mide la calidad de vida en cada manzana urbana y entidad rural de la región,
combinando 18+ indicadores en 4 dimensiones:

| Dimensión | Indicadores |
|-----------|-------------|
| **Accesibilidad** | Áreas verdes, salud, educación, deportivos, culturales, servicios públicos |
| **Ambiental** | Cobertura vegetal (NDVI), amplitud térmica anual |
| **Socioeconómica** | Calidad de vivienda, hacinamiento, escolaridad, empleo, participación juvenil |
| **Seguridad** | Delitos graves/leves contra personas y propiedad |

El resultado: un índice compuesto 0-1 por manzana + **Zonas Atlas** (clusters espaciales
de alto/bajo bienestar via autocorrelación LISA).

---

## Municipios cubiertos

Apartadó · Chigorodó · Carepa · Turbo · Necoclí · San Pedro de Urabá · San Juan de Urabá · Arboletes

---

## Estado del proyecto

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fase 1** | 🔄 En curso | Investigación, auditoría de datos, pipeline piloto (Apartadó) |
| **Fase 2** | ⏳ Pendiente | Construcción completa — todos los municipios, plataforma web |

Ver plan detallado en [FASE1_PLAN.md](FASE1_PLAN.md).

---

## Inicio rápido

```bash
# 1. Clonar
git clone https://github.com/Cespial/atlas-uraba.git
cd atlas-uraba

# 2. Entorno Python
conda env create -f infra/environment.yml
conda activate atlas-uraba

# 3. Base de datos espacial
docker-compose -f infra/docker-compose.yml up -d

# 4. Ejecutar auditoría OSM (primer paso de Fase 1)
jupyter notebook notebooks/01_auditoria_osm.ipynb
```

---

## Arquitectura

```
PostgreSQL/PostGIS  ←  DANE · IGAC · OSM · REPS · SIMAT · SIEDCO · GEE
       ↓
Pipeline Python (GeoPandas · OSMnx · r5py · tobler · PySAL-esda)
       ↓
18+ Indicadores normalizados 0-1 por manzana
       ↓
Índice compuesto + Zonas Atlas (LISA)
       ↓
Kepler.gl / Mapbox GL JS
```

Stack completo: [docs/arquitectura/stack.md](docs/arquitectura/stack.md)

---

## Fuentes de datos principales

- [DANE CNPV 2018 (manzana censal)](https://geoportal.dane.gov.co/geovisores/sociedad/cnpv2018-detallado/)
- [IGAC Catastro Multipropósito](https://geoportal.igac.gov.co/contenido/datos-abiertos-catastro)
- [OpenStreetMap Colombia](https://download.geofabrik.de/south-america/colombia.html)
- Google Earth Engine (Sentinel-2, Landsat 8/9)
- REPS MinSalud · SIMAT MEN · SIEDCO Policía

Ver inventario completo: [docs/metodologia/fuentes.md](docs/metodologia/fuentes.md)

---

## Repositorios de referencia

| Repo | Rol |
|------|-----|
| [GHSCI](https://github.com/healthysustainablecities/global-indicators) | Referente arquitectónico principal (mismo stack) |
| [CS_Urban_Indicators](https://github.com/CityScope/CS_Urban_Indicators) | Arquitectura Indicator/CompositeIndicator |
| [dep_index](https://github.com/geomarker-io/dep_index) | Metodología PCA + normalización 0-1 |
| [accesibilidad-urbana](https://github.com/Observatorio-Ciudades/accesibilidad-urbana) | Referente latinoamericano |

---

## Licencia

MIT
