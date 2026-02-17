# Keelboat Toy Project

A simple ~6m monohull daysailer that exercises the [shipshape](../shipshape) library's pipeline:

```
parameter → design → mass → buoyancy → gz
```

## Quick Start

```bash
make parameter   # compute derived parameters
make design      # generate FreeCAD model (requires FreeCAD)
make mass        # analyze mass properties
make buoyancy    # find buoyancy equilibrium
make gz          # compute GZ righting arm curve
```

Or run the full pipeline: `make all`

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
│   ├── material/keelboat.json        # Material properties (8 materials)
│   └── hull_groups.json              # Single "hull" group
├── src/
│   ├── parameter/compute.py          # Keelboat-specific derived parameters
│   └── design/main.py               # FreeCAD geometry generator
└── artifact/                         # Generated outputs (gitignored)
```
