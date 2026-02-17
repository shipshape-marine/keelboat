#!/usr/bin/env python3
"""
Lines Plan Generation for Keelboat.

Generates a traditional lines plan with three classic views:
- Profile (side elevation, YZ plane) — hull outline with waterline, keel, rudder
- Body plan (cross-sections, XZ plane) — hull sections at evenly spaced stations
- Full-breadth plan (top view, YX plane) — waterlines at several heights

Uses FreeCAD Part.slice() to cut shapes with planes and exports SVGs.
Generates a LaTeX document wrapping the SVGs into a single PDF.

Usage:
    DESIGN_FILE=... PARAMETER_FILE=... OUTPUT_DIR=... freecad-python -m src.lines
"""

import sys
import os
import json

# Check if we're running in FreeCAD
try:
    import FreeCAD as App
    import FreeCADGui as Gui
    import Part
except ImportError:
    print("ERROR: This script must be run with freecad-python or FreeCAD")
    sys.exit(1)


def init_gui():
    """Initialize FreeCAD GUI for headless operation."""
    import platform
    from PySide import QtGui

    if platform.system() == 'Linux':
        try:
            QtGui.QApplication()
        except RuntimeError:
            pass

        Gui.showMainWindow()
        Gui.getMainWindow().destroy()
        App.ParamGet('User parameter:BaseApp/Preferences/Document').SetBool(
            'SaveThumbnail', False)


def get_section_positions(params):
    """
    Get Y positions for body plan section cuts (evenly spaced along hull).
    Returns list of (name, y_position) tuples.
    """
    hull_length = params.get('hull_length', params.get('loa', 6100))
    num_sections = params.get('hull_sections', 7)

    # Hull is centered at Y=0 in the design, extending from -hull_length/2 to +hull_length/2
    half_length = hull_length / 2

    positions = []
    for i in range(num_sections):
        # Evenly spaced from bow to stern
        y = -half_length + i * hull_length / (num_sections - 1)
        # Small offset to avoid slicing exactly at shape boundaries
        y_offset = y + 1.0 if abs(y) < 1 else y
        positions.append((f"stn_{i}", y_offset))

    return positions


def get_waterline_positions(params):
    """
    Get Z positions for waterline cuts (full-breadth plan).
    Returns list of (name, z_position) tuples.
    """
    hull_depth = params.get('hull_depth', 900)
    deck_level = params.get('deck_level', 900)
    draft = params.get('hull_draft', params.get('draft', 300))

    # Waterlines from bottom of hull to deck level
    # Include: bottom, a few intermediate levels, waterline, deck
    positions = []

    # Design waterline
    positions.append(("waterline", 1.0))  # Z=0 is the waterline

    # Below waterline
    step = draft / 3
    for i in range(1, 3):
        z = -i * step
        positions.append((f"wl_below_{i}", z))

    # Above waterline
    freeboard = params.get('freeboard', 600)
    step = freeboard / 3
    for i in range(1, 3):
        z = i * step
        if z < deck_level:
            positions.append((f"wl_above_{i}", z))

    # Deck level
    positions.append(("deck", deck_level - 2))

    # Sort by Z position
    positions.sort(key=lambda x: x[1])
    return positions


def slice_shapes_safely(shapes, normal, position):
    """Slice shapes one by one to avoid segfaults with complex compounds."""
    all_wires = []
    for i, shape in enumerate(shapes):
        try:
            wires = shape.slice(normal, position)
            if wires:
                all_wires.extend(wires)
        except Exception as e:
            print(f"      Warning: Could not slice shape {i}: {e}", flush=True)
    return all_wires


def export_wires_to_svg(wires, svg_path, view='XZ', target_size=800,
                        stroke_width=1.0, clip_z=None):
    """Export a list of wires to an SVG file with scale bar.

    Args:
        wires: List of Part.Wire objects
        svg_path: Output file path
        view: Which plane to project to ('XZ', 'XY', 'YZ', 'YX')
        target_size: Target size for the larger dimension in SVG units
        stroke_width: Line width in SVG
        clip_z: Maximum Z value to include
    """
    all_points = []
    for wire in wires:
        for edge in wire.Edges:
            points = edge.discretize(50)
            if clip_z is not None:
                points = [p for p in points if p.z <= clip_z]
            all_points.extend(points)

    if not all_points:
        return

    def map_point(p):
        if view == 'XZ':
            return (p.x, -p.z)
        elif view == 'XY':
            return (p.x, -p.y)
        elif view == 'YX':
            return (p.y, -p.x)
        elif view == 'YZ':
            return (p.y, -p.z)
        return (p.x, -p.y)

    mapped = [map_point(p) for p in all_points]
    min_x = min(p[0] for p in mapped)
    max_x = max(p[0] for p in mapped)
    min_y = min(p[1] for p in mapped)
    max_y = max(p[1] for p in mapped)

    extent_x = max(max_x - min_x, 0.1)
    extent_y = max(max_y - min_y, 0.1)

    scale = target_size / max(extent_x, extent_y)
    margin = 40
    scale_bar_height = 30

    width = extent_x * scale + 2 * margin
    height = extent_y * scale + 2 * margin + scale_bar_height
    offset_x = -min_x * scale + margin
    offset_y = -min_y * scale + margin

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{width:.1f}" height="{height:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">',
        f'<g fill="none" stroke="black" stroke-width="{stroke_width}">'
    ]

    for wire in wires:
        for edge in wire.Edges:
            points = edge.discretize(50)
            if clip_z is not None:
                points = [p for p in points if p.z <= clip_z]
            if len(points) >= 2:
                path_data = []
                for i, p in enumerate(points):
                    x, y = map_point(p)
                    sx = x * scale + offset_x
                    sy = y * scale + offset_y
                    if i == 0:
                        path_data.append(f"M {sx:.2f} {sy:.2f}")
                    else:
                        path_data.append(f"L {sx:.2f} {sy:.2f}")
                svg_lines.append(f'<path d="{" ".join(path_data)}"/>')

    svg_lines.append('</g>')

    # Scale bar
    max_extent_mm = max(extent_x, extent_y)
    if max_extent_mm > 5000:
        bar_length_mm, bar_label = 1000, "1 m"
    elif max_extent_mm > 2000:
        bar_length_mm, bar_label = 500, "0.5 m"
    elif max_extent_mm > 500:
        bar_length_mm, bar_label = 200, "200 mm"
    else:
        bar_length_mm, bar_label = 100, "100 mm"

    bar_length_svg = bar_length_mm * scale
    bar_x = margin
    bar_y = height - 15

    svg_lines.append('<g stroke="black" stroke-width="1" fill="black">')
    svg_lines.append(
        f'<line x1="{bar_x:.1f}" y1="{bar_y:.1f}" '
        f'x2="{bar_x + bar_length_svg:.1f}" y2="{bar_y:.1f}"/>')
    svg_lines.append(
        f'<line x1="{bar_x:.1f}" y1="{bar_y - 5:.1f}" '
        f'x2="{bar_x:.1f}" y2="{bar_y + 5:.1f}"/>')
    svg_lines.append(
        f'<line x1="{bar_x + bar_length_svg:.1f}" y1="{bar_y - 5:.1f}" '
        f'x2="{bar_x + bar_length_svg:.1f}" y2="{bar_y + 5:.1f}"/>')
    svg_lines.append(
        f'<text x="{bar_x + bar_length_svg / 2:.1f}" y="{bar_y - 8:.1f}" '
        f'text-anchor="middle" font-family="sans-serif" font-size="10">'
        f'{bar_label}</text>')
    svg_lines.append('</g>')

    svg_lines.append('</svg>')

    with open(svg_path, 'w') as f:
        f.write('\n'.join(svg_lines))


def export_wire_groups_to_svg(wire_groups, svg_path, view='XZ',
                              target_size=800, stroke_width=1.0, clip_z=None):
    """Export multiple groups of wires to an SVG file with different colors.

    Args:
        wire_groups: List of (wires, color) tuples, drawn in order
        svg_path: Output file path
        view: Which plane to project to
        target_size: Target size for the larger dimension in SVG units
        stroke_width: Line width in SVG
        clip_z: Maximum Z value to include
    """
    all_points = []
    for wires, color in wire_groups:
        for wire in wires:
            for edge in wire.Edges:
                points = edge.discretize(50)
                if clip_z is not None:
                    points = [p for p in points if p.z <= clip_z]
                all_points.extend(points)

    if not all_points:
        return

    def map_point(p):
        if view == 'XZ':
            return (p.x, -p.z)
        elif view == 'XY':
            return (p.x, -p.y)
        elif view == 'YX':
            return (p.y, -p.x)
        elif view == 'YZ':
            return (p.y, -p.z)
        return (p.x, -p.y)

    mapped = [map_point(p) for p in all_points]
    min_x = min(p[0] for p in mapped)
    max_x = max(p[0] for p in mapped)
    min_y = min(p[1] for p in mapped)
    max_y = max(p[1] for p in mapped)

    extent_x = max(max_x - min_x, 0.1)
    extent_y = max(max_y - min_y, 0.1)

    scale = target_size / max(extent_x, extent_y)
    margin = 40
    scale_bar_height = 30

    width = extent_x * scale + 2 * margin
    height = extent_y * scale + 2 * margin + scale_bar_height
    offset_x = -min_x * scale + margin
    offset_y = -min_y * scale + margin

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{width:.1f}" height="{height:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">'
    ]

    for wires, color in wire_groups:
        svg_lines.append(
            f'<g fill="none" stroke="{color}" stroke-width="{stroke_width}">')
        for wire in wires:
            for edge in wire.Edges:
                points = edge.discretize(50)
                if clip_z is not None:
                    points = [p for p in points if p.z <= clip_z]
                if len(points) >= 2:
                    path_data = []
                    for i, p in enumerate(points):
                        x, y = map_point(p)
                        sx = x * scale + offset_x
                        sy = y * scale + offset_y
                        if i == 0:
                            path_data.append(f"M {sx:.2f} {sy:.2f}")
                        else:
                            path_data.append(f"L {sx:.2f} {sy:.2f}")
                    svg_lines.append(f'<path d="{" ".join(path_data)}"/>')
        svg_lines.append('</g>')

    # Scale bar
    max_extent_mm = max(extent_x, extent_y)
    if max_extent_mm > 5000:
        bar_length_mm, bar_label = 1000, "1 m"
    elif max_extent_mm > 2000:
        bar_length_mm, bar_label = 500, "0.5 m"
    elif max_extent_mm > 500:
        bar_length_mm, bar_label = 200, "200 mm"
    else:
        bar_length_mm, bar_label = 100, "100 mm"

    bar_length_svg = bar_length_mm * scale
    bar_x = margin
    bar_y = height - 15

    svg_lines.append('<g stroke="black" stroke-width="1" fill="black">')
    svg_lines.append(
        f'<line x1="{bar_x:.1f}" y1="{bar_y:.1f}" '
        f'x2="{bar_x + bar_length_svg:.1f}" y2="{bar_y:.1f}"/>')
    svg_lines.append(
        f'<line x1="{bar_x:.1f}" y1="{bar_y - 5:.1f}" '
        f'x2="{bar_x:.1f}" y2="{bar_y + 5:.1f}"/>')
    svg_lines.append(
        f'<line x1="{bar_x + bar_length_svg:.1f}" y1="{bar_y - 5:.1f}" '
        f'x2="{bar_x + bar_length_svg:.1f}" y2="{bar_y + 5:.1f}"/>')
    svg_lines.append(
        f'<text x="{bar_x + bar_length_svg / 2:.1f}" y="{bar_y - 8:.1f}" '
        f'text-anchor="middle" font-family="sans-serif" font-size="10">'
        f'{bar_label}</text>')
    svg_lines.append('</g>')

    svg_lines.append('</svg>')

    with open(svg_path, 'w') as f:
        f.write('\n'.join(svg_lines))


def collect_shapes(design_doc):
    """Collect all relevant solid shapes from the design document."""
    exclude_patterns = [
        'origin', 'indicator', 'arrow',
        'load', 'air', 'plane',
    ]

    exclude_types = [
        'App::Origin',
        'App::Line',
        'App::Plane',
    ]

    # Build parent placement map
    parent_part_map = {}
    for obj in design_doc.Objects:
        if obj.TypeId == 'App::Part':
            if hasattr(obj, 'Group'):
                for child in obj.Group:
                    parent_part_map[child.Name] = obj
                    if hasattr(child, 'Group'):
                        for grandchild in child.Group:
                            parent_part_map[grandchild.Name] = obj

    shapes = []
    for obj in design_doc.Objects:
        if not (hasattr(obj, 'Shape') and obj.Shape and not obj.Shape.isNull()):
            continue
        if obj.TypeId in exclude_types:
            continue
        if obj.TypeId == 'App::Part':
            continue

        name_lower = obj.Name.lower()
        if any(pattern in name_lower for pattern in exclude_patterns):
            print(f"  Skipped: {obj.Name}")
            continue

        shape = obj.Shape.copy()
        if obj.Name in parent_part_map:
            parent_placement = parent_part_map[obj.Name].Placement
            if not parent_placement.isIdentity():
                shape = shape.transformed(parent_placement.toMatrix())

        if shape.Volume > 1:
            shapes.append(shape)
            print(f"  Added: {obj.Name} (Volume: {shape.Volume:.0f} mm3)")

    return shapes


def create_lines_plan(design_path, params, output_dir, boat_name, config_name):
    """Create lines plan drawings for the keelboat."""

    print(f"Opening design: {design_path}")
    design_doc = App.openDocument(design_path)
    design_doc.recompute()

    lines_doc = App.newDocument("LinesPlan")

    print("Collecting shapes from design...")
    shapes = collect_shapes(design_doc)

    if not shapes:
        print("ERROR: No shapes found in design")
        return False

    print(f"Total shapes collected: {len(shapes)}")

    compound = Part.makeCompound(shapes)
    vessel = lines_doc.addObject("Part::Feature", "Vessel")
    vessel.Shape = compound
    lines_doc.recompute()

    bbox = compound.BoundBox
    print(f"Vessel bounds: X=[{bbox.XMin:.0f}, {bbox.XMax:.0f}], "
          f"Y=[{bbox.YMin:.0f}, {bbox.YMax:.0f}], "
          f"Z=[{bbox.ZMin:.0f}, {bbox.ZMax:.0f}]")

    base_name = f"{boat_name}.{config_name}.lines"

    # Clip Z to slightly above deck (exclude tall mast from sections)
    deck_level = params.get('deck_level', 900)
    clip_z = deck_level + 500

    # =========================================================================
    # 1. Profile view (side elevation) — slice at X=0 (centerline)
    # =========================================================================
    print("Exporting profile view...", flush=True)
    try:
        normal = App.Vector(1, 0, 0)
        wires = slice_shapes_safely(shapes, normal, 1.0)  # Small offset from centerline
        if wires:
            # Full version with mast (for summary page and website)
            svg_path = os.path.join(output_dir, f"{base_name}.profile.full.svg")
            export_wires_to_svg(wires, svg_path, view='YZ')
            print(f"  Exported profile (full): {svg_path}", flush=True)

            # Clipped version without mast (for full-page detail)
            svg_path = os.path.join(output_dir, f"{base_name}.profile.svg")
            export_wires_to_svg(wires, svg_path, view='YZ', clip_z=clip_z)
            print(f"  Exported profile (clipped): {svg_path}", flush=True)
        else:
            print("  Warning: No wires for profile view", flush=True)
    except Exception as e:
        import traceback
        print(f"  Error exporting profile: {e}", flush=True)
        traceback.print_exc()

    # =========================================================================
    # 2. Body plan (cross-sections) — slices perpendicular to Y axis
    # =========================================================================
    section_positions = get_section_positions(params)
    print(f"Exporting {len(section_positions)} body plan sections...", flush=True)

    # Export individual section SVGs
    for name, y_pos in section_positions:
        try:
            print(f"  Slicing at Y={y_pos:.0f} for section '{name}'...", flush=True)
            normal = App.Vector(0, 1, 0)
            wires = slice_shapes_safely(shapes, normal, y_pos)
            if wires:
                svg_path = os.path.join(output_dir, f"{base_name}.section.{name}.svg")
                export_wires_to_svg(wires, svg_path, view='XZ', clip_z=clip_z)
                print(f"    Exported: {svg_path}", flush=True)
            else:
                print(f"    Warning: No section found at Y={y_pos}", flush=True)
        except Exception as e:
            import traceback
            print(f"  Error exporting section '{name}': {e}", flush=True)
            traceback.print_exc()

    # Export combined body plan (all sections overlayed in black)
    print("Exporting combined body plan...", flush=True)
    try:
        normal = App.Vector(0, 1, 0)
        wire_groups = []
        for name, y_pos in section_positions:
            wires = slice_shapes_safely(shapes, normal, y_pos)
            if wires:
                wire_groups.append((wires, 'black'))

        if wire_groups:
            # Full version with mast (for summary page and website)
            svg_path = os.path.join(output_dir, f"{base_name}.bodyplan.full.svg")
            export_wire_groups_to_svg(
                wire_groups, svg_path, view='XZ', target_size=600)
            print(f"  Exported combined body plan (full): {svg_path}", flush=True)

            # Clipped version without mast (for full-page detail)
            svg_path = os.path.join(output_dir, f"{base_name}.bodyplan.svg")
            export_wire_groups_to_svg(
                wire_groups, svg_path, view='XZ',
                target_size=600, clip_z=clip_z)
            print(f"  Exported combined body plan (clipped): {svg_path}", flush=True)
    except Exception as e:
        import traceback
        print(f"  Error exporting combined body plan: {e}", flush=True)
        traceback.print_exc()

    # =========================================================================
    # 3. Half-breadth plan (top view) — slices perpendicular to Z axis
    # =========================================================================
    waterline_positions = get_waterline_positions(params)
    print(f"Exporting {len(waterline_positions)} full-breadth waterlines...", flush=True)

    # Export individual waterline SVGs
    for name, z_pos in waterline_positions:
        try:
            print(f"  Slicing at Z={z_pos:.0f} for waterline '{name}'...", flush=True)
            normal = App.Vector(0, 0, 1)
            wires = slice_shapes_safely(shapes, normal, z_pos)
            if wires:
                svg_path = os.path.join(output_dir, f"{base_name}.waterline.{name}.svg")
                export_wires_to_svg(wires, svg_path, view='YX')
                print(f"    Exported: {svg_path}", flush=True)
            else:
                print(f"    Warning: No waterline found at Z={z_pos}", flush=True)
        except Exception as e:
            import traceback
            print(f"  Error exporting waterline '{name}': {e}", flush=True)
            traceback.print_exc()

    # Export combined full-breadth plan (all waterlines overlayed)
    print("Exporting combined full-breadth plan...", flush=True)
    try:
        normal = App.Vector(0, 0, 1)
        wire_groups = []
        for name, z_pos in waterline_positions:
            wires = slice_shapes_safely(shapes, normal, z_pos)
            if wires:
                wire_groups.append((wires, 'black'))

        if wire_groups:
            svg_path = os.path.join(output_dir, f"{base_name}.fullbreadth.svg")
            export_wire_groups_to_svg(wire_groups, svg_path, view='YX',
                                     target_size=800)
            print(f"  Exported combined full-breadth: {svg_path}", flush=True)
    except Exception as e:
        import traceback
        print(f"  Error exporting combined full-breadth: {e}", flush=True)
        traceback.print_exc()

    # =========================================================================
    # Save lines plan FreeCAD document
    # =========================================================================
    fcstd_path = os.path.join(output_dir, f"{base_name}.FCStd")
    lines_doc.saveAs(fcstd_path)
    print(f"Saved lines plan document: {fcstd_path}")

    # =========================================================================
    # Generate LaTeX document
    # =========================================================================
    print("Generating LaTeX document...")
    latex_path = os.path.join(output_dir, f"{base_name}.tex")
    latex_content = generate_latex(
        boat_name, config_name, params,
        section_positions, waterline_positions, base_name)

    with open(latex_path, 'w') as f:
        f.write(latex_content)
    print(f"Generated LaTeX: {latex_path}")

    # Cleanup
    try:
        App.closeDocument(design_doc.Name)
    except Exception as e:
        print(f"Note: Could not close design doc: {e}")
    try:
        App.closeDocument(lines_doc.Name)
    except Exception as e:
        print(f"Note: Could not close lines doc: {e}")

    return True


def generate_latex(boat_name, config_name, params, sections, waterlines,
                   base_name):
    """Generate LaTeX document for the keelboat lines plan."""

    loa = params.get('loa', 6100)
    lwl = params.get('lwl', 5600)
    beam = params.get('beam', 2200)
    draft = params.get('total_draft', params.get('draft', 1200))
    hull_draft = params.get('hull_draft', 300)
    freeboard = params.get('freeboard', 600)
    deck_level = params.get('deck_level', 900)
    displacement = params.get('displacement_estimate_kg', 0)
    sail_area = params.get('sail_area_m2', 0)
    mast_height = params.get('mast_height', 8000)
    ballast_ratio = params.get('ballast_ratio', 0)

    def escape_latex(s):
        return s.replace('_', r'\_')

    section_rows = "\n".join([
        f"        {escape_latex(name)} & {y_pos:.0f} \\\\"
        for name, y_pos in sections
    ])

    waterline_rows = "\n".join([
        f"        {escape_latex(name)} & {z_pos:.0f} \\\\"
        for name, z_pos in waterlines
    ])

    # Generate section figure includes
    section_figures = []
    for name, y_pos in sections:
        svg_name = f"{base_name}.section.{name}"
        section_figures.append(
            f"\\begin{{figure}}[H]\n"
            f"\\centering\n"
            f"\\IfFileExists{{{svg_name}.pdf}}{{%\n"
            f"    \\includegraphics[width=0.95\\textwidth,height=0.85\\textheight,"
            f"keepaspectratio]{{{svg_name}.pdf}}\n"
            f"}}{{%\n"
            f"    \\textit{{(Section {escape_latex(name)}: see {escape_latex(base_name)}.FCStd)}}\n"
            f"}}\n"
            f"\\caption{{Body Plan---Section at {escape_latex(name)} (Y={y_pos:.0f}mm)}}\n"
            f"\\end{{figure}}"
        )
    section_figures_tex = "\n\n".join(section_figures)

    waterline_figures = []
    for name, z_pos in waterlines:
        svg_name = f"{base_name}.waterline.{name}"
        waterline_figures.append(
            f"\\begin{{figure}}[H]\n"
            f"\\centering\n"
            f"\\IfFileExists{{{svg_name}.pdf}}{{%\n"
            f"    \\includegraphics[width=0.95\\textwidth,height=0.85\\textheight,"
            f"keepaspectratio]{{{svg_name}.pdf}}\n"
            f"}}{{%\n"
            f"    \\textit{{(Waterline {escape_latex(name)}: see {escape_latex(base_name)}.FCStd)}}\n"
            f"}}\n"
            f"\\caption{{Full-Breadth---Waterline {escape_latex(name)} (Z={z_pos:.0f}mm)}}\n"
            f"\\end{{figure}}"
        )
    waterline_figures_tex = "\n\n".join(waterline_figures)

    latex = f"""\\documentclass[a3paper,landscape]{{article}}
\\usepackage[margin=20mm]{{geometry}}
\\usepackage{{graphicx}}
\\usepackage{{booktabs}}
\\usepackage{{float}}
\\usepackage{{caption}}

\\title{{Lines Plan: {boat_name.upper()} - {config_name.title()}}}

\\begin{{document}}

%% ===== SUMMARY PAGE =====
\\section*{{Lines Plan of {boat_name.upper()}}}

\\noindent
\\begin{{minipage}}[t]{{0.25\\textwidth}}
\\subsection*{{Profile}}
\\IfFileExists{{{base_name}.profile.full.pdf}}{{%
\\includegraphics[width=\\textwidth,keepaspectratio]{{{base_name}.profile.full.pdf}}
}}{{%
    \\textit{{(Profile: see {escape_latex(base_name)}.FCStd)}}
}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.22\\textwidth}}
\\subsection*{{Body Plan}}
\\IfFileExists{{{base_name}.bodyplan.full.pdf}}{{%
\\includegraphics[width=\\textwidth,keepaspectratio]{{{base_name}.bodyplan.full.pdf}}
}}{{%
    \\textit{{(Body plan)}}
}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.38\\textwidth}}
\\subsection*{{Full-Breadth Plan}}
\\IfFileExists{{{base_name}.fullbreadth.pdf}}{{%
\\includegraphics[width=\\textwidth,keepaspectratio]{{{base_name}.fullbreadth.pdf}}
}}{{%
    \\textit{{(Half-breadth plan)}}
}}
\\end{{minipage}}

\\vspace{{1cm}}
\\noindent
\\begin{{minipage}}[t]{{0.20\\textwidth}}
\\subsection*{{Section Stations}}
\\begin{{tabular}}{{lr}}
\\toprule
Station & Y (mm) \\\\
\\midrule
{section_rows}
\\bottomrule
\\end{{tabular}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.20\\textwidth}}
\\subsection*{{Waterline Heights}}
\\begin{{tabular}}{{lr}}
\\toprule
Waterline & Z (mm) \\\\
\\midrule
{waterline_rows}
\\bottomrule
\\end{{tabular}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.25\\textwidth}}
\\subsection*{{Principal Dimensions}}
\\begin{{tabular}}{{lr}}
\\toprule
\\textbf{{Parameter}} & \\textbf{{Value}} \\\\
\\midrule
LOA & {loa / 1000:.2f} m \\\\
LWL & {lwl / 1000:.2f} m \\\\
Beam & {beam / 1000:.2f} m \\\\
Draft (total) & {draft / 1000:.2f} m \\\\
Hull Draft & {hull_draft / 1000:.2f} m \\\\
Freeboard & {freeboard / 1000:.2f} m \\\\
Deck Level & {deck_level / 1000:.2f} m \\\\
\\bottomrule
\\end{{tabular}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.25\\textwidth}}
\\subsection*{{Performance}}
\\begin{{tabular}}{{lr}}
\\toprule
\\textbf{{Parameter}} & \\textbf{{Value}} \\\\
\\midrule
Displacement & {displacement:.0f} kg \\\\
Sail Area & {sail_area:.1f} m\\textsuperscript{{2}} \\\\
Mast Height & {mast_height / 1000:.2f} m \\\\
Ballast Ratio & {ballast_ratio * 100:.1f}\\% \\\\
\\bottomrule
\\end{{tabular}}
\\end{{minipage}}

%% ===== PROFILE =====
\\newpage
\\section*{{Profile (Sheer Plan)}}

\\begin{{figure}}[H]
\\centering
\\IfFileExists{{{base_name}.profile.pdf}}{{%
    \\includegraphics[width=0.95\\textwidth,height=0.85\\textheight,keepaspectratio]{{{base_name}.profile.pdf}}
}}{{%
    \\textit{{(Profile: see {escape_latex(base_name)}.FCStd)}}
}}
\\caption{{Profile---Centerline section (X=0)}}
\\end{{figure}}

%% ===== BODY PLAN =====
\\newpage
\\section*{{Body Plan}}

\\begin{{figure}}[H]
\\centering
\\IfFileExists{{{base_name}.bodyplan.pdf}}{{%
    \\includegraphics[width=0.95\\textwidth,height=0.85\\textheight,keepaspectratio]{{{base_name}.bodyplan.pdf}}
}}{{%
    \\textit{{(Body plan: see {escape_latex(base_name)}.FCStd)}}
}}
\\caption{{Combined body plan---All sections overlayed}}
\\end{{figure}}

{section_figures_tex}

%% ===== FULL-BREADTH PLAN =====
\\newpage
\\section*{{Full-Breadth Plan}}

\\begin{{figure}}[H]
\\centering
\\IfFileExists{{{base_name}.fullbreadth.pdf}}{{%
    \\includegraphics[width=0.95\\textwidth,height=0.85\\textheight,keepaspectratio]{{{base_name}.fullbreadth.pdf}}
}}{{%
    \\textit{{(Full-breadth plan: see {escape_latex(base_name)}.FCStd)}}
}}
\\caption{{Combined full-breadth plan---All waterlines overlayed}}
\\end{{figure}}

{waterline_figures_tex}

\\end{{document}}
"""
    return latex


if __name__ == "__main__":
    # Get arguments from environment variables
    design_path = os.environ.get('DESIGN_FILE')
    parameter_path = os.environ.get('PARAMETER_FILE')
    output_dir = os.environ.get('OUTPUT_DIR')

    if not design_path or not parameter_path or not output_dir:
        print("ERROR: Required environment variables not set")
        print(f"  DESIGN_FILE={design_path}")
        print(f"  PARAMETER_FILE={parameter_path}")
        print(f"  OUTPUT_DIR={output_dir}")
        sys.exit(1)

    print(f"Design file: {design_path}")
    print(f"Parameter file: {parameter_path}")
    print(f"Output directory: {output_dir}")

    # Load parameters
    with open(parameter_path) as f:
        params = json.load(f)

    boat_name = params.get('boat_name', 'unknown')
    config_name = params.get('configuration_name', 'unknown')

    # Initialize GUI for headless operation
    init_gui()

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Generate lines plan
    success = create_lines_plan(
        design_path, params, output_dir,
        boat_name, config_name
    )

    # Exit cleanly
    import os as _os
    _os._exit(0 if success else 1)
