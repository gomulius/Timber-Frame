# Diagnose a BIM Roof object - everything the roof-to-frame converter
# will need before we write a line of geometry code.
#
# Run from the FreeCAD Python console:
#   exec(open(r"C:\Users\gomul\AppData\Roaming\FreeCAD\v1-1\Mod\TimberFrame\diagnose_roof.py").read())
#
# Change ROOF_LABEL below if your roof has a different label.

ROOF_LABEL = "Roof"  # or e.g. "Roof001"

import FreeCAD, os, sys, importlib, math

mod_path = os.path.join(FreeCAD.getUserAppDataDir(), "v1-1", "Mod", "TimberFrame")
if mod_path not in sys.path:
    sys.path.insert(0, mod_path)
import TimberFrameCore as Core
importlib.reload(Core)


def _looks_like_roof(obj):
    cls = type(obj).__name__
    if cls in ("Roof", "ArchRoof"):
        return True
    ifc = str(getattr(obj, "IfcType", "")).lower()
    return ifc in ("roof", "ifcroof")


doc = FreeCAD.ActiveDocument

roofs = [o for o in doc.Objects if _looks_like_roof(o)]
print(f"Roofs in document: {[r.Label for r in roofs]}")

target = None
for r in roofs:
    if r.Label == ROOF_LABEL:
        target = r
        break
if target is None and roofs:
    target = roofs[0]
    print(f"(label {ROOF_LABEL!r} not found - using first roof {target.Label!r})")

if target is None:
    print("No roof-like object. Add an Arch Roof first.")
else:
    print("=" * 70)
    print(f"Roof: {target.Label}  (class {type(target).__name__})")
    print(f"  Placement: {target.Placement}")

    bb = target.Shape.BoundBox
    print(f"  World BBox: X=[{bb.XMin:.1f}..{bb.XMax:.1f}] "
          f"Y=[{bb.YMin:.1f}..{bb.YMax:.1f}] "
          f"Z=[{bb.ZMin:.1f}..{bb.ZMax:.1f}]  "
          f"(dx={bb.XMax-bb.XMin:.0f} dy={bb.YMax-bb.YMin:.0f} dz={bb.ZMax-bb.ZMin:.0f})")

    # ---- All Arch-specific properties, printed verbatim ----
    print("\n--- Interesting properties ---")
    for prop in ("Angle", "Run", "Rise", "Thickness", "Overhang",
                 "RelativeAngles", "RelativeAnglesList",
                 "RelativeRuns", "RelativeRises",
                 "Angles", "Runs", "Rises", "IdRel", "EdgeId",
                 "RidgeLength", "Face", "Base",
                 "IfcType", "ObjectType", "Flip",
                 "Material", "SubVolume"):
        if hasattr(target, prop):
            try:
                val = getattr(target, prop)
                # Shorten huge collections for readability
                if isinstance(val, (list, tuple)) and len(val) > 12:
                    val = f"[{len(val)} values] {list(val)[:8]} ..."
                print(f"  {prop:20s} = {val}")
            except Exception as e:
                print(f"  {prop:20s} = <error: {e}>")

    base = getattr(target, "Base", None)
    if base is not None:
        print(f"\n--- Base object: {base.Label} ({type(base).__name__}) ---")
        if hasattr(base, "Shape") and base.Shape is not None:
            try:
                bbb = base.Shape.BoundBox
                print(f"  Base BBox: X=[{bbb.XMin:.1f}..{bbb.XMax:.1f}] "
                      f"Y=[{bbb.YMin:.1f}..{bbb.YMax:.1f}] "
                      f"Z=[{bbb.ZMin:.1f}..{bbb.ZMax:.1f}]")
                print(f"  Base faces: {len(base.Shape.Faces)}  "
                      f"edges: {len(base.Shape.Edges)}  "
                      f"wires: {len(base.Shape.Wires)}")
            except Exception as e:
                print(f"  (couldn't read base shape: {e})")

    # ---- Face analysis: which face is the sloped roof plane ----
    print("\n--- Faces of the roof solid ---")
    for i, face in enumerate(target.Shape.Faces):
        try:
            uv = face.Surface.parameter(face.CenterOfMass)
            n = face.normalAt(uv[0], uv[1])
            n = n.normalize()
            com = face.CenterOfMass
            # "Up-ish" face: nz > 0, "down-ish": nz < 0, side faces: |nz| ~ 0
            # Strict horizontal = exactly up/down with zero horizontal
            # component. Shed roofs with a shallow pitch (e.g. 2 deg) have
            # faces with |nz| ~ 0.999 so a looser "almost horizontal" tag
            # would misclassify them. We identify a slope face as any face
            # with |nz| > 0 AND some horizontal component.
            horiz = math.sqrt(n.x * n.x + n.y * n.y)
            if horiz < 1e-4:
                tag = "TOP" if n.z > 0 else "BOTTOM"
            elif abs(n.z) < 1e-4:
                tag = "SIDE"
            elif n.z > 0:
                tag = f"SLOPED-UP ({math.degrees(math.atan2(horiz, abs(n.z))):.1f} deg)"
            else:
                tag = f"SLOPED-DOWN ({math.degrees(math.atan2(horiz, abs(n.z))):.1f} deg)"
            print(f"  face[{i:2d}] A={face.Area:>12.0f}  "
                  f"n=({n.x:+.3f}, {n.y:+.3f}, {n.z:+.3f})  "
                  f"CoM.z={com.z:.1f}  -> {tag}")
        except Exception as e:
            print(f"  face[{i:2d}] <error: {e}>")

    # ---- Find the primary sloped face and derive slope info ----
    # A slope face is the LARGEST face that has some horizontal normal
    # component AND some positive +Z component. Shallow pitches (e.g. 2
    # deg) give nz very close to 1, so we must NOT reject on an upper
    # nz threshold.
    print("\n--- Picked slope face ---")
    best = None
    best_area = 0.0
    for face in target.Shape.Faces:
        try:
            uv = face.Surface.parameter(face.CenterOfMass)
            n = face.normalAt(uv[0], uv[1]).normalize()
            horiz = math.sqrt(n.x * n.x + n.y * n.y)
            if n.z > 0.01 and horiz > 1e-4 and face.Area > best_area:
                best = (face, n)
                best_area = face.Area
        except Exception:
            pass

    if best is None:
        print("  No sloped face found (nz > 0.01 and horizontal component > 0).")
    else:
        face, n = best
        slope_rad = math.atan2(math.sqrt(n.x * n.x + n.y * n.y), n.z)
        slope_deg = math.degrees(slope_rad)
        # Horizontal component of the up-slope direction = projection of
        # the face normal onto XY, pointing INTO the slope.
        up_slope = FreeCAD.Vector(-n.x, -n.y, 0)
        if up_slope.Length > 1e-6:
            up_slope.normalize()
        print(f"  area       = {face.Area:.0f}")
        print(f"  normal     = ({n.x:+.3f}, {n.y:+.3f}, {n.z:+.3f})")
        print(f"  slope      = {slope_deg:.2f} deg from horizontal")
        print(f"  up-slope   (horizontal unit vector going from eave to ridge)")
        print(f"             = ({up_slope.x:+.3f}, {up_slope.y:+.3f}, 0)")

        pts = [v.Point for v in face.OuterWire.Vertexes]
        zs = [p.z for p in pts]
        z_min, z_max = min(zs), max(zs)
        print(f"  face Z range: [{z_min:.1f} .. {z_max:.1f}]  "
              f"(eave to ridge rise = {z_max - z_min:.0f} mm)")
        print(f"  face has {len(pts)} outer-wire vertices")
        # Classify each vertex as eave-end or ridge-end so we can see what
        # the eave edge and ridge edge look like.
        eave_pts = [p for p in pts if p.z - z_min < (z_max - z_min) * 0.1]
        ridge_pts = [p for p in pts if z_max - p.z < (z_max - z_min) * 0.1]
        print(f"  eave vertices  ({len(eave_pts)}):")
        for p in eave_pts:
            print(f"    ({p.x:>9.1f}, {p.y:>9.1f}, {p.z:>7.1f})")
        print(f"  ridge vertices ({len(ridge_pts)}):")
        for p in ridge_pts:
            print(f"    ({p.x:>9.1f}, {p.y:>9.1f}, {p.z:>7.1f})")

    # ---- Hosted / subtracted objects (dormers, skylights, chimneys) ----
    print("\n--- Subtractions / hosts on this roof ---")
    if hasattr(target, "Subtractions"):
        for s in (target.Subtractions or []):
            print(f"  Subtraction: {s.Label}  ({type(s).__name__})")
    for obj in doc.Objects:
        hosts = getattr(obj, "Hosts", None)
        if hosts:
            host_list = hosts if isinstance(hosts, (list, tuple)) else [hosts]
            if target in host_list:
                print(f"  Hosted: {obj.Label}  ({type(obj).__name__})")

    # ---- extract_roof_data (R2 output) ----
    print("\n--- extract_roof_data(roof) ---")
    try:
        data = Core.extract_roof_data(target)
    except NotImplementedError as e:
        print(f"  NotImplementedError: {e}")
    except Exception as e:
        import traceback
        print(f"  FAILED: {e}")
        print(traceback.format_exc())
    else:
        for key in ("is_flat", "slope_angle_rad",
                    "eave_length", "rafter_length",
                    "eave_z", "ridge_z", "thickness",
                    "overhang_eave", "overhang_rake"):
            print(f"  {key:18s} = {data[key]}")
        print(f"  origin_eave      = ({data['origin_eave'].x:.1f}, "
              f"{data['origin_eave'].y:.1f}, {data['origin_eave'].z:.1f})")
        print(f"  eave_axis        = ({data['eave_axis'].x:+.3f}, "
              f"{data['eave_axis'].y:+.3f}, {data['eave_axis'].z:+.3f})")
        print(f"  up_slope_axis    = ({data['up_slope_axis'].x:+.3f}, "
              f"{data['up_slope_axis'].y:+.3f}, {data['up_slope_axis'].z:+.3f})")
        print(f"  face_normal      = ({data['face_normal'].x:+.3f}, "
              f"{data['face_normal'].y:+.3f}, {data['face_normal'].z:+.3f})")
        print(f"  slope_angle_deg  = {math.degrees(data['slope_angle_rad']):.3f}")
        print(f"  openings ({len(data['openings'])}):")
        for op in data['openings']:
            print(f"    {op}")
