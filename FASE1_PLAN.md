# Fase 1 — Plan de investigación y estructuración

**Objetivo:** Tener claridad metodológica y técnica completa para poder arrancar
la construcción (Fase 2) sin sorpresas. Al final de esta fase: pipeline piloto
funcionando para Apartadó con 3-4 indicadores end-to-end.

## Sprint 1 — Semanas 1-2: Auditoría de datos existentes

### Tareas

- [ ] **Inventariar data-lakes propios de Urabá**
  - Qué capas existen, en qué formato, a qué escala geográfica y qué fecha tienen
  - Compatibilidad con PostGIS/GeoPandas
  - Ejecutar: `notebooks/01_auditoria_osm.ipynb`

- [ ] **Inventariar gemelo digital de Urabá**
  - Qué APIs expone (REST, GraphQL, archivos)
  - Formatos de exportación (GeoJSON, IFC, CityGML, shapefile)
  - Geometrías disponibles: ¿tiene manzanas, predios, edificaciones?

- [ ] **Auditar cobertura OSM para los 8 municipios**
  - Ejecutar `src/ingestion/osm_extractor.py` para cada municipio
  - Guardar reporte en `data/processed/auditoria_osm_uraba.csv`
  - Criterio: si < 50% de equipamientos reales están en OSM → necesitamos IGAC

- [ ] **Descargar MGN 2024 y CNPV 2018 para Urabá**
  - MGN: https://www.arcgis.com/home/item.html?id=da6856c2040c4098831605384715d35b
  - CNPV: https://geoportal.dane.gov.co/geovisores/sociedad/cnpv2018-detallado/
  - Ejecutar: `notebooks/02_dane_cnpv_manzana.ipynb`

### Entregable Sprint 1
Documento `docs/referencias/auditoria_datos.md` con:
- Tabla de cobertura OSM por municipio
- Inventario de data-lakes propios
- Lista de brechas de datos identificadas

---

## Sprint 2 — Semanas 3-4: Decisiones metodológicas

### Tareas

- [ ] **Cuantificar supresión DANE a nivel manzana**
  - ¿Qué % de manzanas en Urabá tienen datos suprimidos (< 3 unidades)?
  - Si > 20% → confirmar uso de `tobler` para disagregación
  - Ejecutar: `notebooks/02_dane_cnpv_manzana.ipynb` (sección supresión)

- [ ] **Definir lista final de indicadores para Urabá**
  - Revisar `docs/metodologia/indicadores.md`
  - Decidir qué indicadores adicionales incluir (desplazamiento, manglares, conectividad)
  - Pesos por dimensión (igual o diferenciado)

- [ ] **Decidir unidad mínima**
  - ¿Manzana censal DANE (MGN 2024) o predio catastral IGAC?
  - Recomendado: manzana censal DANE (consistente con CNPV 2018)

- [ ] **Probar interpolación areal con tobler**
  - Datos piloto de Apartadó: sector censal → manzana
  - Comparar area_interpolate vs masked_area_interpolate (dasymetría con edificaciones IGAC)
  - Ejecutar: `notebooks/03_igac_catastro.ipynb`

### Entregable Sprint 2
- `docs/metodologia/indicadores.md` finalizado y aprobado
- Decisión documentada: unidad mínima, método de disagregación

---

## Sprint 3 — Semanas 5-6: Pipeline piloto (Apartadó)

### Tareas

- [ ] **Levantar entorno Docker**
  - `docker-compose -f infra/docker-compose.yml up -d`
  - Verificar PostGIS + pgRouting funcionando

- [ ] **Pipeline piloto end-to-end para Apartadó**
  - 3-4 indicadores: ICV (NDVI), IVI (calidad vivienda), ISAL (salud), IAV (áreas verdes)
  - Ejecutar ingesta → procesamiento → normalización → mapa en Kepler.gl

- [ ] **Primer mapa Atlas Urabá**
  - Kepler.gl con manzanas de Apartadó coloreadas por índice compuesto piloto
  - Screenshot en `docs/referencias/`

- [ ] **Documento de brechas para Fase 2**
  - Qué funcionó, qué necesita trabajo adicional, estimación de esfuerzo Fase 2

### Entregable Sprint 3
- Pipeline funcionando para Apartadó (notebook ejecutable de principio a fin)
- Mapa Kepler.gl exportado
- README final de Fase 1 aprobado

---

## Preguntas abiertas (responder en Sprint 1)

1. ¿Cuál es la cobertura real de OSM en los 8 municipios?
2. ¿Qué % de manzanas DANE tienen supresión de privacidad en Urabá?
3. ¿Cómo integrar el gemelo digital? ¿Qué APIs/formatos expone?
4. ¿Existe ya algún índice territorial calculado para Urabá en datos.gov.co o DANE?
