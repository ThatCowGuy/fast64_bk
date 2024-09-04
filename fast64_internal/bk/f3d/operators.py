import bpy, os, mathutils
from timeit import default_timer as timer
from bpy.types import Operator, Mesh
from bpy.ops import object
from bpy.path import abspath
from bpy.utils import register_class, unregister_class
from mathutils import Matrix
from ...utility import CData, PluginError, raisePluginError, writeCData, toAlnum
from ...f3d.f3d_parser import importMeshC, getImportData, F3DtoBlenderObject
from ...f3d.f3d_gbi import DLFormat, F3D, TextureExportSettings, ScrollMethod, get_F3D_GBI
from ...f3d.f3d_writer import TriangleConverterInfo, removeDL, saveStaticModel, getInfoDict
# from ..oot_utility import ootGetObjectPath, getOOTScale
# from ..oot_model_classes import OOTF3DContext, ootGetIncludedAssetData
# from ..oot_texture_array import ootReadTextureArrays
# from ..oot_model_classes import OOTModel, OOTGfxFormatter
# from ..oot_f3d_writer import ootReadActorScale, writeTextureArraysNew, writeTextureArraysExisting
from .properties import BK_Import_Settings, BK_Export_Settings

from ..bk_utility import binjo_model_LU
from ..bk_utility import binjo_utils

from ..bk_utility.binjo_model_bin import ModelBIN
from ..bk_utility.binjo_model_bin_handler import ModelBIN_Handler

from ..bk_utility.binjo_dicts import Dicts

from ..bk_utility.binjo_model_bin_header import ModelBIN_Header 
from ..bk_utility.binjo_model_bin_vertex_seg import ModelBIN_VtxSeg, ModelBIN_VtxElem
from ..bk_utility.binjo_model_bin_collision_seg import ModelBIN_ColSeg, ModelBIN_TriElem
from ..bk_utility.binjo_model_bin_texture_seg import ModelBIN_TexSeg, ModelBIN_TexElem
from ..bk_utility.binjo_model_bin_displaylist_seg import ModelBIN_DLSeg, DisplayList_Command
from ..bk_utility.binjo_model_bin_geolayout_seg import ModelBIN_GeoSeg, ModelBIN_GeoCommandChain

# BK Map Model Class
map_model_handler = ModelBIN_Handler()

# init the bin-handler with data from ROM, grab a BIN from that ROM and convert it to a model
class BINJO_OT_populate_handler_from_ROM(bpy.types.Operator):
    """Import a model from a selected ROM"""        # Use this as a tooltip for menu items and buttons.
    bl_idname = "object.populate_handler_from_rom"  # Unique identifier for buttons and menu items to reference.
    bl_label = "Import from ROM"                    # Display name in the interface.
    bl_options = {'REGISTER', 'UNDO'}               # Enable undo for the operator.

    def execute(self, context):                 # execute() is called when running the operator.
        global map_model_handler
        scene = context.scene
        
        # get settings
        settings: BK_Import_Settings = context.scene.fast64.bk.DLImportSettings
        # dissect settings
        rom_path            = settings.rom_path
        model_filename_enum = settings.model_filename_enum

        # grab the rom-data, extract (and decompress) the compressed model-data
        model_file_path, model_data = binjo_utils.get_model_file(model_filename_enum, rom_path=rom_path, asset_dir=None)
        
        # populate the model_handler
        map_model_handler.load_model_file_from_BIN(model_file_path)
        if (map_model_handler.model_object is None):
            self.report({'ERROR'}, f"No Model-Object could be pulled from the ROM !")
            return {'CANCELLED'}
        
        bpy.ops.object.from_model_handler()
        return {'FINISHED'}

class BINJO_OT_create_model_from_model_handler(bpy.types.Operator):
    # this OP is hidden - used by the others
    bl_label = ""
    bl_idname = "object.from_model_handler"
    bl_options = {'REGISTER'}

    def execute(self, context):       
        global map_model_handler
        scene = context.scene

        # get settings
        settings: BK_Import_Settings = context.scene.fast64.bk.DLImportSettings
        # dissect settings
        rom_path            = settings.rom_path
        model_filename_enum = settings.model_filename_enum
        scale_factor        = settings.scale_factor

        import_timer_start = timer()

        print("Creating new Object...")
        # setting up a new mesh for the scene
        new_mesh_name = bpy.data.meshes.new("import_Mesh").name
        new_obj_name = bpy.data.objects.new("import_Object", bpy.data.meshes[new_mesh_name]).name

        # this line essentially just divides every coord by the scale factor through a nested list-comprehension
        vertices    = [[(coord / scale_factor) for coord in coordlist] for coordlist in map_model_handler.model_object.vertex_coord_list]
        edges       = []
        faces       = map_model_handler.model_object.face_idx_list
        bpy.data.meshes[new_mesh_name].from_pydata(vertices, edges, faces)

        # create over-arching layer/attribute elements
        new_UV_name = bpy.data.objects[new_obj_name].data.uv_layers.new(name="import_UV").name
        new_col_attr_name = bpy.data.meshes[new_mesh_name].attributes.new(
            name='import_Color',
            domain='CORNER',
            type='BYTE_COLOR'
        ).name

        # now create actual materials from the mat-names
        for binjo_mat in map_model_handler.model_object.mat_list:

            mat = bpy.data.materials.new(binjo_mat.name)
            set_mat_to_default(mat)
            # assign the parsed Tex after defaulting the mat
            tex_node = mat.node_tree.nodes["TEX"]
            tex_node.image = binjo_mat.Blender_IMG
            # if (tex_node.image is not None):
            #     if (os.path.isdir(context.scene.binjo_props.export_path) == False):
            #         self.report({'WARNING'}, f"Export Path is not set to a viable Directory - Not saving tmp Images...")
            #     elif (os.access(context.scene.binjo_props.export_path, (os.R_OK & os.W_OK)) == False):
            #         self.report({'WARNING'}, f"Incorrect Permissions for Export Path Directory !")
            #     else:
            #         tex_node.image.filepath_raw = f"{context.scene.binjo_props.export_path}/{tex_node.image.name}"
            #         tex_node.image.save()
            # also parse the collision properties and assign them correctly after defaulting
            mat["Collision_Disabled"] = bool("NOCOLL" in binjo_mat.name)
            mat["Visibility_Disabled"] = bool("INVIS" in binjo_mat.name)
            mat["Collision_Flags"] = ModelBIN_ColSeg.get_collision_flag_dict(
                initial_value=ModelBIN_ColSeg.get_colltype_from_mat_name(binjo_mat.name)
            )
            mat["Collision_SFX"] = ModelBIN_ColSeg.get_SFX_from_mat_name(binjo_mat.name)
            # TS params
            mat["T_clamp"]  = binjo_mat.T_clamp
            mat["T_mirror"] = binjo_mat.T_mirror
            mat["T_wrap"]   = binjo_mat.T_wrap
            mat["T_shift"]  = binjo_mat.T_shift
            mat["S_clamp"]  = binjo_mat.S_clamp
            mat["S_mirror"] = binjo_mat.S_mirror
            mat["S_wrap"]   = binjo_mat.S_wrap
            mat["S_shift"]  = binjo_mat.S_shift

            # and add it to the mat-list
            bpy.data.objects[new_obj_name].data.materials.append(mat)

        # since Im not creating new data, I can hold a ref to these now
        UV_layer = bpy.data.objects[new_obj_name].data.uv_layers[new_UV_name]
        col_attr = bpy.data.meshes[new_mesh_name].attributes[new_col_attr_name]

        loop_ids = []
        for (face, tri) in zip(bpy.data.meshes[new_mesh_name].polygons, map_model_handler.model_object.complete_tri_list):
            # set material index of the face according to the data within tri
            face.material_index = tri.mat_index
            # and set the UV coords of the face through the loop indices
            UV_layer.data[face.loop_indices[0]].uv = (tri.vtx_1.transformed_U, tri.vtx_1.transformed_V)
            UV_layer.data[face.loop_indices[1]].uv = (tri.vtx_2.transformed_U, tri.vtx_2.transformed_V)
            UV_layer.data[face.loop_indices[2]].uv = (tri.vtx_3.transformed_U, tri.vtx_3.transformed_V)
            
            # aswell as the RGBA shades
            if ("INVIS" in bpy.data.objects[new_obj_name].data.materials[face.material_index].name):
                # pure (invisible) collision tris will be drawn in magenta
                col_attr.data[face.loop_indices[0]].color = (1.0, 0, 1.0, 1.0)
                col_attr.data[face.loop_indices[1]].color = (1.0, 0, 1.0, 1.0)
                col_attr.data[face.loop_indices[2]].color = (1.0, 0, 1.0, 1.0)
            else:
                # others get their vertex RGBA values assigned (regardless of textured or not)
                col_attr.data[face.loop_indices[0]].color = (tri.vtx_1.r/255, tri.vtx_1.g/255, tri.vtx_1.b/255, tri.vtx_1.a/255)
                col_attr.data[face.loop_indices[1]].color = (tri.vtx_2.r/255, tri.vtx_2.g/255, tri.vtx_2.b/255, tri.vtx_2.a/255)
                col_attr.data[face.loop_indices[2]].color = (tri.vtx_3.r/255, tri.vtx_3.g/255, tri.vtx_3.b/255, tri.vtx_3.a/255)

        scene.collection.objects.link(bpy.data.objects[new_obj_name])

        # just some names to check if neccessary
        print([e.name for e in bpy.data.materials[0].node_tree.nodes["Principled BSDF"].inputs])
        print(f"({timer() - import_timer_start:.3f}s) -- Done.")

        return { 'FINISHED' }
def set_mat_to_default(mat):
    # first, retain (potential) old images, and remove old nodes
    # pulled from BBMat4.1
    old_image = None
    if (mat.use_nodes == True):
        for old_node in mat.node_tree.nodes:
            if old_node.type == "TEX_IMAGE":
                old_image = old_node.image
                break
        for old_node in mat.node_tree.nodes:
            # keep these 2 intact (also keeps BSDF settings that arent defaulted)
            if (old_node.name == "Principled BSDF" or old_node.name == "Material Output"):
                continue
            mat.node_tree.nodes.remove(old_node)
        
    # setting internal parameters within the mat
    mat.use_nodes = True
    mat.blend_method = "HASHED" # "HASHED" == Dithered Transparency
    mat.shadow_method = "NONE"
    mat.use_backface_culling = True
    # setting exposed parameters within the mat
    mat.node_tree.nodes["Principled BSDF"].inputs["Specular"].default_value = 0
            
    # texture node (NOTE that this will also assign "None" if the mat doesnt have an image)
    tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex_node.name = "TEX"
    tex_node.location = [-600, +300]
    # using the old_image (it may be None, but that's fine)
    tex_node.image = old_image
        
    # color node (RGB+A)
    color_node = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    color_node.name = "RGBA"
    new_x = (tex_node.location[0] + tex_node.width - color_node.width)
    color_node.location = (new_x, 0)
    color_node.layer_name = "import_Color" # this name is what's connecting the node to the attribute

    # mixer-node (texture * RGB)                  
    mix_node_1 = mat.node_tree.nodes.new("ShaderNodeMixRGB")
    mix_node_1.blend_type = "MULTIPLY"
    mix_node_1.location = (-250, +300)
    mix_node_1.inputs["Fac"].default_value = 1.0
    # mixer-node (texture * A)                  
    mix_node_2 = mat.node_tree.nodes.new("ShaderNodeMixRGB")
    mix_node_2.blend_type = "MULTIPLY"
    mix_node_2.location = (-250, +70)
    mix_node_2.inputs["Fac"].default_value = 1.0

    # link tex and color nodes to mixer
    mat.node_tree.links.new(tex_node.outputs["Color"], mix_node_1.inputs["Color1"])
    mat.node_tree.links.new(color_node.outputs["Color"], mix_node_1.inputs["Color2"])
    # link mixer to base-color input in main-material node
    mat.node_tree.links.new(mix_node_1.outputs["Color"], mat.node_tree.nodes[0].inputs["Base Color"])
    
    # link tex and color nodes to mixer
    mat.node_tree.links.new(tex_node.outputs["Alpha"], mix_node_2.inputs["Color1"])
    mat.node_tree.links.new(color_node.outputs["Alpha"], mix_node_2.inputs["Color2"])
    # link mixer to base-color input in main-material node
    mat.node_tree.links.new(mix_node_2.outputs["Color"], mat.node_tree.nodes[0].inputs["Alpha"])

    mat["Collision_Disabled"] = False
    mat["Visibility_Disabled"] = False
    mat["Collision_Flags"] = ModelBIN_ColSeg.get_collision_flag_dict(0x0000_0000)
    mat["Collision_Flags"]["Use Default SFXs"] = True
    mat["Collision_SFX"] = Dicts.COLLISION_SFX["Normal"]
    mat["BINjo_Version"] = 0
    # TS params
    mat["T_clamp"]  = False
    mat["T_mirror"] = False
    mat["T_wrap"]   = 0
    mat["T_shift"]  = 0
    mat["S_clamp"]  = False
    mat["S_mirror"] = False
    mat["S_wrap"]   = 0
    mat["S_shift"]  = 0


class BK_ImportDL(Operator):
    bl_idname = "object.bk_import_dl"
    bl_label = "Import DL"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        try:
            settings: BK_Import_Settings = context.scene.fast64.bk.DLImportSettings
            
            rom_path            = settings.rom_path
            model_filename_enum = settings.model_filename_enum

            # grab the rom-data, extract (and decompress) the compressed model-data
            model_file_path, model_data = binjo_utils.get_model_file(model_filename_enum, rom_path=rom_path, asset_dir=None)

            bpy.ops.object.populate_handler_from_rom()

            rom_file = open(model_file_path, "rb")

            binjo_model_bin_header = ModelBIN_Header(model_data)
            DL_offset = binjo_utils.read_bytes(model_data, 0x0C, 4, type="uint")

            # these are the segs that SM loads into segmentData[seg_ID] = (seg_start, seg_end)
            # loadSegmentAddresses = {0x03: 0x2ABCAC, 0x04: 0x2ABCA0, 0x13: 0x2ABCD0, 0x16: 0x2ABCC4, 0x17: 0x2ABCB8}
            # BK
            # 1 - vtx
            # 2 - tex
            # 3 - dl
            # segmentData = [0] * 0x20
            # segmentData[0x03] = 
            # [segment] = (segmentStart, segmentEnd)

            # return segmentData


            # readObj = F3DtoBlenderObject(
            #     rom_file, DL_offset, context.scene, "bk_mesh", Matrix.Identity(4), segmentData, True
            # )

            # applyRotation([readObj], radians(-90), "X")
            # F3DtoBlenderObject(model_file_path, )

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
    BINJO_OT_populate_handler_from_ROM,
    BINJO_OT_create_model_from_model_handler,
)


def f3d_ops_register():
    for cls in bk_dl_writer_classes:
        register_class(cls)


def f3d_ops_unregister():
    for cls in reversed(bk_dl_writer_classes):
        unregister_class(cls)
