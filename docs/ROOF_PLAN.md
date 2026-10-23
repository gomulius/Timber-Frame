# Roof to Frame — plan

Convert a BIM Roof object into a timber rafter frame.

Phased: start with a **single-slope (shed) roof**. The infrastructure
(dialog, settings, member types, command, Regenerate hook, blueprint
view) is reused for later phases.

Everything is additive. Default settings leave the feature disabled so
existing wall + floor flows are untouched.

---

## Confirmed from the current sample (`Roof001`)

- Base = `Dach` sketch, flat rectangle 3600 x 5700 mm at Z = 2300.
- `Angles = [2.0, 45.0, 45.0, 45.0]` and `Runs = [6000, 0, 0, 0]` →
  **single pitch along edge 0 only** (the three 45°/0 slots are unused
  defaults).
- `Thickness = [150, 50, 50, 50]` → material depth 150 mm along the
  pitched edge.
- `Overhang = [0, 0, 0, 0]`.
- `Flip = True` → ridge is on the opposite edge of what the sketch
  edge-0 orientation implies. Diagnostic will confirm up-slope direction
  from the slope face normal.
- Pitch ~ 2° (very shallow); slope face normal `nz` ~ 0.999 — so the
  face classifier must NOT reject faces with `nz` close to 1.

---

## Scope

### Phase 1 — Single-slope (shed) roof
Everything in this document ships in Phase 1.

### Phase 2 — Flat roof (nice to have, rare but valid)
A flat roof is just a very shallow single-slope with `slope_angle ≈ 0`
(say, below ~0.5°). It still needs **drainage fall** in practice, but
the frame itself is a plain horizontal joist platform — essentially
equivalent to the floor converter running on top of the walls.

We will:
- Detect it from the roof's `Angles` property: if **all pitched angles
  are < 0.5°** (or all `Runs` are zero and `Angles` are 0), treat the
  roof as flat.
- Route the geometry through `FloorFrameCalculator` with the roof's
  own settings mapped onto floor settings (rafter → joist,
  wall_plate → rim). This re-uses step-3 code and keeps the result
  consistent with floor frames.
- Keep the user-visible command, dialog, and icon as "Convert Roof".
  The user doesn't need to think "oh I should use the slab command for
  my flat roof".

### Phase 3 — Multi-slope roofs (gable, hip, mono-pitch over L-shape)
Deferred, but the architecture must not paint us into a corner.

Needed changes when we get there:
- `extract_roof_data()` returns a **list of slope faces**, not one.
- Each slope face becomes its own `_RoofPitch` with its own eave edge,
  ridge edge (or hip apex), up-slope axis, rafter length, overhang.
- Geometry builder iterates over pitches, emits rafters + wall plate
  per pitch, and emits **hip / valley / ridge** members along the
  shared edges.
- Opening (skylight, dormer) handling stays the same — each pitch
  solves its own openings independently.

This document calls out which pieces of the Phase 1 code must stay
pluggable so Phase 3 is additive, not a rewrite.

---

## Shared infrastructure (reused from wall + floor features)

- `TimberSettings` gains a Roof block (see "Settings" below).
- `TimberMember.TYPES` extends with new roof member types.
- Frame group carries `SourceRoof` link + the usual
  `TimberSettingsJSON`, so Regenerate works out of the box.
- Dedicated `RoofSettingsDialog`, same `_BaseSettingsDialog` scaffold.
- Dedicated `ConvertRoofCommand` with its own icon.
- Blueprint command picks a sensible view (new view type: along-eave
  rafter elevation).

### Settings

```
Roof
├── enabled: bool                       default False
├── rafter_width: float (mm)            45
├── rafter_depth: float (mm)            180      # perpendicular to slope
├── rafter_spacing: float (mm)          600
├── wall_plate: bool                    True     # eave side plate
├── ridge_plate: bool                   True     # ridge side plate
├── roof_sheathing_thickness: float     18       # 0 = off
├── roof_overhang_eave: float           0        # mm, overrides roof's 0
├── roof_overhang_rake: float           0
└── flat_roof_threshold_deg: float      0.5      # Phase 2 trigger
```

Dialog layout: Rafters / Perimeter / Sheathing — same visual language
as the floor dialog, three group boxes. On save `roof_enabled = True`.

### New member types

```
TimberMember.TYPES += {
    'rafter':            'Rafter',
    'wall_plate_roof':   'Roof Wall Plate',
    'ridge_plate':       'Ridge Plate',
    'roof_trimmer':      'Roof Trimmer',
    'roof_header':       'Roof Header',
    'roof_tail_rafter':  'Tail Rafter',
    'roof_sheathing':    'Roof Sheathing',
}
```

### Icon

`convert_roof.svg` — sloped slab at the bottom (grey, tilted bar),
up-arrow in the middle (green, consistent with wall/slab icons), rafter
frame at the top (one tilted "roof outline" with 3–4 tilted rafters
inside, matching the brown colour scheme of the other icons).

---

## Phase 1 implementation steps (small commits)

### R1 — Settings + dialog (no geometry)
- Add Roof block to `TimberSettings`, serialise in `to_dict`/`from_dict`.
- Add roof member types.
- Add `convert_roof.svg`.
- Add `RoofSettingsDialog` subclass of `_BaseSettingsDialog`.
- Stub `ConvertRoofCommand` that shows the dialog and prints "not yet
  implemented". Registered in `InitGui.py` toolbar/menu.

Smoke test: menu entry appears, icon renders, dialog opens with the
correct controls, OK/Cancel work.

### R2 — Roof data extraction (`extract_roof_data`)
- `_roof_slope_faces(roof_obj)` returns a list of (face, normal) with
  `nz > 0.01 AND |n_xy| > tiny` — handles shallow (2°) pitches.
- If 0 slope faces found: **flat-roof branch** (Phase 2 trigger).
- If more than 1 slope face found: raise `NotImplementedError` with a
  clear message pointing at Phase 3.
- For the single-slope case, derive and return:
  ```
  {
    'origin_eave':     Vector,      # eave corner, lowest Z
    'eave_axis':       Vector,      # unit, along the eave edge
    'up_slope_axis':   Vector,      # unit, along slope in 3D
                                    #        from eave toward ridge
    'eave_length':     float,       # length of the eave edge
    'rafter_length':   float,       # slope distance eave->ridge
    'slope_angle_rad': float,
    'face_normal':     Vector,
    'eave_z':          float,
    'ridge_z':         float,
    'thickness':       float,       # material depth from Thickness[0]
    'overhang_eave':   float,       # from roof.Overhang or settings
    'overhang_rake':   float,
    'placement':       Placement,
    'openings':        list[RoofOpening],
    'is_flat':         False,
  }
  ```
- For the flat-roof case same dict, but `is_flat=True`,
  `slope_angle_rad=0`, `up_slope_axis` picked by the base sketch's long
  axis (so joists span the shorter side, same convention as floors).

Diagnostic smoke test: run `diagnose_roof.py` against the sample and
confirm every field matches hand calculations from the earlier
diagnostic output.

### R3 — Rafter + plate geometry
- New helper `_tilted_box(p1, p2, side_dir, side_len, thickness, normal)`
  that produces a solid using the proven `polygon → extrude` pattern.
- `RoofFrameCalculator.calculate()` produces `TimberMember`s with a new
  orientation tag `'roof_rafter'` / `'roof_plate'`. Fields:
  - `rafter`: p1, p2, width (along eave), depth (perpendicular to slope).
  - `wall_plate_roof`: along the eave, laid flat.
  - `ridge_plate`: along the ridge, laid flat.
- `create_roof_frame_group` turns members into world shapes using the
  same `(origin, x_axis, y_axis)`-style basis but on a slope plane.

Smoke test: `ConvertRoofCommand` on the sample produces one plate at
Z = ~2300 along the eave, one plate at Z = ~2300 + rise along the
ridge, and rafters tilted between them. Visually inspect: rafters sit
on top of the wall plate.

### R4 — Overhangs
- `roof_overhang_eave` extends every rafter backward from the eave
  (direction `-up_slope_axis`).
- `roof_overhang_rake` extends the plates past the two gable ends and
  shifts the first/last rafter outward.

Smoke test: non-zero overhangs produce a visibly bigger roof footprint
than the walls below.

### R5 — Roof sheathing
- Single sloped slab using the slope-face outer wire extruded by
  `roof_sheathing_thickness` along the face normal. Lives directly
  above the rafters.

### R6 — Openings (skylight / chimney)
- `RoofOpening` with (along-eave, along-slope, width, length) in
  slope-local 2D.
- Follow floor-opening model: trimmers along the long edges of the hole,
  roof headers across the short edges, tail rafters between the headers
  and the full-length rafters.

### R7 — Blueprint integration
- Blueprint view picker gains a `ROOF` branch:
  - Plan view from above (natural when printed with north arrow).
  - Optional along-eave elevation showing a single rafter's profile +
    slope angle — this is what framers actually print.

### R8 — Regenerate + cut list
- `_tag_roof_frame_group(group, roof, settings)` with `SourceRoof` link.
- `_frame_groups_with_source` recognises `SourceRoof`.
- Cut list rolls up rafters by `(length rounded, cross-section)` same
  way studs/joists already do.

### R9 — Phase 2 (flat roof)
- When `extract_roof_data` returns `is_flat=True`, route through
  `FloorFrameCalculator` with:
  ```
  calc = FloorFrameCalculator(eave_length, rafter_length, settings_mapped)
  ```
  where `settings_mapped` is a floor settings copy with
  `joist_width = rafter_width`, `joist_depth = rafter_depth`,
  `joist_spacing = rafter_spacing`, `floor_rim_board = wall_plate`,
  `floor_sheathing_thickness = roof_sheathing_thickness`.
- Final geometry is translated up to the roof's Z level.
- User-visible behaviour: `Convert Roof to Frame` just works on both
  pitched and flat roofs.

---

## Phase-3 hooks baked into Phase 1

The following choices in Phase 1 are made specifically so Phase 3
doesn't require a rewrite:

1. **`extract_roof_data` returns `openings`, `is_flat`, and a single
   dict today — but as a `List[Dict]` internally.** Phase 1 just wraps
   it with `return pitches[0]`. Phase 3 unwraps the list.
2. **`_tilted_box(p1, p2, side_dir, side_len, thickness, normal)` is
   generic in its basis.** It doesn't assume horizontal eave or vertical
   ridge. Phase 3 hip/valley members use it unchanged.
3. **`RoofFrameCalculator` takes a `pitch_descriptor` dict**, not raw
   positional args. Phase 3 instantiates one per pitch and emits
   members tagged with a `pitch_index`.
4. **Member types are generic.** `rafter`, `wall_plate_roof`,
   `ridge_plate`, `roof_header`, `roof_trimmer`, `roof_tail_rafter`
   cover both single-slope and gable rafter frames. Phase 3 only has to
   add `hip_rafter`, `valley_rafter`, `common_rafter_shortened`.
5. **Regenerate uses `TimberSettingsJSON` only.** No branch on roof
   type. Phase 3 roofs regenerate identically.

---

## What I will ask the user before writing code

- Nothing more needed for Phase 1. The current `diagnose_roof.py` output
  plus the planned fix to the face classifier is enough.
- Phase 2 needs no further input — flat threshold is `0.5°` with a
  settable override.
- Phase 3 will need either an example gable roof model (preferred) or
  a careful spec of how FreeCAD stores multi-slope `Angles` / `Runs`.
