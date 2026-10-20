# Diagnose a BIM Slab object - what extract_slab_data() sees.
# Run from the FreeCAD Python console:
#   exec(open(r"C:\Users\gomul\AppData\Roaming\FreeCAD\v1-1\Mod\TimberFrame\diagnose_slab.py").read())
#
# Change SLAB_LABEL below if the slab in your model has a different label.

SLAB_LABEL = "Slab"

import FreeCAD, os, sys, importlib

mod_path = os.path.join(FreeCAD.getUserAppDataDir(), "v1-1", "Mod", "TimberFrame")
if mod_path not in sys.path:
    sys.path.insert(0, mod_path)
import TimberFrameCore as Core
importlib.reload(Core)

doc = FreeCAD.ActiveDocument

slabs = []
for obj in doc.Objects:
    if Core.is_slab(obj):
        slabs.append(obj)

print(f"Slabs in document: {[s.Label for s in slabs]}")

target = None
for s in slabs:
    if s.Label == SLAB_LABEL:
        target = s
        break
if target is None and slabs:
    target = slabs[0]
    print(f"(label {SLAB_LABEL!r} not found - using first slab {target.Label!r})")

if target is None:
    print("No slabs in document. Add an Arch Slab first.")
else:
    print("=" * 70)
    print(f"Slab: {target.Label}  (type {type(target).__name__})")
    bb = target.Shape.BoundBox
    print(f"  World BBox: X=[{bb.XMin:.1f}..{bb.XMax:.1f}] "
          f"Y=[{bb.YMin:.1f}..{bb.YMax:.1f}] "
          f"Z=[{bb.ZMin:.1f}..{bb.ZMax:.1f}]")
    print(f"  Placement: {target.Placement}")

    tf = Core._slab_top_face(target)
    if tf is None:
        print("  No horizontal top face!")
    else:
        print(f"  Top face area  = {tf.Area:.0f}  CoM.z = {tf.CenterOfMass.z:.1f}")

    try:
        data = Core.extract_slab_data(target)
    except Exception as e:
        print(f"  extract_slab_data FAILED: {e}")
        data = None

    if data is not None:
        print("\n--- extract_slab_data(slab) ---")
        print(f"  length    = {data['length']:.1f} mm  (along local X)")
        print(f"  width     = {data['width']:.1f} mm  (along local Y)")
        print(f"  thickness = {data['thickness']:.1f} mm")
        print(f"  top_z     = {data['top_z']:.1f}")
        print(f"  origin    = {tuple(round(c, 1) for c in data['origin'])}")
        print(f"  x_axis    = {tuple(round(c, 3) for c in data['x_axis'])}")
        print(f"  y_axis    = {tuple(round(c, 3) for c in data['y_axis'])}")

        print(f"\n  Openings ({len(data['openings'])}):")
        for op in data['openings']:
            print(f"    {op}")
