import difflib
import fbx
import FbxCommon
import numpy as np
import math
import re
import os
import core.utils as ut
import core.common as cm
import core.commands as cmd
from .BMP import BMP
from .DDS import DDS
from .XML import XML
from sys import platform

class FBX:
    remove_duplicate_vertex = True
    remove_triangle_strip = True
    use_fbx_face_optimisation = False
    use_per_vertex = True
    version_from_vertices_list = True
    debug_mode = False

    colors_components = ['r', 'g', 'b', 'a']
    others_components = ['x', 'y', 'z', 'w']
    uvs_components = ['u', 'v']

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
        self.get_children(root_node, nodes, ['FbxNull', 'FbxSkeleton'])
        
        # BONES
        self.bone_nodes = {0: root_node.GetChild(0)}
        self.bone_names = {0: root_node.GetChild(0).GetName()}
        
        # Add orphan bones to parent
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
        for i in range(root_node.GetChildCount()):
            null_node = root_node.GetChild(i)
            if 'NULL' in null_node.GetName():
                break
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

        nodes = []
        for i in range(root_node.GetChildCount()):
            model_node = root_node.GetChild(i)
            if 'model' in model_node.GetName():
                break
        self.get_children(model_node, nodes, ['FbxNull', 'FbxMesh'])

        self.mesh_data = {}
        self.mesh_nodes = {}
        for node in nodes:
            if node.GetMesh():
                name = node.GetName()

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

                self.mesh_data[name] = self.get_mesh_data(node, path)
                self.mesh_nodes[name] = node

    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        os.chdir(path)

        (fbx_manager, scene) = FbxCommon.InitializeSdkObjects()
        
        self.handle_data(fbx_manager, scene, path)
        if not self.debug_mode:
            fbx_manager.GetIOSettings().SetIntProp(fbx.EXP_FBX_COMPRESS_LEVEL, 9)
        FbxCommon.SaveScene(fbx_manager, scene, "output.fbx", 0)
        if self.debug_mode:
            FbxCommon.SaveScene(fbx_manager, scene, "output.fbx.txt", 1)

        fbx_manager.Destroy()
        del scene
        del fbx_manager

        os.chdir('..')

        return

    def handle_data(self, manager, scene, path):
        remaining = []
        for texture in self.data['texture']:
            name, ext = os.path.splitext(ut.b2s_name(texture.name))
            
            texture_data = texture.data
            vram_data = texture_data.get_unswizzled_vram_data()
            output_class = texture_data.get_output_format()
            if output_class == 'BMP':
                output_object = BMP(name, texture_data.width, texture_data.height, vram_data)
                output_object.save(path)
            elif output_class == 'DDS':
                output_object = DDS(name, texture_data.width, texture_data.height, vram_data, \
                    texture_data.get_texture_type(), texture_data.mipmap_count)
                output_object.save(path)
            remaining.append(output_object.get_name())

        # Assigning textures to materials
        # Using first eyeball texture until a proper fix for eyes is implemented
        eyeball_count = 1
        for material in self.data['material']:
            if not isinstance(material.data, bytes):
                material.data.sort()
                for layer in material.data.layers:
                    layer_base_name = layer[1].rsplit(b'.', 1)[0]
                    layer_base_name = layer_base_name.replace(b'.', b'')
                    if b'eyeball' in layer_base_name:
                        layer_base_name = re.split(b'\d+$', layer_base_name, 0)[0]
                        layer_base_name += ut.s2b_name(f".{eyeball_count}")
                    matches = difflib.get_close_matches(ut.b2s_name(layer_base_name), remaining, len(remaining), 0)
                    layer[1] = ut.s2b_name(matches[0])

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
            if (scene_entry.data.data_type == b'transform'):
                gt = node.EvaluateGlobalTransform()
                self.bind_pose.Add(node, fbx.FbxMatrix(gt))
        
        # Ignoring shape nodes
        for scene_entry in scene_dict.values():
            if (scene_entry.data.data_type == b'mesh'):
                mesh_name = ut.b2s_name(scene_entry.data.name)
                shape_name = ut.b2s_name(scene_entry.data.parent_name)
                transform_name = scene_dict[shape_name].data.parent_name
                scene_entry.data.parent_name = transform_name
                layered_mesh_names[mesh_name] = \
                    layered_names[ut.b2s_name(scene_entry.name)]
        
        for scene_entry in scene_dict.values():
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
                        parent_node = root_node.FindChild(parent_name)
                        parent_node.AddChild(node)
                    attr = fbx.FbxNull.Create(manager, '')
                    node.AddNodeAttribute(attr)
                    if (scene_entry.data.unknown0x00 == 3):
                        node.Show.Set(False)

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
            data.append(values)

        return data

    def get_mesh_data(self, node, path):
        mesh = node.GetMesh()

        # ------------------------------------------------ 
        # Merge all vertex informations to get just a list of vertex (more easy to deal with)
        # ------------------------------------------------ 
        #
        # TODO: do the version with data from PerPolygon (not only from perVertex)

        name = mesh.GetName()
        vertices = []
        nb_vertex = mesh.GetControlPointsCount()

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
        for i in range(nb_vertex):
            blend_by_vertex.append([])

        skin = mesh.GetDeformer(0)
        if skin:
            for i in range(skin.GetClusterCount()):
                cluster = skin.GetCluster(i)
                nbVertexForCluster = cluster.GetControlPointIndicesCount()
                if (nbVertexForCluster > 0) : 
                    bone_name = cluster.GetLink().GetName()
                    bone_idx = ut.search_index_dict(self.bone_names, bone_name)
                    vertex_indices = cluster.GetControlPointIndices()
                    weights = cluster.GetControlPointWeights()

                    for j in range(nbVertexForCluster):
                        blend_by_vertex[vertex_indices[j]].append({"indexBone": bone_idx, "weight": weights[j]})
                        nb_tmp = len(blend_by_vertex[vertex_indices[j]])
                        nb_bone_layer = nb_tmp if (nb_tmp > nb_bone_layer) else nb_bone_layer

        # TODO look values (in xeno convertion by v_copy.setColorFromRGBAFloat((float)color.mRed, (float)color.mGreen, (float)color.mBlue, (float)color.mAlpha))
        layers_dict = {
            'color': self.retrieve_layers_data(colors_layers, [0, 0, 0, 1.0]),
            'normal': self.retrieve_layers_data(normals_layers),
            'binormal': self.retrieve_layers_data(binormals_layers),
            'tangent': self.retrieve_layers_data(tangents_layers),
            'uv': self.retrieve_layers_data(uvs_layers)
        }

        components_map = {'uv': self.uvs_components, 'color': self.colors_components}

        param_names = ['color', 'normal', 'binormal', 'tangent', 'uv', 'blend_indices', 'blend_weights']
        for i in range(nb_vertex):
            vertices.append({})
            vertices[i] = dict(zip(param_names, [[] for x in range(len(param_names))]))

            # w = 1.0 because it's lost after FBX export
            vertices[i]['position'] = dict(zip(self.others_components, mesh.GetControlPointAt(i)))
            vertices[i]['position']['w'] = 1.0

            for param, layer in layers_dict.items():
                for layer_data in layer:
                    components = components_map[param] if (param in components_map) else self.others_components
                    if (param == 'uv'):
                        layer_data[i] = (layer_data[i][0], (1.0 - layer_data[i][1]))
                    vertices[i][param].append(dict(zip(components, layer_data[i])))

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
                blend = blends[j] if (j < nb_bone_layer) else {'indexBone': 0, 'weight': 0.0}
                vertices[i]['blend_indices'].append(blend['indexBone'])
                vertices[i]['blend_weights'].append(blend['weight'])

        faces_triangles = []
        for i in range(mesh.GetPolygonCount()):
            faces_triangles.append( [mesh.GetPolygonVertex(i, 0), mesh.GetPolygonVertex(i, 1), mesh.GetPolygonVertex(i, 2)])

        if self.debug_mode:
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

        new_faces_triangles = []
        for i in range(0, len(strip_indices), 3):
            new_faces_triangles.append(
                [strip_indices[i],
                 strip_indices[((i + 1) if (i + 1 < len(strip_indices)) else (len(strip_indices) - 1))],
                 strip_indices[((i + 2) if (i + 2 < len(strip_indices)) else (len(strip_indices) - 1))]]
            )

        faces_triangles = new_faces_triangles
        if self.debug_mode:
            self.create_mesh_debug_xml("11_MakingTriangleStrip", name.replace(":", "_"), vertices, faces_triangles)

        # -------------------------------------------------------------------------------------------------------------
        # Apply Triangle Strip  on Vertex (Game's logic  / bad logic : they don't have faceIndex, but duplicate Vertex)
        # -------------------------------------------------------------------------------------------------------------

        new_vertices = []
        for i in range(len(strip_indices)):
            new_vertices.append(vertices[strip_indices[i]])

        new_faces_triangles = []
        for i in range(len(new_vertices) - 2):
            # Triangle strips logic
            if (i % 2 == 0):
                new_faces_triangles.append([i, i + 1, i + 2])
            else:
                new_faces_triangles.append([i, i + 2, i + 1])
        
        vertices = new_vertices
        faces_triangles = new_faces_triangles
        if self.debug_mode:
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
            data.update({'positions': [{'data': []}], 'materials': []})

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
                prop = material.FindProperty(fbx.FbxSurfaceMaterial.sDiffuse)
                layered_texture = prop.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxLayeredTexture.ClassId), 0)
                if layered_texture:
                    texture_count = layered_texture.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId))
                for i in range(texture_count):
                    texture = layered_texture.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId), i)
                    filename = texture.GetFileName()
                    # If not on Windows, assuming textures are in FBX folder (wrong path given from FBX SDK)
                    if platform != 'win32':
                        filename = os.path.join(os.path.dirname(path), filename)
                    data['materials'].append((texture.GetName(), filename))

        data = {k: v for k, v in data.items() if v != []}

        return data

    def build_layers_data_per_vertex(self, mesh, vertex, layers, param, fbx_le, fbx_layers, callback):
        for j in range(len(vertex[param])):
            if (j >= len(fbx_layers)):
                if param in ['uv', 'binormal']:
                    param_name = layers[param][j]['resource_name']
                else:
                    param_name = param + "_"+ (("_" + str(j)) if (j != 0) else "")

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

    def build_layers_data_per_polygon(self, mesh, layers, param, fbx_le, vertex_indices, callback):
        for i in range(len(layers)):
            if param in ['uv', 'binormal']:
                param_name = layers[i]['resource_name']
            else:
                param_name = param + "_"+ (("_" + str(i)) if (i != 0) else "")
            fbx_layer = fbx_le.Create(mesh, param_name)
            fbx_layer.SetMappingMode(fbx.FbxLayerElement.eByPolygonVertex)
            fbx_layer.SetReferenceMode(fbx.FbxLayerElement.eIndexToDirect)

            layer = mesh.GetLayer(i)
            if (not layer):
                mesh.CreateLayer()
                layer = mesh.GetLayer(i)

            for j in range(len(layers[i]['data'])):
                if param == 'uv':
                    fbx_layer.GetDirectArray().Add(fbx.FbxVector2(layers[i]['data'][j][0], 1.0 - layers[i]['data'][j][1]))
                else:
                    fbx_layer.GetDirectArray().Add(fbx.FbxVector4(*layers[i]['data'][j]))

            # Reindexing verts
            for idx in vertex_indices:
                fbx_layer.GetIndexArray().Add(idx)

            eval(f"layer.{callback}")(fbx_layer)

    def add_mesh_node(self, manager, scene, content, mesh_parents, layered_mesh_names):
        data = content.data.get_data()
        root_node = scene.GetRootNode()

        name = ut.b2s_name(content.name)
        parent_node_name = name.rsplit('|')[0]

        if parent_node_name != name:   
            found = False
            for mesh_name, parent_list in mesh_parents.items():
                for parent_name in parent_list:
                    if parent_node_name in parent_name:
                        if layered_mesh_names[name] == mesh_name:
                            parent_node = root_node.FindChild(parent_name)
                            node = parent_node.FindChild(mesh_name)
                            found = True
                            break
                if found:
                    break
        else:
            node = root_node.FindChild(layered_mesh_names[name])

        mesh = fbx.FbxMesh.Create(manager, f"{name}_mesh")
        node.SetNodeAttribute(mesh)

        # ------------------------------------------------ 
        # Merge all vertex informations to get just a list of vertex (more easy to deal with)
        # ------------------------------------------------ 
        # TODO reduce the key's names (ex "position" -> "p") for reduce memory and speed up.

        components_map = {'uv': self.uvs_components, 'color': self.colors_components}

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
                        components = components_map[new_param] if (new_param in components_map) else self.others_components
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
        
        if self.debug_mode:
            self.create_mesh_debug_xml("00_SprOriginal", mesh.GetName().replace(":", "_"), vertices, faces_triangles)

        # ------------------------------------------------ 
        # removing duplicate unnecessary vertices 
        #    (because a good triangle strip is must be on face index, not vertex)
        # Notice: that will change nothing except having less vertices in Fbx
        # ------------------------------------------------ 

        if self.remove_duplicate_vertex:
            list_vertex_id_redirection = []
            new_vertices = []

            for i in range(len(vertices)):
                vertex = vertices[i]
                is_found = -1

                for j in range(len(new_vertices)):
                    vertex_tmp = new_vertices[j]

                    if (vertex['position'] != vertex_tmp['position']):
                        continue
                    
                    params_dict = {
                        'normal': 4,
                        'binormal': 4,
                        'uv': 2,
                        'blend_indices': 1,
                        'blend_weights': 1
                    }

                    is_diff = False
                    for param, nb in params_dict.items():
                        list_components = self.others_components if (param != 'uv') else self.uvs_components
                        is_direct_array = param in ['blend_indices', 'blend_weights']

                        if(len(vertex[param]) != len(vertex_tmp[param])):
                            is_diff = True
                            break
                        
                        for m in range(len(vertex[param])):
                            for n in range(nb):
                                if (((not is_direct_array) and 
                                        (vertex[param][m][list_components[n]] != vertex_tmp[param][m][list_components[n]])) or
                                     ((is_direct_array) and (vertex[param][m] != vertex_tmp[param][m]))):
                                    is_diff = True
                                    break
                            if is_diff: 
                                break
                        if is_diff: 
                            break

                    if not is_diff:
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

            vertices = new_vertices
            faces_triangles = new_faces_triangles

            # So now the triangle strip is only on face index, we got the same, but we reduce vertex number
            if self.debug_mode:
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
            if self.debug_mode:
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
            # Removing duplicated vertices
            i = 0
            pos_dict = {}
            old_idx_list = []
            link_new_index = []
            for j in range(len(data['positions'][0]['data'])):
                vtx = data['positions'][0]['data'][j]

                try:
                    idx = ut.search_index_dict(pos_dict, vtx)
                except KeyError:
                    idx = len(pos_dict)
                    pos_dict[idx] = vtx
                    old_idx_list.append(j)
                link_new_index.append(idx)

            mesh.InitControlPoints(len(pos_dict))

            # Vertices
            vertex_indices = []
            try:
                for idx in range(len(data['positions'][0]['data'])):
                    vtx = data['positions'][0]['data'][idx]
                    i = ut.search_index_dict(pos_dict, vtx)
                    v = fbx.FbxVector4(vtx[0], vtx[1], vtx[2], vtx[3])
                    mesh.SetControlPointAt(v, i)

                for i in range(0, len(data['positions'][0]['data']) - 2):
                    idx =  link_new_index[i]
                    idx1 = link_new_index[i + 1]
                    idx2 = link_new_index[i + 2]

                    mesh.BeginPolygon()
                    mesh.AddPolygon(idx)
                    if (i % 2 == 0):
                        mesh.AddPolygon(idx1)
                        mesh.AddPolygon(idx2)
                        vertex_indices.extend([i, i + 1, i + 2])
                    else:
                        mesh.AddPolygon(idx2)
                        mesh.AddPolygon(idx1)
                        vertex_indices.extend([i, i + 2, i + 1])
                    mesh.EndPolygon()
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
                    
                    i = 0
                    cluster_dict = {}
                    for idx in old_idx_list:
                        for j in range(0, len(data['bone_indices'])): 
                            bone_indices.append(data['bone_indices'][j]['data'][idx][0])
                            bone_weights.append(data['bone_weights'][j]['data'][idx][0])
                        
                        for k in range(0, len(bone_indices)):
                            bone_idx = bone_indices[k]
                            if bone_idx not in cluster_dict:
                                cluster_dict[bone_idx] = fbx.FbxCluster.Create(scene, "")
                                cluster_dict[bone_idx].SetLinkMode(fbx.FbxCluster.eTotalOne)
                                bone_node = self.bone_nodes[bone_idx]
                                cluster_dict[bone_idx].SetLink(bone_node)
                                cluster_dict[bone_idx].SetTransformMatrix(node_mat)
                                cluster_dict[bone_idx].SetTransformLinkMatrix(bone_mats[bone_idx])
                                skin.AddCluster(cluster_dict[bone_idx])
                            # Reindexing weights
                            cluster_dict[bone_idx].AddControlPointIndex(i, bone_weights[k])
                        
                        bone_indices = []
                        bone_weights = []
                        i += 1

                mesh.AddDeformer(skin)
                self.bind_pose.Add(node, fbx.FbxMatrix(node.EvaluateGlobalTransform()))
            except Exception as e:
                print(e)

            # Normals, Binormals, UVs
            try:
                self.build_layers_data_per_polygon(mesh, data['normals'], 'normal', 
                                                   fbx.FbxLayerElementNormal, vertex_indices, "SetNormals")
                if 'binormals' in data:
                    self.build_layers_data_per_polygon(mesh, data['binormals'], 'binormal', 
                                                       fbx.FbxLayerElementBinormal, vertex_indices, "SetBinormals")
                self.build_layers_data_per_polygon(mesh, data['uvs'], 'uv', 
                                                   fbx.FbxLayerElementUV, vertex_indices, "SetUVs")
            except Exception as e:
                print(e)

        # Materials
        material_name_parts = name.rsplit(':')
        if len(material_name_parts) > 2:
            material_name = ':'.join(material_name_parts[1:])
        else:
            material_name = material_name_parts[1]
        
        for material in self.data['material']:
            if ut.b2s_name(material.name) == material_name:
                material.data.sort()
                mat = self.add_material(scene, material_name)

                layered_texture = fbx.FbxLayeredTexture.Create(scene, "")
                mat.Diffuse.ConnectSrcObject(layered_texture)
                node.AddMaterial(mat)

                for i in range(0, len(material.data.layers)):
                    layer = material.data.layers[i]
                    texture = self.add_texture(scene, layer[0], layer[1])
                    layered_texture.ConnectSrcObject(texture)
                break
    
        node.SetShadingMode(fbx.FbxNode.eTextureShading)
        if self.use_fbx_face_optimisation:
            mesh.RemoveBadPolygons()

        return node

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

    def resize(self, array, new_size, new_value = 0):
        # https://stackoverflow.com/questions/30503792/resize-an-array-with-a-specific-value
        """Resize to biggest or lesser size."""
        # Quantity of new elements equals to quantity of first element
        element_size = len(array[0])
        if new_size > len(array):
            new_size = new_size - 1
            while len(array)<=new_size:
                n = tuple(new_value for i in range(element_size))
                array.append(n)
        else:
            array = array[:new_size]
        return array

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

        components_map = {'uv': self.uvs_components, 'color': self.colors_components}

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
                    components = components_map[param] if (param in components_map) else self.others_components
                    if param != 'blend_indices':
                        vertex_node['Vertex']['children'].append({param_name: {'attr': dict(zip(components, vertex[param][j].values()))}})
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