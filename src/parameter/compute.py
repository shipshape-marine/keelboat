"""Compute derived parameters from base parameters (Keelboat-specific)."""

import math
from typing import Dict, Any


def compute_derived(base: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute all derived parameters from base parameters.
    Returns a complete parameter dictionary with both base and derived values.
    """
    params = base.copy()

    # Keel geometry
    keel_root = base['keel_root_chord']
    keel_tip = base['keel_tip_chord']
    keel_span = base['keel_span']
    params['keel_mean_chord'] = (keel_root + keel_tip) / 2
    params['keel_area_mm2'] = params['keel_mean_chord'] * keel_span
    params['keel_aspect_ratio'] = keel_span / params['keel_mean_chord']
    params['keel_root_thickness'] = keel_root * base['keel_thickness_ratio']
    params['keel_tip_thickness'] = keel_tip * base['keel_thickness_ratio']

    # Hull wetted dimensions (approximate)
    params['hull_midship_depth'] = base['hull_depth']
    params['hull_waterline_beam'] = base['hull_beam'] * 0.85

    # Draft breakdown
    params['hull_draft'] = base['hull_depth'] - base['freeboard']
    params['total_draft'] = params['hull_draft'] + keel_span

    # Displacement estimate (for initial guess in buoyancy solver)
    # Prismatic coefficient ~0.55 for a daysailer
    cp = 0.55
    lwl_m = base['lwl'] / 1000
    bwl_m = params['hull_waterline_beam'] / 1000
    draft_m = params['hull_draft'] / 1000
    params['displacement_estimate_kg'] = cp * lwl_m * bwl_m * draft_m * 1025

    # Sail area (mainsail only, approximate triangle)
    mast_h = base['mast_height']
    boom_l = base['boom_length']
    params['sail_area_m2'] = 0.5 * (mast_h / 1000) * (boom_l / 1000)

    # Mast step position (Y coordinate, from midship)
    params['mast_y_position'] = base['hull_length'] / 2 - base['mast_position_from_bow']

    # Rudder position (Y coordinate, near stern)
    params['rudder_y_position'] = -(base['hull_length'] / 2 - base['rudder_offset_from_stern'])

    # Ballast ratio estimate (keel volume * lead density / displacement)
    keel_vol_m3 = (params['keel_area_mm2'] * params['keel_root_thickness'] * 0.7) / 1e9
    params['keel_ballast_kg_estimate'] = keel_vol_m3 * 11340
    if params['displacement_estimate_kg'] > 0:
        params['ballast_ratio'] = (params['keel_ballast_kg_estimate'] /
                                   params['displacement_estimate_kg'])

    # Stability indices
    params['sail_area_displacement_ratio'] = (
        params['sail_area_m2'] /
        (params['displacement_estimate_kg'] / 1000) ** (2/3)
    )

    return params
