import bpy
import os

from bpy.types import UILayout
from bpy.utils import register_class, unregister_class

from ...panels import BK_Panel

from ..bk_constants import get_bk_EnumMapModelNames

from .operators import (
    BK_ImportScene,
    BK_ExportScene,
)
from .properties import (
    BK_ExportScene_Settings,
    BK_ImportScene_Settings,
)


class BK_ImportExportScenePanel(BK_Panel):
    bl_idname = "BK_PT_export_scene"
    bl_label = "BK Scene Importer / Exporter"

    # def drawSceneSearchOp(self, layout: UILayout, enumValue: str, opName: str):
    #     searchBox = layout.box().row()
    #     searchBox.operator(OOT_SearchSceneEnumOperator.bl_idname, icon="VIEWZOOM", text="").opName = opName
    #     searchBox.label(text=getEnumName(ootEnumSceneID, enumValue))

    def draw(self, context):
        # UI candy
        col = self.layout.column()
        exportBox = col.box().column()
        exportBox.label(text="Scene Importer / Exporter")

        # importer
        importSettings: BK_ImportScene_Settings = context.scene.fast64.bk.SceneImportSettings
        importSettings.draw_props(exportBox)
        # import op
        exportBox.operator(BK_ImportScene.bl_idname)

        # (starting a new col to get some space inbetween Import + Export)
        exportBox.split()
        exportBox.split()
        # exporter
        exportSettings: BK_ExportScene_Settings = context.scene.fast64.bk.SceneExportSettings
        exportSettings.draw_props(exportBox)
        exportBox.operator(BK_ExportScene.bl_idname)



classes = (
    BK_ImportExportScenePanel,
)

def scene_panels_register():
    for cls in classes:
        register_class(cls)
def scene_panels_unregister():
    for cls in classes:
        unregister_class(cls)
