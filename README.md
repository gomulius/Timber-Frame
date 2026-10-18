# TimberFrame Workbench for FreeCAD

Convert BIM walls to timber frame structures for wooden construction.

## Features

### Phase 1 (Current)
- ✅ Convert BIM/Arch walls to timber frame
- ✅ Configurable timber dimensions (width, depth)
- ✅ Configurable stud spacing (default 500mm for insulation panels)
- ✅ Single or multiple bottom/top plates
- ✅ Automatic detection of windows and doors
- ✅ Proper framing around openings:
  - King studs (full height)
  - Jack studs (support header)
  - Header beam
  - Rough sill (windows)
  - Cripple studs (above/below openings)
- ✅ Cut list generation (spreadsheet)
- ✅ Basic 2D blueprint generation (TechDraw)

### Phase 2 (Planned)
- 📋 Improved blueprint layouts with proper dimensioning
- 📋 Multiple view projections
- 📋 PDF export
- 📋 Corner post details

### Phase 3 (Planned)
- 📋 Sketch-based frame editing
- 📋 Interactive stud placement
- 📋 Constraint-based spacing

## Installation

The workbench is installed in:
```
%APPDATA%\FreeCAD\Mod\TimberFrame\
```

## Usage

1. **Create or open a BIM model** with walls (use BIM/Arch workbench)
2. **Switch to TimberFrame workbench** (View > Workbench > Timber Frame)
3. **Select one or more walls**
4. **Click "Convert Wall to Frame"** or use menu Timber Frame > Convert Wall to Frame
5. **Configure settings** in the dialog:
   - Stud dimensions (default: 45×145mm)
   - Stud spacing (default: 500mm)
   - Number of bottom/top plates
   - Header depth
   - Enable/disable framing components
6. **Click OK** to generate the frame

### Generate Cut List
1. After converting walls, use **Timber Frame > Generate Cut List**
2. A spreadsheet is created with all timber pieces grouped by type and length

### Generate Blueprint
1. Select a frame group or use **Timber Frame > Generate Blueprint**
2. A TechDraw page is created with elevation view

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Stud Width | 45mm | Width of stud (narrow dimension) |
| Stud Depth | 145mm | Depth of stud (wall thickness direction) |
| Bottom Plates | 1 | Number of bottom plates |
| Top Plates | 2 | Number of top plates (double for rigidity) |
| Stud Spacing | 500mm | Center-to-center spacing |
| Header Depth | 200mm | Height of header beam over openings |
| Rough Opening Gap | 10mm | Extra space around openings |

## Timber Member Types

- **Bottom Plate** - Horizontal member at floor level
- **Top Plate** - Horizontal member(s) at ceiling level
- **Stud** - Regular vertical members
- **King Stud** - Full-height studs on either side of openings
- **Jack Stud** - Shortened studs that support the header
- **Header** - Horizontal beam over openings
- **Rough Sill** - Horizontal member below windows
- **Cripple (Top)** - Short studs above header
- **Cripple (Bottom)** - Short studs below window sill

## File Structure

```
TimberFrame/
├── __init__.py           # Package marker
├── Init.py               # Non-GUI initialization
├── InitGui.py            # Workbench registration
├── TimberFrameCore.py    # Core calculation logic
├── TimberFrameCommands.py # GUI commands
├── README.md             # This file
└── Resources/
    └── icons/            # SVG icons
```

## Requirements

- FreeCAD 1.0 or later
- BIM/Arch workbench (for creating walls)
- TechDraw workbench (for blueprints)

## License

MIT License - Free to use and modify.

## Version History

- **0.1.0** - Initial release
  - Basic wall to frame conversion
  - Opening detection
  - Cut list generation
  - Basic blueprint generation
