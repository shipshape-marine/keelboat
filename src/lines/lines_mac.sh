#!/bin/bash
# lines_mac.sh - Generate lines plan using FreeCAD GUI on macOS
# Usage: ./lines_mac.sh <design.FCStd> <parameter.json> <output_dir> [freecad_path]

if [ $# -lt 3 ]; then
    echo "Usage: $0 <design.FCStd> <parameter.json> <output_dir> [freecad_path]"
    exit 1
fi

DESIGN_FILE="$1"
PARAMETER_FILE="$2"
OUTPUT_DIR="$3"
FREECAD="${4:-/Applications/FreeCAD.app/Contents/MacOS/FreeCAD}"

if [ ! -f "$DESIGN_FILE" ]; then
    echo "ERROR: Design file not found: $DESIGN_FILE"
    exit 1
fi

if [ ! -f "$PARAMETER_FILE" ]; then
    echo "ERROR: Parameter file not found: $PARAMETER_FILE"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Create temp script that sets env vars and runs the module
TEMP_SCRIPT=$(mktemp /tmp/freecad_lines.XXXXXX)
mv "$TEMP_SCRIPT" "${TEMP_SCRIPT}.py"
TEMP_SCRIPT="${TEMP_SCRIPT}.py"

# Use encoding='utf-8' to handle Unicode in the source file
cat > "$TEMP_SCRIPT" << PYEOF
import os
import sys

os.environ['DESIGN_FILE'] = '$DESIGN_FILE'
os.environ['PARAMETER_FILE'] = '$PARAMETER_FILE'
os.environ['OUTPUT_DIR'] = '$OUTPUT_DIR'

repo_root = os.getcwd()
sys.path.insert(0, repo_root)

source_path = os.path.join(repo_root, 'src', 'lines', '__main__.py')
with open(source_path, encoding='utf-8') as f:
    code = f.read()
exec(compile(code, source_path, 'exec'))
PYEOF

echo "Generating lines plan for $DESIGN_FILE..."
"$FREECAD" --console "$TEMP_SCRIPT" 2>&1 | grep -v "3DconnexionNavlib" | grep -v "^$" &
FREECAD_PID=$!

# Wait up to 300 seconds for completion (lines plan takes longer than renders)
for i in {1..600}; do
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

# Clean up
rm -f "$TEMP_SCRIPT"

# Check if lines plan was created
BASENAME=$(basename "$DESIGN_FILE" .FCStd)
BASENAME=${BASENAME%.design}
if ls "$OUTPUT_DIR"/${BASENAME}.lines.*.svg 1>/dev/null 2>&1; then
    echo "Lines plan complete for $BASENAME"
    exit 0
else
    echo "WARNING: No SVG files were generated"
    exit 0  # Don't fail the build
fi
