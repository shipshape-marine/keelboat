---
layout: default
title: Keelboat - Parametric Keelboat Design
---

<div style="margin-bottom: 3em;">
  <img src="{{ '/renders/kb1.upwind.render.isometric.png' | relative_url }}" alt="KB1 Keelboat - Isometric View" style="width: 100%; max-width: 1200px; height: auto; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.15); display: block; margin: 0 auto;">
  <p style="text-align: center; color: #666; font-size: 0.9em; margin-top: 0.5em;">KB1 - 6m fiberglass daysailer with fin keel</p>
</div>

## Key Specifications

{% assign params = site.data.kb1_upwind_parameter %}

| Parameter | Value |
|-----------|-------|
| LOA | {{ params.loa | divided_by: 1000.0 }} m |
| LWL | {{ params.lwl | divided_by: 1000.0 }} m |
| Beam | {{ params.beam | divided_by: 1000.0 }} m |
| Draft (total) | {{ params.total_draft | divided_by: 1000.0 }} m |
| Freeboard | {{ params.freeboard | divided_by: 1000.0 }} m |
| Displacement (est.) | {{ params.displacement_estimate_kg | round }} kg |
| Sail Area | {{ params.sail_area_m2 }} m&sup2; |
| Mast Height | {{ params.mast_height | divided_by: 1000.0 }} m |
| Ballast Ratio | {{ params.ballast_ratio | times: 100 | round: 1 }}% |

---

## Renders

<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5em; margin: 2em 0;">
  <div>
    <img src="{{ '/renders/kb1.upwind.render.isometric.png' | relative_url }}" alt="Isometric View" style="width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
    <p style="text-align: center; color: #666; font-size: 0.9em;">Isometric</p>
  </div>
  <div>
    <img src="{{ '/renders/kb1.upwind.render.right.png' | relative_url }}" alt="Right View" style="width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
    <p style="text-align: center; color: #666; font-size: 0.9em;">Starboard</p>
  </div>
  <div>
    <img src="{{ '/renders/kb1.upwind.render.front.png' | relative_url }}" alt="Front View" style="width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
    <p style="text-align: center; color: #666; font-size: 0.9em;">Stern</p>
  </div>
  <div>
    <img src="{{ '/renders/kb1.upwind.render.top.png' | relative_url }}" alt="Top View" style="width: 100%; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
    <p style="text-align: center; color: #666; font-size: 0.9em;">Top</p>
  </div>
</div>

---

## Lines Plan

<div style="margin: 2em 0;">
  <h3>Profile (Sheer Plan)</h3>
  <img src="{{ '/lines/kb1.upwind.lines.profile.svg' | relative_url }}" alt="Profile View" style="width: 100%; max-width: 1000px; background: white; padding: 1em; border: 1px solid #ddd; border-radius: 8px;">
</div>

<div style="margin: 2em 0;">
  <h3>Body Plan (Cross Sections)</h3>
  <img src="{{ '/lines/kb1.upwind.lines.bodyplan.svg' | relative_url }}" alt="Body Plan" style="width: 100%; max-width: 600px; background: white; padding: 1em; border: 1px solid #ddd; border-radius: 8px;">
</div>

<div style="margin: 2em 0;">
  <h3>Half-Breadth Plan (Waterlines)</h3>
  <img src="{{ '/lines/kb1.upwind.lines.halfbreadth.svg' | relative_url }}" alt="Half-Breadth Plan" style="width: 100%; max-width: 1000px; background: white; padding: 1em; border: 1px solid #ddd; border-radius: 8px;">
</div>

<p><a href="{{ '/lines/kb1.upwind.lines.pdf' | relative_url }}">Download full lines plan (PDF)</a></p>

---

## Stability

<div style="margin: 2em 0;">
  <img src="{{ '/renders/kb1.upwind.gz.png' | relative_url }}" alt="GZ Curve" style="width: 100%; max-width: 800px; background: white; padding: 1em; border: 1px solid #ddd; border-radius: 8px; display: block; margin: 0 auto;">
  <p style="text-align: center; color: #666; font-size: 0.9em; margin-top: 0.5em;">GZ righting arm curve</p>
</div>

---

## Mass Breakdown

{% assign mass = site.data.kb1_upwind_mass %}

{% if mass %}
| Component | Mass (kg) |
|-----------|-----------|
{% for item in mass.parts %}| {{ item.name }} | {{ item.mass_kg | round: 1 }} |
{% endfor %}| **Total** | **{{ mass.total_mass_kg | round: 1 }}** |
{% endif %}

---

## Downloads

- [Design (FCStd)]({{ '/downloads/kb1.upwind.design.FCStd' | relative_url }})
- [Colored Design (FCStd)]({{ '/downloads/kb1.upwind.color.FCStd' | relative_url }})
- [Lines Plan (PDF)]({{ '/lines/kb1.upwind.lines.pdf' | relative_url }})

---

<div style="text-align: center; padding: 2em 0; color: #666; font-size: 0.9em;">
  <p><em>Generated from parametric CAD model using <a href="https://github.com/Shipshape">Shipshape</a></em></p>
</div>
