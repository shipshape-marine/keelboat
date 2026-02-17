#!/usr/bin/env python3
"""
Keelboat FreeCAD design generator.

Generates a simple ~6m monohull daysailer with fin keel:
  - Hull_Shell__fiberglass   : Lofted hull from cross-sections, shelled
  - Deck__fiberglass         : Flat deck at sheer line
  - Keel__lead               : Tapered fin keel
  - Rudder_Blade__wood       : Simple blade at stern
  - Rudder_Stock__stainless_steel : Cylindrical shaft
  - Mast__aluminum           : Cylindrical tube
  - Boom__aluminum           : Horizontal tube
  - Air_Inside__air          : Fill volume inside hull

Arguments via environment variables: PARAMS_PATH and OUTPUT_PATH
"""

import sys
import os
import json
import math

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

# Load parameters
if os.environ.get('PARAMS_PATH') and os.environ.get('OUTPUT_PATH'):
    params_path = os.environ['PARAMS_PATH']
    output_path = os.environ['OUTPUT_PATH']
elif len(sys.argv) >= 5:
    params_path = sys.argv[3]
    output_path = sys.argv[4]
elif len(sys.argv) >= 3:
    params_path = sys.argv[1]
    output_path = sys.argv[2]
else:
    print("ERROR: Set PARAMS_PATH and OUTPUT_PATH environment variables", file=sys.stderr)
    sys.exit(1)

print(f"Loading parameters: {params_path}")
with open(params_path, 'r') as p:
    params = json.load(p)

boat = params.get('boat_name', 'unknown')
configuration = params.get('configuration_name', 'unknown')
print(f"  Boat: {boat}, Configuration: {configuration}")

# Import FreeCAD
print("Importing FreeCAD...")
try:
    import FreeCAD as App
    import Part
    from FreeCAD import Base
    print(f"FreeCAD version = {App.Version()}")
except ImportError as e:
    print(f"ERROR: Could not import FreeCAD: {e}")
    sys.exit(1)

try:
    import FreeCADGui
except ImportError:
    pass

# Initialize headless GUI on Linux
import platform
if platform.system() == 'Linux' and not App.GuiUp:
    try:
        from PySide import QtGui
        try:
            QtGui.QApplication()
        except RuntimeError:
            pass
        import FreeCADGui as Gui
        Gui.showMainWindow()
        Gui.getMainWindow().destroy()
    except Exception:
        pass

# Close existing documents
for doc_name in App.listDocuments():
    App.closeDocument(doc_name)

# Create document
doc_name = f"Keelboat {boat} {configuration}"
doc = App.newDocument(doc_name)
App.setActiveDocument(doc.Name)
doc.recompute()

vessel = doc.addObject("App::Part", "Vessel")

# ============================================================================
# HULL SHELL - Lofted from cross-sections
# ============================================================================

print("Creating hull shell...")

hull_length = params['hull_length']
hull_beam = params['hull_beam']
hull_depth = params['hull_depth']
hull_thickness = params['hull_thickness']
num_sections = params.get('hull_sections', 7)

half_length = hull_length / 2
half_beam = hull_beam / 2

def hull_section_points(hw, hd):
    """
    Generate the U-shaped cross-section points for half-width hw, depth hd.
    Returns list of points from port sheer through keel to starboard sheer.
    Origin at section centroid, sheer at z=0, keel at z=-hd.
    """
    n_pts = 12
    # Starboard side, bottom to top
    stbd = []
    for i in range(n_pts + 1):
        t = i / n_pts  # 0 = keel bottom, 1 = sheer
        x = hw * math.sin(t * math.pi / 2)
        z = -hd * (1 - t)
        stbd.append((x, z))

    # Mirror to port (reversed, skip centerline duplicate)
    port = [(-x, z) for x, z in reversed(stbd[1:])]
    return port + stbd


def hull_section_wire(y_pos, hw, hd):
    """
    Create a closed hull cross-section wire at longitudinal position y_pos.
    """
    pts = hull_section_points(hw, hd)
    vecs = [Base.Vector(x, y_pos, z) for x, z in pts]

    spline = Part.BSplineCurve()
    spline.interpolate(vecs)
    spline_edge = spline.toShape()

    # Close at the sheer line (deck edge)
    closing_edge = Part.makeLine(vecs[-1], vecs[0])
    return Part.Wire([spline_edge, closing_edge])


def hull_section_wire_inner(y_pos, hw, hd, thickness):
    """
    Create an inner hull section wire, offset inward by thickness.
    The inner section has reduced half-width and depth.
    """
    inner_hw = max(hw - thickness, thickness)
    inner_hd = max(hd - thickness, thickness)
    return hull_section_wire(y_pos, inner_hw, inner_hd)


# Generate sections along the hull length
# Explicit (frac, beam_fraction, depth_fraction) control points for a
# pointy bow and a narrower stern.  frac runs 0 (stern) to 1 (bow).
hull_shape_table = [
    # frac   beam_frac  depth_frac
    (0.00,   0.60,      0.70),   # stern (wide transom)
    (0.15,   0.75,      0.85),   # aft quarter
    (0.30,   0.90,      0.95),   # approaching midships
    (0.45,   1.00,      1.00),   # max beam (slightly forward of midships)
    (0.55,   1.00,      1.00),   # max beam
    (0.70,   0.80,      0.90),   # forward quarter
    (0.85,   0.45,      0.65),   # bow transition
    (0.95,   0.15,      0.40),   # near bow
    (1.00,   0.02,      0.20),   # bow point
]


def interp_table(frac):
    """Linearly interpolate beam_frac and depth_frac from hull_shape_table."""
    if frac <= hull_shape_table[0][0]:
        return hull_shape_table[0][1], hull_shape_table[0][2]
    if frac >= hull_shape_table[-1][0]:
        return hull_shape_table[-1][1], hull_shape_table[-1][2]
    for j in range(len(hull_shape_table) - 1):
        f0, b0, d0 = hull_shape_table[j]
        f1, b1, d1 = hull_shape_table[j + 1]
        if f0 <= frac <= f1:
            t = (frac - f0) / (f1 - f0)
            return b0 + t * (b1 - b0), d0 + t * (d1 - d0)
    return hull_shape_table[-1][1], hull_shape_table[-1][2]


# Use more sections for smoother ends
num_sections = max(num_sections, 11)
outer_wires = []
inner_wires = []
for i in range(num_sections):
    frac = i / (num_sections - 1)  # 0 = stern, 1 = bow
    y_pos = -half_length + frac * hull_length
    bf, df = interp_table(frac)
    hw = max(half_beam * bf, hull_thickness * 2)
    hd = max(hull_depth * df, hull_thickness * 2)

    outer_wires.append(hull_section_wire(y_pos, hw, hd))
    inner_wires.append(hull_section_wire_inner(y_pos, hw, hd, hull_thickness))

# Loft outer and inner hulls, subtract to get thin shell
try:
    outer_loft = Part.makeLoft(outer_wires, True, False, False)
    inner_loft = Part.makeLoft(inner_wires, True, False, False)
    hull_shell = outer_loft.cut(inner_loft)

    hull_shell_obj = vessel.newObject("Part::Feature", "Hull_Shell__fiberglass")
    hull_shell_obj.Shape = hull_shell
    hull_shell_obj.Placement = App.Placement(
        Base.Vector(0, 0, params['deck_level']),
        App.Rotation())
    print(f"  Hull shell: volume = {hull_shell.Volume / 1e6:.1f} liters")
    print(f"  (outer={outer_loft.Volume/1e6:.1f}L, inner={inner_loft.Volume/1e6:.1f}L)")
except Exception as e:
    print(f"  Warning: Hull loft failed ({e}), using box fallback")
    hull_box = Part.makeBox(hull_beam, hull_length, hull_depth,
                            Base.Vector(-half_beam, -half_length, -hull_depth))
    hull_shell_obj = vessel.newObject("Part::Feature", "Hull_Shell__fiberglass")
    hull_shell_obj.Shape = hull_box
    hull_shell_obj.Placement = App.Placement(
        Base.Vector(0, 0, params['deck_level']),
        App.Rotation())

# ============================================================================
# DECK - Flat surface at sheer line
# ============================================================================

print("Creating deck...")
deck_thickness = hull_thickness
# Use an elliptical deck plan shape
n_deck_pts = 24
deck_points = []
for i in range(n_deck_pts + 1):
    angle = 2 * math.pi * i / n_deck_pts
    x = half_beam * 0.95 * math.cos(angle)
    y = half_length * 0.95 * math.sin(angle)
    deck_points.append(Base.Vector(x, y, 0))

deck_wire = Part.makePolygon(deck_points + [deck_points[0]])
deck_face = Part.Face(deck_wire)
deck_solid = deck_face.extrude(Base.Vector(0, 0, deck_thickness))

deck_obj = vessel.newObject("Part::Feature", "Deck__fiberglass")
deck_obj.Shape = deck_solid
deck_obj.Placement = App.Placement(
    Base.Vector(0, 0, params['deck_level']),
    App.Rotation())

# ============================================================================
# KEEL - Tapered fin at hull bottom
# ============================================================================

print("Creating keel...")
keel_root = params['keel_root_chord']
keel_tip = params['keel_tip_chord']
keel_span = params['keel_span']
keel_root_t = params['keel_root_thickness']
keel_tip_t = params['keel_tip_thickness']
keel_sweep = math.radians(params['keel_sweep_deg'])

# Keel as a tapered box (root at top, tip at bottom)
# Root section (at hull bottom)
root_hw = keel_root / 2
root_ht = keel_root_t / 2
root_y_offset = 0  # Centered longitudinally

root_pts = [
    Base.Vector(-root_ht, -root_hw + root_y_offset, 0),
    Base.Vector(root_ht, -root_hw + root_y_offset, 0),
    Base.Vector(root_ht, root_hw + root_y_offset, 0),
    Base.Vector(-root_ht, root_hw + root_y_offset, 0),
]
root_wire = Part.makePolygon(root_pts + [root_pts[0]])

# Tip section (at bottom of keel)
tip_hw = keel_tip / 2
tip_ht = keel_tip_t / 2
sweep_offset = keel_span * math.tan(keel_sweep)

tip_pts = [
    Base.Vector(-tip_ht, -tip_hw + sweep_offset, -keel_span),
    Base.Vector(tip_ht, -tip_hw + sweep_offset, -keel_span),
    Base.Vector(tip_ht, tip_hw + sweep_offset, -keel_span),
    Base.Vector(-tip_ht, tip_hw + sweep_offset, -keel_span),
]
tip_wire = Part.makePolygon(tip_pts + [tip_pts[0]])

try:
    keel_shape = Part.makeLoft([root_wire, tip_wire], True)
except Exception as e:
    print(f"  Warning: Keel loft failed ({e}), using box fallback")
    keel_shape = Part.makeBox(keel_root_t, keel_root, keel_span,
                              Base.Vector(-root_ht, -root_hw, -keel_span))

keel_obj = vessel.newObject("Part::Feature", "Keel__lead")
keel_obj.Shape = keel_shape
# Position at hull bottom, centered
keel_z = params['deck_level'] - hull_depth
keel_obj.Placement = App.Placement(
    Base.Vector(0, 0, keel_z),
    App.Rotation())
print(f"  Keel: volume = {keel_shape.Volume / 1e6:.1f} liters")

# ============================================================================
# RUDDER BLADE
# ============================================================================

print("Creating rudder...")
rudder_chord = params['rudder_chord']
rudder_span = params['rudder_span']
rudder_t = params['rudder_thickness']
rudder_y = params['rudder_y_position']

rudder_shape = Part.makeBox(rudder_t, rudder_chord, rudder_span,
                            Base.Vector(-rudder_t / 2, -rudder_chord / 2, 0))

rudder_obj = vessel.newObject("Part::Feature", "Rudder_Blade__wood")
rudder_obj.Shape = rudder_shape
rudder_z = params['deck_level'] - hull_depth
rudder_obj.Placement = App.Placement(
    Base.Vector(0, rudder_y, rudder_z - rudder_span),
    App.Rotation())

# ============================================================================
# RUDDER STOCK
# ============================================================================

stock_d = params['rudder_stock_diameter']
# Stock runs from bottom of rudder blade up to deck level
stock_bottom_z = rudder_z - rudder_span
stock_top_z = params['deck_level']
stock_l = stock_top_z - stock_bottom_z
stock_shape = Part.makeCylinder(stock_d / 2, stock_l)

stock_obj = vessel.newObject("Part::Feature", "Rudder_Stock__stainless_steel")
stock_obj.Shape = stock_shape
stock_obj.Placement = App.Placement(
    Base.Vector(0, rudder_y, stock_bottom_z),
    App.Rotation())

# ============================================================================
# MAST
# ============================================================================

print("Creating rig...")
mast_h = params['mast_height']
mast_d = params['mast_diameter']
mast_t = params['mast_thickness']
mast_y = params['mast_y_position']

mast_outer = Part.makeCylinder(mast_d / 2, mast_h)
mast_inner = Part.makeCylinder(mast_d / 2 - mast_t, mast_h)
mast_shape = mast_outer.cut(mast_inner)

mast_obj = vessel.newObject("Part::Feature", "Mast__aluminum")
mast_obj.Shape = mast_shape
mast_obj.Placement = App.Placement(
    Base.Vector(0, mast_y, params['deck_level']),
    App.Rotation())

# ============================================================================
# BOOM
# ============================================================================

boom_l = params['boom_length']
boom_d = params['boom_diameter']
boom_t = params['boom_thickness']
boom_z_above_deck = params['boom_height_above_deck']

boom_outer = Part.makeCylinder(boom_d / 2, boom_l)
boom_inner = Part.makeCylinder(boom_d / 2 - boom_t, boom_l)
boom_shape = boom_outer.cut(boom_inner)

boom_obj = vessel.newObject("Part::Feature", "Boom__aluminum")
boom_obj.Shape = boom_shape
# Boom runs longitudinally aft from mast
boom_obj.Placement = App.Placement(
    Base.Vector(0, mast_y, params['deck_level'] + boom_z_above_deck),
    App.Rotation(Base.Vector(1, 0, 0), 90))

# ============================================================================
# AIR INSIDE HULL
# ============================================================================

print("Creating air volume...")
# Air volume is the inner hull loft (the space enclosed by the hull shell)
try:
    air_shape = inner_loft
    print(f"  Air volume: {air_shape.Volume / 1e6:.1f} liters (inner hull)")
except Exception:
    # Fallback: simple box
    air_shape = Part.makeBox(
        half_beam * 1.2, half_length * 1.4, hull_depth * 0.5,
        Base.Vector(-half_beam * 0.6, -half_length * 0.7, -hull_depth * 0.5))
    print(f"  Air volume: {air_shape.Volume / 1e6:.1f} liters (box fallback)")

air_obj = vessel.newObject("Part::Feature", "Air_Inside__air")
air_obj.Shape = air_shape
air_obj.Placement = App.Placement(
    Base.Vector(0, 0, params['deck_level']),
    App.Rotation())

# ============================================================================
# FINALIZE
# ============================================================================

doc.recompute()

# Set visibility on Linux
if platform.system() == 'Linux':
    def make_all_visible(obj_list):
        for obj in obj_list:
            try:
                if hasattr(obj, 'ViewObject') and obj.ViewObject:
                    if 'Origin' in obj.Name or obj.TypeId == 'App::Origin':
                        obj.ViewObject.Visibility = False
                    else:
                        obj.ViewObject.Visibility = True
            except Exception:
                pass
            if hasattr(obj, 'Group') and obj.Group:
                make_all_visible(obj.Group)
    try:
        make_all_visible(doc.Objects)
    except Exception:
        pass

# Print summary
print(f"\nDesign summary:")
for obj in vessel.Group:
    if hasattr(obj, 'Shape'):
        vol = obj.Shape.Volume / 1e6
        print(f"  {obj.Label}: {vol:.2f} liters")

# Save
doc.saveAs(output_path)
print(f"\n[ok] Saved to {output_path}")

sys.stdout.flush()
sys.stderr.flush()
App.closeDocument(doc.Name)
import os as _os
_os._exit(0)
