# Copyright 2022 by Hextant Studios. https://HextantStudios.com
# This work is licensed under GNU General Public License Version 3.
# License: https://download.blender.org/release/GPL3-license.txt

# Inspired by: https://github.com/AlansCodeLog/blender-debugger-for-vscode

# Notes:
# * As of 5/3/2022 debugpy provides no methods to stop the server or check if one is
#   still listening.

bl_info = {
    "name": "Python Debugger",
    "author": "Hextant Studios",
    "version": (1, 2, 0),
    "blender": (3, 0, 0),
    "location": "Click 'Install debugpy' below. Main Menu / Blender Icon / System / Start Python Debugger",
    "description": "Starts debugpy and listens for connections from a remote debugger such " \
        "as Visual Studio Code or Visual Studio 2019 v16.6+.",
    "doc_url": "https://github.com/hextantstudios/hextant_python_debugger",
    "category": "Development",
}

import bpy
import sys
import os
import site
import subprocess
import importlib
from bpy.types import Operator, AddonPreferences
from bpy.props import IntProperty
from bpy.app.handlers import persistent
import traceback

# The global debugpy module (imported when the server is started).
debugpy = None

# Returns true if debugpy has been installed.
def is_debugpy_installed() -> bool:
    try:
        # Blender does not add the user's site-packages/ directory by default.
        sys.path.append(site.getusersitepackages())
        return importlib.util.find_spec('debugpy') is not None
    finally:
        sys.path.remove(site.getusersitepackages())

#
# Addon Preferences
#

# Preferences to select the addon package name, etc.
class DebugPythonPreferences(AddonPreferences):
    bl_idname = __package__

    port: IntProperty(name="Server Port", default=5678, min=1024, max=65535,
        description="The port number the debug server will listen on. This must match the " +
        "port number configured in the debugger application.")

    def draw(self, context):
        installed = is_debugpy_installed()
        layout = self.layout
        layout.use_property_split = True

        if installed:
            layout.prop(self, 'port')
            layout.operator(UninstallDebugpy.bl_idname)
        else:
            layout.operator(InstallDebugpy.bl_idname)


#
# Operators
#

# Installs debugpy package into Blender's Python distribution.
class InstallDebugpy(Operator):
    """Installs debugpy package into Blender's Python distribution."""
    bl_idname = "script.install_debugpy"
    bl_label = "Install debugpy"

    def execute(self, context):
        python = os.path.abspath(sys.executable)
        self.report({'INFO'}, "Installing 'debugpy' package.")
        # Verify 'pip' package manager is installed.
        try:
            context.window.cursor_set('WAIT')
            subprocess.call([python, "-m", "ensurepip"])
            # Upgrade 'pip'. This shouldn't be needed.
            # subprocess.call([python, "-m", "pip", "install", "--upgrade", "pip", "--yes"])
        except Exception:
            self.report({'ERROR'}, "Failed to verify 'pip' package manager installation.")
            return {'FINISHED'}
        finally:
            context.window.cursor_set('DEFAULT')

        # Install 'debugpy' package.
        try:
            context.window.cursor_set('WAIT')
            subprocess.call([python, "-m", "pip", "install", "debugpy"])
        except Exception:
            self.report({'ERROR'}, "Failed to install 'debugpy' package.")
            return {'FINISHED'}
        finally:
            context.window.cursor_set('DEFAULT')

        self.report({'INFO'}, "Successfully installed 'debugpy' package.")
        return {'FINISHED'}


# Uninstalls debugpy package into Blender's Python distribution.
class UninstallDebugpy(Operator):
    """Uninstalls debugpy package from Blender's Python distribution."""
    bl_idname = "script.uninstall_debugpy"
    bl_label = "Uninstall debugpy"

    def execute(self, context):
        python = os.path.abspath(sys.executable)
        self.report({'INFO'}, "Uninstalling 'debugpy' package.")

        # Uninstall 'debugpy' package.
        try:
            context.window.cursor_set('WAIT')
            subprocess.call([python, "-m", "pip", "uninstall", "debugpy", "--yes"])
        except Exception:
            self.report({'ERROR'}, "Failed to uninstall 'debugpy' package.")
            return {'FINISHED'}
        finally:
            context.window.cursor_set('DEFAULT')

        self.report({'INFO'}, "Successfully uninstalled 'debugpy' package.")
        return {'FINISHED'}

DEBUGPY_LISTENING = False

def popup(message="", title="Message Box", icon="INFO"):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)
    return

def is_blender_debug_mode():
    """Check if Blender was started with --debug or --debug-all"""
    return any(arg in sys.argv for arg in ('--debug', '--debug-all'))

# Starts the debug server for Python scripts.
class StartDebugServer(Operator):
    """Starts the remote debug server (debugpy) for Python scripts.
    Note: debugpy must be installed from the add-on's preferences."""
    bl_idname = "script.start_debug_server"
    bl_label = "Start Debug Server"

    @classmethod
    def poll(cls, context):
        global DEBUGPY_LISTENING
        return is_debugpy_installed()

    def execute(self, context):
        addon_prefs = context.preferences.addons[__package__].preferences

        # Import the debugpy package.
        global debugpy, DEBUGPY_LISTENING
        if not debugpy:
            try:
                sys.path.append(site.getusersitepackages())
                debugpy = importlib.import_module('debugpy')
            except:
                self.report({'ERROR'}, "Failed to import debugpy! " +
                    "Verify that debugpy has been installed from the add-on's preferences.")
                return {'FINISHED'}
            finally:
                sys.path.remove(site.getusersitepackages())

        # Start debugpy listening. Note: Always try as there is no way to query if debugpy
        # is already listening.
        # Get the desired port to listen on.
        port = addon_prefs.port

        try:
            debugpy.listen(port)
            DEBUGPY_LISTENING = True
            #bpy.context.workspace["auto_start_debugpy"] = True
        except Exception as e:
            print("Exception while starting debugpy:")
            traceback.print_exc()
            self.report({'WARNING'},
                f"Remote python debugger failed to start (or already started) on port {port} : {str(e)}")
            return {'FINISHED'}

        self.report({'INFO'}, f"Remote python debugger started on port {port}.")
        return {'FINISHED'}


# Stop the debug server for Python scripts.
class StopDebugServer(Operator):
    """Stop the remote debug server (debugpy).
    """
    bl_idname = "script.stop_debug_server"
    bl_label = "Stop Debug Server"

    @classmethod
    def poll(cls, context):
        global DEBUGPY_LISTENING
        return DEBUGPY_LISTENING

    def execute(self, context):
        addon_prefs = context.preferences.addons[__package__].preferences

        # Import the debugpy package.
        global debugpy, DEBUGPY_LISTENING
        if not debugpy:
            try:
                sys.path.append(site.getusersitepackages())
                debugpy = importlib.import_module('debugpy')

            except:
                self.report({'ERROR'}, "Failed to import debugpy! " +
                    "Verify that debugpy has been installed from the add-on's preferences.")
                return {'FINISHED'}
            finally:
                sys.path.remove(site.getusersitepackages())

        try:

            DEBUGPY_LISTENING = False
            bpy.context.workspace.remove("auto_start_debugpy")
        except Exception as e:
            self.report({'WARNING'},
                f"Auto start debugger on this file is removed, but we can't stop debugger: {str(e)}")
            return {'FINISHED'}

        self.report({'INFO'}, "Remote python debugger stopped.")
        return {'FINISHED'}

class WORKSPACE_OT_toggle_debugpy(bpy.types.Operator):
    bl_idname = "workspace.toggle_debugpy"
    bl_label = "Auto-Start Debugpy"
    bl_description = "Enable or disable auto-starting debugpy in this workspace"

    def execute(self, context):
        ws = context.workspace
        current = ws.get("auto_start_debugpy", False)
        ws["auto_start_debugpy"] = not current
        if current:
            del ws["auto_start_debugpy"]
        ## Force file as modified TODO
        #bpy.data.is_dirty = True

        self.report({'INFO'}, f"Auto Start debugpy set to {not current}")
        return {'FINISHED'}


class WORKSPACE_PT_DEBUGPY_Panel(bpy.types.Panel):
    """Python Debuging (debugpy)"""
    bl_label = "Python Debuging (debugpy)"
    bl_idname = "WORKSPACE_PT_debugpy"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    #bl_context = "Tool"
    bl_category = "Tool"

    def draw(self, context):
        global DEBUGPY_LISTENING
        ws = bpy.context.workspace
        layout = self.layout

        obj = context.object

        row = layout.row()
        row.enabled = not DEBUGPY_LISTENING
        row.operator(StartDebugServer.bl_idname, icon='SCRIPT')

        row = layout.row()
        #row.enabled = DEBUGPY_LISTENING
        if ws.get("auto_start_debugpy") and ws["auto_start_debugpy"]:
            row.operator("workspace.toggle_debugpy", icon = "CHECKBOX_HLT")
        else:
            row.operator("workspace.toggle_debugpy", icon = "CHECKBOX_DEHLT")

#
# Menu Items
#

# Draw the main menu entry for: {Blender}/System/Start Remote Debugger
def start_remote_debugger_menu(self, context):
    self.layout.operator(StartDebugServer.bl_idname, icon='SCRIPT')

def stop_remote_debugger_menu(self, context):
    self.layout.operator(StopDebugServer.bl_idname, icon='CANCEL')

@persistent
def debugpy_load_handler(dummy):
    ws = bpy.context.workspace
    if is_blender_debug_mode() or (ws.get("auto_start_debugpy") and ws["auto_start_debugpy"]):
        bpy.ops.script.start_debug_server()
        popup("Remote python debugger auto started.", "Debug debugpy")

#
# Registration
#

_classes = (DebugPythonPreferences, InstallDebugpy, UninstallDebugpy,
            StartDebugServer, #StopDebugServer,
            WORKSPACE_OT_toggle_debugpy, WORKSPACE_PT_DEBUGPY_Panel
    )

_register, _unregister = bpy.utils.register_classes_factory(_classes)

def register():
    _register()
    # Add a System menu entry to start the server.
    #bpy.types.TOPBAR_MT_blender_system.prepend(stop_remote_debugger_menu)
    bpy.types.TOPBAR_MT_blender_system.prepend(start_remote_debugger_menu)

    bpy.app.handlers.load_post.append(debugpy_load_handler)

def unregister():
    _unregister()
    bpy.app.handlers.load_post.remove(debugpy_load_handler)

    # Remove System menu entry
    bpy.types.TOPBAR_MT_blender_system.remove(start_remote_debugger_menu)
    #bpy.types.TOPBAR_MT_blender_system.remove(stop_remote_debugger_menu)

if __name__ == "__main__":
    register()