# Makefile for Keelboat Project
# Pipeline: parameter → design → color → mass → buoyancy → gz
# Additional: render, lines, lines-pdf, sync-docs, localhost

# ==============================================================================
# PLATFORM DETECTION AND FREECAD CONFIGURATION
# ==============================================================================

UNAME := $(shell uname)

FREECAD_APP := /Applications/FreeCAD.app/Contents/MacOS/FreeCAD
FREECAD_BUNDLE := /Applications/FreeCAD.app

ifeq ($(UNAME),Darwin)
	FREECAD_CMD := $(FREECAD_APP) --console
	FREECAD_PYTHON := $(FREECAD_BUNDLE)/Contents/Resources/bin/python
	FILTER_NOISE := 2>&1 | grep -v "3DconnexionNavlib" | grep -v "^$$"
	CONDA_PYTHON := /Users/henz/anaconda3/envs/freecad/bin/python
	FREECAD_LIB := /Users/henz/anaconda3/envs/freecad/lib
else
	FREECAD_CMD := xvfb-run -a freecadcmd
	FREECAD_PYTHON := freecad-python
	FILTER_NOISE :=
	CONDA_PYTHON := $(FREECAD_PYTHON)
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
	@echo "Pipeline: parameter → design → color → mass → buoyancy → gz"
	@echo ""
	@echo "Targets:"
	@echo "  make parameter  - Compute derived parameters"
	@echo "  make design     - Generate FreeCAD model"
	@echo "  make color      - Apply color scheme to design"
	@echo "  make mass       - Analyze mass properties"
	@echo "  make buoyancy   - Find buoyancy equilibrium"
	@echo "  make gz         - Compute GZ righting arm curve"
	@echo "  make render     - Render images from colored design"
	@echo "  make lines      - Generate lines plan (SVGs)"
	@echo "  make lines-pdf  - Compile lines plan LaTeX to PDF"
	@echo "  make step       - Export design to STEP format"
	@echo "  make all        - Run full pipeline"
	@echo "  make sync-docs  - Copy artifacts to docs/"
	@echo "  make localhost  - Serve website locally"
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

# ==============================================================================
# RENDER THE COLORED DESIGN
# ==============================================================================

RENDER_DIR := $(SRC_DIR)/render
RENDER_SOURCE := $(wildcard $(RENDER_DIR)/*.py)

.PHONY: render
render: $(COLOR_ARTIFACT) $(RENDER_SOURCE)
	@echo "Rendering images from $(COLOR_ARTIFACT)..."
	@if [ "$(UNAME)" = "Darwin" ]; then \
		$(RENDER_DIR)/render_mac.sh "$(COLOR_ARTIFACT)" "$(ARTIFACT_DIR)" "$(FREECAD_APP)"; \
	else \
		FCSTD_FILE="$(COLOR_ARTIFACT)" IMAGE_DIR="$(ARTIFACT_DIR)" freecad-python -m src.render; \
	fi
	@echo "Cropping images with ImageMagick..."
	@if command -v convert >/dev/null 2>&1; then \
		for img in $(ARTIFACT_DIR)/*.render.*.png; do \
			if [ -f "$$img" ]; then \
				convert "$$img" -fuzz 1% -trim +repage -bordercolor \#C6D2FF -border 25 "$$img" || true; \
			fi \
		done; \
		echo "Cropping complete!"; \
	else \
		echo "ImageMagick not found, skipping crop"; \
	fi
	@echo "✓ Render complete for $(BOAT).$(CONFIGURATION)"

# ==============================================================================
# LINES PLAN - TRADITIONAL NAVAL ARCHITECTURE DRAWINGS
# ==============================================================================

LINES_DIR := $(SRC_DIR)/lines
LINES_SOURCE := $(wildcard $(LINES_DIR)/*.py)
LINES_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).lines.FCStd
LINES_TEX := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).lines.tex
LINES_PDF := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).lines.pdf

$(LINES_ARTIFACT) $(LINES_TEX): $(DESIGN_ARTIFACT) $(PARAMETER_ARTIFACT) $(LINES_SOURCE) | $(ARTIFACT_DIR)
	@echo "Generating lines plan: $(BOAT).$(CONFIGURATION)"
	@if [ "$(UNAME)" = "Darwin" ]; then \
		bash $(LINES_DIR)/lines_mac.sh \
			"$(DESIGN_ARTIFACT)" \
			"$(PARAMETER_ARTIFACT)" \
			"$(ARTIFACT_DIR)" \
			"$(FREECAD_APP)"; \
	else \
		PYTHONPATH=$(PWD) \
		DESIGN_FILE=$(DESIGN_ARTIFACT) \
		PARAMETER_FILE=$(PARAMETER_ARTIFACT) \
		OUTPUT_DIR=$(ARTIFACT_DIR) \
		$(FREECAD_PYTHON) -m src.lines; \
	fi

.PHONY: lines
lines: $(LINES_ARTIFACT)
	@echo "✓ Lines plan complete for $(BOAT).$(CONFIGURATION)"

$(LINES_PDF): $(LINES_TEX)
	@echo "Converting SVGs to PDF for LaTeX inclusion..."
	@for svg in $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).lines.*.svg; do \
		if [ -f "$$svg" ]; then \
			pdf=$${svg%.svg}.pdf; \
			if command -v rsvg-convert >/dev/null 2>&1; then \
				rsvg-convert -f pdf -o "$$pdf" "$$svg" 2>/dev/null || true; \
			elif command -v inkscape >/dev/null 2>&1; then \
				inkscape "$$svg" --export-filename="$$pdf" 2>/dev/null || true; \
			fi; \
		fi; \
	done
	@echo "Compiling lines plan LaTeX: $(BOAT).$(CONFIGURATION)"
	@cd $(ARTIFACT_DIR) && pdflatex -interaction=nonstopmode $(notdir $(LINES_TEX)) || true
	@cd $(ARTIFACT_DIR) && pdflatex -interaction=nonstopmode $(notdir $(LINES_TEX)) || true
	@if [ -f "$(LINES_PDF)" ]; then \
		echo "✓ Lines plan PDF: $(LINES_PDF)"; \
	else \
		echo "Warning: PDF generation failed (pdflatex may not be installed)"; \
	fi

.PHONY: lines-pdf
lines-pdf: $(LINES_PDF)
	@echo "✓ Lines plan PDF complete for $(BOAT).$(CONFIGURATION)"

# ==============================================================================
# STEP EXPORT
# ==============================================================================

STEP_DIR := $(SRC_DIR)/step
STEP_SOURCE := $(wildcard $(STEP_DIR)/*.py)
STEP_ARTIFACT := $(ARTIFACT_DIR)/$(BOAT).$(CONFIGURATION).step.step

$(STEP_ARTIFACT): $(DESIGN_ARTIFACT) $(STEP_SOURCE) | $(ARTIFACT_DIR)
	@echo "Exporting STEP: $(BOAT).$(CONFIGURATION)"
	@if [ "$(UNAME)" = "Darwin" ]; then \
		bash $(STEP_DIR)/step_mac.sh \
			"$(DESIGN_ARTIFACT)" \
			"$(STEP_ARTIFACT)" \
			"$(FREECAD_APP)"; \
	else \
		$(FREECAD_PYTHON) -m src.step \
			--input "$(DESIGN_ARTIFACT)" \
			--output "$(STEP_ARTIFACT)"; \
	fi

.PHONY: step
step: $(STEP_ARTIFACT)
	@echo "✓ STEP export complete: $(STEP_ARTIFACT)"

# ==============================================================================
# DOCS SYNC AND LOCAL PREVIEW
# ==============================================================================

.PHONY: sync-docs
sync-docs:
	@echo "Syncing artifacts to docs folders..."
	@mkdir -p docs/_data docs/renders docs/downloads docs/lines
	@# Copy JSON files with dots→underscores renaming
	@for file in artifact/*.json; do \
		if [ -f "$$file" ]; then \
			basename=$$(basename "$$file" .json); \
			newname=$$(echo "$$basename" | tr '.' '_'); \
			cp "$$file" "docs/_data/$${newname}.json"; \
		fi \
	done
	@echo "  Copied $$(ls artifact/*.json 2>/dev/null | wc -l | tr -d ' ') JSON files to docs/_data/"
	@# Copy PNG renders
	@if ls artifact/*.png 1>/dev/null 2>&1; then \
		cp artifact/*.png docs/renders/; \
		echo "  Copied $$(ls artifact/*.png | wc -l | tr -d ' ') PNG files to docs/renders/"; \
	fi
	@# Copy lines plan SVGs
	@if ls artifact/*.svg 1>/dev/null 2>&1; then \
		cp artifact/*.svg docs/lines/; \
		echo "  Copied $$(ls artifact/*.svg | wc -l | tr -d ' ') SVG files to docs/lines/"; \
	fi
	@# Copy lines plan PDFs
	@if ls artifact/*.pdf 1>/dev/null 2>&1; then \
		cp artifact/*.pdf docs/lines/; \
		echo "  Copied $$(ls artifact/*.pdf | wc -l | tr -d ' ') PDF files to docs/lines/"; \
	fi
	@# Copy downloads (FCStd files)
	@if ls artifact/*.FCStd 1>/dev/null 2>&1; then \
		cp artifact/*.FCStd docs/downloads/; \
		echo "  Copied $$(ls artifact/*.FCStd | wc -l | tr -d ' ') FCStd files to docs/downloads/"; \
	fi
	@# Copy STEP files
	@if ls artifact/*.step 1>/dev/null 2>&1; then \
		cp artifact/*.step docs/downloads/; \
		echo "  Copied $$(ls artifact/*.step | wc -l | tr -d ' ') STEP files to docs/downloads/"; \
	fi
	@echo "✓ Docs sync complete"

.PHONY: localhost
localhost: sync-docs
	@echo "Serving website at localhost:4000..."
	cd docs; bundle exec jekyll serve
