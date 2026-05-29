# Indicadores — Atlas Urabá

Adaptación de los 18 indicadores de la MBHT chilena al contexto de Urabá, Antioquia.
Unidad geográfica mínima: **manzana censal DANE** (urbana) / **entidad rural** (rural).

## Dimensión 1 — Accesibilidad

| Clave | Indicador | Medida | Fuente Colombia | Estado |
|-------|-----------|--------|-----------------|--------|
| IAV | Áreas Verdes | m² de área verde accesible por habitante (radio 800m peatonal) | OSM + IGAC + trabajo de campo | Pendiente |
| IDEP | Equipamientos Deportivos | m² de canchas/estadios por habitante | OSM + IDRD + alcaldías | Pendiente |
| ICUL | Equipamientos Culturales | m² de equipamiento cultural por habitante | OSM + MinCulturas | Pendiente |
| ISAL | Equipamientos de Salud | m² de salud pública y privada por habitante | REPS MinSalud (geocodificado) | Pendiente |
| ISER | Servicios Públicos | Tasa de servicios cada 1.000 hab. | OSM + catastro IGAC | Pendiente |
| ISE | Educación | Matrículas disponibles por niño/a 4-18 años | SIMAT MEN | Pendiente |

**Método de accesibilidad:** análisis de red peatonal (OSMnx + pgRouting) desde el centroide
de cada manzana hasta la entrada real del equipamiento (no radio buffer simple).

## Dimensión 2 — Ambiental

| Clave | Indicador | Medida | Fuente | Estado |
|-------|-----------|--------|--------|--------|
| ICV | Cobertura Vegetal | % de superficie con vegetación (NDVI) | Sentinel-2 vía Google Earth Engine | Pendiente |
| IATA | Amplitud Térmica Anual | Diferencia °C entre LST fría y cálida | Landsat 8/9 vía GEE | Pendiente |

**Nota Urabá:** ICV incluirá cobertura de bosque húmedo tropical y manglares,
variables de alta relevancia para la región que no existen en la MBHT chilena.

## Dimensión 3 — Socioeconómica

| Clave | Indicador | Medida | Fuente | Inversión |
|-------|-----------|--------|--------|-----------|
| IVI | Calidad de Vivienda | % viviendas con materiales insuficientes (paredes/piso/techo) | CNPV 2018 | Sí (más alto = peor) |
| ISV | Suficiencia de Vivienda | Hacinamiento + hacinamiento severo | CNPV 2018 | Sí |
| IEJ | Escolaridad Jefe de Hogar | Promedio años de estudio | CNPV 2018 | No |
| IRH | Resiliencia de Hogares | Inverso de % hogares monoparentales | CNPV 2018 | Sí |
| IEM | Empleo | Proporción de PEA ocupada | CNPV 2018 | No |
| IPJ | Participación Juvenil | % jóvenes 15-24 que trabajan o estudian | CNPV 2018 | No |

**Brecha crítica:** datos CNPV 2018 pueden tener supresión en manzanas pequeñas.
Usar `tobler` (interpolación areal) para disagregar de sector → manzana cuando sea necesario.

## Dimensión 4 — Seguridad

| Clave | Indicador | Fuente | Estado |
|-------|-----------|--------|--------|
| IGPE | Delitos Graves contra Personas | SIEDCO Policía + datos.gov.co | Pendiente |
| IGPR | Delitos Graves contra Propiedad | SIEDCO + datos.gov.co | Pendiente |
| ILPE | Delitos Leves contra Personas | SIEDCO | Pendiente |
| ILPR | Delitos Leves contra Propiedad | SIEDCO | Pendiente |

**Nota Urabá:** Complementar con datos de desplazamiento forzado (UARIV),
confinamiento (OCHA) y presencia de grupos armados (Defensoría del Pueblo),
variables sin equivalente en la MBHT chilena.

## Indicadores adicionales propuestos para Urabá

| Clave | Indicador | Justificación |
|-------|-----------|---------------|
| IDES | Desplazamiento | Hogares víctimas de desplazamiento — alta relevancia en Urabá |
| ICON | Conectividad | Acceso a internet / telefonía — brecha digital en zonas rurales |
| IMAN | Cobertura Manglares | Ecosistema estratégico del Urabá Antioqueño |

## Normalización

- Todos los indicadores se normalizan a escala **0-1 nacional** (dentro de Urabá inicialmente).
- Variables negativas (más alto = peor) se **invierten**: `valor_normalizado = 1 - ((x - min) / (max - min))`
- Índice compuesto: **promedio ponderado de dimensiones** (pesos iguales por defecto; ajustables).
- Zonas Atlas: **autocorrelación espacial LISA** (Moran local) → HH, LL, HL, LH, NS.
