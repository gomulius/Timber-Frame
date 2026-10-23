# TimberFrame Core - Framing calculation logic

import FreeCAD
from FreeCAD import Vector, Placement, Rotation
import Part
import math


class TimberSettings:
    """Settings for timber frame generation."""
    
    def __init__(self):
        # Get FreeCAD's unit system
        self.unit_schema = FreeCAD.Units.getSchema()
        
        # Default stud dimensions (width x depth in mm - internal units)
        self.stud_width = 45.0   # 45mm typical European timber
        self.stud_depth = 145.0  # 145mm for good insulation
        
        # Plate settings
        self.bottom_plate_count = 1  # Single bottom plate
        self.top_plate_count = 2     # Double top plate (default)
        
        # Spacing
        self.stud_spacing = 500.0    # 500mm center-to-center (insulation panels)
        
        # Opening framing
        self.header_depth = 200.0    # Header beam height/depth (vertical dimension)
        self.jack_stud_enabled = True
        self.king_stud_enabled = True
        self.cripple_stud_enabled = True
        
        # Header timber dimensions (can be different from studs)
        # Use same as studs by default, but can be set to larger timber
        self.header_use_same_timber = True  # If True, use stud dimensions
        self.header_width = 45.0     # Header width (if different from studs)
        self.header_timber_depth = 145.0  # Header depth into wall (if different)
        
        # Rough opening allowance (mm added to each side of window/door)
        self.rough_opening_gap = 10.0

        # -------- Floor (Base-to-Frame) settings --------
        # Convert a BIM Slab into a timber floor platform. Default disabled
        # so the existing wall-to-frame flow is untouched.
        self.floor_enabled = False
        self.joist_width = 45.0        # mm, narrow dimension (horizontal)
        self.joist_depth = 220.0       # mm, structural dimension (vertical)
        self.joist_spacing = 400.0     # mm, centre-to-centre
        self.floor_rim_board = True    # Perimeter rim joists on open ends
        self.floor_deck_direction = 'auto'  # 'auto' | 'X' | 'Y' (slab-local)
        self.floor_sheathing_thickness = 22.0  # mm, 0 = no deck
        self.floor_blocking_every = 0.0        # mm between rows, 0 = none

        # -------- Roof (Pitch-to-Frame) settings --------
        # Convert a BIM Roof into a timber rafter frame. Default disabled
        # so existing wall + floor conversions are unaffected.
        #
        # Phase 1 supports single-slope (shed) roofs. Flat roofs below
        # flat_roof_threshold_deg route through the floor frame builder
        # with these settings mapped onto floor settings (rafter -> joist,
        # wall_plate -> rim, ...).
        self.roof_enabled = False
        self.rafter_width = 45.0        # mm, narrow dimension (along eave)
        self.rafter_depth = 180.0       # mm, perpendicular to the slope
        self.rafter_spacing = 600.0     # mm, centre-to-centre along eave
        self.roof_wall_plate = True     # eave plate on top of outer walls
        self.roof_ridge_plate = True    # ridge plate at the high side
        self.roof_sheathing_thickness = 18.0   # mm, 0 = no deck
        self.roof_overhang_eave = 0.0   # mm, extends rafters past eave
        self.roof_overhang_rake = 0.0   # mm, extends plates past gables
        self.flat_roof_threshold_deg = 0.5  # Phase 2 trigger

    def to_dict(self):
        """Convert settings to dictionary for storage."""
        return {
            'stud_width': self.stud_width,
            'stud_depth': self.stud_depth,
            'bottom_plate_count': self.bottom_plate_count,
            'top_plate_count': self.top_plate_count,
            'stud_spacing': self.stud_spacing,
            'header_depth': self.header_depth,
            'jack_stud_enabled': self.jack_stud_enabled,
            'king_stud_enabled': self.king_stud_enabled,
            'cripple_stud_enabled': self.cripple_stud_enabled,
            'header_use_same_timber': self.header_use_same_timber,
            'header_width': self.header_width,
            'header_timber_depth': self.header_timber_depth,
            'rough_opening_gap': self.rough_opening_gap,

            # Floor
            'floor_enabled': self.floor_enabled,
            'joist_width': self.joist_width,
            'joist_depth': self.joist_depth,
            'joist_spacing': self.joist_spacing,
            'floor_rim_board': self.floor_rim_board,
            'floor_deck_direction': self.floor_deck_direction,
            'floor_sheathing_thickness': self.floor_sheathing_thickness,
            'floor_blocking_every': self.floor_blocking_every,

            # Roof
            'roof_enabled': self.roof_enabled,
            'rafter_width': self.rafter_width,
            'rafter_depth': self.rafter_depth,
            'rafter_spacing': self.rafter_spacing,
            'roof_wall_plate': self.roof_wall_plate,
            'roof_ridge_plate': self.roof_ridge_plate,
            'roof_sheathing_thickness': self.roof_sheathing_thickness,
            'roof_overhang_eave': self.roof_overhang_eave,
            'roof_overhang_rake': self.roof_overhang_rake,
            'flat_roof_threshold_deg': self.flat_roof_threshold_deg,
        }
    
    def from_dict(self, data):
        """Load settings from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


class Opening:
    """Represents a window or door opening in a wall."""
    
    def __init__(self, x_position, width, height, sill_height, opening_type="window"):
        self.x_position = x_position  # Distance from wall start to opening center
        self.width = width
        self.height = height
        self.sill_height = sill_height  # Height from floor to bottom of opening
        self.opening_type = opening_type  # "window" or "door"
    
    @property
    def left_edge(self):
        return self.x_position - self.width / 2
    
    @property
    def right_edge(self):
        return self.x_position + self.width / 2
    
    @property
    def top_edge(self):
        return self.sill_height + self.height
    
    def __repr__(self):
        return f"Opening({self.opening_type}, x={self.x_position:.0f}, w={self.width:.0f}, h={self.height:.0f}, sill={self.sill_height:.0f})"


class TimberMember:
    """Represents a single piece of timber in the frame."""
    
    TYPES = {
        # --- Wall members ---
        'bottom_plate': 'Bottom Plate',
        'top_plate': 'Top Plate',
        'top_plate_sloped': 'Top Plate (Sloped)',
        'stud': 'Stud',
        'king_stud': 'King Stud',
        'jack_stud': 'Jack Stud',
        'header': 'Header',
        'sill': 'Rough Sill',
        'cripple_top': 'Cripple (Top)',
        'cripple_bottom': 'Cripple (Bottom)',

        # --- Floor members (step 1: vocabulary only, no geometry yet) ---
        'joist': 'Joist',
        'rim_joist': 'Rim Joist',
        'floor_trimmer': 'Trimmer Joist',
        'floor_header': 'Floor Header',
        'tail_joist': 'Tail Joist',
        'floor_blocking': 'Blocking',
        'floor_sheathing': 'Floor Sheathing',

        # --- Roof members (R1: vocabulary only, no geometry yet) ---
        'rafter': 'Rafter',
        'wall_plate_roof': 'Roof Wall Plate',
        'ridge_plate': 'Ridge Plate',
        'roof_trimmer': 'Roof Trimmer',
        'roof_header': 'Roof Header',
        'roof_tail_rafter': 'Tail Rafter',
        'roof_sheathing': 'Roof Sheathing',
    }
    
    def __init__(self, member_type, x, y, z, length, width, depth, orientation='vertical'):
        self.member_type = member_type
        self.x = x  # Position along wall length
        self.y = y  # Position through wall thickness
        self.z = z  # Position in height
        self.length = length
        self.width = width
        self.depth = depth
        self.orientation = orientation  # 'vertical' or 'horizontal'
    
    def get_label(self):
        return self.TYPES.get(self.member_type, self.member_type)
    
    def __repr__(self):
        return f"TimberMember({self.member_type}, pos=({self.x:.0f},{self.y:.0f},{self.z:.0f}), L={self.length:.0f})"


class WallFrameCalculator:
    """Calculates timber frame layout for a wall."""
    
    def __init__(self, wall_length, wall_height, wall_thickness, settings=None, top_profile=None):
        self.wall_length = wall_length
        self.wall_height = wall_height
        self.wall_thickness = wall_thickness
        self.settings = settings or TimberSettings()
        self.openings = []
        self.members = []
        self.top_profile = top_profile  # For sloped walls: list of (x, z) points
    
    def add_opening(self, opening):
        """Add a window or door opening."""
        self.openings.append(opening)
    
    @staticmethod
    def _header_pieces_for_span(opening_span_mm):
        """Rule-of-thumb header sizing for light timber framing.

        Returns (num_pieces, warning_or_None).
            up to ~1.0 m span -> 2 pieces (2x stud, e.g. 90 mm)
            up to ~1.5 m span -> 3 pieces (3x stud, e.g. 135 mm)
            up to ~2.0 m span -> 4 pieces (4x stud, e.g. 180 mm)
            > 2.0 m           -> engineered lumber (LVL) or steel
        For spans > 2 m we still emit 4 pieces so the geometry is
        buildable, but surface a warning to the user.
        """
        # Thresholds in millimetres with a small tolerance so e.g. a nominal
        # 1000 mm opening still falls into the 2-piece bucket.
        if opening_span_mm <= 1050:
            return 2, None
        if opening_span_mm <= 1550:
            return 3, None
        if opening_span_mm <= 2050:
            return 4, None
        return 4, (
            f"Opening span {opening_span_mm:.0f} mm exceeds 2 m - "
            "stacked stud header is not sufficient, use engineered "
            "lumber (LVL) or steel."
        )

    def calculate_frame(self):
        """Generate all timber members for the frame."""
        self.members = []
        
        s = self.settings
        
        # Calculate plate heights
        plate_height = s.stud_width  # Plates are laid flat
        bottom_plates_height = s.bottom_plate_count * plate_height
        top_plates_height = s.top_plate_count * plate_height
        
        # Check if wall has sloped top
        is_sloped = self.top_profile is not None and len(self.top_profile) >= 2
        
        # Default stud height (for flat walls)
        default_stud_height = self.wall_height - bottom_plates_height - top_plates_height
        
        # 1. Bottom plate(s) - always flat
        for i in range(s.bottom_plate_count):
            self.members.append(TimberMember(
                'bottom_plate',
                x=0,
                y=0,
                z=i * plate_height,
                length=self.wall_length,
                width=s.stud_depth,
                depth=s.stud_width,
                orientation='horizontal'
            ))
        
        # 2. Top plate(s)
        if not is_sloped:
            for i in range(s.top_plate_count):
                self.members.append(TimberMember(
                    'top_plate',
                    x=0,
                    y=0,
                    z=self.wall_height - (s.top_plate_count - i) * plate_height,
                    length=self.wall_length,
                    width=s.stud_depth,
                    depth=s.stud_width,
                    orientation='horizontal'
                ))
        else:
            # For sloped walls, create angled top plate
            # Store slope info in a special member type
            FreeCAD.Console.PrintMessage("Sloped wall detected - creating angled top plate\n")
            
            # Height of the TOP face of the wall at the two ends. The plate
            # stack sits BELOW this: the bottom face of the lowest plate rests
            # on the stud tops, which end at (wall_top - top_plates_height).
            z_start = self.top_profile[0][1] - top_plates_height
            z_end = self.top_profile[-1][1] - top_plates_height

            # Stack plates upward: plate i's bottom face is i*plate_height
            # above z_start/z_end. For a double top plate this puts plate 0
            # directly on the studs and plate 1 on top of plate 0, matching
            # the flat-wall formula a few lines above (which grows with i).
            # The old formula grew with (count-1-i), which inverted the
            # stack and shifted the whole assembly down by one plate - so
            # the studs appeared to pass through the lowest sloped plate.
            for i in range(s.top_plate_count):
                self.members.append(TimberMember(
                    'top_plate_sloped',
                    x=0,
                    y=0,
                    z=z_start + i * plate_height,
                    length=self.wall_length,
                    width=s.stud_depth,
                    depth=s.stud_width,
                    orientation='sloped',
                ))
                # End-of-plate Z for the sloped-plate geometry builder.
                self.members[-1].z_end = z_end + i * plate_height
        
        # 3. Calculate stud positions
        stud_positions = self._calculate_stud_positions(default_stud_height, bottom_plates_height)
        
        # 4. Add studs (with variable height for sloped walls)
        for x_pos in stud_positions:
            if is_sloped:
                # Calculate height at this X position
                wall_height_at_x = _get_height_at_x(self.top_profile, x_pos, self.wall_height)
                stud_height_at_x = wall_height_at_x - bottom_plates_height - top_plates_height
                self._add_stud_or_framing(x_pos, stud_height_at_x, bottom_plates_height)
            else:
                self._add_stud_or_framing(x_pos, default_stud_height, bottom_plates_height)
        
        # 5. Add opening framing (headers, sills, jack studs, king studs).
        # On sloped walls we don't pass a single flat height: _add_opening_framing
        # queries the top profile per-stud so king studs stop under the sloped
        # top plate rather than poking through it.
        for opening in self.openings:
            self._add_opening_framing(opening, default_stud_height, bottom_plates_height)
        
        return self.members
    
    def _calculate_stud_positions(self, stud_height, bottom_z):
        """Calculate regular stud X positions along the wall."""
        s = self.settings
        positions = []
        
        # Always start with a stud at the beginning
        positions.append(s.stud_width / 2)
        
        # Regular studs at spacing intervals
        x = s.stud_spacing
        while x < self.wall_length - s.stud_width:
            positions.append(x)
            x += s.stud_spacing
        
        # Always end with a stud
        end_pos = self.wall_length - s.stud_width / 2
        if end_pos not in positions and end_pos > positions[-1] + s.stud_width:
            positions.append(end_pos)
        
        return positions
    
    def _stud_intersects_opening(self, stud_x, opening):
        """Check if a stud position intersects with an opening."""
        s = self.settings
        stud_left = stud_x - s.stud_width / 2
        stud_right = stud_x + s.stud_width / 2
        
        # Add rough opening gap
        opening_left = opening.left_edge - s.rough_opening_gap
        opening_right = opening.right_edge + s.rough_opening_gap
        
        return not (stud_right <= opening_left or stud_left >= opening_right)
    
    def _add_stud_or_framing(self, x_pos, full_stud_height, bottom_z):
        """Add a stud at x_pos, handling openings."""
        s = self.settings
        
        # Check if this position intersects any opening
        intersecting_opening = None
        for opening in self.openings:
            if self._stud_intersects_opening(x_pos, opening):
                intersecting_opening = opening
                break
        
        if intersecting_opening is None:
            # Full height stud
            self.members.append(TimberMember(
                'stud',
                x=x_pos - s.stud_width / 2,
                y=0,
                z=bottom_z,
                length=full_stud_height,
                width=s.stud_width,
                depth=s.stud_depth,
                orientation='vertical'
            ))
        else:
            # Stud is interrupted by opening - add cripples instead
            opening = intersecting_opening
            
            # Bottom cripple (for windows only)
            if opening.opening_type == "window" and s.cripple_stud_enabled:
                # Cripple stud stops at the bottom face of the rough sill
                # (which itself sits rough_opening_gap below the opening).
                sill_bottom = (
                    opening.sill_height - s.rough_opening_gap - s.stud_width
                )
                cripple_height = sill_bottom - bottom_z
                if cripple_height > s.stud_width:  # Only if there's room
                    self.members.append(TimberMember(
                        'cripple_bottom',
                        x=x_pos - s.stud_width / 2,
                        y=0,
                        z=bottom_z,
                        length=cripple_height,
                        width=s.stud_width,
                        depth=s.stud_depth,
                        orientation='vertical'
                    ))
            
            # Top cripple (above header)
            if s.cripple_stud_enabled:
                # Calculate actual header height based on opening span
                header_piece_thickness = s.stud_width if s.header_use_same_timber else s.header_width
                num_header_pieces, _warn = self._header_pieces_for_span(opening.width)
                actual_header_height = num_header_pieces * header_piece_thickness
                
                header_top = opening.top_edge + s.rough_opening_gap + actual_header_height
                cripple_top_height = (bottom_z + full_stud_height) - header_top
                if cripple_top_height > s.stud_width:  # Only if there's room
                    self.members.append(TimberMember(
                        'cripple_top',
                        x=x_pos - s.stud_width / 2,
                        y=0,
                        z=header_top,
                        length=cripple_top_height,
                        width=s.stud_width,
                        depth=s.stud_depth,
                        orientation='vertical'
                    ))
    
    def _add_opening_framing(self, opening, full_stud_height, bottom_z):
        """Add framing members around an opening (header, sill, king/jack studs)."""
        s = self.settings
        
        # Calculate positions
        rough_left = opening.left_edge - s.rough_opening_gap
        rough_right = opening.right_edge + s.rough_opening_gap
        rough_width = rough_right - rough_left
        
        # King studs (full height, on outside of opening). On sloped walls
        # each king stud's height follows the roof profile at that X so it
        # terminates just under the sloped top plate.
        is_sloped = self.top_profile is not None and len(self.top_profile) >= 2
        top_plates_height = s.top_plate_count * s.stud_width  # plates laid flat

        def _king_stud_height(x_center):
            if not is_sloped:
                return full_stud_height
            wall_h = _get_height_at_x(self.top_profile, x_center, self.wall_height)
            return wall_h - bottom_z - top_plates_height

        if s.king_stud_enabled:
            left_ks_x = rough_left - s.stud_width
            right_ks_x = rough_right
            # Left king stud
            self.members.append(TimberMember(
                'king_stud',
                x=left_ks_x,
                y=0,
                z=bottom_z,
                length=_king_stud_height(left_ks_x + s.stud_width / 2),
                width=s.stud_width,
                depth=s.stud_depth,
                orientation='vertical'
            ))
            # Right king stud
            self.members.append(TimberMember(
                'king_stud',
                x=right_ks_x,
                y=0,
                z=bottom_z,
                length=_king_stud_height(right_ks_x + s.stud_width / 2),
                width=s.stud_width,
                depth=s.stud_depth,
                orientation='vertical'
            ))
        
        # Jack studs (support header, inside king studs)
        if s.jack_stud_enabled:
            jack_height = opening.top_edge + s.rough_opening_gap - bottom_z
            
            # For doors, jack studs go to floor
            if opening.opening_type == "door":
                jack_z = bottom_z
            else:
                # For windows, jack studs sit on sill
                jack_z = bottom_z
            
            # Left jack stud
            self.members.append(TimberMember(
                'jack_stud',
                x=rough_left,
                y=0,
                z=jack_z,
                length=jack_height,
                width=s.stud_width,
                depth=s.stud_depth,
                orientation='vertical'
            ))
            # Right jack stud
            self.members.append(TimberMember(
                'jack_stud',
                x=rough_right - s.stud_width,
                y=0,
                z=jack_z,
                length=jack_height,
                width=s.stud_width,
                depth=s.stud_depth,
                orientation='vertical'
            ))
        
        # Header (spans opening, sits on jack studs)
        # Headers are built by stacking multiple pieces of timber
        # Number of pieces depends on SPAN (opening width), not a fixed setting
        if s.header_use_same_timber:
            header_piece_thickness = s.stud_width  # Each piece is stud_width thick
            header_timber_depth = s.stud_depth     # Depth into wall
        else:
            header_piece_thickness = s.header_width
            header_timber_depth = s.header_timber_depth
        
        header_z = opening.top_edge + s.rough_opening_gap
        # Header spans only the rough opening and sits ON TOP of the jack
        # studs (or, if jack studs are disabled, directly between the king
        # studs). It must NOT extend into the king studs - the king studs
        # are full-height and would otherwise visibly pass through the
        # header beam. Verticals support horizontals from below only.
        header_span = rough_width
        header_x = rough_left
        
        # Header pieces follow the rule of thumb for light timber framing.
        # See WallFrameCalculator._header_pieces_for_span for the sizing table.
        num_header_pieces, _header_warning = self._header_pieces_for_span(opening.width)
        if _header_warning:
            FreeCAD.Console.PrintWarning(_header_warning + "\n")
        
        # Actual header total height
        actual_header_height = num_header_pieces * header_piece_thickness
        
        # Create stacked header pieces
        for i in range(num_header_pieces):
            self.members.append(TimberMember(
                'header',
                x=header_x,
                y=0,
                z=header_z + (i * header_piece_thickness),
                length=header_span,
                width=header_timber_depth,      # Depth into wall
                depth=header_piece_thickness,   # Thickness of each piece
                orientation='horizontal'
            ))
        
        # Store actual header top for cripple calculations
        header_top_z = header_z + actual_header_height
        
        # Rough sill (for windows only)
        if opening.opening_type == "window":
            sill_z = opening.sill_height - s.rough_opening_gap - s.stud_width
            # Rough sill spans only the rough opening (between the jack
            # studs); it must not extend into the king studs.
            sill_width = rough_width
            sill_x = rough_left
            
            self.members.append(TimberMember(
                'sill',
                x=sill_x,
                y=0,
                z=sill_z,
                length=sill_width,
                width=s.stud_depth,
                depth=s.stud_width,
                orientation='horizontal'
            ))
    
    def calculate_frame_with_custom_studs(self):
        """Generate frame using custom stud positions from sketch."""
        self.members = []
        s = self.settings
        
        # Calculate plate heights
        plate_height = s.stud_width
        bottom_plates_height = s.bottom_plate_count * plate_height
        top_plates_height = s.top_plate_count * plate_height
        stud_height = self.wall_height - bottom_plates_height - top_plates_height
        
        # Add plates (same as normal)
        for i in range(s.bottom_plate_count):
            self.members.append(TimberMember(
                'bottom_plate', x=0, y=0, z=i * plate_height,
                length=self.wall_length, width=s.stud_depth, depth=s.stud_width,
                orientation='horizontal'
            ))
        
        for i in range(s.top_plate_count):
            self.members.append(TimberMember(
                'top_plate', x=0, y=0,
                z=self.wall_height - (s.top_plate_count - i) * plate_height,
                length=self.wall_length, width=s.stud_depth, depth=s.stud_width,
                orientation='horizontal'
            ))
        
        # Add studs at custom positions (from sketch)
        for stud_x in self.custom_stud_positions:
            self._add_stud_or_framing(stud_x, stud_height, bottom_plates_height)
        
        # Add opening framing
        for opening in self.openings:
            self._add_opening_framing(opening, stud_height, bottom_plates_height)
        
        return self.members

    def get_cut_list(self):
        """Generate a summary of all timber pieces grouped by type and length."""
        cut_list = {}
        
        for member in self.members:
            # Round length to nearest mm for grouping
            length = round(member.length)
            key = (member.member_type, member.width, member.depth, length)
            
            if key not in cut_list:
                cut_list[key] = {
                    'type': member.get_label(),
                    'width': member.width,
                    'depth': member.depth,
                    'length': length,
                    'count': 0,
                    'total_length': 0,
                }
            
            cut_list[key]['count'] += 1
            cut_list[key]['total_length'] += length
        
        return list(cut_list.values())
    
    def get_total_timber_length(self):
        """Get total length of all timber members."""
        return sum(m.length for m in self.members)


def _get_wall_top_profile(wall_obj):
    """Extract the top edge profile of a wall to handle sloped tops.
    
    Returns a list of (x, z) points defining the top edge, relative to wall start.
    Returns None if wall has a simple flat top.
    """
    try:
        wall_bb = wall_obj.Shape.BoundBox
        wall_x_min = wall_bb.XMin
        wall_length = wall_bb.XMax - wall_bb.XMin
        
        # Find the main elevation face (largest face with Y-normal)
        main_face = None
        max_area = 0
        for face in wall_obj.Shape.Faces:
            try:
                uv = face.Surface.parameter(face.CenterOfMass)
                normal = face.normalAt(uv[0], uv[1])
                if abs(normal.y) > 0.9 and face.Area > max_area:
                    max_area = face.Area
                    main_face = face
            except:
                continue
        
        if main_face is None:
            return None

        # Only consider the OUTER boundary of the elevation face. If we used
        # face.Vertexes we would also pick up vertices from inner wires
        # (window / door cutouts), and their top corners would be treated as
        # part of the roof profile - producing a bogus V-shaped top that
        # dipped down into every opening (and gave studs a "floating" look).
        outer_wire = main_face.OuterWire
        verts = [v.Point for v in outer_wire.Vertexes]

        # Classify each outer-wire vertex. For each X, keep the maximum Z;
        # for identifying the real top edge we additionally require that
        # the vertex be within a small tolerance of the overall max Z of
        # the outer wire. Anything below that is a bottom/side vertex and
        # must not be inserted as a top-profile point - otherwise walls
        # with non-rectangular bottoms would also feed garbage into the
        # profile.
        if not verts:
            return None
        wire_z_max = max(v.z for v in verts)
        wire_z_min = min(v.z for v in verts)

        # Fold near-equal X together (BIM walls commonly have duplicates
        # within sub-millimetre of each other after boolean ops).
        TOL_X = 0.5  # mm
        TOL_Z_FROM_TOP = 1.0  # mm - "on the top edge"

        candidates = []
        for v in verts:
            if (wire_z_max - v.z) <= TOL_Z_FROM_TOP or (
                v.z > (wire_z_min + wire_z_max) / 2.0
            ):
                # Keep vertices that are either on the top edge or in the
                # upper half of the wire (so a gable's apex still qualifies
                # even if we're a few millimetres off the exact maximum).
                candidates.append((v.x - wall_x_min, v.z))
        if not candidates:
            return None

        candidates.sort(key=lambda p: p[0])
        top_points = []
        for x_rel, z in candidates:
            if top_points and abs(x_rel - top_points[-1][0]) <= TOL_X:
                # Merge near-duplicate X: keep the higher Z.
                if z > top_points[-1][1]:
                    top_points[-1] = (x_rel, z)
            else:
                top_points.append((x_rel, z))

        if len(top_points) < 2:
            return None

        # Only treat as sloped if the top edge actually varies.
        z_variation = max(p[1] for p in top_points) - min(
            p[1] for p in top_points
        )
        if z_variation < 50:
            return None  # Flat top, no special handling needed

        return top_points
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Could not analyze wall top profile: {e}\n")
        return None


def _get_height_at_x(top_profile, x_pos, default_height):
    """Get the wall height at a given X position using linear interpolation."""
    if top_profile is None or len(top_profile) < 2:
        return default_height
    
    # Find the two points that bracket this X position
    for i in range(len(top_profile) - 1):
        x1, z1 = top_profile[i]
        x2, z2 = top_profile[i + 1]
        
        if x1 <= x_pos <= x2:
            # Linear interpolation
            if x2 - x1 < 0.1:  # Avoid division by zero
                return z1
            t = (x_pos - x1) / (x2 - x1)
            return z1 + t * (z2 - z1)
    
    # X is outside the profile, use nearest endpoint
    if x_pos < top_profile[0][0]:
        return top_profile[0][1]
    else:
        return top_profile[-1][1]


def _get_segment_heights(wall_obj, seg_start, seg_end, default_height):
    """Get the wall height at the start and end of a segment.

    For walls shortened against a sloped roof the height varies along the
    segment. The reliable way to find the wall's top at a given XY is to
    probe the solid itself (not its vertex list): at an inside corner
    between two sketch segments there is NO vertex of the wall shape at
    that XY, so a vertex-proximity search silently falls back to the
    default wall height and the top plate spikes up at every corner.

    Strategy:
      1. For each endpoint, build a vertical line from z=0 to a value far
         above the wall and intersect it with the wall shape.
      2. Take the highest Z of the resulting points. That's the top surface
         height exactly at that XY.
      3. If the intersection fails (e.g. the probe is right on the wall's
         outer edge and misses the solid due to numeric roundoff), fall
         back to a tiny inward step along the segment axis.
      4. Only as a last resort, keep the previous vertex-scan behaviour so
         we never regress on walls without a sloped top.
    """
    wall_shape = wall_obj.Shape
    bb = wall_shape.BoundBox
    probe_top_z = bb.ZMax + 10.0 if bb.ZMax > 0 else 20000.0

    def _probe_z(x, y):
        """Return top-of-solid Z at XY, or None if no hit."""
        import Part
        try:
            line = Part.makeLine(
                FreeCAD.Vector(x, y, bb.ZMin - 1.0),
                FreeCAD.Vector(x, y, probe_top_z),
            )
            common = wall_shape.common(line)
            zs = [v.Point.z for v in common.Vertexes]
            if zs:
                return max(zs)
        except Exception:
            pass
        return None

    def _height_at(point, direction_sign, other_point):
        # Try the exact endpoint first.
        z = _probe_z(point.x, point.y)
        if z is not None:
            return z
        # Nudge a few millimetres inward along the segment to escape the
        # outer edge; try progressively larger offsets.
        seg_dx = other_point.x - point.x
        seg_dy = other_point.y - point.y
        seg_len = math.sqrt(seg_dx * seg_dx + seg_dy * seg_dy) or 1.0
        ux = seg_dx / seg_len
        uy = seg_dy / seg_len
        for step in (1.0, 5.0, 25.0, 100.0):
            z = _probe_z(point.x + ux * step, point.y + uy * step)
            if z is not None:
                return z
        return None

    height_start = _height_at(seg_start, +1, seg_end)
    height_end = _height_at(seg_end, -1, seg_start)

    if height_start is not None and height_end is not None:
        return height_start, height_end

    # Fallback: original vertex-scan behaviour, used only when the solid
    # probe failed on both ends (should be extremely rare).
    tolerance = 50
    hs = default_height if height_start is None else height_start
    he = default_height if height_end is None else height_end
    for vertex in wall_shape.Vertexes:
        v = vertex.Point
        if math.hypot(v.x - seg_start.x, v.y - seg_start.y) < tolerance and v.z > 100:
            hs = max(hs, v.z)
        if math.hypot(v.x - seg_end.x, v.y - seg_end.y) < tolerance and v.z > 100:
            he = max(he, v.z)
    height_start = hs
    height_end = he
    
    return height_start, height_end


def extract_wall_segments(wall_obj):
    """Extract individual wall segments from a multi-segment wall.
    
    Returns a list of segment data, each with its own length, direction, and position.
    For single-segment walls, returns a list with one item.
    """
    segments = []
    
    # Check if wall has a base sketch with multiple lines
    if hasattr(wall_obj, 'Base') and wall_obj.Base:
        sketch = wall_obj.Base
        
        lines = []
        for i in range(sketch.GeometryCount):
            # Skip construction geometry
            try:
                if sketch.getConstruction(i):
                    continue
            except:
                pass
            
            geom = sketch.Geometry[i]
            
            # Only process LineSegment geometry (not points, circles, etc.)
            geom_type = type(geom).__name__
            if 'LineSegment' not in geom_type and 'Line' not in geom_type:
                continue
                
            if hasattr(geom, 'StartPoint') and hasattr(geom, 'EndPoint'):
                lines.append({
                    'start': geom.StartPoint,
                    'end': geom.EndPoint,
                    'index': i
                })
        
        FreeCAD.Console.PrintMessage(f"Found {len(lines)} line segments in wall sketch\n")
        
        if len(lines) > 1:
            # Multi-segment wall
            wall_height = float(wall_obj.Height)
            wall_width = float(wall_obj.Width)
            
            # Get sketch placement to transform coordinates
            sketch_placement = sketch.Placement
            
            for i, line in enumerate(lines):
                start = sketch_placement.multVec(line['start'])
                end = sketch_placement.multVec(line['end'])
                
                # Calculate segment properties
                dx = end.x - start.x
                dy = end.y - start.y
                length = math.sqrt(dx*dx + dy*dy)
                
                # Direction angle (for placing the frame)
                angle = math.atan2(dy, dx) * 180 / math.pi
                
                # Get height at start and end of this segment for sloped walls
                # We'll analyze the wall shape to find actual heights
                height_start = wall_height
                height_end = wall_height
                
                # Try to find actual heights from wall shape
                try:
                    height_start, height_end = _get_segment_heights(wall_obj, start, end, wall_height)
                except Exception as e:
                    FreeCAD.Console.PrintWarning(f"Could not analyze segment slope: {e}\n")
                
                segments.append({
                    'start': start,
                    'end': end,
                    'length': length,
                    'height': wall_height,
                    'height_start': height_start,
                    'height_end': height_end,
                    'width': wall_width,
                    'angle': angle,
                    'index': i,
                    'is_first': i == 0,
                    'is_last': i == len(lines) - 1,
                })
            
            return segments
    
    # Single segment - return None to use standard processing
    return None


def extract_wall_data(wall_obj):
    """Extract wall dimensions and openings from a FreeCAD BIM Wall object."""
    
    # Get wall dimensions from properties
    wall_length = float(wall_obj.Length)
    wall_height = float(wall_obj.Height)
    wall_width = float(wall_obj.Width)  # Thickness
    
    # Get wall bounding box to understand its actual position and orientation
    wall_bb = wall_obj.Shape.BoundBox
    
    # Determine wall orientation from bounding box
    # The smallest dimension is thickness, largest is usually length
    x_size = wall_bb.XMax - wall_bb.XMin
    y_size = wall_bb.YMax - wall_bb.YMin
    z_size = wall_bb.ZMax - wall_bb.ZMin
    
    # Wall origin (minimum corner in X and Z)
    wall_x_min = wall_bb.XMin
    wall_z_min = wall_bb.ZMin
    
    # Get wall placement for coordinate transformation
    wall_placement = wall_obj.Placement
    
    # Find openings (windows and doors)
    openings = []
    seen_objects = set()  # Avoid duplicates
    
    # Check for TimberOpenings property (custom data from test script)
    if hasattr(wall_obj, 'TimberOpenings') and wall_obj.TimberOpenings:
        for op_data in wall_obj.TimberOpenings:
            opening = Opening(
                x_position=op_data['x'],
                width=op_data['width'],
                height=op_data['height'],
                sill_height=op_data['sill'],
                opening_type=op_data['type']
            )
            openings.append(opening)
        # If we have custom data, return early
        return {
            'length': wall_length,
            'height': wall_height,
            'width': wall_width,
            'placement': wall_placement,
            'openings': openings,
            'x_min': wall_x_min,
            'z_min': wall_z_min,
        }
    
    # Check Subtractions (older method)
    if hasattr(wall_obj, 'Subtractions') and wall_obj.Subtractions:
        for sub in wall_obj.Subtractions:
            if sub.Name not in seen_objects:
                seen_objects.add(sub.Name)
                opening = _extract_opening_from_bim_object(sub, wall_obj)
                if opening:
                    openings.append(opening)
    
    # Check for objects that have this wall as host
    doc = wall_obj.Document
    for obj in doc.Objects:
        if obj.Name in seen_objects:
            continue
            
        is_hosted = False
        if hasattr(obj, 'Hosts'):
            # Hosts can be a list or a single object
            hosts = obj.Hosts if isinstance(obj.Hosts, (list, tuple)) else [obj.Hosts]
            if wall_obj in hosts:
                is_hosted = True
        elif hasattr(obj, 'Host') and obj.Host == wall_obj:
            is_hosted = True
        
        if is_hosted:
            seen_objects.add(obj.Name)
            opening = _extract_opening_from_bim_object(obj, wall_obj)
            if opening:
                openings.append(opening)
    
    # Check for sloped top
    top_profile = _get_wall_top_profile(wall_obj)
    
    return {
        'length': wall_length,
        'height': wall_height,
        'width': wall_width,
        'placement': wall_placement,
        'openings': openings,
        'x_min': wall_x_min,
        'z_min': wall_z_min,
        'top_profile': top_profile,  # None if flat, list of (x,z) if sloped
    }


# =========================================================================
# Base-to-Frame (Floor)  -  step 2: slab outline extraction only.
# =========================================================================

class SlabOpening:
    """A hole in a floor slab (stair / chimney / duct).

    Carries the opening rectangle in slab-local XY coordinates, with X
    along the slab's longer dimension and Y along the shorter one. These
    are the same conventions the floor framing geometry builder will
    expect in step 3.
    """

    def __init__(self, x, y, width, length, label=''):
        self.x = x            # slab-local X of lower-left corner (mm)
        self.y = y            # slab-local Y of lower-left corner (mm)
        self.width = width    # extent along slab-local X (mm)
        self.length = length  # extent along slab-local Y (mm)
        self.label = label

    def __repr__(self):
        return (
            f"SlabOpening({self.label!r}, "
            f"x={self.x:.0f}, y={self.y:.0f}, "
            f"w={self.width:.0f}, L={self.length:.0f})"
        )


def _slab_top_face(slab_obj):
    """Return the top horizontal face of a slab, or None.

    "Top" = face whose normal has +Z component close to 1. We pick the
    largest such face so a chamfered or stepped slab still yields the
    main deck plane.
    """
    best = None
    best_area = 0.0
    for face in slab_obj.Shape.Faces:
        try:
            uv = face.Surface.parameter(face.CenterOfMass)
            n = face.normalAt(uv[0], uv[1])
            if n.z > 0.9 and face.Area > best_area:
                best = face
                best_area = face.Area
        except Exception:
            continue
    return best


def _slab_local_basis(slab_obj, top_face):
    """Compute slab-local axes from the top face's oriented bounding rectangle.

    Returns a tuple (origin, x_axis, y_axis, length, width) where:
      - origin is a world Vector at the lower-left of the OBB (slab-local
        (0, 0));
      - x_axis / y_axis are unit Vectors in world coords aligned with the
        longer and shorter OBB edges respectively;
      - length is the extent along x_axis (longer side, mm);
      - width  is the extent along y_axis (shorter side, mm).

    For the rectangular case this is unambiguous. For non-rectangular
    outlines we take the oriented bounding box of the top-face vertices
    projected onto the slab's own horizontal plane - which gives a
    tight-enough bounding rectangle to lay out joists along the long
    axis. Non-rectangular clipping is a step-5 concern.
    """
    # Collect top-face outer-wire vertices in world coords, projected to
    # the top face's Z plane.
    pts = [v.Point for v in top_face.OuterWire.Vertexes]
    if len(pts) < 3:
        return None

    # Use the top face's bounding box as the rectangular approximation for
    # step 2. (A full oriented-bbox would need PCA; the plan tags that as
    # a step-5 concern and we don't need it for axis-aligned slabs.)
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    z = sum(p.z for p in pts) / len(pts)
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    dx = x_max - x_min
    dy = y_max - y_min

    # X axis = long side so joists span the shorter direction by default.
    # The local frame must be right-handed (y_axis = Z x x_axis) AND land
    # on the slab, which pins the origin to a specific corner.
    if dx >= dy:
        length = dx
        width = dy
        x_axis = FreeCAD.Vector(1, 0, 0)
        y_axis = FreeCAD.Vector(0, 1, 0)      # right-handed, +Y into slab
        origin = FreeCAD.Vector(x_min, y_min, z)
    else:
        length = dy
        width = dx
        x_axis = FreeCAD.Vector(0, 1, 0)      # local X along world +Y
        y_axis = FreeCAD.Vector(-1, 0, 0)     # right-handed, points to -X
        # Because local +Y points to world -X, local (0, 0) must be at
        # the slab's HIGH-X corner so local Y increasing sweeps INTO the
        # slab (toward low X). Using x_min here was the earlier bug: the
        # frame landed on the wrong side of the slab.
        origin = FreeCAD.Vector(x_max, y_min, z)

    return origin, x_axis, y_axis, length, width


def _world_to_slab_local(point, origin, x_axis, y_axis):
    """Project a world point into the slab's local 2D frame."""
    d = FreeCAD.Vector(point.x - origin.x, point.y - origin.y, 0)
    return d.dot(x_axis), d.dot(y_axis)


def _extract_slab_opening_from_object(obj, origin, x_axis, y_axis):
    """Build a SlabOpening in slab-local coords from a hosted/subtracted object.

    Any object whose shape intersects the slab top plane and that is NOT a
    structural element (Wall / Roof / Slab / Floor) is treated as a hole.
    """
    try:
        obj_class = type(obj).__name__
        if obj_class in ('Roof', 'ArchRoof', 'Slab', 'ArchSlab',
                         'Floor', 'ArchFloor', 'Wall', 'ArchWall'):
            return None

        bb = obj.Shape.BoundBox
        corners = [
            FreeCAD.Vector(bb.XMin, bb.YMin, 0),
            FreeCAD.Vector(bb.XMax, bb.YMin, 0),
            FreeCAD.Vector(bb.XMax, bb.YMax, 0),
            FreeCAD.Vector(bb.XMin, bb.YMax, 0),
        ]
        locals_ = [
            _world_to_slab_local(c, origin, x_axis, y_axis) for c in corners
        ]
        xs = [p[0] for p in locals_]
        ys = [p[1] for p in locals_]
        return SlabOpening(
            x=min(xs), y=min(ys),
            width=max(xs) - min(xs),
            length=max(ys) - min(ys),
            label=str(getattr(obj, 'Label', '')),
        )
    except Exception as e:
        FreeCAD.Console.PrintWarning(
            f"Could not extract slab opening from {getattr(obj, 'Label', '?')}: {e}\n"
        )
        return None


def is_slab(obj):
    """Return True if obj looks like a BIM/Arch floor slab."""
    try:
        if type(obj).__name__ in ('Slab', 'ArchSlab', 'Floor', 'ArchFloor'):
            return True
        ifc = str(getattr(obj, 'IfcType', '')).lower()
        if ifc in ('ifcslab', 'slab', 'ifcfloor', 'floor'):
            return True
    except Exception:
        pass
    return False


def extract_slab_data(slab_obj):
    """Extract the data needed to build a floor frame from a BIM Slab.

    Returns a dict with:
      - 'length': extent along the slab's local long axis (mm)
      - 'width':  extent along the slab's local short axis (mm)
      - 'thickness': slab vertical thickness (mm), best-effort
      - 'origin': world Vector at slab-local (0, 0, top-face-Z)
      - 'x_axis': unit world Vector for slab-local +X (long side)
      - 'y_axis': unit world Vector for slab-local +Y (short side)
      - 'top_z':  world Z of the slab's top face
      - 'placement': slab_obj.Placement (for reference)
      - 'openings': list[SlabOpening] in slab-local coordinates

    For non-rectangular slabs this is a tight axis-aligned bounding
    rectangle (good enough for step 2). Step 5 will clip joists against
    the actual outer wire for L / polygon shapes.
    """
    top_face = _slab_top_face(slab_obj)
    if top_face is None:
        raise RuntimeError(
            f"Slab {slab_obj.Label!r}: no horizontal top face found. "
            "Expected a face with normal close to +Z."
        )

    basis = _slab_local_basis(slab_obj, top_face)
    if basis is None:
        raise RuntimeError(
            f"Slab {slab_obj.Label!r}: top face has fewer than 3 vertices "
            "- cannot determine local axes."
        )
    origin, x_axis, y_axis, length, width = basis

    # Slab thickness: prefer explicit property, else infer from bbox.
    thickness = None
    for prop in ('Thickness', 'Height'):
        val = getattr(slab_obj, prop, None)
        if val is not None:
            try:
                thickness = float(val)
                if thickness > 0:
                    break
            except Exception:
                pass
    if not thickness or thickness <= 0:
        bb = slab_obj.Shape.BoundBox
        thickness = bb.ZMax - bb.ZMin

    # Openings: subtractions + hosted non-structural objects whose bbox
    # overlaps the top face region.
    openings = []
    seen = set()

    if hasattr(slab_obj, 'Subtractions') and slab_obj.Subtractions:
        for sub in slab_obj.Subtractions:
            if sub.Name in seen:
                continue
            seen.add(sub.Name)
            op = _extract_slab_opening_from_object(sub, origin, x_axis, y_axis)
            if op is not None:
                openings.append(op)

    doc = slab_obj.Document
    for obj in doc.Objects:
        if obj.Name in seen:
            continue
        hosts = getattr(obj, 'Hosts', None)
        is_hosted = False
        if hosts:
            host_list = hosts if isinstance(hosts, (list, tuple)) else [hosts]
            if slab_obj in host_list:
                is_hosted = True
        elif getattr(obj, 'Host', None) == slab_obj:
            is_hosted = True
        if not is_hosted:
            continue
        seen.add(obj.Name)
        op = _extract_slab_opening_from_object(obj, origin, x_axis, y_axis)
        if op is not None:
            openings.append(op)

    return {
        'length': length,
        'width': width,
        'thickness': thickness,
        'origin': origin,
        'x_axis': x_axis,
        'y_axis': y_axis,
        'top_z': origin.z,
        'placement': slab_obj.Placement,
        'openings': openings,
    }


# =========================================================================
# Roof-to-Frame (R2): extract the geometry we need from a BIM Roof.
# Phase 1 supports a single-slope (shed) roof plus a flat-roof fast path.
# Multi-slope roofs raise NotImplementedError.
# =========================================================================


class RoofOpening:
    """Hole in the roof (skylight / chimney / vent).

    Stored in slope-local 2D coords:
      - u: along the eave edge (0 = origin_eave end)
      - v: along the slope going eave -> ridge
      - width:  extent along u
      - length: extent along v
    """

    def __init__(self, u, v, width, length, label=''):
        self.u = u
        self.v = v
        self.width = width
        self.length = length
        self.label = label

    def __repr__(self):
        return (
            f"RoofOpening({self.label!r}, u={self.u:.0f}, v={self.v:.0f}, "
            f"w={self.width:.0f}, L={self.length:.0f})"
        )


def is_roof(obj):
    """Return True if obj looks like a BIM/Arch roof."""
    try:
        if type(obj).__name__ in ('Roof', 'ArchRoof'):
            return True
        ifc = str(getattr(obj, 'IfcType', '')).lower()
        if ifc in ('roof', 'ifcroof'):
            return True
    except Exception:
        pass
    return False


def _roof_slope_faces(roof_obj):
    """Return every slope face of a roof solid as (face, normal).

    A slope face has +Z component AND some horizontal component. This
    picks up shallow pitches (where |nz| is close to 1) just as well as
    steep ones; it only excludes strictly horizontal and strictly
    vertical faces.
    """
    out = []
    for face in roof_obj.Shape.Faces:
        try:
            uv = face.Surface.parameter(face.CenterOfMass)
            n = face.normalAt(uv[0], uv[1]).normalize()
            horiz = math.sqrt(n.x * n.x + n.y * n.y)
            if n.z > 0.01 and horiz > 1e-4:
                out.append((face, n))
        except Exception:
            continue
    # Sort largest first so callers that only want the main pitch can
    # just take the head.
    out.sort(key=lambda fn: fn[0].Area, reverse=True)
    return out


def _nearest_horizontal_edge_pair(face, normal, prefer_eave=True):
    """Return (low_edge, high_edge) of a slope face.

    The slope face's outer wire has 4 edges for a rectangular shed roof:
    two run along the eave direction (constant lower Z and constant upper
    Z) and two run along the rake (going from low to high). We identify
    the two edges whose both endpoints are at the same Z - those are the
    eave and the ridge.
    """
    outer = face.OuterWire
    edges = outer.Edges

    # Find min/max Z of the outer wire so we can match endpoints robustly
    # even on shallow pitches where numeric roundoff matters.
    zs = [v.Point.z for v in outer.Vertexes]
    z_min = min(zs)
    z_max = max(zs)
    span = max(z_max - z_min, 1.0)
    tol = max(0.5, span * 0.01)  # within 1% of the rise, min 0.5 mm

    low_edge = None
    high_edge = None
    for e in edges:
        if len(e.Vertexes) < 2:
            continue
        a = e.Vertexes[0].Point
        b = e.Vertexes[-1].Point
        at_low = abs(a.z - z_min) <= tol and abs(b.z - z_min) <= tol
        at_high = abs(a.z - z_max) <= tol and abs(b.z - z_max) <= tol
        if at_low and (low_edge is None or e.Length > low_edge.Length):
            low_edge = e
        elif at_high and (high_edge is None or e.Length > high_edge.Length):
            high_edge = e

    return low_edge, high_edge


def _edge_as_segment(edge):
    """Return (p1, p2) as world Vectors for a straight edge, with
    p1.y <= p2.y (or p1.x <= p2.x if the edge runs along X)."""
    a = edge.Vertexes[0].Point
    b = edge.Vertexes[-1].Point
    # Order endpoints deterministically so eave and ridge both start on
    # the same "side" and the up-slope projection has a consistent sign.
    if abs(b.y - a.y) > abs(b.x - a.x):
        if b.y < a.y:
            a, b = b, a
    else:
        if b.x < a.x:
            a, b = b, a
    return FreeCAD.Vector(a.x, a.y, a.z), FreeCAD.Vector(b.x, b.y, b.z)


def _roof_openings_from_doc(roof_obj, origin_eave, eave_axis, up_slope_axis):
    """Return RoofOpening instances for every chimney / skylight / dormer
    cutout. Anything that isn't positively identifiable as an opening (or
    is a structural element) is ignored, just like with walls and slabs."""
    openings = []
    seen = set()

    def _project(point_world):
        d = point_world - origin_eave
        u = d.dot(eave_axis)
        v = d.dot(up_slope_axis)
        return u, v

    def _bbox_to_opening(obj):
        try:
            bb = obj.Shape.BoundBox
            corners_world = [
                FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMin),
                FreeCAD.Vector(bb.XMax, bb.YMin, bb.ZMin),
                FreeCAD.Vector(bb.XMax, bb.YMax, bb.ZMin),
                FreeCAD.Vector(bb.XMin, bb.YMax, bb.ZMin),
                FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMax),
                FreeCAD.Vector(bb.XMax, bb.YMin, bb.ZMax),
                FreeCAD.Vector(bb.XMax, bb.YMax, bb.ZMax),
                FreeCAD.Vector(bb.XMin, bb.YMax, bb.ZMax),
            ]
            uv = [_project(c) for c in corners_world]
            us = [p[0] for p in uv]
            vs = [p[1] for p in uv]
            return RoofOpening(
                u=min(us), v=min(vs),
                width=max(us) - min(us),
                length=max(vs) - min(vs),
                label=str(getattr(obj, 'Label', '')),
            )
        except Exception as e:
            FreeCAD.Console.PrintWarning(
                f"Could not extract roof opening from "
                f"{getattr(obj, 'Label', '?')}: {e}\n"
            )
            return None

    if hasattr(roof_obj, 'Subtractions') and roof_obj.Subtractions:
        for sub in roof_obj.Subtractions:
            cls = type(sub).__name__
            if cls in ('Wall', 'ArchWall', 'Slab', 'ArchSlab',
                       'Floor', 'ArchFloor', 'Roof', 'ArchRoof'):
                continue
            seen.add(sub.Name)
            op = _bbox_to_opening(sub)
            if op is not None:
                openings.append(op)

    doc = roof_obj.Document
    for obj in doc.Objects:
        if obj.Name in seen:
            continue
        hosts = getattr(obj, 'Hosts', None)
        host_list = (
            hosts if isinstance(hosts, (list, tuple)) else [hosts] if hosts else []
        )
        if roof_obj not in host_list and getattr(obj, 'Host', None) != roof_obj:
            continue
        cls = type(obj).__name__
        if cls in ('Wall', 'ArchWall', 'Slab', 'ArchSlab',
                   'Floor', 'ArchFloor', 'Roof', 'ArchRoof'):
            continue
        seen.add(obj.Name)
        op = _bbox_to_opening(obj)
        if op is not None:
            openings.append(op)

    return openings


def _flat_roof_data_from_base(roof_obj, settings_like_threshold_deg):
    """Build a flat-roof data dict from the roof's base sketch, used by
    the Phase-2 route that frames the roof as a horizontal joist platform.

    Returns the same keys as the pitched case but with is_flat=True,
    slope_angle_rad=0, up_slope_axis = unit vector along the base's short
    side, eave_axis = unit vector along the base's long side.
    """
    bb = roof_obj.Shape.BoundBox
    dx = bb.XMax - bb.XMin
    dy = bb.YMax - bb.YMin
    top_z = bb.ZMax
    thickness = 0.0
    try:
        thickness = float(getattr(roof_obj, 'Thickness', [0])[0])
    except Exception:
        pass

    # Long side = eave (joists span the shorter dimension)
    if dx >= dy:
        length = dx
        width = dy
        origin = FreeCAD.Vector(bb.XMin, bb.YMin, top_z)
        eave_axis = FreeCAD.Vector(1, 0, 0)
        up_slope_axis = FreeCAD.Vector(0, 1, 0)
    else:
        length = dy
        width = dx
        # Flip the origin to the high-X corner so up_slope sweeps into
        # the roof (same trick we use for Y-aligned slabs).
        origin = FreeCAD.Vector(bb.XMax, bb.YMin, top_z)
        eave_axis = FreeCAD.Vector(0, 1, 0)
        up_slope_axis = FreeCAD.Vector(-1, 0, 0)

    openings = _roof_openings_from_doc(roof_obj, origin, eave_axis, up_slope_axis)

    return {
        'origin_eave': origin,
        'eave_axis': eave_axis,
        'up_slope_axis': up_slope_axis,
        'face_normal': FreeCAD.Vector(0, 0, 1),
        'eave_length': length,
        'rafter_length': width,
        'slope_angle_rad': 0.0,
        'eave_z': top_z,
        'ridge_z': top_z,
        'thickness': thickness,
        'overhang_eave': 0.0,
        'overhang_rake': 0.0,
        'placement': roof_obj.Placement,
        'openings': openings,
        'is_flat': True,
    }


def extract_roof_data(roof_obj, flat_threshold_deg=0.5):
    """Extract everything the roof-to-frame builder needs.

    Phase 1 constraints:
      - Single-slope (shed) roofs are fully supported.
      - Flat roofs (slope <= flat_threshold_deg or no slope face at all)
        are routed through a horizontal joist layout.
      - Multi-slope roofs (gable, hip, ...) raise NotImplementedError.

    Returns a dict - see ROOF_PLAN.md section "R2" for the keys.
    """
    faces = _roof_slope_faces(roof_obj)

    # 0 slope faces -> flat
    if not faces:
        return _flat_roof_data_from_base(roof_obj, flat_threshold_deg)

    # Primary slope face (largest). If there's more than one slope face
    # of comparable area we have a multi-slope roof.
    primary_face, primary_n = faces[0]
    if len(faces) > 1:
        second_area = faces[1][0].Area
        if second_area > primary_face.Area * 0.25:
            raise NotImplementedError(
                f"Roof {roof_obj.Label!r} has {len(faces)} slope faces "
                "(looks like a multi-slope roof - gable / hip / ...). "
                "Phase 3 of the roof converter will handle these; for "
                "now only single-slope (shed) roofs are supported."
            )

    horiz = math.sqrt(primary_n.x ** 2 + primary_n.y ** 2)
    slope_rad = math.atan2(horiz, primary_n.z)
    slope_deg = math.degrees(slope_rad)

    # Flat-roof fast path for very shallow pitches.
    if slope_deg <= flat_threshold_deg:
        return _flat_roof_data_from_base(roof_obj, flat_threshold_deg)

    # ---- Build the slope-local basis from the primary face ------------
    low_edge, high_edge = _nearest_horizontal_edge_pair(primary_face, primary_n)
    if low_edge is None or high_edge is None:
        raise RuntimeError(
            f"Roof {roof_obj.Label!r}: could not identify eave and ridge "
            "edges on the primary slope face. Only rectangular shed-roof "
            "outlines are supported in Phase 1."
        )

    eave_p1, eave_p2 = _edge_as_segment(low_edge)
    ridge_p1, ridge_p2 = _edge_as_segment(high_edge)

    eave_vec = eave_p2 - eave_p1
    eave_length = eave_vec.Length
    eave_axis = FreeCAD.Vector(eave_vec)
    eave_axis.normalize()

    # Up-slope axis in 3D: horizontal projection of the face normal
    # points OUTWARD from the slope (away from the roof body). The
    # vector going from eave to ridge is the opposite horizontal
    # direction, lifted by the pitch.
    horiz_vec = FreeCAD.Vector(-primary_n.x, -primary_n.y, 0)
    if horiz_vec.Length > 1e-9:
        horiz_vec.normalize()
    # Combine horizontal travel with vertical rise to get the real 3D
    # up-slope direction (unit vector along the rafter).
    up_slope_axis = FreeCAD.Vector(
        horiz_vec.x * math.cos(slope_rad),
        horiz_vec.y * math.cos(slope_rad),
        math.sin(slope_rad),
    )
    up_slope_axis.normalize()

    # Rafter length (hypotenuse): distance from a point on the eave to
    # the ridge measured along up_slope_axis.
    ridge_mid = (ridge_p1 + ridge_p2) * 0.5
    eave_mid = (eave_p1 + eave_p2) * 0.5
    rafter_length = (ridge_mid - eave_mid).Length

    # Thickness (material depth, perpendicular to the slope). Prefer the
    # roof's own Thickness[0] property; fall back to a sensible value.
    thickness = 0.0
    try:
        t = getattr(roof_obj, 'Thickness', None)
        if t:
            thickness = float(t[0])
    except Exception:
        pass
    if thickness <= 0:
        thickness = 150.0

    overhang_eave = 0.0
    overhang_rake = 0.0
    try:
        oh = getattr(roof_obj, 'Overhang', None)
        if oh:
            overhang_eave = float(oh[0])
    except Exception:
        pass

    openings = _roof_openings_from_doc(
        roof_obj, eave_p1, eave_axis, up_slope_axis
    )

    return {
        'origin_eave': eave_p1,
        'eave_axis': eave_axis,
        'up_slope_axis': up_slope_axis,
        'face_normal': primary_n,
        'eave_length': eave_length,
        'rafter_length': rafter_length,
        'slope_angle_rad': slope_rad,
        'eave_z': eave_p1.z,
        'ridge_z': ridge_p1.z,
        'thickness': thickness,
        'overhang_eave': overhang_eave,
        'overhang_rake': overhang_rake,
        'placement': roof_obj.Placement,
        'openings': openings,
        'is_flat': False,
    }


# -------------------------------------------------------------------------
# Floor framing calculator (step 3): rim joists + end joists + joists.
# Openings (trimmers + headers + tail joists) are a step-4 concern.
# -------------------------------------------------------------------------

class FloorFrameCalculator:
    """Lay out the timber members for a rectangular floor platform.

    Everything is produced in slab-local coordinates:
      - local +X runs along the long side (joists span the short side);
      - local +Y runs along the short side;
      - local Z=0 is the slab's TOP face; the frame sits below.

    Member Z extents (all negative, measured from the top of the slab):
      joists:    [z=-joist_depth .. z=0]
      rim joists are joists aligned with the long edges (full-length) and
      end joists are joists at local X=0 and X=length (span the full width).

    joist orientation / dimensions (in slab-local frame):
      length = extent along local Y (span)
      width  = joist_width  (local X)
      depth  = joist_depth  (local Z)

    This mirrors the "horizontal" plates in the wall calculator, laid on
    their narrow face.
    """

    def __init__(self, length, width, settings=None):
        """length = slab-local X span, width = slab-local Y span."""
        self.length = length
        self.width = width
        self.settings = settings or TimberSettings()
        self.openings = []     # step 4 will consume these
        self.members = []

    def add_opening(self, opening):
        self.openings.append(opening)

    def calculate(self):
        self.members = []
        s = self.settings

        jw = s.joist_width
        jd = s.joist_depth

        # 1. Rim joists along the two LONG edges (local Y = 0 and Y = width).
        # They run the full length of the slab, their width is along local Y
        # (= jw) and their length is along local X.
        if s.floor_rim_board:
            # near rim (Y = 0 .. jw)
            self.members.append(TimberMember(
                'rim_joist',
                x=0, y=0, z=-jd,
                length=self.length,
                width=jw,     # local Y extent
                depth=jd,     # local Z extent
                orientation='floor_long',
            ))
            # far rim (Y = width - jw .. width)
            self.members.append(TimberMember(
                'rim_joist',
                x=0, y=self.width - jw, z=-jd,
                length=self.length,
                width=jw,
                depth=jd,
                orientation='floor_long',
            ))

        # 2. Joists along local Y, placed at joist_spacing centres along X.
        #    The first and last joist are flush with the slab's short edges
        #    (end joists) and span the full width.
        #
        #    Y extent of the "field": sits BETWEEN the two rim joists so
        #    joists don't overlap them, otherwise it spans the whole width.
        if s.floor_rim_board:
            y_start = jw
            span = self.width - 2 * jw
        else:
            y_start = 0.0
            span = self.width

        if span <= 0:
            FreeCAD.Console.PrintWarning(
                "FloorFrameCalculator: slab is too narrow for rim joists + "
                "joists (span <= 0). Skipping field joists.\n"
            )
            return self.members

        joist_positions = self._joist_x_positions()
        for x in joist_positions:
            self.members.append(TimberMember(
                'joist',
                x=x - jw / 2.0, y=y_start, z=-jd,
                length=span,
                width=jw,      # local X extent
                depth=jd,      # local Z extent
                orientation='floor_short',
            ))

        return self.members

    def _joist_x_positions(self):
        """Centrelines of joists along local X."""
        s = self.settings
        jw = s.joist_width
        spacing = s.joist_spacing

        positions = []
        # Start joist flush with the slab's low-X edge (acts as end joist).
        positions.append(jw / 2.0)

        x = spacing
        while x < self.length - jw:
            positions.append(x)
            x += spacing

        end_pos = self.length - jw / 2.0
        if positions and end_pos - positions[-1] > jw:
            positions.append(end_pos)

        return positions


# -------------------------------------------------------------------------
# Floor geometry builder - turn FloorFrameCalculator members into solids
# and place them under the slab in world space.
# -------------------------------------------------------------------------

def _apply_slab_appearance(view_object, member_type):
    """Give floor members their own colour so they are visually distinct
    from the wall framing timber."""
    try:
        colors = {
            'joist':           (0.70, 0.52, 0.33),  # medium wood
            'rim_joist':       (0.60, 0.42, 0.26),  # darker wood
            'floor_trimmer':   (0.60, 0.42, 0.26),
            'floor_header':    (0.52, 0.36, 0.22),
            'tail_joist':      (0.70, 0.52, 0.33),
            'floor_blocking':  (0.78, 0.62, 0.44),
            'floor_sheathing': (0.86, 0.72, 0.47),
        }
        color = colors.get(member_type, (0.70, 0.52, 0.33))
        view_object.ShapeColor = color
        view_object.LineColor = (color[0] * 0.6, color[1] * 0.6, color[2] * 0.6)
        view_object.Transparency = 0
        view_object.LineWidth = 1.0
    except Exception as e:
        FreeCAD.Console.PrintWarning(
            f"Could not apply slab appearance: {e}\n"
        )


def _build_floor_box(member, origin, x_axis, y_axis, top_z):
    """Build the solid for one floor member in world space.

    All members are axis-aligned boxes in slab-local coords. We build the
    local box, then transform its corner into world coords by composing
    (origin + x_axis * local_x + y_axis * local_y + Z * local_z).

    Returns a Part.Shape (Solid).
    """
    import Part

    # Local extents based on orientation.
    if member.orientation == 'floor_long':
        # Rim joist: length along local X, width along local Y, depth in Z.
        lx = member.length
        ly = member.width
    elif member.orientation == 'floor_short':
        # Joist: width along local X, length along local Y.
        lx = member.width
        ly = member.length
    else:
        lx = member.width
        ly = member.length

    lz = member.depth

    # 8 corners in local coordinates (lower-left-bottom = (x, y, z)).
    local_corners = [
        (member.x,      member.y,      member.z),
        (member.x + lx, member.y,      member.z),
        (member.x + lx, member.y + ly, member.z),
        (member.x,      member.y + ly, member.z),
    ]

    def _to_world(lx_, ly_, lz_):
        p = FreeCAD.Vector(
            origin.x + x_axis.x * lx_ + y_axis.x * ly_,
            origin.y + x_axis.y * lx_ + y_axis.y * ly_,
            top_z + lz_,
        )
        return p

    base = [_to_world(c[0], c[1], c[2]) for c in local_corners]
    bottom_wire = Part.makePolygon(base + [base[0]])
    bottom_face = Part.Face(bottom_wire)
    # Extrude upward (in slab-local +Z, which is world +Z for axis-aligned
    # slabs; the floor plane is horizontal in all current cases).
    return bottom_face.extrude(FreeCAD.Vector(0, 0, lz))


def create_floor_frame_group(doc, slab_obj, members, slab_data, settings,
                             group_name=None):
    """Create a document group containing one Part::Feature per floor member."""
    if group_name is None:
        group_name = f"Frame_{slab_obj.Label}"

    group = doc.addObject("App::DocumentObjectGroup", group_name)

    origin = slab_data['origin']
    x_axis = slab_data['x_axis']
    y_axis = slab_data['y_axis']
    top_z = slab_data['top_z']

    for member in members:
        try:
            shape = _build_floor_box(member, origin, x_axis, y_axis, top_z)
        except Exception as e:
            FreeCAD.Console.PrintError(
                f"Failed to build shape for {member}: {e}\n"
            )
            continue

        part_obj = doc.addObject("Part::Feature", member.get_label())
        part_obj.Shape = shape

        part_obj.addProperty("App::PropertyString", "TimberType",
                             "Timber", "Type of timber member")
        part_obj.TimberType = member.member_type
        part_obj.addProperty("App::PropertyFloat", "TimberLength",
                             "Timber", "Length of timber piece")
        part_obj.TimberLength = member.length

        if part_obj.ViewObject:
            _apply_slab_appearance(part_obj.ViewObject, member.member_type)

        group.addObject(part_obj)

    return group


# =========================================================================
# Roof framing calculator + geometry builder (R3).
# Phase 1 scope: wall plate on the eave, ridge plate on the ridge, rafters
# between them at `rafter_spacing` centres. Overhangs land in R4, sheathing
# in R5, openings in R6.
# =========================================================================


class RoofFrameCalculator:
    """Lay out rafters + plates for a single-slope roof.

    Operates on a `pitch` dict with the same shape as extract_roof_data()
    returns. All geometry is produced in slope-local (u, v) coordinates:
      u -> along the eave edge (0 = origin_eave)
      v -> along the slope going eave -> ridge
    plus a thickness perpendicular to the slope face. The geometry
    builder (_build_roof_box) maps (u, v, thickness) into world coords
    using the pitch's basis vectors.
    """

    # Local orientation tags consumed by _build_roof_box.
    #   'roof_plate'  - member laid flat on the (u, v=const) line,
    #                   extruded upward (world +Z)
    #   'roof_rafter' - member tilted along +v with its depth normal to
    #                   the slope face
    _ORIENT_PLATE = 'roof_plate'
    _ORIENT_RAFTER = 'roof_rafter'

    def __init__(self, pitch, settings=None):
        self.pitch = pitch
        self.settings = settings or TimberSettings()
        self.members = []

    def calculate(self):
        self.members = []
        s = self.settings
        p = self.pitch

        # Plate thickness = rafter_width (plate is "laid flat"), plate
        # depth into the wall = plate's width across the eave. We reuse
        # rafter_width as both for consistency with light-timber shed
        # construction; a dedicated plate_depth setting can be added
        # later if required.
        plate_t = s.rafter_width

        # 1. Wall plate on the eave (v = 0).
        if s.roof_wall_plate:
            self.members.append(TimberMember(
                'wall_plate_roof',
                x=0.0,                  # u-start
                y=0.0,                  # v position
                z=0.0,                  # unused for plates
                length=p['eave_length'],
                width=s.rafter_width,   # extent along v (into the roof)
                depth=plate_t,          # vertical thickness in world Z
                orientation=self._ORIENT_PLATE,
            ))

        # 2. Ridge plate at v = rafter_length. Its "width" extent is
        #    carved OUT of the roof (negative v) so the plate sits just
        #    short of the ridge edge rather than past it.
        if s.roof_ridge_plate:
            self.members.append(TimberMember(
                'ridge_plate',
                x=0.0,
                y=p['rafter_length'] - s.rafter_width,
                z=0.0,
                length=p['eave_length'],
                width=s.rafter_width,
                depth=plate_t,
                orientation=self._ORIENT_PLATE,
            ))

        # 3. Rafters at rafter_spacing along the eave. They span the
        #    full slope distance so they rest on the wall plate's inner
        #    face and butt into the ridge plate's inner face.
        for u in self._rafter_u_positions():
            self.members.append(TimberMember(
                'rafter',
                x=u - s.rafter_width / 2.0,
                y=0.0,
                z=0.0,
                length=p['rafter_length'],
                width=s.rafter_width,    # extent along u
                depth=s.rafter_depth,    # perpendicular to the slope face
                orientation=self._ORIENT_RAFTER,
            ))

        return self.members

    def _rafter_u_positions(self):
        """Centres of rafters along the eave axis."""
        s = self.settings
        p = self.pitch
        half_w = s.rafter_width / 2.0
        spacing = s.rafter_spacing

        positions = [half_w]  # end rafter flush with the gable
        u = spacing
        while u < p['eave_length'] - s.rafter_width:
            positions.append(u)
            u += spacing

        end = p['eave_length'] - half_w
        if positions and end - positions[-1] > s.rafter_width:
            positions.append(end)

        return positions


def _apply_roof_appearance(view_object, member_type):
    """Give roof members distinct colouring so they're visually separate
    from wall framing and floor joists."""
    try:
        colors = {
            'rafter':           (0.58, 0.40, 0.24),  # cedar-ish
            'wall_plate_roof':  (0.70, 0.52, 0.33),
            'ridge_plate':      (0.70, 0.52, 0.33),
            'roof_sheathing':   (0.86, 0.72, 0.47),
            'roof_trimmer':     (0.60, 0.42, 0.26),
            'roof_header':      (0.52, 0.36, 0.22),
            'roof_tail_rafter': (0.58, 0.40, 0.24),
        }
        color = colors.get(member_type, (0.58, 0.40, 0.24))
        view_object.ShapeColor = color
        view_object.LineColor = (color[0] * 0.6, color[1] * 0.6, color[2] * 0.6)
        view_object.Transparency = 0
        view_object.LineWidth = 1.0
    except Exception as e:
        FreeCAD.Console.PrintWarning(
            f"Could not apply roof appearance: {e}\n"
        )


def _build_roof_box(member, pitch):
    """Build the world-space solid for one roof member.

    For PLATES: a flat box laid on the eave or ridge line. Extruded
    upward in world +Z by its vertical thickness (`member.depth`), the
    box extends `member.width` into the roof along the up-slope axis.

    For RAFTERS: a tilted box resting on the slope face. The base
    rectangle lies ON the slope face (u, v) with the given rafter width
    (u-extent) and length (v-extent). The box is then extruded along the
    face normal (perpendicular to the slope) by `member.depth`, so the
    rafter stands on edge above the slope surface.
    """
    import Part

    origin = pitch['origin_eave']
    eave = pitch['eave_axis']
    up = pitch['up_slope_axis']
    n = pitch['face_normal']

    u0 = member.x
    v0 = member.y
    u1 = u0 + member.width
    v1 = v0 + member.length

    def _P(u, v):
        return FreeCAD.Vector(
            origin.x + eave.x * u + up.x * v,
            origin.y + eave.y * u + up.y * v,
            origin.z + eave.z * u + up.z * v,
        )

    if member.orientation == RoofFrameCalculator._ORIENT_PLATE:
        # The plate's "length" is along the eave (u), but the member was
        # stored with length = eave_length and width = rafter_width,
        # which maps to extent along v = rafter_width. Rebuild the four
        # bottom corners on the slope plane...
        p1 = _P(u0, v0)
        p2 = _P(u0 + member.length, v0)
        p3 = _P(u0 + member.length, v0 + member.width)
        p4 = _P(u0, v0 + member.width)
        # ...and extrude straight UP in world Z by the plate's thickness.
        # This gives a horizontal top face on the plate even though its
        # bottom follows the (very slight) slope - which is how real
        # plates sit on a wall below the sloped sheathing.
        wire = Part.makePolygon([p1, p2, p3, p4, p1])
        face = Part.Face(wire)
        return face.extrude(FreeCAD.Vector(0, 0, member.depth))

    if member.orientation == RoofFrameCalculator._ORIENT_RAFTER:
        # Base rectangle lies on the slope face.
        p1 = _P(u0, v0)
        p2 = _P(u1, v0)
        p3 = _P(u1, v1)
        p4 = _P(u0, v1)
        wire = Part.makePolygon([p1, p2, p3, p4, p1])
        face = Part.Face(wire)
        # Extrude perpendicular to the slope face by rafter_depth so the
        # rafter stands on edge above the slope.
        return face.extrude(
            FreeCAD.Vector(n.x * member.depth,
                           n.y * member.depth,
                           n.z * member.depth)
        )

    raise ValueError(
        f"_build_roof_box: unsupported orientation {member.orientation!r}"
    )


def create_roof_frame_group(doc, roof_obj, members, pitch, settings,
                            group_name=None):
    """Create a document group containing one Part::Feature per roof member."""
    if group_name is None:
        group_name = f"Frame_{roof_obj.Label}"

    group = doc.addObject("App::DocumentObjectGroup", group_name)

    for member in members:
        try:
            shape = _build_roof_box(member, pitch)
        except Exception as e:
            FreeCAD.Console.PrintError(
                f"Failed to build shape for {member}: {e}\n"
            )
            continue

        part_obj = doc.addObject("Part::Feature", member.get_label())
        part_obj.Shape = shape

        part_obj.addProperty("App::PropertyString", "TimberType",
                             "Timber", "Type of timber member")
        part_obj.TimberType = member.member_type
        part_obj.addProperty("App::PropertyFloat", "TimberLength",
                             "Timber", "Length of timber piece")
        part_obj.TimberLength = member.length

        if part_obj.ViewObject:
            _apply_roof_appearance(part_obj.ViewObject, member.member_type)

        group.addObject(part_obj)

    return group


def _extract_opening_from_bim_object(obj, wall_obj):
    """Extract opening data from a BIM window or door object using bounding boxes."""
    try:
        # Only accept actual windows / doors. Rejecting anything else here
        # avoids e.g. a Roof used as a Subtraction being framed as a giant
        # window (which also wipes out every stud behind it).
        obj_type = _is_window_or_door(obj)
        if obj_type is None:
            return None

        # Get the object's bounding box - this tells us exactly where it is
        obj_bb = obj.Shape.BoundBox
        wall_bb = wall_obj.Shape.BoundBox
        
        # Get opening dimensions from bounding box
        # For a wall along X axis: opening width is X size, height is Z size
        opening_width = obj_bb.XMax - obj_bb.XMin
        opening_height = obj_bb.ZMax - obj_bb.ZMin
        
        # Calculate position relative to wall start (wall's X minimum)
        # x_position is the CENTER of the opening relative to wall start
        opening_x_center = (obj_bb.XMin + obj_bb.XMax) / 2
        x_position_relative = opening_x_center - wall_bb.XMin
        
        # Sill height (bottom of opening relative to wall bottom)
        sill_height = obj_bb.ZMin - wall_bb.ZMin
        
        # For doors, sill should be 0 (at floor level)
        if obj_type == "door":
            sill_height = max(0, sill_height)  # Ensure not negative
        
        FreeCAD.Console.PrintMessage(
            f"Found {obj_type}: {obj.Label} - "
            f"width={opening_width:.0f}, height={opening_height:.0f}, "
            f"x_pos={x_position_relative:.0f}, sill={sill_height:.0f}\n"
        )
        
        return Opening(
            x_position=x_position_relative,
            width=opening_width,
            height=opening_height,
            sill_height=sill_height,
            opening_type=obj_type
        )
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Could not extract opening data from {obj.Label}: {e}\n")
        return None


def _is_window_or_door(obj):
    """Return 'window', 'door', or None.

    An object only counts as a wall opening if we can positively identify
    it as a window or a door. Anything else (roofs, slabs, generic voids
    used as Subtractions) must be rejected so we don't accidentally frame
    around them: that would produce ghost king/jack/sill assemblies and
    delete every stud behind the "opening".
    """
    try:
        # Strongest signal: Arch workbench stores a human-readable type.
        obj_class = type(obj).__name__
        if obj_class in ('Window', 'ArchWindow'):
            # Arch Window is used for both windows AND doors; disambiguate
            # via IfcType / preset.
            ifc = str(getattr(obj, 'IfcType', '')).lower()
            if 'door' in ifc:
                return 'door'
            preset = str(getattr(obj, 'WindowType', '')).lower()
            if 'door' in preset:
                return 'door'
            return 'window'
        if obj_class in ('Door', 'ArchDoor'):
            return 'door'
        if obj_class in ('Roof', 'ArchRoof', 'Slab', 'ArchSlab',
                         'Floor', 'ArchFloor', 'Wall', 'ArchWall'):
            return None  # structural element, never an opening

        # Fall back to IfcType / ObjectType strings.
        ifc = str(getattr(obj, 'IfcType', '')).lower()
        if 'door' in ifc:
            return 'door'
        if 'window' in ifc:
            return 'window'
        if ifc in ('roof', 'ifcroof', 'slab', 'ifcslab',
                   'floor', 'ifcfloor', 'wall', 'ifcwall'):
            return None

        obj_type_str = str(getattr(obj, 'ObjectType', '')).lower()
        if 'door' in obj_type_str:
            return 'door'
        if 'window' in obj_type_str:
            return 'window'

        # Last resort: label hints. We used to default to "window" here,
        # which caused roof-cut subtractions to be framed as giant windows.
        label = str(getattr(obj, 'Label', '')).lower()
        if 'door' in label:
            return 'door'
        if 'window' in label:
            return 'window'

        return None
    except Exception:
        return None


def _extract_opening_from_object(obj, wall_obj):
    """Extract opening data from a window or door object."""
    try:
        obj_type = _is_window_or_door(obj)
        if obj_type is None:
            # Not an opening (e.g. a Roof used as a Subtraction to trim the
            # wall's top). Silently ignore.
            return None
        
        # Get dimensions
        width = float(getattr(obj, 'Width', getattr(obj, 'OverallWidth', 1000)))
        height = float(getattr(obj, 'Height', getattr(obj, 'OverallHeight', 1000)))
        
        # Get position relative to wall
        obj_placement = obj.Placement
        wall_placement = wall_obj.Placement
        
        # Calculate relative position (simplified - assumes wall along X axis)
        rel_pos = obj_placement.Base - wall_placement.Base
        x_position = rel_pos.x + width / 2
        sill_height = rel_pos.z
        
        # For doors, sill is typically 0
        if obj_type == "door":
            sill_height = 0
        
        return Opening(
            x_position=x_position,
            width=width,
            height=height,
            sill_height=sill_height,
            opening_type=obj_type
        )
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Could not extract opening data: {e}\n")
        return None


def _apply_wood_appearance(view_object, member_type):
    """Apply wood-like appearance to a timber member."""
    
    # Wood colors for different member types (RGB 0-1 range)
    # Slightly different shades to distinguish member types
    wood_colors = {
        'bottom_plate': (0.76, 0.60, 0.42),    # Light oak
        'top_plate': (0.76, 0.60, 0.42),       # Light oak
        'top_plate_sloped': (0.76, 0.60, 0.42),# Light oak
        'stud': (0.82, 0.65, 0.45),            # Pine/spruce
        'king_stud': (0.70, 0.52, 0.35),       # Darker - structural
        'jack_stud': (0.70, 0.52, 0.35),       # Darker - structural
        'header': (0.65, 0.45, 0.28),          # Dark oak - heavy beam
        'sill': (0.72, 0.55, 0.38),            # Medium brown
        'cripple_top': (0.85, 0.70, 0.50),     # Lighter - small pieces
        'cripple_bottom': (0.85, 0.70, 0.50),  # Lighter - small pieces
    }
    
    # Get color for this member type, default to generic wood
    color = wood_colors.get(member_type, (0.78, 0.62, 0.44))
    
    try:
        # Set shape color
        view_object.ShapeColor = color
        
        # Set line color slightly darker
        view_object.LineColor = (color[0] * 0.6, color[1] * 0.6, color[2] * 0.6)
        
        # Set transparency (0 = opaque)
        view_object.Transparency = 0
        
        # Make edges visible for better definition
        view_object.LineWidth = 1.0
        
    except Exception as e:
        FreeCAD.Console.PrintWarning(f"Could not apply wood appearance: {e}\n")


def create_timber_shapes(members, wall_placement=None):
    """Create Part shapes for all timber members.
    
    Frame is created in XZ plane (vertical wall):
    - X axis: along wall length
    - Y axis: wall thickness direction  
    - Z axis: wall height (vertical)
    
    Member coordinates:
    - member.x = position along wall length (X)
    - member.y = position in wall thickness (Y) - usually 0
    - member.z = position in height (Z)
    """
    shapes = []
    
    for member in members:
        # Create box at origin, then translate to position
        if member.orientation == 'vertical':
            # Vertical member (stud): stands upright
            # - width goes along X (wall length direction) - e.g., 45mm
            # - depth goes along Y (wall thickness direction) - e.g., 145mm
            # - length goes along Z (height - vertical)
            box = Part.makeBox(
                member.width,   # X - stud width (e.g., 45mm)
                member.depth,   # Y - stud depth (e.g., 145mm)
                member.length   # Z - stud length/height
            )
        else:
            # Horizontal member (plate, header, sill): lies flat
            # - length goes along X (wall length direction)
            # - depth goes along Y (wall thickness direction) - e.g., 145mm  
            # - width is the thickness when laid flat - e.g., 45mm
            box = Part.makeBox(
                member.length,  # X - plate length
                member.depth,   # Y - plate depth (e.g., 145mm)
                member.width    # Z - plate thickness (e.g., 45mm laid flat)
            )
        
        # Translate to correct position
        # member.x, member.y, member.z are the corner positions
        translation = Vector(member.x, member.y, member.z)
        box.translate(translation)
        
        shapes.append((member, box))
    
    return shapes


def create_frame_sketch(doc, wall_obj, members, settings, sketch_name=None):
    """Create a sketch representing stud positions for editing.
    
    The sketch is in the XZ plane (wall elevation view).
    Vertical lines represent stud centerlines.
    User can edit these to adjust stud positions.
    """
    import Sketcher
    import Part
    
    if sketch_name is None:
        sketch_name = f"FrameSketch_{wall_obj.Label}"
    
    # Get wall dimensions
    wall_bb = wall_obj.Shape.BoundBox
    wall_x_min = wall_bb.XMin
    wall_z_min = wall_bb.ZMin
    wall_length = float(wall_obj.Length)
    wall_height = float(wall_obj.Height)
    
    # Create sketch on XZ plane (vertical, facing Y)
    sketch = doc.addObject("Sketcher::SketchObject", sketch_name)
    
    # Position sketch IN FRONT of the frame (negative Y to be in front when viewing from front)
    sketch.Placement = Placement(
        Vector(wall_x_min, wall_bb.YMin - 100, wall_z_min),  # 100mm in front of wall (negative Y)
        Rotation(Vector(1, 0, 0), 90)  # Rotate to stand up (XZ plane)
    )
    sketch.MapMode = "Deactivated"
    
    # Calculate stud region
    plate_height = settings.stud_width
    bottom_plates_height = settings.bottom_plate_count * plate_height
    top_plates_height = settings.top_plate_count * plate_height
    stud_bottom = bottom_plates_height
    stud_top = wall_height - top_plates_height
    
    # Draw boundary lines (construction geometry) - these are FIXED reference lines
    # Index 0: Bottom line (at stud bottom level)
    idx_bottom = sketch.addGeometry(Part.LineSegment(
        Vector(0, stud_bottom, 0),
        Vector(wall_length, stud_bottom, 0)
    ), True)
    
    # Index 1: Top line (at stud top level)
    idx_top = sketch.addGeometry(Part.LineSegment(
        Vector(0, stud_top, 0),
        Vector(wall_length, stud_top, 0)
    ), True)
    
    # Fix the construction lines in place (Block constraint)
    sketch.addConstraint(Sketcher.Constraint('Block', idx_bottom))
    sketch.addConstraint(Sketcher.Constraint('Block', idx_top))
    
    # Add stud centerlines with constraints to top/bottom
    stud_indices = []
    for member in members:
        if member.member_type == 'stud':
            stud_center_x = member.x + settings.stud_width / 2
            
            # Add vertical line for this stud
            idx = sketch.addGeometry(Part.LineSegment(
                Vector(stud_center_x, stud_bottom, 0),
                Vector(stud_center_x, stud_top, 0)
            ), False)
            stud_indices.append(idx)
            
            # Constrain bottom point to bottom line (PointOnObject)
            sketch.addConstraint(Sketcher.Constraint('PointOnObject', idx, 1, idx_bottom))
            # Constrain top point to top line
            sketch.addConstraint(Sketcher.Constraint('PointOnObject', idx, 2, idx_top))
            # Make the line vertical
            sketch.addConstraint(Sketcher.Constraint('Vertical', idx))
    
    doc.recompute()
    
    # Store metadata on sketch for rebuilding
    sketch.addProperty("App::PropertyLink", "SourceWall", "TimberFrame", "Source wall object")
    sketch.SourceWall = wall_obj
    
    sketch.addProperty("App::PropertyString", "SettingsJSON", "TimberFrame", "Frame settings as JSON")
    import json
    sketch.SettingsJSON = json.dumps(settings.to_dict())
    
    return sketch


def rebuild_frame_from_sketch(doc, sketch, group_name=None):
    """Rebuild 3D frame from an edited sketch."""
    import json
    
    # Get source wall
    if not hasattr(sketch, 'SourceWall') or not sketch.SourceWall:
        raise ValueError("Sketch has no linked source wall")
    
    wall_obj = sketch.SourceWall
    
    # Get settings
    if not hasattr(sketch, 'SettingsJSON'):
        raise ValueError("Sketch has no stored settings")
    
    settings = TimberSettings()
    settings.from_dict(json.loads(sketch.SettingsJSON))
    
    # Get wall dimensions
    wall_length = float(wall_obj.Length)
    wall_height = float(wall_obj.Height)
    wall_width = float(wall_obj.Width)
    
    # Extract stud positions from sketch geometry
    stud_positions = []
    for i in range(sketch.GeometryCount):
        geom = sketch.Geometry[i]
        # Skip construction geometry
        if sketch.getConstruction(i):
            continue
        # Get vertical lines (studs)
        if hasattr(geom, 'StartPoint') and hasattr(geom, 'EndPoint'):
            start = geom.StartPoint
            end = geom.EndPoint
            # Check if it's roughly vertical
            if abs(start.x - end.x) < 1:  # Same X = vertical line
                stud_x = start.x
                stud_positions.append(stud_x)
    
    stud_positions.sort()
    
    # Get openings from wall
    wall_data = extract_wall_data(wall_obj)
    openings = wall_data['openings']
    
    # Create frame calculator with custom stud positions
    calc = WallFrameCalculator(wall_length, wall_height, wall_width, settings)
    for opening in openings:
        calc.add_opening(opening)
    
    # Override stud positions with sketch positions
    calc.custom_stud_positions = stud_positions
    
    # Calculate frame
    members = calc.calculate_frame_with_custom_studs()
    
    # Create 3D geometry
    if group_name is None:
        group_name = f"Frame_{wall_obj.Label}"
    
    # Remove old frame group if exists
    old_group = doc.getObject(group_name)
    if old_group:
        for obj in old_group.Group:
            doc.removeObject(obj.Name)
        doc.removeObject(old_group.Name)
    
    group = create_frame_group(doc, wall_obj, members, group_name, settings)
    
    return group


def create_frame_group(doc, wall_obj, members, group_name=None, settings=None):
    """Create a group containing all timber frame objects."""
    
    if group_name is None:
        group_name = f"Frame_{wall_obj.Label}"
    
    # Create group
    group = doc.addObject("App::DocumentObjectGroup", group_name)
    
    # Get wall's actual position from bounding box
    # This handles walls that are centered or offset
    wall_bb = wall_obj.Shape.BoundBox
    wall_x_start = wall_bb.XMin  # Where wall actually starts in X
    wall_y_start = wall_bb.YMin  # Where wall starts in Y (for centering frame in wall)
    wall_z_start = wall_bb.ZMin  # Where wall starts in Z (usually 0)
    
    # Center the frame in the wall thickness
    wall_thickness = wall_bb.YMax - wall_bb.YMin
    frame_y_offset = wall_y_start + (wall_thickness - settings.stud_depth) / 2 if settings else wall_y_start
    
    for member in members:
        # Calculate actual position including wall offset
        pos_x = member.x + wall_x_start
        pos_y = member.y + frame_y_offset
        pos_z = member.z + wall_z_start
        
        # Create box at the correct position directly
        if member.orientation == 'vertical':
            # Vertical member (stud): stands upright
            box = Part.makeBox(
                member.width,   # X - stud width (e.g., 45mm)
                member.depth,   # Y - stud depth (e.g., 145mm)
                member.length,  # Z - stud height
                Vector(pos_x, pos_y, pos_z)
            )
        elif member.orientation == 'sloped':
            # Sloped member (angled top plate): create as extruded trapezoid
            z_start = pos_z
            z_end = member.z_end + wall_z_start if hasattr(member, 'z_end') else pos_z
            
            # Create a sloped box using points
            # Bottom face at z_start/z_end, top face at z_start+depth/z_end+depth
            pts = [
                Vector(pos_x, pos_y, z_start),
                Vector(pos_x + member.length, pos_y, z_end),
                Vector(pos_x + member.length, pos_y + member.width, z_end),
                Vector(pos_x, pos_y + member.width, z_start),
            ]
            # Create bottom wire
            bottom_wire = Part.makePolygon(pts + [pts[0]])
            bottom_face = Part.Face(bottom_wire)
            
            # Extrude upward by plate thickness
            box = bottom_face.extrude(Vector(0, 0, member.depth))
        else:
            # Horizontal member (plate, header, sill): laid flat
            box = Part.makeBox(
                member.length,  # X - plate length
                member.width,   # Y - plate width (into wall)
                member.depth,   # Z - plate thickness
                Vector(pos_x, pos_y, pos_z)
            )
        
        # Create Part feature
        part_obj = doc.addObject("Part::Feature", member.get_label())
        part_obj.Shape = box
        
        # Add custom properties for identification
        part_obj.addProperty("App::PropertyString", "TimberType", "Timber", "Type of timber member")
        part_obj.TimberType = member.member_type
        
        part_obj.addProperty("App::PropertyFloat", "TimberLength", "Timber", "Length of timber piece")
        part_obj.TimberLength = member.length
        
        # Apply wood appearance
        if part_obj.ViewObject:
            _apply_wood_appearance(part_obj.ViewObject, member.member_type)
        
        # Add to group
        group.addObject(part_obj)
    
    return group
