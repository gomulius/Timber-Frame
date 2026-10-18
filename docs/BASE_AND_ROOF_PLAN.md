# Base-to-frame and Roof-to-frame — plan

Two new "Convert X to Frame" features for the plugin:

1. **Base to Frame** — convert a BIM `Slab` (floor slab) into a timber floor
   platform (joists + rim boards + sheathing deck).
2. **Roof to Frame** — convert a single-slope BIM `Roof` into a timber rafter
   roof (rafters + ridge/wall plates + optional ties).

Base is architecturally simpler and is tackled first. Roof shares most of
the infrastructure but has to deal with the slope.

Everything here is additive. Default settings leave both features disabled
when converting a wall, so the existing wall-to-frame flow is untouched.

---

## Shared infrastructure (used by both)

- A new generic command dispatch in `ConvertWallCommand` →
  `ConvertSelectionCommand`. It inspects what the user selected (walls,
  slabs, roofs) and routes to the correct converter. Walls keep working
  exactly as today.
- A new menu entry **"Convert BIM Object to Frame"** that replaces the
  current wall-only menu entry. Internally there are still three
  converters: `convert_wall`, `convert_slab`, `convert_roof`.
- `TimberMember` grows a free-form `kind_group` (`'wall' | 'floor' | 'roof'`)
  so cut-list / blueprint / colour code can treat them separately.
- New colours in `_apply_wood_appearance` for the new member types.
- `TimberSettings` grows two new sub-settings blocks:

```
TimberSettings
├── (existing stud / plate / header settings)
├── Floor
│   ├── enabled: bool                  ─ allow Convert Slab to Frame
│   ├── joist_width: float (mm)        ─ e.g. 45
│   ├── joist_depth: float (mm)        ─ e.g. 220
│   ├── joist_spacing: float (mm)      ─ e.g. 400
│   ├── rim_board: bool                ─ perimeter joist
│   ├── sheathing_thickness: float (mm) or 0 ─ OSB/plywood deck, 0 = none
│   ├── deck_direction: {auto, X, Y}   ─ joist span direction (auto = short)
│   └── blocking_every: float (mm) or 0 ─ 0 = disabled
└── Roof
    ├── enabled: bool
    ├── rafter_width: float (mm)       ─ e.g. 45
    ├── rafter_depth: float (mm)       ─ e.g. 180
    ├── rafter_spacing: float (mm)     ─ e.g. 600
    ├── wall_plate: bool               ─ bottom plate along the eave
    ├── ridge_plate: bool              ─ top plate along the ridge
    ├── sheathing_thickness: float (mm) or 0
    ├── overhang_eave: float (mm)      ─ how far rafters extend past wall
    └── overhang_rake: float (mm)
```

- Settings dialog grows two new group boxes mirroring the structure above.
- Settings serialised into `TimberSettingsJSON` on the frame group, so the
  **Regenerate Frame** command picks up changes without extra work.

---

## 1. Base to Frame (BIM Slab → floor joist frame)

### What a BIM Slab is

An Arch/BIM `Slab` is a planar solid: a 2D profile extruded perpendicular
to its base plane, usually horizontal. It has:

- `Base` (sketch or face) — the outline, in slab-local coordinates,
- `Length`/`Width`/`Height` or `Thickness`,
- `Placement` — where the slab sits in the world,
- `Subtractions` — openings for stairs or chimneys.

We treat it as a 2D rectangle in XY (the slab's local base plane) with a
thickness in Z. For non-rectangular slabs (L-shaped, polygonal) we fall
back to the outer boundary wire of the top face.

### Mapping Slab → Floor frame

The timber platform under a slab is directly analogous to a stud wall
rotated 90° so that studs become joists:

| Stud wall                            | Floor platform                    |
|--------------------------------------|-----------------------------------|
| Studs (vertical)                     | Joists (horizontal)               |
| Bottom plate / top plate             | Rim boards (perimeter joists)     |
| Wall length                          | Joist span (short direction)      |
| Wall thickness                       | Joist depth (vertical thickness)  |
| Studs under header/opening (cripple) | Trimmer joists around openings    |
| Window / door openings               | Stair / chimney openings          |

So we re-use most of `WallFrameCalculator`:

1. Compute the slab's bounding rectangle (in slab-local coords).
2. Decide joist direction (`deck_direction = auto` → joists span the
   shorter dimension so the longest run is minimised).
3. Place:
   - **Rim boards** along the two edges perpendicular to the joists
     (same role as top/bottom plates).
   - **End joists** flush with the two edges parallel to the joists
     (same role as end studs).
   - **Joists** at `joist_spacing` centres between them (regular studs).
4. For each slab opening, call a floor version of `_add_opening_framing`
   that:
   - Places **trimmers** (doubled joists on each side of the opening) —
     the analogue of king studs.
   - Places **headers** at the two ends perpendicular to the joists —
     the analogue of header beams; sized by the opening span using the
     existing `_header_pieces_for_span` rule-of-thumb.
   - Places **tail joists** between the headers and the rims — the
     analogue of cripples.
5. Optionally add a **sheathing deck**: a single Part.Face on top of the
   joists cut by all openings. Thickness = `sheathing_thickness`.
6. Optionally add **blocking**: short pieces perpendicular to the joists
   every `blocking_every` mm, to stop joists twisting.

### Geometry construction

- Joists are the same shape as studs but rotated so the length is along
  the joist direction and the depth is Z. We can reuse the existing
  "horizontal" orientation in `create_timber_shapes` with slightly
  different member types.
- Positioning uses the slab's `Placement.Base` and the slab's local
  axes (same way the multi-segment wall code uses a `seg_placement`).
- Non-rectangular slabs: joists are clipped against the outer wire using
  `Part.Face.common(joist_shape)`.

### New types

```
TimberMember.TYPES += {
    'joist':              'Joist',
    'rim_board':          'Rim Board',
    'floor_trimmer':      'Trimmer Joist',
    'floor_header':       'Floor Header',
    'tail_joist':         'Tail Joist',
    'floor_blocking':     'Blocking',
    'floor_sheathing':    'Floor Sheathing',
}
```

### Commands

- `TimberFrame_ConvertSlab` — new command, selects slab(s) and runs the
  floor converter. Also hidden entry inside `TimberFrame_ConvertWall`'s
  dispatcher so selecting both walls and slabs works.
- `TimberFrame_RegenerateFrame` already works, since it just re-runs the
  stored converter via `SourceWall`-like link. We add a `SourceSlab` /
  `SourceRoof` property on the frame group so it knows what to rebuild.

### Edge cases

- **Non-axis-aligned slab**: we rotate the joists into the slab's local
  frame first (identical to wall segment placement).
- **Overlapping slabs (stacked floors)**: each slab generates its own
  frame group; `_apply_wood_appearance` colours them differently.
- **L-shaped slabs**: joists stay in one direction; the outer wire
  bounds them. We don't try to "optimally" split the direction.
- **Slab with no openings**: trivially just rims + joists + optional
  sheathing.

### Implementation steps (small, independent commits)

1. `floor: settings + dialog`
2. `floor: extract slab outline (rectangular case)`
3. `floor: generate rims + joists + end joists`
4. `floor: openings (trimmers + headers + tail joists)`
5. `floor: non-rectangular outline + clipping`
6. `floor: optional sheathing + blocking`
7. `floor: integrate with Regenerate + cut list`

---

## 2. Roof to Frame (single-slope BIM Roof → rafter frame)

Roofs are harder because:

- They sit at an angle, not horizontal.
- The eave and ridge lines are usually at **different heights**.
- The rafter depth is perpendicular to the slope, not vertical.

But if we **limit ourselves to a single-slope (mono-pitch / shed) roof**,
the problem becomes: tilt a floor platform. Everything else carries over.

### What a single-slope BIM Roof looks like

In FreeCAD Arch, a single-slope roof typically has:

- A base sketch outline (a quadrilateral in plan).
- One `Angle` list where every edge of the base shares the same slope
  value, with one eave at the low side and the ridge at the high side.
- A `Placement` to locate it in the world.
- An `Overhang` property.

We can get what we need by:

1. Reading the roof's top face via `roof.Shape.Faces` (the sloped
   outer face — identified by its normal having a Z component between
   0 and 1 exclusive, i.e. tilted but not horizontal).
2. Computing the slope plane from that face (normal + a point).
3. Taking the two long edges of the plan outline — the lower edge is
   the eave, the upper edge is the ridge.

### Mapping Roof → Rafter frame

| Floor platform          | Mono-pitch rafter roof                |
|-------------------------|---------------------------------------|
| Rim boards              | Wall plate (eave) + Ridge plate (apex)|
| Joists                  | Rafters                               |
| Joist direction         | Slope-up direction (eave → ridge)     |
| Sheathing deck          | Roof sheathing                        |
| Trimmers / headers      | Skylight / chimney framing            |

Then the geometry is:

1. **Wall plate** — box lying flat along the eave, length = eave edge.
2. **Ridge plate** — box lying flat along the ridge edge, at the high Z.
3. **Rafters** — one per `rafter_spacing` along the eave, each oriented
   along the slope direction, length = slope distance (hypotenuse),
   depth = `rafter_depth` perpendicular to the slope.
4. Optional **overhang** at eave and rake extends the rafter past the
   wall plate; rafter length grows accordingly.
5. Optional **sheathing** — same slope plane, extruded by the deck
   thickness in the slope-normal direction, clipped to the roof outline.

### Geometry construction — the one new primitive

The only genuinely new piece is **"box tilted along the slope"**. We've
already solved this once for the sloped head beam: build the four
corners of the rafter's bottom face in world coordinates, make a
polygon, and extrude by `rafter_depth` along the slope normal. That
same function works for ridge/wall plates (they're flat, so slope
normal = Z) and sheathing (one big tilted plate).

Pseudocode:

```python
def _make_tilted_box(p1, p2, width_vec, thickness, normal):
    """Build a solid between the two world points p1-p2 (the length of the
    beam), extend perpendicularly by width_vec, extrude by thickness along
    'normal'. Used for rafters, ridge/wall plates, and sheathing."""
    pts = [p1, p2, p2 + width_vec, p1 + width_vec]
    face = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return face.extrude(normal * thickness)
```

With that primitive, rafter placement is identical to joist placement
except each rafter's two endpoints live on the sloped eave and ridge
edges instead of two parallel horizontal edges.

### New types

```
TimberMember.TYPES += {
    'rafter':             'Rafter',
    'wall_plate_roof':    'Roof Wall Plate',
    'ridge_plate':        'Ridge Plate',
    'roof_trimmer':       'Roof Trimmer',
    'roof_header':        'Roof Header',
    'roof_sheathing':     'Roof Sheathing',
}
```

### Commands

- `TimberFrame_ConvertRoof` — new command for roof selection.
- Dispatcher in the unified "Convert BIM Object" entry.
- `SourceRoof` link on the frame group for Regenerate.

### Edge cases

- **Hosted objects (skylights / chimneys)**: treat like floor openings
  — trimmers + headers around the hole on the sloped plane.
- **Overhang vs wall plate position**: wall plate sits on the top of the
  wall below; the rafter's lower end extends past it by `overhang_eave`
  parallel to the slope. We can read the hosted wall if the user has
  linked them, otherwise just use the roof outline edge.
- **Rafter birdsmouth cut**: cosmetic. Deferred — initial version keeps
  rafters as plain tilted boxes resting on the wall plate.
- **Non-rectangular roof outline (trapezoid)**: fine, same clipping
  technique as the floor sheathing.
- **Pitched vs rotated-pitched roofs**: we support only single-slope.
  Anything with more than one slope face (gable, hip, dutch, mansard)
  surfaces a warning and refuses to convert.

### Implementation steps

1. `roof: settings + dialog + stub Convert command`
2. `roof: extract outline + eave/ridge edges + slope normal`
3. `roof: generate wall plate + ridge plate`
4. `roof: generate rafters`
5. `roof: eave / rake overhangs`
6. `roof: optional roof sheathing`
7. `roof: openings for skylights / chimneys`
8. `roof: integrate with Regenerate + cut list`

### What's deliberately out of scope (for now)

- Multi-slope roofs (gable / hip / mansard / dutch).
- Collar ties, rafter ties, purlins — mostly engineering decisions, not
  pure geometry.
- Fascia / soffit — these belong with the siding feature.
- Birdsmouth / plumb cut / tail cut. We can add them as a post-process
  that cuts each rafter with the wall plate's top plane and the eave's
  vertical plane, but that's cosmetic and should come after the basic
  flow works.

---

## Order of work

1. Finish the current list of real-world fixes (none outstanding).
2. **Base to Frame** — simplest, biggest win, gets infrastructure in place.
3. Decide if we want to pursue **Siding** before or after roofs — siding
   is "cosmetic" and runs on wall data we already have; roofs introduce
   a new input topology.
4. **Roof to Frame** — single-slope only.

Everything above is tracked here. We'll pick it up when the current
wall-fixes work stabilises.
