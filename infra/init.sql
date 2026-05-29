-- Extensiones espaciales
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- Esquemas principales
CREATE SCHEMA IF NOT EXISTS raw;        -- datos ingestados sin transformar
CREATE SCHEMA IF NOT EXISTS staging;    -- datos limpios / transformados
CREATE SCHEMA IF NOT EXISTS indicators; -- indicadores calculados por manzana
CREATE SCHEMA IF NOT EXISTS outputs;    -- índice final y zonas atlas
