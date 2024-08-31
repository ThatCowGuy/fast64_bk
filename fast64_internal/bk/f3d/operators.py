import bpy, os, mathutils
from bpy.types import Operator, Mesh
from bpy.ops import object
from bpy.path import abspath
from bpy.utils import register_class, unregister_class
from mathutils import Matrix
from ...utility import CData, PluginError, raisePluginError, writeCData, toAlnum
from ...f3d.f3d_parser import importMeshC, getImportData
from ...f3d.f3d_gbi import DLFormat, F3D, TextureExportSettings, ScrollMethod, get_F3D_GBI
from ...f3d.f3d_writer import TriangleConverterInfo, removeDL, saveStaticModel, getInfoDict
# from ..oot_utility import ootGetObjectPath, getOOTScale
# from ..oot_model_classes import OOTF3DContext, ootGetIncludedAssetData
# from ..oot_texture_array import ootReadTextureArrays
# from ..oot_model_classes import OOTModel, OOTGfxFormatter
# from ..oot_f3d_writer import ootReadActorScale, writeTextureArraysNew, writeTextureArraysExisting
from .properties import BK_DLImportSettings, BK_DLExportSettings

from ..bk_utility import binjo_model_LU
from ..bk_utility import binjo_utils
# from ..bk_utility import (
#     OOTObjectCategorizer,
#     ootDuplicateHierarchy,
#     ootCleanupScene,
#     ootGetPath,
#     addIncludeFiles,
#     getOOTScale,
# )



class BK_ImportDL(Operator):
    bl_idname = "object.bk_import_dl"
    bl_label = "Import DL"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        try:
            settings: BK_DLImportSettings = context.scene.fast64.bk.DLImportSettings
            
            rom_path            = settings.rom_path
            model_filename_enum = settings.model_filename_enum

            # grab the rom-data, extract (and decompress) the compressed model-data
            with open(rom_path, mode="rb") as rom_file:
                rom_data = rom_file.read()
            model_data = binjo_utils.extract_model(rom_data, model_filename_enum)
            
            print("hello", len(model_data))

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class BK_ExportDL(Operator):
    bl_idname = "object.bk_export_dl"
    bl_label = "Export DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")
        if len(context.selected_objects) == 0:
            raise PluginError("Mesh not selected.")
        obj = context.active_object
        if obj.type != "MESH":
            raise PluginError("Mesh not selected.")
        
        try:
            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


bk_dl_writer_classes = (
    BK_ImportDL,
    BK_ExportDL,
)


def f3d_ops_register():
    for cls in bk_dl_writer_classes:
        register_class(cls)


def f3d_ops_unregister():
    for cls in reversed(bk_dl_writer_classes):
        unregister_class(cls)
