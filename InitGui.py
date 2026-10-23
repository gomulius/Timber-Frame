# TimberFrame Workbench - GUI initialization

import FreeCAD
import FreeCADGui
import os


class TimberFrameWorkbench(FreeCADGui.Workbench):
    """Timber Frame workbench for converting BIM walls to wooden frames."""
    
    MenuText = "Timber Frame"
    ToolTip = "Convert BIM walls to timber frame structures"
    # Icon will be set if available
    
    def __init__(self):
        # Get the path to this workbench
        workbench_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "TimberFrame")
        icon_path = os.path.join(workbench_path, "Resources", "icons", "TimberFrameWorkbench.svg")
        if os.path.exists(icon_path):
            self.__class__.Icon = icon_path
    
    def Initialize(self):
        """Called when workbench is first activated."""
        import TimberFrameCommands
        
        # List of commands
        self.commands = [
            "TimberFrame_ConvertWall",
            "TimberFrame_ConvertSlab",
            "TimberFrame_ConvertRoof",
            "TimberFrame_RegenerateFrame",
            "TimberFrame_EditFrame",
            "TimberFrame_RebuildFrame",
            "TimberFrame_GenerateBlueprint",
            "TimberFrame_GenerateCutList",
            "TimberFrame_Settings",
        ]
        
        # Create menu
        self.appendMenu("Timber Frame", self.commands)
        
        # Create toolbar
        self.appendToolbar("Timber Frame Tools", self.commands)
        
        FreeCAD.Console.PrintMessage("TimberFrame workbench loaded\n")
    
    def Activated(self):
        """Called when workbench is activated."""
        pass
    
    def Deactivated(self):
        """Called when workbench is deactivated."""
        pass
    
    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(TimberFrameWorkbench())
