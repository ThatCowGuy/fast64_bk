from bpy.utils import register_class, unregister_class
from bpy.props import StringProperty, FloatProperty, BoolProperty
from bpy.types import Scene
from ..utility import prop_split
from ..render_settings import on_update_render_settings
from ..panels import BK_Panel


class BK_FileSettingsPanel(BK_Panel):
    bl_idname = "BK_PT_file_settings"
    bl_label = "BK File Settings"
    bl_options = set()  # default to being open

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding, makes it easier to see these main settings
        prop_split(col, context.scene, "bkBlenderScale", "BK Scene Scale")

        prop_split(col, context.scene, "bkDecompPath", "Decomp Path")

        prop_split(col, context.scene.fast64.bk, "bk_version", "BK Version")
        # if context.scene.fast64.bk.bk_version == "Custom":
        #     prop_split(col, context.scene.fast64.bk, "bk_version_custom", "Custom Version")

        # col.prop(context.scene.fast64.bk, "headerTabAffectsVisibility")
        # col.prop(context.scene.fast64.bk, "hackerFeaturesEnabled")

        # if not context.scene.fast64.bk.hackerFeaturesEnabled:
        #     col.prop(context.scene.fast64.bk, "useDecompFeatures")
        # col.prop(context.scene.fast64.bk, "exportMotionOnly")



classes = (BK_FileSettingsPanel,)

def file_register():
    for cls in classes:
        register_class(cls)
    Scene.bkBlenderScale = FloatProperty(name="Blender to BK Scale", default=100, update=on_update_render_settings)
    Scene.bkDecompPath = StringProperty(name="Decomp Folder", subtype="FILE_PATH")

def file_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    del Scene.bkBlenderScale
    del Scene.bkDecompPath
