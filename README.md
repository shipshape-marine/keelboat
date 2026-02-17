# Keelboat

A simple ~6m monohull daysailer that exercises the [shipshape](https://pypi.org/project/shipshape/) library's pipeline.

**Website:** [shipshape-marine.github.io/keelboat](https://shipshape-marine.github.io/keelboat/)

## Pipeline

```
parameter → design → color → mass → buoyancy → gz
                 ↓                              ↓
              render                         GZ curve
                 ↓
              lines → lines-pdf
```

## Quick Start

```bash
make all         # full pipeline: parameter → design → mass → buoyancy → gz
make color       # apply color scheme
make render      # generate PNG renders (requires color)
make lines       # generate lines plan SVGs (requires design)
make lines-pdf   # compile lines plan LaTeX to PDF
make sync-docs   # copy artifacts to docs/
make localhost   # serve website at localhost:4000
```

## Boat: KB1

A 6.1m fiberglass daysailer with:
- LOA 6100mm, beam 2200mm, draft 1200mm
- Lead fin keel (900mm span)
- Sloop rig (8m mast)
- Single hull group (monohull)

## Project Structure

```
keelboat/
├── Makefile                          # Pipeline orchestration
├── constant/
│   ├── boat/kb1.json                 # Boat dimensions
│   ├── configuration/upwind.json     # Sailing configuration
│   ├── material/keelboat.json        # Material properties
│   ├── hull_groups.json              # Single "hull" group
│   └── view.json                     # Render view definitions
├── src/
│   ├── parameter/compute.py          # Keelboat-specific derived parameters
│   ├── design/main.py                # FreeCAD geometry generator
│   ├── color/                        # Color scheme application
│   ├── render/                       # PNG render export
│   └── lines/                        # Lines plan generation (SVG + LaTeX)
├── docs/                             # Jekyll website (GitHub Pages)
│   ├── _config.yml
│   ├── _layouts/default.html
│   ├── index.md                      # Single-page site
│   └── Gemfile
├── .github/workflows/pages.yml       # CI/CD: build pipeline + deploy to Pages
└── artifact/                         # Generated outputs (gitignored)
```
