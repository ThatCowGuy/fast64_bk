import bpy, os, mathutils
from bpy.types import Operator, Mesh
from bpy.ops import object
from bpy.path import abspath
from bpy.utils import register_class, unregister_class

from timeit import default_timer as timer
from mathutils import Matrix

from ...utility import PluginError, raisePluginError

from .properties import BK_ImportScene_Settings, BK_ExportScene_Settings

from ..bk_model_classes import BKF3DContext
from ...f3d.f3d_material import (
    CreateFast3DMaterial,
    createF3DMat,
    # have to add "BK": "Unlit Texture" as defaultmat in f3d/f3d_material.py
    getDefaultMaterialPreset,
    update_all_node_values
)
from ...f3d.f3d_gbi import get_F3D_GBI

from ..bk_constants import bk_DictMapModelABIndexTable

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



# backup the real view-layer update func, overwrite it with a dummy,
# execute your func() and reinstate the real update func (from OOT module)
def run_ops_without_view_layer_update(func):
    from bpy.ops import _BPyOpsSubModOp
    view_layer_update = _BPyOpsSubModOp._view_layer_update

    def dummy_view_layer_update(context):
        pass

    try:
        _BPyOpsSubModOp._view_layer_update = dummy_view_layer_update
        func()
    finally:
        _BPyOpsSubModOp._view_layer_update = view_layer_update



# class OOT_SearchSceneEnumOperator(Operator):
#     bl_idname = "object.oot_search_scene_enum_operator"
#     bl_label = "Choose Scene"
#     bl_property = "ootSceneID"
#     bl_options = {"REGISTER", "UNDO"}

#     ootSceneID: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")
#     opName: StringProperty(default="Export")

#     def execute(self, context):
#         if self.opName == "Export":
#             context.scene.ootSceneExportSettings.option = self.ootSceneID
#         elif self.opName == "Import":
#             context.scene.ootSceneImportSettings.option = self.ootSceneID
#         elif self.opName == "Remove":
#             context.scene.ootSceneRemoveSettings.option = self.ootSceneID
#         else:
#             raise Exception(f'Invalid OOT scene search operator name: "{self.opName}"')

#         context.region.tag_redraw()
#         self.report({"INFO"}, "Selected: " + self.ootSceneID)
#         return {"FINISHED"}

#     def invoke(self, context, event):
#         context.window_manager.invoke_search_popup(self)
#         return {"RUNNING_MODAL"}


# class BINJO_OT_fast64(bpy.types.Operator):
#     # set scene default registers (see sDefaultDisplayList)
#     f3dContext = BKF3DContext(get_F3D_GBI(), [], "")
#     f3dContext.mat().prim_color = (0.5, 0.5, 0.5, 0.5)
#     f3dContext.mat().env_color = (0.5, 0.5, 0.5, 0.5)

#     bpy.context.space_data.overlay.show_relationship_lines = False
#     bpy.context.space_data.overlay.show_curve_normals = True
#     bpy.context.space_data.overlay.normals_length = 2




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
        settings: BK_ImportScene_Settings = context.scene.fast64.bk.SceneImportSettings
        # dissect settings
        rom_path            = settings.rom_path
        model_filename_enum = settings.model_filename_enum

        modelA_index = bk_DictMapModelABIndexTable[model_filename_enum][0]
        modelB_index = bk_DictMapModelABIndexTable[model_filename_enum][1]

        # first extract and prepare the modelA file; this should always exist
        # grab the rom-data, extract (and decompress) the compressed model-data
        model_file_path, model_data = binjo_utils.get_model_file(modelA_index, rom_path=rom_path, asset_dir=None)
        # populate the model_handler
        map_model_handler.load_model_file_from_BIN(model_file_path)
        if (map_model_handler.model_object is None):
            self.report({'ERROR'}, f"No Model-Object could be pulled from the ROM !")
            return {'CANCELLED'}
        # and create an object from the data
        bpy.ops.object.from_model_handler()

        # for the modelB file, we have to check if its an valid index
        if (modelB_index != 0xFF):
            model_file_path, model_data = binjo_utils.get_model_file(modelB_index, rom_path=rom_path, asset_dir=None)
            map_model_handler.load_model_file_from_BIN(model_file_path)
            if (map_model_handler.model_object is None):
                self.report({'ERROR'}, f"No Model-Object could be pulled from the ROM !")
                return {'CANCELLED'}
            bpy.ops.object.from_model_handler()

        return {'FINISHED'}

# use the data within a populated model-handler to create a blender object
class BINJO_OT_create_model_from_model_handler(bpy.types.Operator):
    # this OP is hidden - used by the others
    bl_label = ""
    bl_idname = "object.from_model_handler"
    bl_options = {'REGISTER'}

    def execute(self, context):       
        global map_model_handler
        scene = context.scene

        # get settings
        settings: BK_ImportScene_Settings = context.scene.fast64.bk.SceneImportSettings
        # dissect settings
        rom_path            = settings.rom_path
        model_filename_enum = settings.model_filename_enum
        scale_factor        = settings.scale_factor

        import_timer_start = timer()

        print("Creating new Object...")
        # setting up a new mesh for the scene
        new_mesh_name = bpy.data.meshes.new("import_Mesh").name
        new_obj_name = bpy.data.objects.new("import_Object", bpy.data.meshes[new_mesh_name]).name

        scene.collection.objects.link(bpy.data.objects[new_obj_name])
        bpy.context.view_layer.objects.active = bpy.data.objects[new_obj_name]

        # this line essentially just divides every coord by the scale factor through a nested list-comprehension
        vertices    = [[(coord / scale_factor) for coord in coordlist] for coordlist in map_model_handler.model_object.vertex_coord_list]
        edges       = []
        faces       = map_model_handler.model_object.face_idx_list
        bpy.data.meshes[new_mesh_name].from_pydata(vertices, edges, faces)

        # create over-arching layer/attribute elements
        new_UV_name = bpy.data.objects[new_obj_name].data.uv_layers.new(name="UVMap").name
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

            
            # bpy.ops.object.create_f3d_mat()
            # newest_f3d_mat = bpy.data.objects[new_obj_name].data.materials[-1]

            preset = getDefaultMaterialPreset("Shaded Texture")
            # see valid preset names in f3d/f3d_material_presets.py "material_presets" dict
            newest_f3d_mat = createF3DMat(bpy.data.objects[new_obj_name], "sm64_vertex_colored_texture_transparent")
            newest_f3d_mat.name = f"BK_F3DMat_{new_obj_name}"
            
            internal_mat = newest_f3d_mat.f3d_mat
            # change the combiner settings to use SHADE for alpha values instead of ENV
            internal_mat.combiner1.A = "TEXEL0"
            internal_mat.combiner1.B = "0"
            internal_mat.combiner1.C = "SHADE"
            internal_mat.combiner1.D = "0"
            internal_mat.combiner1.A_alpha = "TEXEL0"
            internal_mat.combiner1.B_alpha = "0"
            internal_mat.combiner1.C_alpha = "SHADE"
            internal_mat.combiner1.D_alpha = "0"
            # internal_mat.combiner2.name = ""
            # internal_mat.combiner2.A = "TEXEL0"
            # internal_mat.combiner2.B = "0"
            # internal_mat.combiner2.C = "SHADE"
            # internal_mat.combiner2.D = "0"
            # internal_mat.combiner2.A_alpha = "TEXEL0"
            # internal_mat.combiner2.B_alpha = "0"
            # internal_mat.combiner2.C_alpha = "SHADE"
            # internal_mat.combiner2.D_alpha = "0"
            
            # BK shadows are done through VTX shading exclusively (also this enables shading)
            internal_mat.rdp_settings.g_lighting = False

            internal_mat.rdp_settings.set_rendermode = True
            internal_mat.rdp_settings.rendermode_preset_cycle_1 = "G_RM_ZB_XLU_SURF"

            internal_mat.rdp_settings.g_cull_back = True
            
            linked_tex0 = internal_mat.tex0
            linked_tex0.tex = binjo_mat.Blender_IMG
            linked_tex0.tex_format = "RGBA32"
            linked_tex0.T.clamp  = binjo_mat.T_clamp
            linked_tex0.T.mirror = binjo_mat.T_mirror
            linked_tex0.T.mask   = binjo_mat.T_wrap
            linked_tex0.T.shift  = binjo_mat.T_shift
            linked_tex0.S.clamp  = binjo_mat.S_clamp
            linked_tex0.S.mirror = binjo_mat.S_mirror
            linked_tex0.S.mask   = binjo_mat.S_wrap
            linked_tex0.S.shift  = binjo_mat.S_shift

            # linked_tex0.tex.size = (binjo_mat.Blender_IMG.width, binjo_mat.Blender_IMG.height)
            # linked_tex0.tex.size = binjo_mat.Blender_IMG.size


            with bpy.context.temp_override(material=newest_f3d_mat):
                update_all_node_values(newest_f3d_mat, bpy.context)

                # bpy.data.objects[new_obj_name].data.materials.append(newest_f3d_mat)

            # and add it to the mat-list
            #bpy.data.objects[new_obj_name].data.materials.append(mat)

        # since Im not creating new data, I can hold a ref to these now
        UV_layer = bpy.data.objects[new_obj_name].data.uv_layers[new_UV_name]
        color_attr = bpy.data.meshes[new_mesh_name].attributes["Col"]
        alpha_attr = bpy.data.meshes[new_mesh_name].attributes["Alpha"]

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
                color_attr.data[face.loop_indices[0]].color = (1.0, 0, 1.0, 1.0)
                color_attr.data[face.loop_indices[1]].color = (1.0, 0, 1.0, 1.0)
                color_attr.data[face.loop_indices[2]].color = (1.0, 0, 1.0, 1.0)
                alpha_attr.data[face.loop_indices[0]].color = (1.0, 0, 1.0, 1.0)
                alpha_attr.data[face.loop_indices[1]].color = (1.0, 0, 1.0, 1.0)
                alpha_attr.data[face.loop_indices[2]].color = (1.0, 0, 1.0, 1.0)
            else:
                # others get their vertex RGBA values assigned (regardless of textured or not)
                color_attr.data[face.loop_indices[0]].color = (tri.vtx_1.r/255, tri.vtx_1.g/255, tri.vtx_1.b/255, tri.vtx_1.a/255)
                color_attr.data[face.loop_indices[1]].color = (tri.vtx_2.r/255, tri.vtx_2.g/255, tri.vtx_2.b/255, tri.vtx_2.a/255)
                color_attr.data[face.loop_indices[2]].color = (tri.vtx_3.r/255, tri.vtx_3.g/255, tri.vtx_3.b/255, tri.vtx_3.a/255)
                # Note that Fast64 uses grayscale as its alpha component...
                alpha_attr.data[face.loop_indices[0]].color = (tri.vtx_1.a/255, tri.vtx_1.a/255, tri.vtx_1.a/255, tri.vtx_1.a/255)
                alpha_attr.data[face.loop_indices[1]].color = (tri.vtx_2.a/255, tri.vtx_2.a/255, tri.vtx_2.a/255, tri.vtx_2.a/255)
                alpha_attr.data[face.loop_indices[2]].color = (tri.vtx_3.a/255, tri.vtx_3.a/255, tri.vtx_3.a/255, tri.vtx_3.a/255)

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


class BK_ImportScene(Operator):
    bl_idname = "object.bk_import_scene"
    bl_label = "Import Scene"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            object.mode_set(mode="OBJECT")

        try:
            # get settings
            settings: BK_ImportScene_Settings = context.scene.fast64.bk.SceneImportSettings
            # dissect settings
            rom_path            = settings.rom_path
            model_filename_enum = settings.model_filename_enum

            bpy.ops.object.populate_handler_from_rom()

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class BK_ExportScene(Operator):
    bl_idname = "object.bk_export_scene"
    bl_label = "Export Scene"
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


classes = (
    BK_ImportScene,
    BK_ExportScene,
    BINJO_OT_populate_handler_from_ROM,
    BINJO_OT_create_model_from_model_handler,
)

def scene_ops_register():
    for cls in classes:
        register_class(cls)
def scene_ops_unregister():
    for cls in reversed(classes):
        unregister_class(cls)

