# TimberFrame Commands - FreeCAD GUI Commands

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui
import os

# Import core module
try:
    from . import TimberFrameCore as Core
except ImportError:
    import TimberFrameCore as Core


class _BaseSettingsDialog(QtGui.QDialog):
    """Common infrastructure for the dedicated wall / floor dialogs.

    Each subclass must implement:
      - build_content(layout)  : populate the scroll area body
      - load_settings()        : copy self.settings -> UI widgets
      - save_settings()        : copy UI widgets -> self.settings (returns settings)
    """

    WINDOW_TITLE = "Timber Frame Settings"

    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings or Core.TimberSettings()
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        self.setWindowTitle(self.WINDOW_TITLE)
        self.setMinimumWidth(440)
        self.resize(460, 640)

        outer = QtGui.QVBoxLayout(self)
        scroll = QtGui.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtGui.QFrame.NoFrame)
        outer.addWidget(scroll, 1)

        content = QtGui.QWidget()
        scroll.setWidget(content)
        self._content_layout = QtGui.QVBoxLayout(content)
        self.build_content(self._content_layout)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _create_length_spinbox(self, min_val, max_val, default):
        spin = QtGui.QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setSuffix(" mm")
        spin.setDecimals(1)
        return spin


class WallSettingsDialog(_BaseSettingsDialog):
    """Settings dialog shown when converting WALLS to timber frames.

    Only exposes wall-relevant controls. Floor-related fields on the
    TimberSettings object are left untouched.
    """

    WINDOW_TITLE = "Wall Framing Settings"

    def build_content(self, layout):
        g = QtGui.QGroupBox("Timber Dimensions")
        f = QtGui.QFormLayout(g)
        self.stud_width_spin = self._create_length_spinbox(20, 100, 45)
        f.addRow("Stud Width:", self.stud_width_spin)
        self.stud_depth_spin = self._create_length_spinbox(50, 300, 145)
        f.addRow("Stud Depth:", self.stud_depth_spin)
        layout.addWidget(g)

        g = QtGui.QGroupBox("Plates")
        f = QtGui.QFormLayout(g)
        self.bottom_plate_spin = QtGui.QSpinBox()
        self.bottom_plate_spin.setRange(1, 3)
        self.bottom_plate_spin.setValue(1)
        f.addRow("Bottom Plates:", self.bottom_plate_spin)
        self.top_plate_spin = QtGui.QSpinBox()
        self.top_plate_spin.setRange(1, 3)
        self.top_plate_spin.setValue(2)
        f.addRow("Top Plates:", self.top_plate_spin)
        layout.addWidget(g)

        g = QtGui.QGroupBox("Stud Spacing")
        f = QtGui.QFormLayout(g)
        self.stud_spacing_spin = self._create_length_spinbox(200, 800, 500)
        f.addRow("Stud Spacing (center-to-center):", self.stud_spacing_spin)
        layout.addWidget(g)

        g = QtGui.QGroupBox("Opening Framing")
        f = QtGui.QFormLayout(g)
        self.header_depth_spin = self._create_length_spinbox(100, 400, 200)
        f.addRow("Header Depth (height):", self.header_depth_spin)
        header_info = QtGui.QLabel(
            "Typical: 1m span -> 90mm, 1.5m -> 135mm, 2m -> 180mm"
        )
        header_info.setStyleSheet("color: gray; font-size: 10px;")
        f.addRow("", header_info)
        self.rough_gap_spin = self._create_length_spinbox(5, 50, 10)
        f.addRow("Rough Opening Gap:", self.rough_gap_spin)
        self.king_stud_check = QtGui.QCheckBox("King Studs")
        self.king_stud_check.setChecked(True)
        f.addRow("", self.king_stud_check)
        self.jack_stud_check = QtGui.QCheckBox("Jack Studs")
        self.jack_stud_check.setChecked(True)
        f.addRow("", self.jack_stud_check)
        self.cripple_check = QtGui.QCheckBox("Cripple Studs")
        self.cripple_check.setChecked(True)
        f.addRow("", self.cripple_check)
        layout.addWidget(g)

        g = QtGui.QGroupBox("Header Timber (Lintels)")
        f = QtGui.QFormLayout(g)
        self.header_same_check = QtGui.QCheckBox("Use same timber as studs")
        self.header_same_check.setChecked(True)
        self.header_same_check.stateChanged.connect(self._toggle_header_options)
        f.addRow("", self.header_same_check)
        self.header_width_spin = self._create_length_spinbox(20, 200, 45)
        self.header_width_spin.setEnabled(False)
        f.addRow("Header Width:", self.header_width_spin)
        self.header_timber_depth_spin = self._create_length_spinbox(50, 400, 145)
        self.header_timber_depth_spin.setEnabled(False)
        f.addRow("Header Depth (into wall):", self.header_timber_depth_spin)
        layout.addWidget(g)

    def _toggle_header_options(self, state):
        enabled = state != QtCore.Qt.Checked
        self.header_width_spin.setEnabled(enabled)
        self.header_timber_depth_spin.setEnabled(enabled)

    def load_settings(self):
        s = self.settings
        self.stud_width_spin.setValue(s.stud_width)
        self.stud_depth_spin.setValue(s.stud_depth)
        self.bottom_plate_spin.setValue(s.bottom_plate_count)
        self.top_plate_spin.setValue(s.top_plate_count)
        self.stud_spacing_spin.setValue(s.stud_spacing)
        self.header_depth_spin.setValue(s.header_depth)
        self.rough_gap_spin.setValue(s.rough_opening_gap)
        self.king_stud_check.setChecked(s.king_stud_enabled)
        self.jack_stud_check.setChecked(s.jack_stud_enabled)
        self.cripple_check.setChecked(s.cripple_stud_enabled)
        self.header_same_check.setChecked(s.header_use_same_timber)
        self.header_width_spin.setValue(s.header_width)
        self.header_timber_depth_spin.setValue(s.header_timber_depth)
        self._toggle_header_options(
            QtCore.Qt.Checked if s.header_use_same_timber else QtCore.Qt.Unchecked
        )

    def save_settings(self):
        s = self.settings
        s.stud_width = self.stud_width_spin.value()
        s.stud_depth = self.stud_depth_spin.value()
        s.bottom_plate_count = self.bottom_plate_spin.value()
        s.top_plate_count = self.top_plate_spin.value()
        s.stud_spacing = self.stud_spacing_spin.value()
        s.header_depth = self.header_depth_spin.value()
        s.rough_opening_gap = self.rough_gap_spin.value()
        s.king_stud_enabled = self.king_stud_check.isChecked()
        s.jack_stud_enabled = self.jack_stud_check.isChecked()
        s.cripple_stud_enabled = self.cripple_check.isChecked()
        s.header_use_same_timber = self.header_same_check.isChecked()
        s.header_width = self.header_width_spin.value()
        s.header_timber_depth = self.header_timber_depth_spin.value()
        return s


class FloorSettingsDialog(_BaseSettingsDialog):
    """Settings dialog shown when converting SLABS to floor platforms.

    Only exposes floor-relevant controls. Wall-related fields on the
    TimberSettings object are left untouched. The floor_enabled flag is
    forced ON on save - this dialog is only reached from the Convert Slab
    command, so running it is a positive consent.
    """

    WINDOW_TITLE = "Floor (Base) Framing Settings"

    def build_content(self, layout):
        info = QtGui.QLabel(
            "Floor platform under a BIM Slab. Joists span the slab's "
            "shorter dimension by default."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info)

        g = QtGui.QGroupBox("Joists")
        f = QtGui.QFormLayout(g)
        self.joist_width_spin = self._create_length_spinbox(20, 150, 45)
        f.addRow("Joist Width:", self.joist_width_spin)
        self.joist_depth_spin = self._create_length_spinbox(100, 400, 220)
        f.addRow("Joist Depth:", self.joist_depth_spin)
        self.joist_spacing_spin = self._create_length_spinbox(200, 800, 400)
        f.addRow("Joist Spacing:", self.joist_spacing_spin)
        self.floor_direction_combo = QtGui.QComboBox()
        self.floor_direction_combo.addItems(
            ["auto (short span)", "X", "Y"]
        )
        f.addRow("Joist Direction:", self.floor_direction_combo)
        layout.addWidget(g)

        g = QtGui.QGroupBox("Perimeter")
        f = QtGui.QFormLayout(g)
        self.floor_rim_check = QtGui.QCheckBox("Add perimeter rim joists")
        self.floor_rim_check.setChecked(True)
        f.addRow("", self.floor_rim_check)
        layout.addWidget(g)

        g = QtGui.QGroupBox("Deck / Blocking")
        f = QtGui.QFormLayout(g)
        self.floor_sheathing_spin = self._create_length_spinbox(0, 50, 22)
        self.floor_sheathing_spin.setSpecialValueText("off")
        f.addRow("Sheathing Thickness:", self.floor_sheathing_spin)
        self.floor_blocking_spin = self._create_length_spinbox(0, 3000, 0)
        self.floor_blocking_spin.setSpecialValueText("off")
        f.addRow("Blocking Every:", self.floor_blocking_spin)
        layout.addWidget(g)

    def load_settings(self):
        s = self.settings
        self.joist_width_spin.setValue(s.joist_width)
        self.joist_depth_spin.setValue(s.joist_depth)
        self.joist_spacing_spin.setValue(s.joist_spacing)
        dir_index = {'auto': 0, 'X': 1, 'Y': 2}.get(
            getattr(s, 'floor_deck_direction', 'auto'), 0
        )
        self.floor_direction_combo.setCurrentIndex(dir_index)
        self.floor_rim_check.setChecked(s.floor_rim_board)
        self.floor_sheathing_spin.setValue(s.floor_sheathing_thickness)
        self.floor_blocking_spin.setValue(s.floor_blocking_every)

    def save_settings(self):
        s = self.settings
        s.joist_width = self.joist_width_spin.value()
        s.joist_depth = self.joist_depth_spin.value()
        s.joist_spacing = self.joist_spacing_spin.value()
        s.floor_deck_direction = (
            ['auto', 'X', 'Y'][self.floor_direction_combo.currentIndex()]
        )
        s.floor_rim_board = self.floor_rim_check.isChecked()
        s.floor_sheathing_thickness = self.floor_sheathing_spin.value()
        s.floor_blocking_every = self.floor_blocking_spin.value()
        s.floor_enabled = True   # running this dialog is positive consent
        return s


# Backwards-compat alias: anything that still imports the old name gets the
# wall dialog, which is the pre-split behaviour for wall conversion.
TimberFrameSettingsDialog = WallSettingsDialog


def _icon_path(name):
    """Return the absolute path to an SVG icon, or '' if it doesn't exist.

    FreeCAD accepts an empty Pixmap and falls back to the default command
    icon; returning '' instead of a broken path avoids runtime warnings.
    """
    base = os.path.dirname(os.path.abspath(__file__))
    full = os.path.join(base, "Resources", "icons", name)
    return full if os.path.exists(full) else ""


def _tag_frame_group(group, wall, settings):
    """Attach SourceWall + settings metadata to a frame group so that the
    Regenerate command can later rebuild it from the (possibly modified)
    source wall. Safe to call multiple times."""
    import json
    try:
        if not hasattr(group, 'SourceWall'):
            group.addProperty(
                "App::PropertyLink", "SourceWall", "TimberFrame",
                "Source BIM wall this frame was generated from"
            )
        group.SourceWall = wall

        if not hasattr(group, 'TimberSettingsJSON'):
            group.addProperty(
                "App::PropertyString", "TimberSettingsJSON", "TimberFrame",
                "Settings used to generate this frame (JSON)"
            )
        group.TimberSettingsJSON = json.dumps(settings.to_dict())
    except Exception as e:
        FreeCAD.Console.PrintWarning(
            f"Could not tag frame group '{group.Label}': {e}\n"
        )


def _tag_floor_frame_group(group, slab, settings):
    """Attach SourceSlab + settings metadata so the floor frame can be
    regenerated the same way wall frames are."""
    import json
    try:
        if not hasattr(group, 'SourceSlab'):
            group.addProperty(
                "App::PropertyLink", "SourceSlab", "TimberFrame",
                "Source BIM slab this floor frame was generated from"
            )
        group.SourceSlab = slab

        if not hasattr(group, 'TimberSettingsJSON'):
            group.addProperty(
                "App::PropertyString", "TimberSettingsJSON", "TimberFrame",
                "Settings used to generate this frame (JSON)"
            )
        group.TimberSettingsJSON = json.dumps(settings.to_dict())
    except Exception as e:
        FreeCAD.Console.PrintWarning(
            f"Could not tag floor frame group '{group.Label}': {e}\n"
        )


def _frame_groups_with_source(doc):
    """Return every frame group that has a SourceWall OR SourceSlab link
    (i.e. that we know how to regenerate)."""
    out = []
    for obj in doc.Objects:
        if not obj.Label.startswith("Frame_"):
            continue
        if (hasattr(obj, 'SourceWall') and obj.SourceWall is not None):
            out.append(obj)
        elif (hasattr(obj, 'SourceSlab') and obj.SourceSlab is not None):
            out.append(obj)
    return out


def _delete_frame_group_recursive(doc, group):
    """Delete a frame group and all objects it (transitively) contains."""
    # Snapshot contents first - mutating the group as we iterate is unsafe.
    to_remove = []
    stack = list(getattr(group, 'Group', []))
    while stack:
        obj = stack.pop()
        if obj is None:
            continue
        # If it's a sub-group, descend into it before removing.
        if hasattr(obj, 'Group'):
            stack.extend(obj.Group)
        to_remove.append(obj)
    for obj in to_remove:
        try:
            doc.removeObject(obj.Name)
        except Exception:
            pass
    try:
        doc.removeObject(group.Name)
    except Exception:
        pass


class ConvertWallCommand:
    """Convert selected BIM wall(s) to a timber stud frame."""

    def GetResources(self):
        return {
            'MenuText': "Convert Wall to Frame",
            'ToolTip': "Convert selected BIM wall(s) to timber stud frame",
            'Pixmap': _icon_path('convert_wall.svg'),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        return len(FreeCADGui.Selection.getSelection()) > 0

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        selection = FreeCADGui.Selection.getSelection()

        if not selection:
            QtGui.QMessageBox.warning(
                None, "No Selection",
                "Please select one or more BIM walls to convert."
            )
            return

        walls = []
        for obj in selection:
            if Core.is_slab(obj):
                continue  # slabs go through Convert Slab to Frame
            if hasattr(obj, 'IfcType') and 'wall' in str(obj.IfcType).lower():
                walls.append(obj)
            elif hasattr(obj, 'Proxy') and hasattr(obj.Proxy, '__class__'):
                if 'Wall' in obj.Proxy.__class__.__name__:
                    walls.append(obj)
            elif 'Wall' in obj.TypeId or (
                hasattr(obj, 'Height')
                and hasattr(obj, 'Length')
                and hasattr(obj, 'Width')
            ):
                walls.append(obj)

        if not walls:
            QtGui.QMessageBox.warning(
                None, "No Walls",
                "No BIM wall was found in the selection.\n"
                "Use 'Convert Slab to Frame' for floor slabs."
            )
            return

        settings = Core.TimberSettings()
        dialog = WallSettingsDialog(settings)
        if dialog.exec_() != QtGui.QDialog.Accepted:
            return
        settings = dialog.save_settings()

        doc.openTransaction("Convert Walls to Timber Frame")
        try:
            for wall in walls:
                self._convert_wall(doc, wall, settings)
            doc.commitTransaction()
            doc.recompute()
            FreeCAD.Console.PrintMessage(
                f"Converted {len(walls)} wall(s) to timber frame.\n"
            )
        except Exception as e:
            doc.abortTransaction()
            import traceback
            FreeCAD.Console.PrintError(
                f"Error converting walls: {e}\n{traceback.format_exc()}"
            )
            QtGui.QMessageBox.critical(
                None, "Error", f"Failed to convert walls:\n{str(e)}"
            )

    def _convert_slab(self, doc, slab, settings):
        """Convert a BIM Slab to a timber floor frame (step 3: rims+joists)."""
        slab_data = Core.extract_slab_data(slab)
        FreeCAD.Console.PrintMessage(
            f"Converting slab '{slab.Label}': "
            f"{slab_data['length']:.0f} x {slab_data['width']:.0f} mm, "
            f"{len(slab_data['openings'])} opening(s)\n"
        )

        calc = Core.FloorFrameCalculator(
            slab_data['length'], slab_data['width'], settings
        )
        for op in slab_data['openings']:
            calc.add_opening(op)
        members = calc.calculate()
        FreeCAD.Console.PrintMessage(
            f"  Generated {len(members)} floor member(s)\n"
        )

        group = Core.create_floor_frame_group(
            doc, slab, members, slab_data, settings
        )
        _tag_floor_frame_group(group, slab, settings)

        try:
            if slab.ViewObject is not None:
                slab.ViewObject.Visibility = False
        except Exception:
            pass

        return group
    
    def _convert_wall(self, doc, wall, settings):
        """Convert a single wall to timber frame."""
        
        # Check for multi-segment wall
        segments = Core.extract_wall_segments(wall)
        
        if segments and len(segments) > 1:
            # Multi-segment wall - create frame for each segment
            FreeCAD.Console.PrintMessage(
                f"Converting multi-segment wall '{wall.Label}': {len(segments)} segments\n"
            )
            return self._convert_multi_segment_wall(doc, wall, segments, settings)
        
        # Single segment wall - standard processing
        wall_data = Core.extract_wall_data(wall)
        
        FreeCAD.Console.PrintMessage(
            f"Converting wall '{wall.Label}': {wall_data['length']:.0f} x {wall_data['height']:.0f} mm, "
            f"{len(wall_data['openings'])} opening(s)\n"
        )
        
        # Create frame calculator
        calc = Core.WallFrameCalculator(
            wall_data['length'],
            wall_data['height'],
            wall_data['width'],
            settings,
            top_profile=wall_data.get('top_profile')  # For sloped walls
        )
        
        # Add openings
        for opening in wall_data['openings']:
            calc.add_opening(opening)
            FreeCAD.Console.PrintMessage(f"  Opening: {opening}\n")
        
        # Calculate frame
        members = calc.calculate_frame()
        FreeCAD.Console.PrintMessage(f"  Generated {len(members)} timber members\n")
        
        # Create 3D geometry
        group = Core.create_frame_group(doc, wall, members, settings=settings)

        # Tag the frame group with its source wall and the settings used,
        # so Regenerate can re-run the conversion on the same inputs later.
        _tag_frame_group(group, wall, settings)

        # Create editable sketch for stud positions
        sketch = Core.create_frame_sketch(doc, wall, members, settings)

        # The frame REPLACES the wall. Hide the original BIM wall so the
        # frame alone represents the structure and the building's outer
        # dimensions are driven by the frame, not by the (now hidden) wall.
        try:
            if wall.ViewObject is not None:
                wall.ViewObject.Visibility = False
        except Exception:
            pass

        return group
    
    def _convert_multi_segment_wall(self, doc, wall, segments, settings):
        """Convert a multi-segment wall (L-shaped, etc.) to timber frames."""
        import Part
        import math
        from FreeCAD import Vector, Placement, Rotation
        
        # Create a parent group for all segments
        parent_group = doc.addObject("App::DocumentObjectGroup", f"Frame_{wall.Label}")
        # Tag it so Regenerate can find and rebuild it later.
        _tag_frame_group(parent_group, wall, settings)
        
        # Find all openings hosted by this wall
        all_openings = []
        for obj in doc.Objects:
            if hasattr(obj, 'Hosts'):
                hosts = obj.Hosts if isinstance(obj.Hosts, list) else [obj.Hosts]
                if wall in hosts:
                    all_openings.append(obj)
        
        # Segments use raw sketch endpoints (centerline). No in-plane
        # extension and no cross-axis offset: segment placement is identical
        # to the behaviour that was known good before the Align experiments.
        for seg in segments:
            seg['_x_shift'] = 0.0

            seg_name = f"{wall.Label}_Seg{seg['index']}"
            FreeCAD.Console.PrintMessage(
                f"  Segment {seg['index']}: length={seg['length']:.0f}mm, angle={seg['angle']:.1f}°\n"
            )
            
            # Find openings that belong to this segment
            seg_openings = []
            seg_start = seg['start']
            seg_end = seg['end']
            seg_angle_rad = seg['angle'] * math.pi / 180
            
            for opening_obj in all_openings:
                # Get opening bounding box
                open_bb = opening_obj.Shape.BoundBox
                open_center = Vector(
                    (open_bb.XMin + open_bb.XMax) / 2,
                    (open_bb.YMin + open_bb.YMax) / 2,
                    open_bb.ZMin
                )
                
                # Transform opening center to segment local coordinates
                dx = open_center.x - seg_start.x
                dy = open_center.y - seg_start.y
                
                # Project onto segment direction
                local_x = dx * math.cos(seg_angle_rad) + dy * math.sin(seg_angle_rad)
                local_y = -dx * math.sin(seg_angle_rad) + dy * math.cos(seg_angle_rad)
                
                # More generous tolerance for matching - wall width + 500mm
                tolerance = seg['width'] + 500
                
                # Check if within segment bounds
                in_segment = (0 - tolerance/2) <= local_x <= (seg['length'] + tolerance/2)
                near_wall = abs(local_y) < tolerance
                
                FreeCAD.Console.PrintMessage(f"    Checking {opening_obj.Label}: local_x={local_x:.0f}, local_y={local_y:.0f}, in_seg={in_segment}, near={near_wall}\n")
                
                if in_segment and near_wall:
                    # This opening belongs to this segment
                    open_width = open_bb.XMax - open_bb.XMin
                    open_height = open_bb.ZMax - open_bb.ZMin
                    
                    # For angled segments, recalculate width along segment
                    if abs(seg['angle']) > 1 and abs(seg['angle']) < 179:  # Not axis-aligned
                        open_width = max(open_bb.XMax - open_bb.XMin, open_bb.YMax - open_bb.YMin)
                    
                    # Determine type
                    open_type = "window"
                    if hasattr(opening_obj, 'IfcType') and 'door' in str(opening_obj.IfcType).lower():
                        open_type = "door"
                    
                    # Clamp local_x to be within segment
                    local_x = max(open_width/2, min(local_x, seg['length'] - open_width/2))
                    
                    # local_x was computed relative to the original
                    # (non-extended) segment start; add the shift so the
                    # opening keeps its real-world X.
                    seg_openings.append(Core.Opening(
                        x_position=local_x + seg.get('_x_shift', 0.0),
                        width=open_width,
                        height=open_height,
                        sill_height=max(0, open_bb.ZMin),
                        opening_type=open_type
                    ))
                    FreeCAD.Console.PrintMessage(f"    *** Found {open_type}: {opening_obj.Label} at local_x={local_x:.0f}\n")
            
            # Check if segment has sloped top
            height_start = seg.get('height_start', seg['height'])
            height_end = seg.get('height_end', seg['height'])
            
            is_sloped = abs(height_start - height_end) > 50  # More than 50mm difference
            
            if is_sloped:
                FreeCAD.Console.PrintMessage(f"    Sloped segment: height {height_start:.0f} -> {height_end:.0f}\n")
                # Create top profile for sloped segment
                top_profile = [
                    (0, height_start),
                    (seg['length'], height_end)
                ]
                use_height = max(height_start, height_end)
            else:
                FreeCAD.Console.PrintMessage(f"    Flat segment: height {height_start:.0f}\n")
                top_profile = None
                use_height = height_start  # Use actual height, not max wall height
            
            # Create frame calculator for this segment
            calc = Core.WallFrameCalculator(
                seg['length'],
                use_height,
                seg['width'],
                settings,
                top_profile=top_profile
            )
            
            # Add openings for this segment
            for opening in seg_openings:
                calc.add_opening(opening)
            
            # Calculate frame members (in local coordinates)
            members = calc.calculate_frame()
            
            # Create geometry for this segment
            seg_group = doc.addObject("App::DocumentObjectGroup", f"Frame_{seg_name}")
            
            # Calculate placement for this segment
            # Note: Z stays at 0 in placement - members have Z built into their shapes
            seg_placement = Placement(
                Vector(seg['start'].x, seg['start'].y, 0),  # Z=0, shapes have correct Z
                Rotation(Vector(0, 0, 1), seg['angle'])
            )
            
            # Create timber members with segment placement
            for member in members:
                if member.orientation == 'vertical':
                    box = Part.makeBox(
                        member.width, member.depth, member.length,
                        Vector(member.x, member.y, member.z)
                    )
                elif member.orientation == 'sloped':
                    # Sloped member (angled top plate) - tilted beam following roof.
                    # Build the tilted beam directly from a polygon face
                    # extruded along +Z by the plate thickness. This matches
                    # the technique used in TimberFrameCore.py and avoids
                    # relying on Shape.rotated()/translated(), which are not
                    # uniformly non-mutating across FreeCAD versions. The old
                    # code assigned the return value (None) back to `box`,
                    # which raised an exception and silently fell through to
                    # the flat-box fallback - the reason sloped beams showed
                    # up straight instead of tilted.
                    z_start = member.z
                    z_end = member.z_end if hasattr(member, 'z_end') else member.z

                    try:
                        dz = z_end - z_start
                        FreeCAD.Console.PrintMessage(
                            f"    Creating sloped plate: dz={dz:.0f}mm, "
                            f"length={member.length:.0f}mm, z_start={z_start:.0f}\n"
                        )

                        # Four corners of the plate's bottom face in LOCAL
                        # segment coordinates. The far end is lifted by dz so
                        # the plate tilts to follow the roof slope.
                        pts = [
                            Vector(member.x,                 member.y,                z_start),
                            Vector(member.x + member.length, member.y,                z_end),
                            Vector(member.x + member.length, member.y + member.width, z_end),
                            Vector(member.x,                 member.y + member.width, z_start),
                        ]
                        bottom_wire = Part.makePolygon(pts + [pts[0]])
                        bottom_face = Part.Face(bottom_wire)

                        # Extrude upward by the plate thickness to form the beam.
                        box = bottom_face.extrude(Vector(0, 0, member.depth))

                    except Exception as e:
                        import traceback
                        FreeCAD.Console.PrintError(f"Error creating sloped plate: {e}\n")
                        FreeCAD.Console.PrintError(traceback.format_exc())
                        # Fallback to flat box (keeps generation from aborting)
                        box = Part.makeBox(
                            member.length, member.width, member.depth,
                            Vector(member.x, member.y, z_start)
                        )
                else:
                    box = Part.makeBox(
                        member.length, member.width, member.depth,
                        Vector(member.x, member.y, member.z)
                    )
                
                part_obj = doc.addObject("Part::Feature", member.get_label())
                part_obj.Shape = box
                # Apply segment placement but preserve Z from the shape
                final_placement = Placement(seg_placement)
                # The shape already has correct Z, placement should only rotate around Z and offset XY
                part_obj.Placement = final_placement
                
                # Add properties
                part_obj.addProperty("App::PropertyString", "TimberType", "Timber", "Type of timber member")
                part_obj.TimberType = member.member_type
                part_obj.addProperty("App::PropertyFloat", "TimberLength", "Timber", "Length of timber piece")
                part_obj.TimberLength = member.length
                
                # Apply wood appearance
                if part_obj.ViewObject:
                    Core._apply_wood_appearance(part_obj.ViewObject, member.member_type)
                
                seg_group.addObject(part_obj)
            
            parent_group.addObject(seg_group)
            FreeCAD.Console.PrintMessage(f"    Generated {len(members)} members\n")

        # Hide the original BIM wall - the frame now represents it.
        try:
            if wall.ViewObject is not None:
                wall.ViewObject.Visibility = False
        except Exception:
            pass

        return parent_group


class ConvertSlabCommand:
    """Convert selected BIM slab(s) to a timber floor platform."""

    def GetResources(self):
        return {
            'MenuText': "Convert Slab to Frame",
            'ToolTip': (
                "Convert the selected BIM floor slab(s) to a timber "
                "floor platform (rim joists + joists)"
            ),
            'Pixmap': _icon_path('convert_slab.svg'),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        return len(FreeCADGui.Selection.getSelection()) > 0

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        selection = FreeCADGui.Selection.getSelection()
        slabs = [o for o in selection if Core.is_slab(o)]

        if not slabs:
            QtGui.QMessageBox.warning(
                None, "No Slabs",
                "No BIM slab (Arch Slab / Floor) was found in the "
                "selection.\nSelect one or more slabs and try again."
            )
            return

        settings = Core.TimberSettings()
        dialog = FloorSettingsDialog(settings)
        if dialog.exec_() != QtGui.QDialog.Accepted:
            return
        settings = dialog.save_settings()
        # FloorSettingsDialog already forces floor_enabled = True on save.

        doc.openTransaction("Convert Slabs to Timber Floor Frame")
        try:
            # Reuse the slab converter method that lives on ConvertWallCommand
            # (kept there to keep step-3's single-dispatch path symmetric).
            dispatcher = ConvertWallCommand()
            for slab in slabs:
                dispatcher._convert_slab(doc, slab, settings)
            doc.commitTransaction()
            doc.recompute()
            FreeCAD.Console.PrintMessage(
                f"Converted {len(slabs)} slab(s) to timber floor frame.\n"
            )
        except Exception as e:
            doc.abortTransaction()
            import traceback
            FreeCAD.Console.PrintError(
                f"Error converting slabs: {e}\n{traceback.format_exc()}"
            )
            QtGui.QMessageBox.critical(
                None, "Error", f"Failed to convert slabs:\n{str(e)}"
            )


class EditFrameCommand:
    """Command to edit a timber frame using sketcher."""
    
    def GetResources(self):
        return {
            'MenuText': "Edit Frame Layout",
            'ToolTip': "Edit timber frame stud positions using Sketcher",
            'Pixmap': _icon_path('edit_frame.svg'),
        }
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        # Check if a frame sketch exists
        for obj in FreeCAD.ActiveDocument.Objects:
            if obj.Label.startswith("FrameSketch_"):
                return True
        return False
    
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        
        # Find frame sketches
        sketches = [obj for obj in doc.Objects if obj.Label.startswith("FrameSketch_")]
        
        if not sketches:
            QtGui.QMessageBox.warning(None, "No Sketch", "No frame sketch found.\nConvert a wall first.")
            return
        
        # Select sketch to edit
        if len(sketches) > 1:
            items = [s.Label for s in sketches]
            item, ok = QtGui.QInputDialog.getItem(
                None, "Select Sketch", "Choose frame sketch to edit:", items, 0, False
            )
            if not ok:
                return
            sketch = next(s for s in sketches if s.Label == item)
        else:
            sketch = sketches[0]
        
        # Open sketch in sketcher workbench
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(sketch)
        FreeCADGui.runCommand('Sketcher_EditSketch', 0)
        
        QtGui.QMessageBox.information(
            None,
            "Edit Frame Layout",
            "The frame sketch is now open for editing.\n\n"
            "• Move stud lines to adjust positions\n"
            "• Delete lines to remove studs\n"
            "• Add new vertical lines to add studs\n\n"
            "When done, close the sketch and use\n"
            "'Rebuild Frame from Sketch' to update the 3D frame."
        )


class RebuildFrameCommand:
    """Command to rebuild 3D frame from edited sketch."""
    
    def GetResources(self):
        return {
            'MenuText': "Rebuild Frame from Sketch",
            'ToolTip': "Regenerate 3D frame from edited sketch",
            'Pixmap': _icon_path('rebuild_frame.svg'),
        }
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        for obj in FreeCAD.ActiveDocument.Objects:
            if obj.Label.startswith("FrameSketch_"):
                return True
        return False
    
    def Activated(self):
        doc = FreeCAD.ActiveDocument
        
        # Find frame sketches
        sketches = [obj for obj in doc.Objects if obj.Label.startswith("FrameSketch_")]
        
        if not sketches:
            QtGui.QMessageBox.warning(None, "No Sketch", "No frame sketch found.")
            return
        
        # Select sketch
        if len(sketches) > 1:
            items = [s.Label for s in sketches]
            item, ok = QtGui.QInputDialog.getItem(
                None, "Select Sketch", "Choose frame sketch to rebuild:", items, 0, False
            )
            if not ok:
                return
            sketch = next(s for s in sketches if s.Label == item)
        else:
            sketch = sketches[0]
        
        # Rebuild
        try:
            doc.openTransaction("Rebuild Timber Frame")
            Core.rebuild_frame_from_sketch(doc, sketch)
            doc.commitTransaction()
            doc.recompute()
            FreeCAD.Console.PrintMessage("Frame rebuilt from sketch.\n")
        except Exception as e:
            doc.abortTransaction()
            FreeCAD.Console.PrintError(f"Error rebuilding frame: {e}\n")
            QtGui.QMessageBox.critical(None, "Error", f"Failed to rebuild frame:\n{str(e)}")


class RegenerateFrameCommand:
    """Regenerate an existing timber frame from its source BIM wall.

    This re-runs the full conversion pipeline for the frame's SourceWall
    with the settings that were used when it was first generated. Use this
    after changing wall properties (Align, Height, openings, ...) so you
    don't have to delete the frame by hand and build a new one from scratch.
    """

    def GetResources(self):
        return {
            'MenuText': "Regenerate Frame",
            'ToolTip': (
                "Rebuild the selected timber frame from its source BIM "
                "wall or slab. Picks up changes to properties "
                "(Align / Height / openings for walls, Length / Width / "
                "openings for slabs)."
            ),
            'Pixmap': _icon_path('regenerate_frame.svg'),
        }

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        return bool(_frame_groups_with_source(FreeCAD.ActiveDocument))

    def Activated(self):
        doc = FreeCAD.ActiveDocument
        groups = _frame_groups_with_source(doc)
        if not groups:
            QtGui.QMessageBox.warning(
                None, "No Frame",
                "No regenerable timber frame found.\n"
                "Convert a wall first - frames created by this version are "
                "tagged with a SourceWall link that makes them regenerable."
            )
            return

        # Prefer whatever the user has selected in the tree.
        selected = FreeCADGui.Selection.getSelection() if FreeCADGui else []
        selected_groups = [g for g in groups if g in selected]
        if selected_groups:
            targets = selected_groups
        elif len(groups) == 1:
            targets = groups
        else:
            items = [g.Label for g in groups]
            item, ok = QtGui.QInputDialog.getItem(
                None, "Regenerate Frame",
                "Choose the frame to regenerate:", items, 0, False
            )
            if not ok:
                return
            targets = [next(g for g in groups if g.Label == item)]

        import json
        doc.openTransaction("Regenerate Timber Frame")
        try:
            for group in targets:
                wall = getattr(group, 'SourceWall', None)
                slab = getattr(group, 'SourceSlab', None)
                if wall is None and slab is None:
                    FreeCAD.Console.PrintWarning(
                        f"'{group.Label}' has no SourceWall/SourceSlab - "
                        "skipped.\n"
                    )
                    continue

                # Rehydrate the settings that were used originally so a
                # regenerate doesn't silently reset the user's choices.
                settings = Core.TimberSettings()
                raw = getattr(group, 'TimberSettingsJSON', '') or ''
                if raw:
                    try:
                        settings.from_dict(json.loads(raw))
                    except Exception as e:
                        FreeCAD.Console.PrintWarning(
                            f"Could not read saved settings for "
                            f"'{group.Label}' ({e}); using defaults.\n"
                        )

                if wall is not None:
                    # Clean up: delete this frame group and any FrameSketch
                    # that was created alongside it (single-segment path).
                    sketch_label = f"FrameSketch_{wall.Label}"
                    for obj in list(doc.Objects):
                        if obj.Label == sketch_label:
                            try:
                                doc.removeObject(obj.Name)
                            except Exception:
                                pass
                    _delete_frame_group_recursive(doc, group)
                    ConvertWallCommand()._convert_wall(doc, wall, settings)
                    FreeCAD.Console.PrintMessage(
                        f"Regenerated wall frame for '{wall.Label}' "
                        f"(Align={getattr(wall, 'Align', 'Left')}).\n"
                    )
                else:
                    # Slab-based floor frame.
                    _delete_frame_group_recursive(doc, group)
                    # Force floor framing on regenerate even if the user
                    # had it disabled when the dialog opened, since the
                    # existing frame proves it was requested at least once.
                    settings.floor_enabled = True
                    ConvertWallCommand()._convert_slab(doc, slab, settings)
                    FreeCAD.Console.PrintMessage(
                        f"Regenerated floor frame for '{slab.Label}'.\n"
                    )

            doc.commitTransaction()
            doc.recompute()
        except Exception as e:
            doc.abortTransaction()
            import traceback
            FreeCAD.Console.PrintError(
                f"Error regenerating frame: {e}\n{traceback.format_exc()}"
            )
            QtGui.QMessageBox.critical(
                None, "Error", f"Failed to regenerate frame:\n{e}"
            )


class GenerateBlueprintCommand:
    """Command to generate 2D blueprints of timber frames."""
    
    def GetResources(self):
        return {
            'MenuText': "Generate Blueprint",
            'ToolTip': "Generate 2D blueprint drawings with dimensions",
            'Pixmap': _icon_path('blueprint.svg'),
        }
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        # Check if there are any frame groups
        for obj in FreeCAD.ActiveDocument.Objects:
            if obj.Label.startswith("Frame_") or (
                hasattr(obj, 'TypeId') and 'Group' in obj.TypeId
            ):
                return True
        return False
    
    def Activated(self):
        """Generate TechDraw views of the frame."""
        doc = FreeCAD.ActiveDocument
        
        # Find frame groups
        frame_groups = []
        for obj in doc.Objects:
            if obj.Label.startswith("Frame_"):
                frame_groups.append(obj)
        
        if not frame_groups:
            QtGui.QMessageBox.warning(None, "No Frames", "No timber frame groups found.\nConvert walls first.")
            return
        
        # Select which frame to blueprint
        if len(frame_groups) > 1:
            items = [g.Label for g in frame_groups]
            item, ok = QtGui.QInputDialog.getItem(
                None, "Select Frame", "Choose frame for blueprint:", items, 0, False
            )
            if not ok:
                return
            frame_group = next(g for g in frame_groups if g.Label == item)
        else:
            frame_group = frame_groups[0]
        
        try:
            self._create_blueprint(doc, frame_group)
            doc.recompute()
            FreeCAD.Console.PrintMessage(f"Blueprint created for {frame_group.Label}\n")
        except Exception as e:
            FreeCAD.Console.PrintError(f"Error creating blueprint: {e}\n")
            QtGui.QMessageBox.critical(None, "Error", f"Failed to create blueprint:\n{str(e)}")
    
    def _create_blueprint(self, doc, frame_group):
        """Create TechDraw page with frame views."""
        import TechDraw
        
        # Create page
        page_name = f"Blueprint_{frame_group.Label}"
        page = doc.addObject("TechDraw::DrawPage", page_name)
        
        # Add template (A3 landscape ISO)
        template = doc.addObject("TechDraw::DrawSVGTemplate", f"Template_{frame_group.Label}")
        
        # Try to find a template file
        template_paths = [
            "C:/Program Files/FreeCAD 1.1/data/Mod/TechDraw/Templates/ISO/A3_Landscape_blank.svg",
            "C:/Program Files/FreeCAD 1.1/data/Mod/TechDraw/Templates/ISO/A3_Landscape_TD.svg",
            os.path.join(FreeCAD.getResourceDir(), "Mod", "TechDraw", "Templates", "ISO", "A3_Landscape_blank.svg"),
        ]
        
        template_found = False
        for tpath in template_paths:
            if os.path.exists(tpath):
                template.Template = tpath
                page.Template = template
                template_found = True
                break
        
        if not template_found:
            FreeCAD.Console.PrintWarning("Could not find TechDraw template, using page without template\n")
        
        # Get all timber objects in the group
        timber_objects = [obj for obj in frame_group.Group if hasattr(obj, 'Shape')]
        
        if not timber_objects:
            FreeCAD.Console.PrintWarning("No timber objects found in group\n")
            return
        
        # Pick the view direction so the wall is seen in elevation (its
        # longest horizontal dimension lies flat across the page).
        #
        # The previous version hard-coded Direction = (0, -1, 0), which is
        # correct only for walls running along X. A wall running along Y
        # then appeared edge-on (just the stud thickness visible). We now
        # look at the combined bounding box of the frame and choose:
        #   - longest horizontal dim along X  -> Direction = (0, -1, 0)
        #                                         XAxis     = (1, 0, 0)
        #   - longest horizontal dim along Y  -> Direction = (-1, 0, 0)
        #                                         XAxis     = (0, 1, 0)
        import Part
        try:
            combined = timber_objects[0].Shape
            for o in timber_objects[1:]:
                combined = combined.fuse(o.Shape)
            bb = combined.BoundBox
        except Exception:
            # Fuse can be slow / fragile on many parts; fall back to the
            # per-shape bbox union.
            bb = timber_objects[0].Shape.BoundBox.__class__()
            bb.setVoid()
            for o in timber_objects:
                bb.add(o.Shape.BoundBox)

        dx = bb.XMax - bb.XMin
        dy = bb.YMax - bb.YMin

        # TechDraw derives the view's paper-up axis as
        # paper_up = Direction x XDirection
        # so to keep world +Z pointing to the top of the page we need
        # Direction x XDirection = (0, 0, +1).
        #
        #   Wall along X:   Direction=(0,-1,0)  XDir=(1,0,0)  -> up=(0,0,1)  ✓
        #   Wall along Y:   Direction=(+1,0,0)  XDir=(0,1,0)  -> up=(0,0,1)  ✓
        #
        # The previous Y-aligned combination (-1,0,0) + (0,1,0) gave
        # up = (0,0,-1) -> blueprint was flipped vertically.
        if dy > dx:
            view_direction = FreeCAD.Vector(1, 0, 0)
            x_direction = FreeCAD.Vector(0, 1, 0)
        else:
            view_direction = FreeCAD.Vector(0, -1, 0)
            x_direction = FreeCAD.Vector(1, 0, 0)

        FreeCAD.Console.PrintMessage(
            f"Blueprint for {frame_group.Label}: "
            f"BBox dx={dx:.0f} dy={dy:.0f} -> "
            f"direction={tuple(view_direction)} x_axis={tuple(x_direction)}\n"
        )

        # Create front view (elevation)
        front_view = doc.addObject(
            "TechDraw::DrawViewPart", f"FrontView_{frame_group.Label}"
        )
        front_view.Source = timber_objects
        front_view.Direction = view_direction
        # XDirection controls which world axis maps to the page's +X. Some
        # FreeCAD builds expose this as 'XDirection' on DrawViewPart; guard
        # the assignment to stay compatible with older versions.
        try:
            front_view.XDirection = x_direction
        except Exception:
            try:
                front_view.setExpression('XDirection', None)
                front_view.XDirection = x_direction
            except Exception:
                pass
        front_view.Scale = 0.02  # 1:50 scale
        front_view.X = 150
        front_view.Y = 200
        page.addView(front_view)
        
        # Add title annotation
        title = doc.addObject("TechDraw::DrawViewAnnotation", f"Title_{frame_group.Label}")
        title.Text = [frame_group.Label.replace("Frame_", "Wall Frame: ")]
        title.X = 150
        title.Y = 280
        title.TextSize = 7
        page.addView(title)
        
        return page


class GenerateCutListCommand:
    """Command to generate a cut list / material summary."""
    
    def GetResources(self):
        return {
            'MenuText': "Generate Cut List",
            'ToolTip': "Generate material cut list with quantities",
            'Pixmap': _icon_path('cut_list.svg'),
        }
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        for obj in FreeCAD.ActiveDocument.Objects:
            if obj.Label.startswith("Frame_"):
                return True
        return False
    
    def Activated(self):
        """Generate cut list spreadsheet."""
        doc = FreeCAD.ActiveDocument
        
        # Collect all timber members from all frame groups
        all_members = []
        frame_count = 0
        
        for obj in doc.Objects:
            if obj.Label.startswith("Frame_"):
                frame_count += 1
                for timber in obj.Group:
                    if hasattr(timber, 'TimberType') and hasattr(timber, 'TimberLength'):
                        all_members.append({
                            'type': timber.TimberType,
                            'length': timber.TimberLength,
                            'label': timber.Label,
                            'frame': obj.Label,
                        })
        
        if not all_members:
            QtGui.QMessageBox.warning(None, "No Data", "No timber members found in frame groups.")
            return
        
        # Create or get spreadsheet
        sheet_name = "TimberCutList"
        if hasattr(doc, sheet_name):
            sheet = getattr(doc, sheet_name)
            # Clear existing content
            sheet.clear("A1:Z1000")
        else:
            sheet = doc.addObject("Spreadsheet::Sheet", sheet_name)
        
        # Aggregate by type and length
        cut_list = {}
        for m in all_members:
            key = (m['type'], round(m['length']))
            if key not in cut_list:
                cut_list[key] = {'count': 0, 'total': 0}
            cut_list[key]['count'] += 1
            cut_list[key]['total'] += m['length']
        
        # Write header
        sheet.set('A1', 'TIMBER CUT LIST')
        sheet.set('A2', f'Total Frames: {frame_count}')
        sheet.set('A3', f'Total Pieces: {len(all_members)}')
        
        sheet.set('A5', 'Type')
        sheet.set('B5', 'Length (mm)')
        sheet.set('C5', 'Quantity')
        sheet.set('D5', 'Total Length (mm)')
        sheet.set('E5', 'Total Length (m)')
        
        # Write data
        row = 6
        grand_total = 0
        
        for (timber_type, length), data in sorted(cut_list.items()):
            type_label = Core.TimberMember.TYPES.get(timber_type, timber_type)
            sheet.set(f'A{row}', type_label)
            sheet.set(f'B{row}', str(length))
            sheet.set(f'C{row}', str(data['count']))
            sheet.set(f'D{row}', str(round(data['total'])))
            sheet.set(f'E{row}', f"{data['total']/1000:.2f}")
            grand_total += data['total']
            row += 1
        
        # Write totals
        row += 1
        sheet.set(f'A{row}', 'GRAND TOTAL')
        sheet.set(f'D{row}', str(round(grand_total)))
        sheet.set(f'E{row}', f"{grand_total/1000:.2f}")
        
        doc.recompute()
        
        # Show message with summary
        QtGui.QMessageBox.information(
            None,
            "Cut List Generated",
            f"Cut list created in spreadsheet '{sheet_name}'.\n\n"
            f"Total pieces: {len(all_members)}\n"
            f"Total timber length: {grand_total/1000:.2f} m"
        )


class SettingsCommand:
    """Command to open settings dialog."""
    
    def GetResources(self):
        return {
            'MenuText': "Settings",
            'ToolTip': "Configure default timber frame settings",
            'Pixmap': _icon_path('settings.svg'),
        }
    
    def IsActive(self):
        return True
    
    def Activated(self):
        settings = Core.TimberSettings()

        # Simple two-choice launcher so Wall and Floor settings each live in
        # their own focused dialog instead of being mashed together.
        choice = QtGui.QInputDialog.getItem(
            None, "Timber Frame Settings",
            "Which defaults would you like to edit?",
            ["Wall framing", "Floor (Base) framing"],
            0, False,
        )
        if not choice[1]:
            return
        picked = choice[0]

        dialog_cls = WallSettingsDialog if picked == "Wall framing" else FloorSettingsDialog
        dialog = dialog_cls(settings)
        if dialog.exec_() == QtGui.QDialog.Accepted:
            dialog.save_settings()
            QtGui.QMessageBox.information(
                None, "Settings",
                "Settings will be used for the next conversion.\n\n"
                "Note: these defaults are not yet persisted between sessions."
            )


# Register commands
FreeCADGui.addCommand('TimberFrame_ConvertWall', ConvertWallCommand())
FreeCADGui.addCommand('TimberFrame_ConvertSlab', ConvertSlabCommand())
FreeCADGui.addCommand('TimberFrame_EditFrame', EditFrameCommand())
FreeCADGui.addCommand('TimberFrame_RebuildFrame', RebuildFrameCommand())
FreeCADGui.addCommand('TimberFrame_RegenerateFrame', RegenerateFrameCommand())
FreeCADGui.addCommand('TimberFrame_GenerateBlueprint', GenerateBlueprintCommand())
FreeCADGui.addCommand('TimberFrame_GenerateCutList', GenerateCutListCommand())
FreeCADGui.addCommand('TimberFrame_Settings', SettingsCommand())
