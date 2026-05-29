# =============================================================================
# Atlas Urabá — Makefile
# Bienestar Humano Territorial, Urabá, Antioquia
# =============================================================================

.DEFAULT_GOAL := help
ENV_NAME      := atlas-uraba
PYTHON        := python

# Colores para output
CYAN  := \033[36m
RESET := \033[0m
BOLD  := \033[1m

# ---------------------------------------------------------------------------
# Entorno
# ---------------------------------------------------------------------------

.PHONY: setup
setup: ## Crea el entorno conda y lo instala en modo editable con dependencias dev
	@echo "$(CYAN)Creando entorno conda '$(ENV_NAME)'...$(RESET)"
	conda env create -f environment.yml --name $(ENV_NAME) || \
		conda env update -f environment.yml --name $(ENV_NAME) --prune
	@echo "$(CYAN)Instalando paquete en modo editable...$(RESET)"
	conda run -n $(ENV_NAME) pip install -e ".[dev]"
	@echo "$(BOLD)Entorno listo. Activa con: conda activate $(ENV_NAME)$(RESET)"

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

.PHONY: db
db: ## Levanta PostGIS con Docker Compose (modo daemon)
	@echo "$(CYAN)Levantando PostGIS...$(RESET)"
	docker-compose up -d
	@echo "$(BOLD)PostGIS disponible en localhost:5432$(RESET)"

.PHONY: db-stop
db-stop: ## Detiene los contenedores Docker
	@echo "$(CYAN)Deteniendo contenedores...$(RESET)"
	docker-compose down

# ---------------------------------------------------------------------------
# Ingesta de datos
# ---------------------------------------------------------------------------

.PHONY: audit-osm
audit-osm: ## Ejecuta extracción y auditoría de datos OSM para Urabá
	@echo "$(CYAN)Extrayendo datos OSM...$(RESET)"
	$(PYTHON) src/ingestion/osm_extractor.py

# ---------------------------------------------------------------------------
# Calidad de código
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Corre toda la suite de tests con pytest
	@echo "$(CYAN)Ejecutando tests...$(RESET)"
	pytest tests/ -v

.PHONY: test-cov
test-cov: ## Tests con reporte de cobertura HTML
	@echo "$(CYAN)Ejecutando tests con cobertura...$(RESET)"
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
	@echo "$(BOLD)Reporte en htmlcov/index.html$(RESET)"

.PHONY: lint
lint: ## Linting con ruff sobre src/ y tests/
	@echo "$(CYAN)Verificando estilo con ruff...$(RESET)"
	ruff check src/ tests/

.PHONY: lint-fix
lint-fix: ## Aplica auto-correcciones de ruff
	@echo "$(CYAN)Auto-corrigiendo con ruff...$(RESET)"
	ruff check src/ tests/ --fix

.PHONY: format
format: ## Formatea código con black
	@echo "$(CYAN)Formateando con black...$(RESET)"
	black src/ tests/

.PHONY: format-check
format-check: ## Verifica formato sin modificar archivos
	black src/ tests/ --check

# ---------------------------------------------------------------------------
# Limpieza
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Elimina datos procesados y outputs generados
	@echo "$(CYAN)Limpiando datos procesados y outputs...$(RESET)"
	rm -rf data/processed/* data/outputs/*
	@echo "$(BOLD)Limpieza completada.$(RESET)"

.PHONY: clean-pyc
clean-pyc: ## Elimina archivos .pyc y directorios __pycache__
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true

.PHONY: clean-all
clean-all: clean clean-pyc ## Limpieza completa (datos + pyc)

# ---------------------------------------------------------------------------
# Desarrollo
# ---------------------------------------------------------------------------

.PHONY: notebook
notebook: ## Abre JupyterLab en el directorio notebooks/
	@echo "$(CYAN)Iniciando JupyterLab...$(RESET)"
	jupyter lab notebooks/

.PHONY: docs
docs: ## Genera documentación con mkdocs (requiere mkdocs instalado)
	mkdocs serve

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Muestra este mensaje de ayuda con todos los targets disponibles
	@echo ""
	@echo "$(BOLD)Atlas Urabá — Comandos disponibles$(RESET)"
	@echo "============================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
