import difflib
import fbx
import FbxCommon
import numpy as np
import math
import re
import os
import copy
import core.utils as ut
import core.common as cm
import core.commands as cmd
from .BMP import BMP
from .DDS import DDS
from .XML import XML
from sys import platform
from colorama import Fore, Style

class FBX:
    remove_triangle_strip = True
    use_fbx_face_optimisation = False
    use_per_vertex = not cm.use_blender
    version_from_vertices_list = True

    colors_components = ['r', 'g', 'b', 'a']
    others_components = ['x', 'y', 'z', 'w']
    uvs_components = ['u', 'v']
    components_map = {'uv': uvs_components, 'color': colors_components}

    # To access FBXColor properties
    color_prop_map = {
        'r': 'mRed',
        'b': 'mBlue',
        'g': 'mGreen',
        'a': 'mAlpha'
    }

    params_map = {
        'positions': 'position',
        'colors': 'color',
        'normals': 'normal',
        'binormals': 'binormal',
        'tangents': 'tangent',
        'uvs': 'uv',
        'bone_indices': 'blend_indices',
        'bone_weights': 'blend_weights'
    }

    params_nb = {
        'normal': 4,
        'binormal': 4,
        'uv': 2,
        'blend_indices': 1,
        'blend_weights': 1
    }

    def __init__(self):
        self.data = {}

    def load(self, path):
        global fbx_manager
        fbx_manager = fbx.FbxManager.Create()
        scene = fbx.FbxScene.Create(fbx_manager, '')
        importer = fbx.FbxImporter.Create(fbx_manager, '')

        ios = fbx.FbxIOSettings.Create(fbx_manager, fbx.IOSROOT)
        fbx_manager.SetIOSettings(ios)
        importer.Initialize(path, -1, fbx_manager.GetIOSettings())
        importer.Import(scene)

        # RB axis system
        axis_system = scene.GetGlobalSettings().GetAxisSystem()
        new_axis_system = fbx.FbxAxisSystem(
            fbx.FbxAxisSystem.eYAxis, 
            fbx.FbxAxisSystem.eParityOdd, 
            fbx.FbxAxisSystem.eRightHanded
        )

        if (axis_system != new_axis_system):
            new_axis_system.ConvertScene(scene)

        axis_system = scene.GetGlobalSettings().GetAxisSystem()
        
        root_node = scene.GetRootNode()
        nodes = []
        self.get_children(root_node, nodes, ['FbxNull', 'FbxSkeleton', 'FbxMesh'])

        # Add orphan nodes to parent
        node_dict = {}
        for node in nodes:
            name = node.GetName()
            if name not in node_dict.keys():
                node_dict[name] = node
                parent_name = node.GetParent().GetName()
                if parent_name != 'RootNode':
                    if not node_dict[parent_name].FindChild(name):
                        node_dict[parent_name].AddChild(node)

        nodes = []
        null_node = None
        for i in range(root_node.GetChildCount()):
            null_node = root_node.GetChild(i)
            if 'NULL' in null_node.GetName():
                break
            else:
                null_node = None

        if null_node != None:
        # BONES
            self.bone_nodes = {0: null_node}
            self.bone_names = {0: null_node.GetName()}
            self.get_children(null_node, nodes, ['FbxNull', 'FbxSkeleton'])

            index = 0
            for node in nodes:
                if node.GetName() != self.bone_names[0]:
                    if node.GetName() not in self.bone_names.values():
                        index += 1
                        self.bone_nodes[index] = node
                        self.bone_names[index] = node.GetName()
                else:
                    self.bone_nodes[0] = node
                    self.bone_names[0] = node.GetName()
        else:
            print('No bone data found in FBX file. Check if NULL bone is present in the scene.')

        base_nodes = []
        for i in range(root_node.GetChildCount()):
            base_node = root_node.GetChild(i)
            if 'NULL' not in base_node.GetName():
                base_nodes.append(base_node)

        nodes = []
        for base_node in base_nodes:
            child_nodes = []
            self.get_children(base_node, nodes, ['FbxNull', 'FbxMesh'])
            nodes.extend(child_nodes)

        self.mesh_data = {}
        self.mesh_nodes = {}
        self.other_nodes = {}
        for node in nodes:
            name = node.GetName()
            if node.GetMesh():
                # Fix for chars with duplicated parts using "face_" in material
                material_name = name.rsplit(':')[-1]
                name_parts = name.rsplit(':')[0:-1]
                if 'face_' in material_name:
                    name_parts.append(material_name.replace('face_', ''))
                else:
                    name_parts.append(f"face_{material_name}")
                test_name = ':'.join(name_parts)
                for mesh_name in self.mesh_data.keys():
                    if test_name in mesh_name.rsplit('|')[-1]:
                        self.use_full_node_name(mesh_name)
                        break

                unlayered_name = self.remove_layer_from_name(name)
                for mesh_name in self.mesh_data.keys():
                    if unlayered_name in mesh_name:
                        self.use_full_node_name(mesh_name)
                        name = self.get_full_node_name(node)
                        break

                # Fix missing nodes (same name as existing nodes) when reading from blender export
                i = 1
                while (name in self.mesh_data):
                    name_parts = name.rsplit(':', 1)
                    name = f"{name_parts[0]}_{i}:{name_parts[-1]}"
                    i += 1

                self.mesh_data[name] = self.get_mesh_data(node, path)
                self.mesh_nodes[name] = node
            else:
                if node.GetChildCount() == 0:
                    self.other_nodes[name] = node

    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        os.chdir(path)

        (fbx_manager, scene) = FbxCommon.InitializeSdkObjects()
        
        self.handle_data(fbx_manager, scene)
        if not cm.use_debug_mode:
            fbx_manager.GetIOSettings().SetIntProp(fbx.EXP_FBX_COMPRESS_LEVEL, 9)
        FbxCommon.SaveScene(fbx_manager, scene, "output.fbx", 0)
        if cm.use_debug_mode:
            FbxCommon.SaveScene(fbx_manager, scene, "output.fbx.txt", 1)

        fbx_manager.Destroy()
        del scene
        del fbx_manager

        os.chdir('..')

        return

    def handle_data(self, manager, scene):
        root_node = scene.GetRootNode()
        parent_node = root_node

        self.bind_pose = fbx.FbxPose.Create(scene, "Default")
        self.bind_pose.SetIsBindPose(True)
        if len(self.data['bone']) > 0:
            bone_entries = self.data['bone'][0].data.bone_entries
            self.bone_nodes = []

            for bone in bone_entries:
                node = fbx.FbxNode.Create(parent_node, bone.name)
                self.bone_nodes.append(node)
                attr = fbx.FbxNull.Create(manager, '')
                node.AddNodeAttribute(attr)

                skeleton_attribute = fbx.FbxSkeleton.Create(parent_node, bone.name)

                if bone.parent != None:
                    parent_node = root_node.FindChild(ut.b2s_name(bone.parent.name))
                    skeleton_attribute.SetSkeletonType(fbx.FbxSkeleton.eLimbNode)
                else:
                    skeleton_attribute.SetSkeletonType(fbx.FbxSkeleton.eRoot)
                node.SetNodeAttribute(skeleton_attribute)

                if bone.parent != None:
                    mat = np.linalg.inv(bone.parent.abs_transform) @ bone.abs_transform
                else:
                    mat = bone.abs_transform
                
                trans, rot, scale = self.mat44_to_TRS(mat)

                node.LclTranslation.Set(fbx.FbxDouble3(*tuple(trans)[:3]))
                node.LclRotation.Set(fbx.FbxDouble3(*tuple(rot)[:3]))
                node.LclScaling.Set(fbx.FbxDouble3(*tuple(scale)[:3]))
                parent_node.AddChild(node)

                gt = node.EvaluateGlobalTransform()
                self.bind_pose.Add(node, fbx.FbxMatrix(gt))

        scene_entries = self.data['scene'][0].search_entries([], '[NODES]')[0]
        scene_dict = {}
        layered_names = {}
        layered_mesh_names = {}
        mesh_parents = {}
        self.scene_materials = {}

        entries_to_keep = []
        for scene_entry in scene_entries.children:
            name = ut.b2s_name(scene_entry.name)
            scene_dict[name] = scene_entry
            node_name = name.rsplit('|', 1)[1]
            if (scene_entry.data.layer_name != b''):
                layer_name = ut.b2s_name(scene_entry.data.layer_name)
                layered_names[name] = f"[{layer_name}]{node_name}"
            else:
                layered_names[name] = node_name
            name = layered_names[name]
            if (scene_entry.data.data_type != b'shape'):
                node = fbx.FbxNode.Create(manager, name)
                root_node.AddChild(node)
            # Handle special cases: shape nodes that have a shape node as parent
            else:
                parent_name = scene_entry.data.parent_name
                for entry in scene_entries.children:
                    if (entry.name == parent_name):
                        if (entry.data.data_type == b'shape'):
                            name = ut.b2s_name(entry.name)
                            node_name_parts = name.split('|')
                            node_name = node_name_parts[-1]
                            node = root_node.FindChild(node_name)
                            layered_names[name] = node_name
                            if (node == None):
                                node = fbx.FbxNode.Create(manager, node_name)
                                attr = fbx.FbxNull.Create(manager, '')
                                node.AddNodeAttribute(attr)
                                root_node.AddChild(node)
                            entries_to_keep.append(entry)
                        break
            if (scene_entry.data.data_type == b'transform'):
                gt = node.EvaluateGlobalTransform()
                self.bind_pose.Add(node, fbx.FbxMatrix(gt))
        
        # Ignoring shape nodes except if they are direct parents
        for scene_entry in scene_dict.values():
            if (scene_entry.data.data_type == b'mesh'):
                mesh_name = ut.b2s_name(scene_entry.data.name)
                shape_name = ut.b2s_name(scene_entry.data.parent_name)
                transform_name = scene_dict[shape_name].data.parent_name
                scene_entry.data.parent_name = transform_name
                layered_mesh_names[mesh_name] = \
                    layered_names[ut.b2s_name(scene_entry.name)]
        
        for scene_key, scene_entry in scene_dict.items():
            name = ut.b2s_name(scene_entry.name)
            if scene_entry.data.data_type != b'shape':
                if name in layered_names.keys():
                    name = layered_names[name]
                    node = root_node.FindChild(name)
                    if scene_entry.data.parent_name != b'':
                        parent_name = layered_names[ut.b2s_name(scene_entry.data.parent_name)]
                        if scene_entry.data.data_type == b'mesh':
                            if name in mesh_parents.keys():
                                mesh_parents[name].append(parent_name)
                            else:
                                mesh_parents[name] = [parent_name]

                            # Retrieve all material names per mesh
                            mesh_name = scene_entry.data.name
                            if mesh_name not in self.scene_materials:
                                self.scene_materials[mesh_name] = []
                            for child in scene_entry.children:
                                if hasattr(child.data, 'type') and (child.data.type == 'SCNE_MATERIAL'):
                                    self.scene_materials[mesh_name].append(child.data.name)
                        parent_node = root_node.FindChild(parent_name)
                        parent_node.AddChild(node)
                    attr = fbx.FbxNull.Create(manager, '')
                    node.AddNodeAttribute(attr)
                    if (scene_entry.data.unknown0x00 == 3):
                        node.Show.Set(False)
            # Handle special cases: shape nodes that have a shape node as parent
            elif scene_entry in entries_to_keep:
                name_parts = scene_key.split('|')
                node = root_node.FindChild(name_parts[-1])
                name_parts.remove('')
                name_parts.reverse()
                # Build parent hierarchy if it doesn't exist
                for parent_name in name_parts[1:]:
                    parent_node = root_node.FindChild(parent_name)
                    if (parent_node == None):
                        parent_node = fbx.FbxNode.Create(manager, parent_name)
                        attr = fbx.FbxNull.Create(manager, '')
                        parent_node.AddNodeAttribute(attr)
                        root_node.AddChild(parent_node)
                    if (parent_node.FindChild(node.GetName()) == None):
                        parent_node.AddChild(node)
                    node = parent_node

        # Build materials
        self.build_materials(scene)

        nodes = []
        for i in range(root_node.GetChildCount()):
            model_node = root_node.GetChild(i)
            if 'model' in model_node.GetName():
                break

        nodes_to_remove = ['model', 'body', 'head', 'face']
        for mesh_name, parent_list in mesh_parents.items():
            node_array = []
            node = model_node.FindChild(mesh_name)
            self.add_node_recursively(node_array, node)
            node_name_array = \
                [x.GetName() for x in node_array if x.GetName() not in nodes_to_remove]
            if mesh_name in node_name_array:
                node_name_array.remove(mesh_name)

            for node_name in node_name_array:
                if node_name not in parent_list:
                    mesh_parents[mesh_name].append(node_name)

        # Build nodes
        for model in self.data['model']:
            self.add_mesh_node(manager, scene, model, mesh_parents, layered_mesh_names)

        self.get_children(model_node, nodes, ['FbxNull', 'FbxMesh'])

        # Setting hidden nodes
        for node in nodes:
            if not node.GetParent().Show.Get():
                node.Show.Set(False)

    def get_children(self, node, node_list, class_names = []):
        if node.GetNodeAttribute():
            node_list.append(node)
        if (node.GetChildCount() > 0):
            for i in range(node.GetChildCount()):
                child = node.GetChild(i)
                if child.GetNodeAttribute():
                    if class_names == []:
                        self.get_children(child, node_list, class_names)
                    elif child.GetNodeAttribute().GetClassId().GetName() in class_names:
                        self.get_children(child, node_list, class_names)

    def add_node_recursively(self, node_array, node):
        if node:
            self.add_node_recursively(node_array, node.GetParent())
            found = False
            for elt in node_array:
                if elt.GetName() == node.GetName():
                    found = True
            if not found and (node.GetName() != 'RootNode'):
                # If node is not in the list, add it
                node_array += [node]

    def retrieve_layers_data(self, layers, default_val = [0, 0, 0, 0]):
        """Take care about eIndexToDirect or eDirect"""
        data = []
        for layer in layers:
            values = []

            if (layer.GetReferenceMode() == fbx.FbxLayerElement.eIndexToDirect):
                list_index = layer.GetIndexArray()
                list_values = layer.GetDirectArray()

                for j in range(list_index.GetCount()):
                    index = list_index.GetAt(j)
                    if (index < list_values.GetCount()):
                        values.append(list_values.GetAt(index))
                    else:
                        values.append(default_val)
            else:
                for val in layer.GetDirectArray():
                    values.append(val)
            data.append({'list': values, 'mapping': layer.GetMappingMode()})

        return data

    def get_mesh_data(self, node, path):
        mesh = node.GetMesh()
        name = mesh.GetName()

        # ------------------------------------------------ 
        # Merge all vertex informations to get just a list of vertex (more easy to deal with)
        # ------------------------------------------------ 

        # TODO check when this is False
        use_per_polygone_values = True

        nb_layers = mesh.GetLayerCount()
        colors_layers = []
        normals_layers = []
        binormals_layers = []
        tangents_layers = []
        uvs_layers = []

        for i in range(nb_layers):
            layer = mesh.GetLayer(i)

            color = layer.GetVertexColors()
            if color != None:
                colors_layers.append(color)

            normal = layer.GetNormals()
            if normal != None:
                normals_layers.append(normal)

            binormal = layer.GetBinormals()
            if binormal != None:
                binormals_layers.append(binormal)
            
            tangent = layer.GetTangents()
            if tangent != None:
                tangents_layers.append(tangent)

            uv = layer.GetUVs()
            if uv != None:
                uvs_layers.append(uv)
        
        nb_bone_layer = 0
        blend_by_vertex = []
        for i in range(mesh.GetControlPointsCount()):
            blend_by_vertex.append([])

        skin = mesh.GetDeformer(0)
        if skin:
            for i in range(skin.GetClusterCount()):
                cluster = skin.GetCluster(i)
                nb_vertex_for_cluster = cluster.GetControlPointIndicesCount()
                if (nb_vertex_for_cluster > 0) : 
                    bone_name = cluster.GetLink().GetName()
                    bone_idx = ut.search_index_dict(self.bone_names, bone_name)
                    vertex_indices = cluster.GetControlPointIndices()
                    weights = cluster.GetControlPointWeights()

                    for j in range(nb_vertex_for_cluster):
                        blend_by_vertex[vertex_indices[j]].append({'indexBone': bone_idx, 'weight': weights[j]})
                        nb_tmp = len(blend_by_vertex[vertex_indices[j]])
                        nb_bone_layer = nb_tmp if (nb_tmp > nb_bone_layer) else nb_bone_layer

            if (nb_bone_layer > 4):
                print(f"{Fore.YELLOW}\nWarning: Too many bones rigged at same vertex for mesh '{name}'.\n"
                      f"At least one vertex is mapped to {nb_bone_layer} bone(s).\n"
                      f"Only 4 bone layers will be kept (max for raging blast games).\n{Style.RESET_ALL}")

        # Fix bone layers amount to avoid in-game crashes
        if (nb_bone_layer > 4):
            nb_bone_layer = 4

        # TODO look values (in xeno convertion by v_copy.setColorFromRGBAFloat((float)color.mRed, (float)color.mGreen, (float)color.mBlue, (float)color.mAlpha))
        layers_dict = {
            'color': self.retrieve_layers_data(colors_layers, [0, 0, 0, 1.0]),
            'normal': self.retrieve_layers_data(normals_layers),
            'binormal': self.retrieve_layers_data(binormals_layers),
            'tangent': self.retrieve_layers_data(tangents_layers),
            'uv': self.retrieve_layers_data(uvs_layers)
        }

        param_names = ['color', 'normal', 'binormal', 'tangent', 'uv', 'blend_indices', 'blend_weights']

        vertices = []
        for i in range(mesh.GetControlPointsCount()):
            vertices.append({})
            vertices[i] = dict(zip(param_names, [[] for x in range(len(param_names))]))

            # w = 1.0 because it's lost after FBX export
            vertices[i]['position'] = dict(zip(self.others_components, mesh.GetControlPointAt(i)))
            vertices[i]['position']['w'] = 1.0

            # (Olganix) here we only do the eByControlPoint (or fill default value), eByPolygon will be done after.
            for param, layer in layers_dict.items():
                components = self.components_map[param] if (param in self.components_map) else self.others_components
                for layer_data in layer:
                    if not use_per_polygone_values:
                        if (param == 'uv'):
                            layer_data['list'][i] = (layer_data['list'][i][0], (1.0 - layer_data['list'][i][1]))
                        vertices[i][param].append(dict(zip(components, layer_data['list'][i])))
                    else:
                        vertices[i][param].append(dict(zip(components, [0 for x in range(len(components))])))

            blends = blend_by_vertex[i]
            # Apparently we have to order by weight (bigger first), and for the same weight, order by index
            # Cheating by order by index first
            blends.sort(key=lambda x: x.get('indexBone'))
            # Order rewritten by weight (but index's order will be correct for same weight)
            blends.sort(key=lambda x: x.get('weight'), reverse=True)

            vertices[i]['blend_indices'] = []
            vertices[i]['blend_weights'] = []

            # Fill if not defined to always have nb_bone_layer values
            for j in range(nb_bone_layer):
                blend = blends[j] if ((j < nb_bone_layer) and (j < len(blends))) \
                                else {'indexBone': 0, 'weight': 0.0}
                vertices[i]['blend_indices'].append(blend['indexBone'])
                vertices[i]['blend_weights'].append(blend['weight'])

        faces_triangles = []
        new_vertices_per_poly = []
        for i in range(mesh.GetPolygonCount()):
            face = [mesh.GetPolygonVertex(i, 0), mesh.GetPolygonVertex(i, 1), mesh.GetPolygonVertex(i, 2)]
            if use_per_polygone_values:
                face = self.build_per_polygon_vertices(vertices, layers_dict, new_vertices_per_poly, face, i)
            faces_triangles.append(face)

        if use_per_polygone_values:
            vertices = new_vertices_per_poly

        if cm.use_debug_mode:
            self.create_mesh_debug_xml("10_ImportedFromFbx", name.replace(":", "_"), vertices, faces_triangles)

        # TODO maybe add a part to optimize the vertex and face before making triangle strip (depend of optimisation of 3dsmax / blender)

        # ------------------------------------------------ 
        # Transform Triangle list -> Triangle Strip 
        # ------------------------------------------------

        # Using NviTriStripper to generate the strip indices then build the strip
        flat_tri = sum(faces_triangles, [])
        tri_indices_text = str(flat_tri).replace(" ", "").replace("[", "").replace("]", "")

        tri_in_path = os.path.join(cm.temp_path, "triangles.txt")
        tri_input = open(os.path.join(cm.temp_path, "triangles.txt"), 'w')
        tri_input.write(tri_indices_text)
        tri_input.flush()

        tri_out_path = os.path.join(cm.temp_path, "triangles_out.txt")
        cmd.nvtri_stripper(tri_in_path, tri_out_path)
        tri_output = open(tri_out_path, "r")
        strip_indices = eval(tri_output.readline().strip())

        if cm.use_debug_mode:
            new_faces_triangles = []
            for i in range(0, len(strip_indices), 3):
                new_faces_triangles.append(
                    [strip_indices[i],
                     strip_indices[((i + 1) if (i + 1 < len(strip_indices)) else (len(strip_indices) - 1))],
                     strip_indices[((i + 2) if (i + 2 < len(strip_indices)) else (len(strip_indices) - 1))]]
                )
            faces_triangles = new_faces_triangles
            self.create_mesh_debug_xml("11_MakingTriangleStrip", name.replace(":", "_"), vertices, faces_triangles)

        # -------------------------------------------------------------------------------------------------------------
        # Apply Triangle Strip  on Vertex (Game's logic  / bad logic : they don't have faceIndex, but duplicate Vertex)
        # RB uses duplicate vertices while UT uses face indices
        # -------------------------------------------------------------------------------------------------------------

        if cm.selected_game in ['dbrb', 'dbrb2']:
            new_vertices = []
            for i in range(len(strip_indices)):
                new_vertices.append(vertices[strip_indices[i]])
            vertices = new_vertices

            if cm.use_debug_mode:
                new_faces_triangles = []
                for i in range(len(vertices) - 2):
                    # Triangle strips logic
                    if (i % 2 == 0):
                        new_faces_triangles.append([i, i + 1, i + 2])
                    else:
                        new_faces_triangles.append([i, i + 2, i + 1])

                faces_triangles = new_faces_triangles
                self.create_mesh_debug_xml("12_TriangleStripOnVertex", name.replace(":", "_"), vertices, faces_triangles)

        # ------------------------------------------------ 
        # Fill internal data for building spr
        # ------------------------------------------------ 

        if self.version_from_vertices_list:

            # TODO case no Vertex

            param_names = ['normals', 'binormals', 'uvs', 'bone_weights', 'bone_indices']
            data = dict(zip(param_names, [[] for x in range(len(param_names))]))
            for param in data.keys():
                new_param = self.params_map[param]
                for i in range(len(vertices[0][new_param])):
                    data[param].append({'data': []})
                    if param == 'uvs':
                        data[param][-1]['resource_name'] = uvs_layers[i].GetName()
            data.update({'positions': [{'data': []}], 'materials': {}})

            for i in range(len(vertices)):
                vertex = vertices[i]

                data['positions'][0]['data'].append(list(vertex['position'].values()))
                for j in range(len(vertices[0]['normal'])):
                    data['normals'][j]['data'].append(list(vertex['normal'][j].values()))
                for j in range(len(vertices[0]['binormal'])):
                    data['binormals'][j]['data'].append(list(vertex['binormal'][j].values()))
                for j in range(len(vertices[0]['uv'])):
                    data['uvs'][j]['data'].append(list(vertex['uv'][j].values()))
                for j in range(len(vertices[0]['blend_indices'])):
                    data['bone_indices'][j]['data'].append(vertex['blend_indices'][j])
                    data['bone_weights'][j]['data'].append(vertex['blend_weights'][j])

            for i in range(node.GetMaterialCount()):
                material = node.GetMaterial(i)
                material_name = material.GetName()
                prop = material.FindProperty(fbx.FbxSurfaceMaterial.sDiffuse)

                if material_name not in data['materials']:
                    # Reading textures from materials directly if layered textures aren't found
                    source_obj = prop.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxLayeredTexture.ClassId), 0)
                    if source_obj:
                        texture_count = source_obj.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId))
                    else:
                        texture_count = prop.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId))
                        source_obj = prop

                    for i in range(texture_count):
                        texture = source_obj.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId), i)
                        filename = texture.GetFileName()
                        # GetFileName sometimes returns the filename or a path
                        # Assuming textures are in FBX folder if filename only is provided
                        if not os.path.exists(os.path.dirname(filename)):
                            filename = os.path.join(os.path.dirname(path), filename)

                        if isinstance(source_obj, fbx.FbxLayeredTexture):
                            layer = texture.GetName()
                        elif cm.use_blender:
                            name_parts = material.GetName().rsplit(':', 1)
                            material_name = name_parts[0]
                            layer = name_parts[-1].split('.')[0]
                        else:
                            layer = material.GetName()

                        if (material_name not in data['materials']):
                            data['materials'][material_name] = []
                        data['materials'][material_name].append((layer, filename))

        if cm.selected_game in ['dbut', 'dbzb']:
            data['face_indices'] = strip_indices
        data = {k: v for k, v in data.items() if v != []}

        return data

    def remove_duplicate_vertices(self, vertices, faces_triangles):
        list_vertex_id_redirection = []
        new_vertices = []

        for i in range(len(vertices)):
            vertex = vertices[i]
            is_found = -1

            for j in range(len(new_vertices)):
                if (vertex == new_vertices[j]):
                    is_found = j
                    break

            list_vertex_id_redirection.append(is_found if (is_found != -1) else len(new_vertices))
            if is_found == -1:
                new_vertices.append(vertex)

        # Now we have just to change index for faces to get the same.
        new_faces_triangles = []
        for i in range(len(faces_triangles)):
            new_triangle = []
            for j in range(3): 
                new_triangle.append(list_vertex_id_redirection[faces_triangles[i][j]])
            new_faces_triangles.append(new_triangle)

        return new_vertices, new_faces_triangles

    def build_per_polygon_vertices(self, vertices, layers_dict, new_vertices_per_poly, face, poly_idx):
        for k in range(3):
            # Clone vertex
            new_vertex = copy.deepcopy(vertices[face[k]])

            for param, layer in layers_dict.items():
                components = self.components_map[param] \
                    if (param in self.components_map) else self.others_components
                for j in range(len(layer)):
                    if (param == 'uv'):
                        uv = layer[j]['list'][poly_idx * 3 + k]
                        new_vertex[param][j] = dict(zip(components, [uv[0], (1.0 - uv[1])]))
                    elif (param == 'color'):
                        # use color prop map to retrieve r,g,b,a from FBXColor
                        color = layer[j]['list'][poly_idx * 3 + k]
                        new_color = []
                        for c in components:
                            prop = self.color_prop_map[c]
                            new_color.append(eval(f"color.{prop}"))
                        new_vertex[param][j] = dict(zip(components, new_color))
                    else:
                        new_vertex[param][j] = dict(zip(components, layer[j]['list'][poly_idx * 3 + k]))

            if (new_vertex not in new_vertices_per_poly):
                new_index = len(new_vertices_per_poly)
                new_vertices_per_poly.append(new_vertex)
            else:
                new_index = new_vertices_per_poly.index(new_vertex)
            face[k] = new_index

        return face

    def build_layers_data_per_vertex(self, mesh, vertex, layers, param, fbx_le, fbx_layers, callback):
        for j in range(len(vertex[param])):
            if (j >= len(fbx_layers)):
                if param in ['uv', 'binormal']:
                    param_name = layers[param][j]['resource_name']
                else:
                    param_name = param + (("_" + str(j)) if (j != 0) else "")

                fbx_layer = fbx_le.Create(mesh, param_name)
                fbx_layer.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                fbx_layer.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                fbx_layers.append(fbx_layer)

                layer = mesh.GetLayer(j)
                if (not layer):
                    mesh.CreateLayer()
                    layer = mesh.GetLayer(j)
                eval(f"layer.{callback}")(fbx_layer)

            fbx_layer = fbx_layers[j]
            if (param == 'uv'):
                fbx_layer.GetDirectArray().Add(fbx.FbxVector2(vertex[param][j]['u'], 1.0 - vertex[param][j]['v']))
            else:
                fbx_layer.GetDirectArray().Add(fbx.FbxVector4(*vertex[param][j].values()))

    def build_layers_data_per_polygon(self, mesh, vertices, layers, param, fbx_le, vertex_indices, callback):
        for j in range(len(layers)):
            if param in ['uv', 'binormal']:
                param_name = layers[j]['resource_name']
            else:
                param_name = param + (("_" + str(j)) if (j != 0) else "")

            fbx_layer = fbx_le.Create(mesh, param_name)
            fbx_layer.SetMappingMode(fbx.FbxLayerElement.eByPolygonVertex)
            fbx_layer.SetReferenceMode(fbx.FbxLayerElement.eIndexToDirect)

            layer = mesh.GetLayer(j)
            if (not layer):
                mesh.CreateLayer()
                layer = mesh.GetLayer(j)

            for i in range(len(vertices)):
                if (param == 'uv'):
                    fbx_layer.GetDirectArray().Add(
                        fbx.FbxVector2(vertices[i][param][j]['u'], 1.0 - vertices[i][param][j]['v'])
                    )
                else:
                    fbx_layer.GetDirectArray().Add(fbx.FbxVector4(*vertices[i][param][j].values()))

            # Reindexing verts
            for idx in vertex_indices:
                fbx_layer.GetIndexArray().Add(idx)

            eval(f"layer.{callback}")(fbx_layer)

    def add_mesh_node(self, manager, scene, content, mesh_parents, layered_mesh_names):
        data = content.data.get_data()
        root_node = scene.GetRootNode()

        name = ut.b2s_name(content.name)
        node = root_node.FindChild(layered_mesh_names[name])
        mesh = fbx.FbxMesh.Create(manager, f"{name}")
        node.SetNodeAttribute(mesh)

        # ------------------------------------------------ 
        # Merge all vertex informations to get just a list of vertex (more easy to deal with)
        # ------------------------------------------------ 
        # TODO reduce the key's names (ex "position" -> "p") for reduce memory and speed up.

        # Use face indices to obtain all vertices for UT
        if (cm.selected_game in ['dbut', 'dbzb']):
            for param, layers in data.items():
                for layer_data in layers:
                    if 'data' in layer_data:
                        new_data = []
                        for idx in content.data.face_indices:
                            if idx < len(layer_data['data']):
                                new_data.append(layer_data['data'][idx])
                        layer_data['data'] = new_data

        vertices = []
        param_names = ['color', 'normal', 'binormal', 'tangent', 'uv', 'blend_indices', 'blend_weights']
        layers = dict(zip(param_names, [[] for x in range(len(param_names))]))

        for i in range(len(data['positions'][0]['data'])):
            vertices.append({})
            vertices[i] = dict(zip(param_names, [[] for x in range(len(param_names))]))
            vertices[i]['position'] = dict(zip(self.others_components, data['positions'][0]['data'][i]))
            for param, layer in data.items():
                if param not in ['positions', 'bone_indices', 'bone_weights']:
                    new_param = self.params_map[param]
                    for j in range(len(layer)):
                        components = self.components_map[new_param] \
                            if (new_param in self.components_map) else self.others_components
                        vertices[i][new_param].append(dict(zip(components, data[param][j]['data'][i])))
                        if (j >= len(layers[new_param])):
                            layers[new_param].append({k: v for k, v in data[param][j].items() if k != 'data'})

            if 'bone_weights' in data:
                for j in range(len(data['bone_weights'])):
                    vertices[i]['blend_indices'].append(data['bone_indices'][j]['data'][i][0])
                    if (j >= len(layers['uv'])):
                        layers['blend_indices'].append({k: v for k, v in data['bone_indices'][j].items() if k != 'data'})
                    vertices[i]['blend_weights'].append(data['bone_weights'][j]['data'][i][0])
                    if (j >= len(layers['blend_weights'])):
                        layers['blend_weights'].append({k: v for k, v in data['bone_weights'][j].items() if k != 'data'})

        # Faces from Triangle Strips algorithm
        faces_triangles = []
        for i in range(len(vertices) - 2):
            # Triangle strips logic
            if (i % 2 == 0):
                faces_triangles.append([i, i + 1, i + 2])
            else:
                faces_triangles.append([i, i + 2, i + 1])
        
        if cm.use_debug_mode:
            self.create_mesh_debug_xml("00_SprOriginal", mesh.GetName().replace(":", "_"), vertices, faces_triangles)

        # ------------------------------------------------ 
        # removing duplicate unnecessary vertices 
        #    (because a good triangle strip is must be on face index, not vertex)
        # Notice: that will change nothing except having less vertices in Fbx
        # ------------------------------------------------ 

        vertices, faces_triangles = self.remove_duplicate_vertices(vertices, faces_triangles)

        # So now the triangle strip is only on face index, we got the same, but we reduce vertex number
        if cm.use_debug_mode:
            self.create_mesh_debug_xml("01_VertexReduced", mesh.GetName().replace(":", "_"), vertices, faces_triangles)

        # ------------------------------------------------
        # Remove Triangle degenerate strip 
        # ------------------------------------------------
        # notice : after delete duplicate vertex, the Fbx's function 
        #    mesh.RemoveBadPolygons() detect the bad Triangle, 
        #    so this step is not really necessary, just to have the debug on it

        if self.remove_triangle_strip:
            new_faces_triangles = []
            for i in range(len(faces_triangles)):
                triangle = faces_triangles[i][0:3]

                # In triangle strip algo, a degenerative strip (for cut the list) is done with 2 same vertex index in triangle.
                if ((triangle[0] != triangle[1]) and (triangle[0] != triangle[2]) and (triangle[1] != triangle[2])):
                    # So keep only triangles with 3 differents index.
                    new_faces_triangles.append(triangle)

            faces_triangles = new_faces_triangles
            if cm.use_debug_mode:
                self.create_mesh_debug_xml("02_RemoveStripDegen", mesh.GetName().replace(":", "_"), vertices, faces_triangles)

        # ------------------------------------------------
        # Fbx Construction
        # ------------------------------------------------
        # Test trying to do per Vertex buffers, instead of per Face which complexify for nothing the FBX

        if (self.use_per_vertex):
            scene = mesh.GetScene()

            # Vertices
            mesh.InitControlPoints(len(vertices))

            # Fbx layers data
            fbx_normals = []
            fbx_binormals = []
            fbx_uvs = []

            # One cluster per bone used
            skin = None
            fbx_bone_cluster = []
            nb_bones = 0
            if hasattr(self, 'bone_nodes'):
                nb_bones = len(self.bone_nodes)
                for i in range(nb_bones):
                    fbx_bone_cluster.append(None)

            for i in range(len(vertices)):
                vertex = vertices[i]

                # Position
                v = fbx.FbxVector4(*vertex['position'].values())
                mesh.SetControlPointAt(v, i)

                # TODO vertexColor
                # TODO Tangent

                # Normals, Binormals, UVs
                self.build_layers_data_per_vertex(mesh, vertex, layers, "normal", 
                                                  fbx.FbxLayerElementNormal, fbx_normals, "SetNormals")
                self.build_layers_data_per_vertex(mesh, vertex, layers, "binormal", 
                                                  fbx.FbxLayerElementBinormal, fbx_binormals, "SetBinormals")
                self.build_layers_data_per_vertex(mesh, vertex, layers, "uv", 
                                                  fbx.FbxLayerElementUV, fbx_uvs, "SetUVs")

                # Bone Blend
                if (nb_bones):
                    for j in range(len(vertex["blend_indices"])):
                        index_bone = vertex["blend_indices"][j]
                        weight = vertex["blend_weights"][j]

                        # TODO Warning

                        if (index_bone >= nb_bones):
                            index_bone = 0

                        if (fbx_bone_cluster[index_bone] == None):
                            cluster = fbx.FbxCluster.Create(scene, "bone_" + str(index_bone) + "_cluster")
                            cluster.SetLinkMode(fbx.FbxCluster.eTotalOne)
                            bone_node = self.bone_nodes[index_bone]
                            cluster.SetLink(bone_node)
                            # Node support the mesh
                            cluster.SetTransformMatrix(node.EvaluateGlobalTransform())
                            cluster.SetTransformLinkMatrix(bone_node.EvaluateGlobalTransform())

                            if (skin == None):
                                skin = fbx.FbxSkin.Create(scene, "skin_"+ name)
                                mesh.AddDeformer(skin)
                            skin.AddCluster(cluster)
                            fbx_bone_cluster[index_bone] = cluster

                        cluster = fbx_bone_cluster[index_bone]
                        cluster.AddControlPointIndex(i, weight)

            # Faces
            for i in range(len(faces_triangles)):
                mesh.BeginPolygon()
                for j in range(3):
                    mesh.AddPolygon(faces_triangles[i][j])
                mesh.EndPolygon()

        else:
            # Vertices
            vertex_indices = []
            try:
                for i in range(len(vertices)):
                    v = fbx.FbxVector4(*vertices[i]['position'].values())
                    mesh.SetControlPointAt(v, i)

                # Faces
                for i in range(len(faces_triangles)):
                    mesh.BeginPolygon()
                    for j in range(3):
                        mesh.AddPolygon(faces_triangles[i][j])
                    mesh.EndPolygon()
                vertex_indices = sum(faces_triangles, [])
            except Exception as e:
                print(e)

            # Bone weights
            try:
                scene = mesh.GetScene()
                skin = fbx.FbxSkin.Create(scene, "")
                node_mat = node.EvaluateGlobalTransform()
                bone_indices = []
                bone_weights = []
                bone_mats = []
                
                if hasattr(self, 'bone_nodes'):
                    for bone in self.bone_nodes:
                        bone_mats.append(bone.EvaluateGlobalTransform())

                    cluster_dict = {}
                    for i in range(len(vertices)):
                        for j in range(len(vertices[i]['blend_indices'])):
                            bone_idx = vertices[i]['blend_indices'][j]
                            if bone_idx not in cluster_dict:
                                cluster_dict[bone_idx] = fbx.FbxCluster.Create(scene, "")
                                cluster_dict[bone_idx].SetLinkMode(fbx.FbxCluster.eTotalOne)
                                bone_node = self.bone_nodes[bone_idx]
                                cluster_dict[bone_idx].SetLink(bone_node)
                                cluster_dict[bone_idx].SetTransformMatrix(node_mat)
                                cluster_dict[bone_idx].SetTransformLinkMatrix(bone_mats[bone_idx])
                                skin.AddCluster(cluster_dict[bone_idx])
                            # Reindexing weights
                            cluster_dict[bone_idx].AddControlPointIndex(i, vertices[i]['blend_weights'][j])

                mesh.AddDeformer(skin)
                self.bind_pose.Add(node, fbx.FbxMatrix(node.EvaluateGlobalTransform()))
            except Exception as e:
                print(e)

            # Normals, Binormals, UVs
            try:
                self.build_layers_data_per_polygon(mesh, vertices, data['normals'], 'normal', 
                                                   fbx.FbxLayerElementNormal, vertex_indices, "SetNormals")
                if 'binormals' in data:
                    self.build_layers_data_per_polygon(mesh, vertices, data['binormals'], 'binormal', 
                                                       fbx.FbxLayerElementBinormal, vertex_indices, "SetBinormals")
                self.build_layers_data_per_polygon(mesh, vertices, data['uvs'], 'uv', 
                                                   fbx.FbxLayerElementUV, vertex_indices, "SetUVs")
            except Exception as e:
                print(e)

        # Assign materials
        for material_name in self.scene_materials[content.name]:
            for material in self.materials[material_name]:
                node.AddMaterial(material)
    
        node.SetShadingMode(fbx.FbxNode.eTextureShading)
        if self.use_fbx_face_optimisation:
            mesh.RemoveBadPolygons()

        return node

    def build_materials(self, scene):
        self.materials = {}

        for material in self.data['material']:
            if material.name not in self.materials:
                self.materials[material.name] = []
            material.data.sort(cm.use_blender)

            if cm.use_blender:
                for i in range(0, len(material.data.layers)):
                    layer = material.data.layers[i]

                    mat = self.add_material(scene, f"{ut.b2s_name(material.name)}:{ut.b2s_name(layer[0])}")
                    texture = self.add_texture(scene, layer[0], layer[1])
                    mat.Diffuse.ConnectSrcObject(texture)
                    self.materials[material.name].append(mat)
            else:
                mat = self.add_material(scene, ut.b2s_name(material.name))
                layered_texture = fbx.FbxLayeredTexture.Create(scene, "")
                mat.Diffuse.ConnectSrcObject(layered_texture)

                for i in range(0, len(material.data.layers)):
                    layer = material.data.layers[i]
                    texture = self.add_texture(scene, layer[0], layer[1])
                    layered_texture.ConnectSrcObject(texture)
                self.materials[material.name].append(mat)

    def add_material(self, scene, material_name):
        black = fbx.FbxDouble3(0.0, 0.0, 0.0)
        white = fbx.FbxDouble3(1.0, 1.0, 1.0)
        material = fbx.FbxSurfacePhong.Create(scene, material_name)
        # Generate primary and secondary colors.
        material.Emissive.Set(black)
        material.Ambient.Set(white)
        material.AmbientFactor.Set(1.)
        # Add texture for diffuse channel
        material.Diffuse.Set(white)
        material.DiffuseFactor.Set(1.)
        material.TransparencyFactor.Set(0.5)
        material.ShadingModel.Set("Phong")
        material.Shininess.Set(0.5)
        material.Specular.Set(black)
        material.SpecularFactor.Set(1.0)
        material.MultiLayer.Set(True)

        return material
    
    def add_texture(self, scene, textureName, textureFileName):
        texture = fbx.FbxFileTexture.Create(scene, textureFileName)
        texture.SetFileName(textureFileName)
        texture.SetName(textureName)
        
        texture.SetTextureUse( fbx.FbxTexture.eStandard )
        texture.SetMappingType(fbx.FbxTexture.eUV)
        texture.SetMaterialUse( fbx.FbxFileTexture.eModelMaterial )
        texture.SetSwapUV( False )
        texture.SetTranslation( 0.0, 0.0 )
        texture.SetScale( 1.0, 1.0 )
        texture.SetRotation( 0.0, 0.0 )
        texture.Alpha.Set( True )

        return texture

    # Credits to Bigchillghost
    def mat44_to_TRS(self, mat):
        trans = (mat[0][3], mat[1][3], mat[2][3])
        rot = np.delete(mat, 3, 0)
        rot = np.delete(rot, 3, 1)
        rot, scale = self.mat33_to_RS(rot)

        return trans, rot, scale
    
    def mat33_to_RS(self, mat):
        scale = (math.sqrt(mat[0][0]**2 + mat[0][1]**2 + mat[0][2]**2),
                 math.sqrt(mat[1][0]**2 + mat[1][1]**2 + mat[1][2]**2),
                 math.sqrt(mat[2][0]**2 + mat[2][1]**2 + mat[2][2]**2))
        
        rot = np.copy(mat)
        for i in range(3):
            for j in range(3):
                rot[i][j] /= float(scale[i])
        
        r = [math.atan2(rot[2][1], rot[2][2])]
        r.append(math.atan2(-rot[2][0], (rot[2][1] * math.sin(r[0])) + 
                (rot[2][2] * math.cos(r[0]))))
        r.append(math.atan2(rot[1][0], rot[0][0]))
        r = [x * (180 / math.pi) for x in r]
        
        return tuple(r), scale

    def use_full_node_name(self, node_name):
        data = self.mesh_data[node_name]
        node = self.mesh_nodes[node_name]
        new_name = self.get_full_node_name(node)

        del self.mesh_data[node_name]
        del self.mesh_nodes[node_name]

        self.mesh_data[new_name] = data
        self.mesh_nodes[new_name] = node

    def get_full_node_name(self, node, nodes_to_remove = ['model', 'body', 'head']):
        node_array = []
        self.add_node_recursively(node_array, node)

        name_parts = []
        for elt in node_array:
            name = self.remove_layer_from_name(elt.GetName())
            if name not in nodes_to_remove:
                name_parts.append(name)

        shape_name = name_parts[-1].rsplit(':')[0]
        name_parts.insert(len(name_parts) - 1, shape_name)

        return '|'.join(name_parts)
    
    def remove_layer_from_name(self, name):
        layer_name = re.findall(r'^\[(.*?)\]', name)
        if layer_name != []:
            layer_name = layer_name[0]
            return name.replace(f"[{layer_name}]", '')
        return name

    def create_mesh_debug_xml(self, folder_name = "debug_mesh", name = "", vertices = [], faces_triangles = []):
        # Hyp : all vertices have the same nb_layers for each normals, uv, etc .. (bone blend indices and weight are fill by 0, 0.0 to complete)

        count_dict = {
            'color': len(vertices[0]['color']) if (len(vertices) and vertices[0]['color']) else 0,
            'normal': len(vertices[0]['normal']) if (len(vertices) and vertices[0]['normal']) else 0,
            'binormal': len(vertices[0]['binormal']) if (len(vertices) and vertices[0]['binormal']) else 0,
            'tangent': len(vertices[0]['tangent']) if (len(vertices) and vertices[0]['tangent']) else 0,
            'uv': len(vertices[0]['uv']) if (len(vertices) and vertices[0]['uv']) else 0,
            'blend_indices': len(vertices[0]['blend_indices']) if (len(vertices) and vertices[0]['blend_indices']) else 0
        }

        root_node = {'Mesh': {'attr': {'name': name, 'nbVertex': len(vertices)},'children': []}}
        root_node['Mesh']['attr'].update(
            dict(zip(['nbColorLy', 'nbNormalLy', 'nbBinormalLy', 'nbTangentLy', 'nbUvLy', 'nbBoneLayer'], count_dict.values()))
        )

        vertices_node = {'Vertices': {'children': []}}
        root_node['Mesh']['children'].append(vertices_node)

        for i in range(len(vertices)):
            vertex = vertices[i]

            vertex_node = {'Vertex': {'attr': {'index': i}, 'children': []}}
            vertices_node['Vertices']['children'].append(vertex_node)

            position_node = {'Position': {'attr': dict(zip(self.others_components, vertex['position'].values()))}}
            vertex_node['Vertex']['children'].append(position_node)

            for param, size in count_dict.items():
                for j in range(size):
                    param_name = param + (("_" + str(j)) if (j != 0) else "")
                    components = self.components_map[param] if (param in self.components_map) else self.others_components
                    if param != 'blend_indices':
                        vertex_node['Vertex']['children'].append(
                            {param_name: {'attr': dict(zip(components, vertex[param][j].values()))}}
                        )
                if param == 'blend_indices':
                    blend_node = {'Blend': {'attr': {'indices': vertex[param], 'weights': vertex['blend_weights']}}}
                    vertex_node['Vertex']['children'].append(blend_node)

        # Faces
        faces_node = {'Faces': {'attr': {'nbFaces': len(faces_triangles)}, 'children': []}}
        for i in range(len(faces_triangles)):
            triangle = faces_triangles[i]
            faces_node['Faces']['children'].append({'Triangle': {'attr': dict(zip(['a','b','c'], triangle))}})
        root_node['Mesh']['children'].append(faces_node)

        last_working_dir = os.getcwd()
        if not os.path.exists(folder_name):
            os.mkdir(folder_name)
        os.chdir(folder_name)

        xml_obj = XML()
        stream = open(name + ".xml", "w")
        xml_obj.write(stream, root_node)

        os.chdir(last_working_dir)