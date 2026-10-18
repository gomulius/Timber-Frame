# Diagnose the Int Wall's top_profile and stud sizing.
# Run from the FreeCAD Python console with:
#   exec(open(r"C:\Users\gomul\AppData\Roaming\FreeCAD\v1-1\Mod\TimberFrame\diagnose_int_wall.py").read())
#
# Change WALL_LABEL below if the wall has a different name in your model.

WALL_LABEL = "Int Wall"

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
    print(f"Wall: {wall.Label}")
    print(f"  Height = {float(wall.Height):.1f}, Width = {float(wall.Width):.1f}")
    bb = wall.Shape.BoundBox
    print(f"  BBox Z = [{bb.ZMin:.1f} .. {bb.ZMax:.1f}]")
    print(f"  BBox X = [{bb.XMin:.1f} .. {bb.XMax:.1f}]")
    print(f"  BBox Y = [{bb.YMin:.1f} .. {bb.YMax:.1f}]")
    print(f"  Placement = {wall.Placement}")

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
                  f"height_start={s.get('height_start')}  "
                  f"height_end={s.get('height_end')}")

    print("\n--- extract_wall_data(wall) ---")
    wd = Core.extract_wall_data(wall)
    print(f"  length  = {wd['length']:.1f}")
    print(f"  height  = {wd['height']:.1f}")
    print(f"  width   = {wd['width']:.1f}")
    tp = wd.get('top_profile')
    print(f"  top_profile ({len(tp) if tp else 0} points): {tp}")

    print("\n--- Unique vertex Z values in wall shape ---")
    zs = sorted({round(v.Point.z, 2) for v in wall.Shape.Vertexes})
    print(f"  {zs}")

    print("\n--- Vertices near the top (Z within 1 mm of max Z) ---")
    pts = [(v.Point.x, v.Point.y, v.Point.z) for v in wall.Shape.Vertexes]
    top_z = max(p[2] for p in pts)
    print(f"  top_z candidate = {top_z:.1f}")
    near_top = sorted((p for p in pts if p[2] > top_z - 1.0), key=lambda p: p[0])
    print(f"  count = {len(near_top)}")
    for p in near_top:
        print(f"    X={p[0]:>9.2f}  Y={p[1]:>9.2f}  Z={p[2]:>9.2f}")

    if tp:
        print("\n--- _get_height_at_x sampled across wall length ---")
        L = wd['length']
        for i in range(0, 11):
            x = L * i / 10
            h = Core._get_height_at_x(tp, x, wd['height'])
            print(f"  x = {x:8.1f}  ->  wall_h = {h:8.1f}  "
                  f"stud top (- 2*45) = {h - 2*45:.1f}")

    print("\n--- Subtractions / hosts on this wall ---")
    if hasattr(wall, 'Subtractions'):
        for s in (wall.Subtractions or []):
            print(f"  Subtraction: {s.Label}  type={type(s).__name__}")
    for obj in doc.Objects:
        hosts = getattr(obj, 'Hosts', None)
        if hosts:
            host_list = hosts if isinstance(hosts, (list, tuple)) else [hosts]
            if wall in host_list:
                print(f"  Hosted: {obj.Label}  type={type(obj).__name__}  "
                      f"IfcType={getattr(obj, 'IfcType', '?')}")
                try:
                    obb = obj.Shape.BoundBox
                    print(f"    bbox Z=[{obb.ZMin:.1f}..{obb.ZMax:.1f}] "
                          f"X=[{obb.XMin:.1f}..{obb.XMax:.1f}]")
                except Exception as e:
                    print(f"    (no bbox: {e})")
