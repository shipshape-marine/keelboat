#!/bin/bash
# Apply color scheme to FreeCAD design (macOS - GUI mode required)

if [ $# -lt 3 ]; then
    echo "Usage: $0 <input.FCStd> <colors.json> <output.FCStd> [freecad_path]"
    exit 1
fi

INPUT_FCSTD="$1"
COLOR_JSON="$2"
OUTPUT_FCSTD="$3"
FREECAD="${4:-/Applications/FreeCAD.app/Contents/MacOS/FreeCAD}"

if [ ! -f "$INPUT_FCSTD" ]; then
    echo "ERROR: Input file not found: $INPUT_FCSTD"
    exit 1
fi

if [ ! -f "$COLOR_JSON" ]; then
    echo "ERROR: Color scheme file not found: $COLOR_JSON"
    exit 1
fi

# Create temporary Python script
TEMP_SCRIPT=$(mktemp /tmp/freecad_color_XXXXXX.py)

cat > "$TEMP_SCRIPT" << 'EOFPYTHON'
import FreeCAD
import FreeCADGui
import sys
import os
import json

def get_material_from_label(label):
    label_lower = label.lower()
    if '(' in label_lower:
        return label_lower.split('(')[1].rstrip(')').strip()
    if '__' in label_lower:
        parts = label_lower.split('__')
        if len(parts) >= 2:
            return parts[1].rstrip('_0123456789').strip()
    return None

def apply_colors(doc, color_scheme):
    materials_def = color_scheme.get('materials', {})
    stats = {'total_objects': 0, 'colored_objects': 0, 'by_material': {}}

    def process_objects(obj_list):
        for obj in obj_list:
            stats['total_objects'] += 1
            if hasattr(obj, 'ViewObject') and obj.ViewObject:
                mat_key = get_material_from_label(obj.Label)
                if mat_key and mat_key in materials_def:
                    mat_def = materials_def[mat_key]
                    try:
                        if 'color' in mat_def:
                            obj.ViewObject.ShapeColor = tuple(mat_def['color'])
                        if 'transparency' in mat_def:
                            obj.ViewObject.Transparency = mat_def['transparency']
                        if 'display_mode' in mat_def:
                            if hasattr(obj.ViewObject, 'DisplayMode'):
                                obj.ViewObject.DisplayMode = mat_def['display_mode']
                        stats['colored_objects'] += 1
                        stats['by_material'][mat_key] = stats['by_material'].get(mat_key, 0) + 1
                    except Exception as e:
                        print(f"Warning: Could not color {obj.Label}: {e}")
            if hasattr(obj, 'Group'):
                process_objects(obj.Group)

    process_objects(doc.Objects)
    return stats

input_fcstd = sys.argv[-3]
color_json = sys.argv[-2]
output_fcstd = sys.argv[-1]

print(f"Loading color scheme: {color_json}")
with open(color_json, 'r') as f:
    color_scheme = json.load(f)

print(f"  Scheme: {color_scheme.get('scheme_name', 'Unknown')}")
print(f"Opening design: {input_fcstd}")
doc = FreeCAD.openDocument(input_fcstd)

print("Applying colors...")
stats = apply_colors(doc, color_scheme)
doc.recompute()

print("Setting visibility...")
def make_all_visible(obj_list):
    for obj in obj_list:
        try:
            if hasattr(obj, 'ViewObject') and obj.ViewObject:
                if 'Origin' in obj.Name or obj.TypeId == 'App::Origin':
                    obj.ViewObject.Visibility = False
                else:
                    obj.ViewObject.Visibility = True
        except:
            pass
        if hasattr(obj, 'Group'):
            make_all_visible(obj.Group)

make_all_visible(doc.Objects)

print(f"Saving colored design: {output_fcstd}")
doc.saveAs(output_fcstd)

print(f"Done - colored {stats['colored_objects']}/{stats['total_objects']} objects")
for mat, count in sorted(stats['by_material'].items()):
    print(f"    {mat}: {count}")

FreeCAD.closeDocument(doc.Name)
os._exit(0)
EOFPYTHON

echo "Running FreeCAD to apply colors..."
"$FREECAD" "$TEMP_SCRIPT" "$INPUT_FCSTD" "$COLOR_JSON" "$OUTPUT_FCSTD" &
FREECAD_PID=$!

# Wait up to 30 seconds for completion
for i in {1..60}; do
    if ! kill -0 $FREECAD_PID 2>/dev/null; then
        break
    fi
    sleep 0.5
done

# Force kill if still running
if kill -0 $FREECAD_PID 2>/dev/null; then
    echo "Warning: FreeCAD did not exit cleanly, forcing..."
    kill -9 $FREECAD_PID 2>/dev/null
fi

rm -f "$TEMP_SCRIPT"

if [ ! -f "$OUTPUT_FCSTD" ]; then
    echo "ERROR: Colored design was not created"
    exit 1
fi

echo "[ok] Color application complete"
