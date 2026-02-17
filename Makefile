# Makefile for Keelboat Toy Project
# Pipeline: parameter → design → mass → buoyancy → gz

# ==============================================================================
# PLATFORM DETECTION AND FREECAD CONFIGURATION
# ==============================================================================

UNAME := $(shell uname)

FREECAD_APP := /Applications/FreeCAD.app/Contents/MacOS/FreeCAD
FREECAD_BUNDLE := /Applications/FreeCAD.app

ifeq ($(UNAME),Darwin)
	FREECAD_CMD := $(FREECAD_APP) --console
	FILTER_NOISE := 2>&1 | grep -v "3DconnexionNavlib" | grep -v "^$$"
	CONDA_PYTHON := /Users/henz/anaconda3/envs/freecad/bin/python
	FREECAD_LIB := /Users/henz/anaconda3/envs/freecad/lib
else
	FREECAD_CMD := xvfb-run -a freecadcmd
	FILTER_NOISE :=
	CONDA_PYTHON := freecad-python
	FREECAD_LIB :=
endif

# ==============================================================================
# DIRECTORY STRUCTURE
# ==============================================================================

CONST_DIR := constant
BOAT_DIR := $(CONST_DIR)/boat
CONFIGURATION_DIR := $(CONST_DIR)/configuration
MATERIAL_DIR := $(CONST_DIR)/material
SRC_DIR := src
ARTIFACT_DIR := artifact

$(ARTIFACT_DIR):
	@mkdir -p $@

# ==============================================================================
# DEFAULTS AND VARIABLES
# ==============================================================================

BOAT ?= kb1
CONFIGURATION ?= upwind
MATERIAL ?= keelboat

BOAT_FILE := $(BOAT_DIR)/$(BOAT).json
CONFIGURATION_FILE := $(CONFIGURATION_DIR)/$(CONFIGURATION).json
MATERIAL_FILE := $(MATERIAL_DIR)/$(MATERIAL).json

# ==============================================================================
# MAIN TARGETS
# ==============================================================================

.DEFAULT_GOAL := all

.PHONY: all
all: gz
	@echo "✓ Full pipeline complete for $(BOAT).$(CONFIGURATION)"

.PHONY: help
help:
	@echo "Keelboat Project Makefile"
	@echo ""
	@echo "Pipeline: parameter → design → mass → buoyancy → gz"
	@echo ""
	@echo "Targets:"
	@echo "  make parameter  - Compute derived parameters"
	@echo "  make design     - Generate FreeCAD model"
	@echo "  make mass       - Analyze mass properties"
	@echo "  make buoyancy   - Find buoyancy equilibrium"
	@echo "  make gz         - Compute GZ righting arm curve"
	@echo "  make all        - Run full pipeline"
	@echo "  make clean      - Remove generated files"
	@echo ""
	@echo "Variables:"
	@echo "  BOAT=$(BOAT) CONFIGURATION=$(CONFIGURATION) MATERIAL=$(MATERIAL)"

.PHONY: clean
clean:
	@echo "Cleaning generated files..."
	@rm -rf $(ARTIFACT_DIR)
	@find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Clean complete"

# ==============================================================================
# PARAMETER COMPUTATION
# ==============================================================================

PARAMETER_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).parameter.json

$(PARAMETER_ARTIFACT): $(BOAT_FILE) $(CONFIGURATION_FILE) $(SRC_DIR)/parameter/compute.py | $(ARTIFACT_DIR)
	@echo "Computing parameters for $(BOAT).$(CONFIGURATION)..."
	@PYTHONPATH=$(PWD) python3 -m shipshape.parameter \
		--compute src.parameter.compute \
		--boat $(BOAT_FILE) \
		--configuration $(CONFIGURATION_FILE) \
		--output $@
	@echo "✓ Parameters saved to $@"

.PHONY: parameter
parameter: $(PARAMETER_ARTIFACT)

# ==============================================================================
# DESIGN GENERATION
# ==============================================================================

DESIGN_DIR := $(SRC_DIR)/design
DESIGN_SOURCE := $(wildcard $(DESIGN_DIR)/*.py)
DESIGN_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).design.FCStd

$(DESIGN_ARTIFACT): $(PARAMETER_ARTIFACT) $(DESIGN_SOURCE) | $(ARTIFACT_DIR)
	@echo "Generating design: $(BOAT).$(CONFIGURATION)"
	@echo "  Parameters: $(PARAMETER_ARTIFACT)"
	@PARAMS_PATH=$(PARAMETER_ARTIFACT) OUTPUT_PATH=$(DESIGN_ARTIFACT) \
		$(FREECAD_CMD) $(DESIGN_DIR)/main.py $(FILTER_NOISE) || true
	@if [ -f "$(DESIGN_ARTIFACT)" ]; then \
		echo "✓ Design complete: $(DESIGN_ARTIFACT)"; \
		if [ "$(UNAME)" = "Darwin" ]; then \
			echo "Fixing visibility on macOS..."; \
			bash $(DESIGN_DIR)/fix_visibility.sh "$(DESIGN_ARTIFACT)" "$(FREECAD_APP)"; \
		fi; \
	else \
		echo "ERROR: Design failed - no file created"; \
		exit 1; \
	fi

.PHONY: design
design: $(DESIGN_ARTIFACT)

# ==============================================================================
# COLOR THE DESIGN
# ==============================================================================

COLOR_DIR := $(SRC_DIR)/color
COLOR_SOURCE := $(wildcard $(COLOR_DIR)/*.py)
COLOR_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).color.FCStd

$(COLOR_ARTIFACT): $(DESIGN_ARTIFACT) $(MATERIAL_FILE) $(COLOR_SOURCE) | $(ARTIFACT_DIR)
	@echo "Applying color scheme '$(MATERIAL)' to $(BOAT).$(CONFIGURATION)..."
	@if [ "$(UNAME)" = "Darwin" ]; then \
		bash $(COLOR_DIR)/color_mac.sh \
			"$(DESIGN_ARTIFACT)" \
			"$(MATERIAL_FILE)" \
			"$(COLOR_ARTIFACT)" \
			"$(FREECAD_APP)"; \
	else \
		freecad-python -m src.color \
			--design "$(DESIGN_ARTIFACT)" \
			--colors "$(MATERIAL_FILE)" \
			--outputdesign "$(COLOR_ARTIFACT)"; \
	fi

.PHONY: color
color: $(COLOR_ARTIFACT)
	@echo "✓ Color scheme '$(MATERIAL)' applied to $(BOAT).$(CONFIGURATION)"

# ==============================================================================
# MASS ANALYSIS
# ==============================================================================

MASS_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).mass.json

$(MASS_ARTIFACT): $(DESIGN_ARTIFACT) $(MATERIAL_FILE) | $(ARTIFACT_DIR)
	@echo "Running mass analysis: $(BOAT).$(CONFIGURATION)"
	@PYTHONPATH=$(FREECAD_LIB):$(PWD) $(CONDA_PYTHON) -m shipshape.mass \
		--design $(DESIGN_ARTIFACT) --materials $(MATERIAL_FILE) --output $@
	@echo "✓ Mass analysis: $@"

.PHONY: mass
mass: $(MASS_ARTIFACT)

# ==============================================================================
# BUOYANCY EQUILIBRIUM
# ==============================================================================

HULL_GROUPS_FILE := $(CONST_DIR)/hull_groups.json
BUOYANCY_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).buoyancy.json

$(BUOYANCY_ARTIFACT): $(DESIGN_ARTIFACT) $(MASS_ARTIFACT) $(MATERIAL_FILE) $(HULL_GROUPS_FILE) | $(ARTIFACT_DIR)
	@echo "Running buoyancy analysis: $(BOAT).$(CONFIGURATION)"
	@PYTHONPATH=$(FREECAD_LIB):$(PWD) $(CONDA_PYTHON) -m shipshape.buoyancy \
		--design $(DESIGN_ARTIFACT) \
		--mass $(MASS_ARTIFACT) \
		--materials $(MATERIAL_FILE) \
		--hull-groups $(HULL_GROUPS_FILE) \
		--tolerance 0.005 \
		--output $@
	@echo "✓ Buoyancy analysis: $@"

.PHONY: buoyancy
buoyancy: $(BUOYANCY_ARTIFACT)

# ==============================================================================
# GZ CURVE (RIGHTING ARM)
# ==============================================================================

GZ_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).gz.json
GZ_PNG := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).gz.png

$(GZ_ARTIFACT): $(BUOYANCY_ARTIFACT) $(DESIGN_ARTIFACT) $(PARAMETER_ARTIFACT) | $(ARTIFACT_DIR)
	@echo "Computing GZ curve: $(BOAT).$(CONFIGURATION)"
	@PYTHONPATH=$(FREECAD_LIB):$(PWD) $(CONDA_PYTHON) -m shipshape.gz \
		--design $(DESIGN_ARTIFACT) \
		--buoyancy $(BUOYANCY_ARTIFACT) \
		--parameters $(PARAMETER_ARTIFACT) \
		--hull-groups $(HULL_GROUPS_FILE) \
		--output $@ \
		--output-png $(GZ_PNG) \
		--min-heel -90 \
		--max-heel 90
	@echo "✓ GZ curve: $@"

.PHONY: gz
gz: $(GZ_ARTIFACT)
