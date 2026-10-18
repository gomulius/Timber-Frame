# Siding (boazeria / podbitka) — feasibility & plan

## Is it possible? Yes.

Geometrically siding is much easier than the frame itself: siding is basically
a thin rectangular slab per wall face. We already know, for every segment:

- its start/end points in world space,
- its length,
- its top profile (flat or sloped),
- the wall thickness and where the frame sits inside it.

So a siding panel = a plate aligned with one face of the segment, as tall as
the wall (possibly with a sloped top), as long as the segment, and
`siding_thickness` thick. Doors and windows get subtracted using the openings
data we already have.

## Where it goes in the plugin

```
TimberSettings
├── (existing stud/plate settings)
└── Siding
    ├── enabled: bool                     ─ generate siding? (default True)
    ├── sides: {outer, inner, both}       ─ which face(s) of the wall
    ├── material: wood species / name     ─ picked from a short list
    ├── thickness: float (mm)             ─ e.g. 19 mm boazeria, 22 mm podbitka
    ├── profile: {flat, shiplap, T&G, boazeria vertical, boazeria horizontal}
    ├── board_width: float (mm)           ─ visual grooves only
    ├── orientation: {vertical, horizontal, diagonal}
    ├── overhang_top / overhang_bottom    ─ typical for podbitka under eaves
    └── appearance: wood species picker   ─ oak / pine / larch / spruce / cedar
```

Settings dialog gets a new "Siding" group box with these controls. The settings
dict is serialised just like today, so the `TimberSettingsJSON` on each frame
group will capture them and **Regenerate** will reapply them.

## Where the geometry gets built

For every segment we already run:

```python
calc = Core.WallFrameCalculator(...)
members = calc.calculate_frame()
# ...build boxes...
```

Add after the stud/plate members a new pass (either in `calculate_frame` or
as a sibling function `calculate_siding(members, settings)`) that appends
`siding` `TimberMember`s:

- One rectangular slab per enabled side, placed at the right local Y
  (`y = -thickness` for outer, `y = stud_depth` for inner).
- Length = segment length, height = wall height (or sloped profile),
  depth = siding thickness.
- Subtract every opening's bounding rectangle (window/door) from that slab.

The slab is just a `Part.makeBox` for a flat-top wall, or an extruded polygon
(same technique I already used for the sloped head beam) for a sloped-top
wall. Opening subtraction = `Part.makeBox(opening) → shape.cut(opening_box)`.

A new `TimberMember.member_type` is added:

- `'siding_outer'`
- `'siding_inner'`

Both are tagged orientation `'panel'` so `create_frame_group` / the Commands.py
segment loop branch on it and build the slab.

## How materials work in FreeCAD (short version)

Three layers, from simplest to richest:

1. **ShapeAppearance / ShapeColor + per-face DiffuseColor** (what we already
   do with `_apply_wood_appearance`). Purely visual, in the active document.
   Zero new dependencies.
2. **App::MaterialObject** (Arch workbench "Material" object). A document
   object you can share across many parts; stores Name, Color, Transparency,
   Shininess, etc. Each timber piece gets a `Material` link property. Good
   for cut-list / BIM export (IFC round-trips the material name).
3. **View materials with real textures** (image-mapped). FreeCAD can apply
   a texture via `ViewObject.ShapeMaterial` on supported shapes, but applying
   image textures programmatically is version-dependent. We'd ship a few
   preset textures (JPG/PNG in `Resources/textures/`) and apply them to the
   siding ViewObject.

**Recommended path for this plugin**:

- Phase 1: level 1 + level 2. One `App::MaterialObject` per selected wood
  species, shared by all siding parts across the document. Visually distinct
  via `ShapeAppearance` (colour + shininess per species). No external texture
  files required, zero compatibility risk.
- Phase 2 (optional, later): drop a handful of seamless 1024px PNG textures
  into `Resources/textures/` (pine, oak, larch, spruce, cedar) and apply them
  to the siding ViewObject only. Cheap, but only when the user asks for it.

A tiny species table lives in `TimberFrameCore.py`:

```python
WOOD_SPECIES = {
    'Pine':    {'color': (0.86, 0.72, 0.47), 'shininess': 0.10, 'texture': 'pine.png'},
    'Oak':     {'color': (0.65, 0.45, 0.28), 'shininess': 0.20, 'texture': 'oak.png'},
    'Larch':   {'color': (0.78, 0.52, 0.30), 'shininess': 0.15, 'texture': 'larch.png'},
    'Spruce':  {'color': (0.92, 0.84, 0.66), 'shininess': 0.08, 'texture': 'spruce.png'},
    'Cedar':   {'color': (0.72, 0.46, 0.33), 'shininess': 0.12, 'texture': 'cedar.png'},
}
```

## Implementation plan (concrete, in order)

**Step 1 — Data model & settings (no geometry yet)**
- Add `SidingSettings` fields to `TimberSettings` + `to_dict / from_dict`.
- Add `WOOD_SPECIES` constant in Core.
- Add `siding_outer` / `siding_inner` to `TimberMember.TYPES`.
- Add a "Siding" `QGroupBox` to the settings dialog with sensible defaults
  (disabled, so existing behaviour is unchanged).

**Step 2 — Geometry builder**
- `calculate_siding(wall_length, wall_height, top_profile, openings, settings)`
  returns a list of panel descriptors (same `TimberMember` shape but with
  `orientation='panel'`, carrying face=outer/inner).
- Extend `WallFrameCalculator.calculate_frame` to call it when siding is enabled.
- In the segment loop (`_convert_multi_segment_wall`) and `create_frame_group`,
  add a branch for `orientation == 'panel'`:
  - build the slab (flat or sloped-top via polygon extrude),
  - subtract opening boxes,
  - position at the right local Y based on `member.face`.

**Step 3 — Materials**
- Create (or find) one `App::MaterialObject` per species in use, named e.g.
  `TF_Mat_Pine`. Reuse across all siding parts in the document.
- Apply `ShapeAppearance` (colour + shininess) via the ViewObject so it
  renders distinctly from the structural timber.
- Tag the siding `Part::Feature` with `TimberSpecies` + `TimberBoardWidth`
  properties so cut-list / blueprint can pick them up later.

**Step 4 — Cut list integration**
- `get_cut_list` groups siding by species + profile + orientation, sums area
  (not length) so you can quote boards by m².

**Step 5 — (optional) Grooves**
- For the "boazeria" profiles with visible boards, we can either:
  - draw thin groove rectangles as separate micro-boxes (slower, prettier), or
  - fake it with a repeating texture (Phase 2 above).

**Step 6 — Blueprint integration**
- Siding is already a `Part::Feature`, so TechDraw views pick it up
  automatically. We'll just want a "hide siding" toggle in the blueprint
  command so the stud layout stays readable in elevation drawings.

## Risks / things to double-check before coding

- **Opening Z coordinates in the current data.** Siding needs the opening
  rectangle in local segment coords (x_pos, sill, width, height). We already
  compute those for the frame; confirm sill_height is relative to
  `wall_z_start`, not world Z, on every path (single-segment vs
  multi-segment). Add an assertion the first time we build a sample.
- **Sloped-top polygon winding.** The sloped-plate code works; reuse that
  polygon construction for sloped-wall siding so there's one function to
  maintain.
- **Corner meeting on the outer face.** At L corners, two siding slabs will
  meet at an outside corner. Options: (a) one slab owns the full corner
  thickness and the other butts (lower-index-wins rule — safe here because
  we're no longer adjusting the structural frame); (b) mitre the slabs 45°.
  Option (a) is good enough for a start; mitres are a nice-to-have later.
- **Materials across versions.** `App::MaterialObject` exists in all
  FreeCAD 1.x. Textures via `ShapeMaterial` are flakier — that's why
  textures stay in Phase 2.

## How we'd ship it

Each step is a small focused commit on `main`:

1. `siding: settings model + dialog (geometry disabled)`
2. `siding: outer panel geometry with opening cuts`
3. `siding: inner panel + sloped-top support`
4. `siding: materials via App::MaterialObject + ShapeAppearance`
5. `siding: cut-list area totals`
6. (optional) `siding: grooves / textures`

Default settings will have siding **disabled**, so nothing in existing files
changes until the user opts in.
