# Generic wall diagnostic. Edit WALL_LABEL for the wall you want to inspect.
# Run from the FreeCAD Python console:
#   exec(open(r"C:\Users\gomul\AppData\Roaming\FreeCAD\v1-1\Mod\TimberFrame\diagnose_wall.py").read())

WALL_LABEL = "Ext Walls"   # <-- change this to the wall label in your model

import FreeCAD, os, sys, importlib

mod_path = os.path.join(FreeCAD.getUserAppDataDir(), "v1-1", "Mod", "TimberFrame")
if mod_path not in sys.path:
    sys.path.insert(0, mod_path)
import TimberFrameCore as Core
importlib.reload(Core)

doc = FreeCAD.ActiveDocument
walls = doc.getObjectsByLabel(WALL_LABEL)
if not walls:
    print(f"No object labelled {WALL_LABEL!r}.")
else:
    wall = walls[0]
    print("=" * 70)
    print(f"Wall: {wall.Label}  (type {type(wall).__name__})")
    print(f"  Height = {float(wall.Height):.1f}, "
          f"Width = {float(wall.Width):.1f}, "
          f"Length = {float(getattr(wall, 'Length', 0)):.1f}")
    bb = wall.Shape.BoundBox
    print(f"  BBox X=[{bb.XMin:.1f}..{bb.XMax:.1f}] "
          f"Y=[{bb.YMin:.1f}..{bb.YMax:.1f}] "
          f"Z=[{bb.ZMin:.1f}..{bb.ZMax:.1f}]")
    print(f"  Placement = {wall.Placement}")

    # 1. Segments (if any)
    print("\n--- extract_wall_segments(wall) ---")
    segs = Core.extract_wall_segments(wall)
    if segs is None:
        print("  (returned None - single-segment path)")
    else:
        for s in segs:
            print(f"  idx={s['index']} length={s['length']:.1f} "
                  f"angle={s['angle']:.2f}")
            print(f"    start={s['start']}  end={s['end']}")
            print(f"    height={s['height']}  "
                  f"h_start={s.get('height_start')}  "
                  f"h_end={s.get('height_end')}")

    # 2. Single-segment path data
    print("\n--- extract_wall_data(wall) ---")
    wd = Core.extract_wall_data(wall)
    print(f"  length={wd['length']:.1f} height={wd['height']:.1f} "
          f"width={wd['width']:.1f}")
    tp = wd.get('top_profile')
    print(f"  top_profile ({len(tp) if tp else 0} points): {tp}")

    # 3. Unique Z values and all top-ish vertices
    print("\n--- Unique vertex Z values (rounded to 1 mm) ---")
    zs = sorted({round(v.Point.z, 2) for v in wall.Shape.Vertexes})
    print(f"  {zs}")

    print("\n--- Elevation (main) face OuterWire vertices sorted by X ---")
    try:
        max_a = 0
        main_face = None
        for face in wall.Shape.Faces:
            try:
                uv = face.Surface.parameter(face.CenterOfMass)
                n = face.normalAt(uv[0], uv[1])
                if abs(n.y) > 0.9 and face.Area > max_a:
                    max_a = face.Area; main_face = face
            except Exception:
                pass
        if main_face is None:
            print("  (no main elevation face)")
        else:
            print(f"  main face area = {main_face.Area:.0f}")
            pts = [(v.Point.x, v.Point.y, v.Point.z)
                   for v in main_face.OuterWire.Vertexes]
            for p in sorted(pts, key=lambda q: (q[0], q[2])):
                print(f"    X={p[0]:>9.2f}  Y={p[1]:>9.2f}  Z={p[2]:>9.2f}")
            inner_count = len(main_face.Wires) - 1
            print(f"  inner wires (openings) = {inner_count}")
    except Exception as e:
        print(f"  error: {e}")

    # 4. Height sampled from the resulting top profile
    if tp and len(tp) >= 2:
        print("\n--- _get_height_at_x sampled across wall length ---")
        L = wd['length']
        for i in range(0, 11):
            x = L * i / 10
            h = Core._get_height_at_x(tp, x, wd['height'])
            print(f"  x={x:7.1f}  wall_h={h:8.1f}  "
                  f"stud top (- 2*45) = {h - 2*45:.1f}")

    # 5. Which frame groups refer to this wall and how many of each type?
    print("\n--- Existing frame groups for this wall ---")
    for obj in doc.Objects:
        src = getattr(obj, 'SourceWall', None)
        if src is wall:
            kids = []
            stack = list(getattr(obj, 'Group', []))
            while stack:
                it = stack.pop()
                if hasattr(it, 'Group'):
                    stack.extend(it.Group)
                else:
                    kids.append(it)
            counts = {}
            for k in kids:
                t = getattr(k, 'TimberType', '?')
                counts[t] = counts.get(t, 0) + 1
            print(f"  {obj.Label}: {len(kids)} leaves, by type: {counts}")

    # 6. Subtractions / hosted objects
    print("\n--- Subtractions / hosts on this wall ---")
    if hasattr(wall, 'Subtractions'):
        for s in (wall.Subtractions or []):
            print(f"  Subtraction: {s.Label}  type={type(s).__name__}")
    for obj in doc.Objects:
        hosts = getattr(obj, 'Hosts', None)
        if hosts:
            host_list = hosts if isinstance(hosts, (list, tuple)) else [hosts]
            if wall in host_list:
                try:
                    obb = obj.Shape.BoundBox
                    print(f"  Hosted: {obj.Label} ({type(obj).__name__}) "
                          f"Z=[{obb.ZMin:.1f}..{obb.ZMax:.1f}] "
                          f"X=[{obb.XMin:.1f}..{obb.XMax:.1f}]")
                except Exception:
                    print(f"  Hosted: {obj.Label} ({type(obj).__name__})")
