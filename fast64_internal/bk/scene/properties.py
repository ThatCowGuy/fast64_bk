import bpy

from bpy.types import PropertyGroup, Object, World, Material, UILayout
from bpy.props import PointerProperty, StringProperty, BoolProperty, EnumProperty, IntProperty, FloatProperty
from bpy.utils import register_class, unregister_class

from ..bk_utility import binjo_model_LU
from .. import bk_constants 



class BK_ImportScene_Settings(PropertyGroup):
    rom_path: StringProperty(
        name="",
        description="Path to ROM",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    model_filename_enum : EnumProperty(
        name="Model File Name Enum",
        description="Internal Model Filename Enum",
        default="TTC - Treasure Trove Cove",
        items = bk_constants.get_bk_EnumMapModelNames()
    )
    scale_factor : bpy.props.IntProperty(
        name="",
        description="The Model is downscaled by this factor on Import, and upscaled on Export",
        default = 100,
        min = 1,
        max = 1000
    )

    def draw_props(self, layout: UILayout):
        # import from ROM
        row = layout.row()
        row.label(text="Source ROM :")
        row = layout.row()
        row.prop(self, "rom_path", text="")

        row = layout.row()
        row.label(text="Targetted Map :")
        row = layout.row()
        row.prop(self, "model_filename_enum", text="")

        row = layout.row()
        row.label(text="Scale Factor :")
        row.prop(self, "scale_factor")



class BK_ExportScene_Settings(PropertyGroup):
    export_path: StringProperty(
        name="",
        description="Path to Store Exports",
        default="",
        maxlen=1024,
        subtype='DIR_PATH'
    )
    force_model_A : BoolProperty(
        name="Force only Model-A",
        description="Force everything to export into a singular Model-BIN.",
        default = False
    )
    scale_factor : bpy.props.IntProperty(
        name="",
        description="The Model is downscaled by this factor on Import, and upscaled on Export",
        default = 100,
        min = 1,
        max = 1000
    )

    def draw_props(self, layout: UILayout):
        # export
        row = layout.row()
        row.label(text="Set Export Path :")
        row = layout.row()
        row.prop(self, "export_path", text="")
        row = layout.row()
        row.prop(self, "force_model_A")

        row = layout.row()
        row.label(text="Scale Factor :")
        row.prop(self, "scale_factor")



classes = (
    BK_ImportScene_Settings,
    BK_ExportScene_Settings,
)

def scene_props_register():
    for cls in classes:
        register_class(cls)
def scene_props_unregister():
    for cls in reversed(classes):
        unregister_class(cls)
        
