import bpy
from bpy.types import Panel, Mesh, Armature
from bpy.utils import register_class, unregister_class
from ...panels import BK_Panel
from ...utility import prop_split
from .operators import BK_ImportDL, BK_ExportDL
from .properties import (
    BK_Export_Settings,
    BK_Import_Settings,
)


class BK_DisplayListPanel(Panel):
    bl_label = "Display List Inspector"
    bl_idname = "OBJECT_PT_BK_DL_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "BK" and (
            context.object is not None and isinstance(context.object.data, Mesh)
        )

    def draw(self, context):
        box = self.layout.box().column()
        box.box().label(text="BK DL Inspector")
        obj = context.object

        # prop_split(box, obj, "bkDrawLayer", "Draw Layer")
        box.prop(obj, "ignore_render")
        box.prop(obj, "ignore_collision")
        if bpy.context.scene.f3d_type == "F3DEX/LX":
            box.prop(obj, "is_occlusion_planes")
            if obj.is_occlusion_planes and (not obj.ignore_render or not obj.ignore_collision):
                box.label(icon="INFO", text="Suggest Ignore Render & Ignore Collision.")

        if not (obj.parent is not None and isinstance(obj.parent.data, Armature)):
            actorScaleBox = box.box().column()
            # prop_split(actorScaleBox, obj, "bkActorScale", "Actor Scale")
            actorScaleBox.label(text="This applies to actor exports only.", icon="INFO")

        # Doesn't work since all static meshes are pre-transformed
        # box.prop(obj.bkDynamicTransform, "billboard")


class BK_MaterialPanel(Panel):
    bl_label = "BK Material"
    bl_idname = "MATERIAL_PT_BK_Material_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.material is not None and context.scene.gameEditorMode == "BK"

    def draw(self, context):
        layout = self.layout
        mat = context.material
        col = layout.column()

        if (
            hasattr(context, "object")
            and context.object is not None
            and context.object.parent is not None
            and isinstance(context.object.parent.data, Armature)
        ):
            drawLayer = context.object.parent.bkDrawLayer
            if drawLayer != mat.f3d_mat.draw_layer.bk:
                col.label(text="Draw layer is being overriden by skeleton.", icon="OUTLINER_DATA_ARMATURE")
        else:
            drawLayer = mat.f3d_mat.draw_layer.bk

        dynMatProps: BK_DynamicMaterialProperty = mat.bkMaterial
        dynMatProps.draw_props(col.box().column(), mat, drawLayer)


class BK_DrawLayersPanel(Panel):
    bl_label = "BK Draw Layers"
    bl_idname = "WORLD_PT_BK_Draw_Layers_Panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "world"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "BK"

    def draw(self, context):
        world = context.scene.world
        if not world:
            return
        # bkDefaultRenderModeProp: BK_DefaultRenderModesProperty = world.bkDefaultRenderModes
        # bkDefaultRenderModeProp.draw_props(self.layout)


class BK_ImportExportPanel(BK_Panel):
    bl_idname = "BK_PT_importexport"
    bl_label = "BK Import / Export Panel"

    def draw(self, context):
        layout = self.layout
        col = layout.column()

        # import
        importSettings: BK_Import_Settings = context.scene.fast64.bk.DLImportSettings
        importSettings.draw_props(col)
        col.operator(BK_ImportDL.bl_idname)

        # export (starting a new col to get some space inbetween Import + Export)
        layout.split()
        layout.split()
        col = layout.column()

        exportSettings: BK_Export_Settings = context.scene.fast64.bk.DLExportSettings
        exportSettings.draw_props(col)
        col.operator(BK_ExportDL.bl_idname)



bk_dl_writer_panel_classes = (
    BK_DisplayListPanel,
    BK_MaterialPanel,
    BK_DrawLayersPanel,
    BK_ImportExportPanel,
)


def f3d_panels_register():
    for cls in bk_dl_writer_panel_classes:
        register_class(cls)


def f3d_panels_unregister():
    for cls in bk_dl_writer_panel_classes:
        unregister_class(cls)
