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

class FBX:
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

                self.mesh_data[name] = self.get_mesh_data(node)
                self.mesh_nodes[name] = node

    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        os.chdir(path)

        (fbx_manager, scene) = FbxCommon.InitializeSdkObjects()
        
        self.handle_data(fbx_manager, scene, path)
        ios = fbx.FbxIOSettings.Create(fbx_manager, fbx.IOSROOT)
        fbx_manager.SetIOSettings(ios)
        fbx_manager.GetIOSettings().SetIntProp(fbx.EXP_FBX_COMPRESS_LEVEL, 9)
        FbxCommon.SaveScene(fbx_manager, scene, "output.fbx", False)

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

    def get_texture_uv_by_ge(self, mesh, uv_ge, poly_idx, vert_idx):
        cp_idx = mesh.GetPolygonVertex(poly_idx, vert_idx)
        uv_idx = mesh.GetTextureUVIndex(poly_idx, vert_idx)
        uv = (0.0, 0.0)

        if (uv_ge.GetMappingMode() == fbx.FbxLayerElement.eByControlPoint):
            if (uv_ge.GetReferenceMode() == fbx.FbxLayerElement.eDirect):
                uv = tuple(uv_ge.GetDirectArray().GetAt(cp_idx))
            elif (uv_ge.GetReferenceMode() == fbx.FbxLayerElement.eIndexToDirect):
                idx = uv_ge.GetIndexArray().GetAt(cp_idx)
                uv = tuple(uv_ge.GetDirectArray().GetAt(idx))
            else:
                raise Exception('Unhandled UV reference mode')
        elif (uv_ge.GetMappingMode() == fbx.FbxLayerElement.eByPolygonVertex):
            if (uv_ge.GetReferenceMode() in (fbx.FbxLayerElement.eDirect, \
                                            fbx.FbxLayerElement.eIndexToDirect)):
                uv = tuple(uv_ge.GetDirectArray().GetAt(uv_idx))
            else:
                raise Exception('Unhandled UV reference mode')
        else:
            raise Exception('Unhandled UV mapping mode')
        uv = (uv[0], 1.0 - uv[1])

        return uv

    def get_mesh_data(self, node):
        mesh = node.GetMesh()

        data = {
            'positions': [],
            'normals': [],
            'binormals': [],
            'uvs': [],
            'bone_weights': [],
            'bone_indices': [],
            'materials': []
        }

        data['positions'] = [{'data': []}]
        data['normals'].append({'data': []})

        new_vertex_indices = []
        for i in range(mesh.GetControlPointsCount()):
            new_vertex_indices.append([])

        # Using NviTriStripper to generate the strip indices then build the strip
        j = 0
        tri_indices = []
        for i in range(mesh.GetPolygonCount()):
            indices = [mesh.GetPolygonVertex(i, j) for j in range(3)]
            tri_indices.extend(indices)
        tri_indices_text = str(tri_indices).replace(" ", "").replace("[", "").replace("]", "")

        tri_input = open(f"{cm.temp_path}/triangles.txt", "w")
        tri_input.write(tri_indices_text)
        tri_input.flush()

        cmd.nvtri_stripper(f"{cm.temp_path}\\triangles.txt", f"{cm.temp_path}\\triangles_out.txt")
        tri_output = open(f"{cm.temp_path}\\triangles_out.txt", "r")
        strip_indices = eval(tri_output.readline().strip())

        for idx in strip_indices:
            data['positions'][0]['data'].append(mesh.GetControlPointAt(idx))
            new_vertex_indices[idx].append(j)
            j += 1

        for i in range(mesh.GetLayerCount()):
            layer = mesh.GetLayer(i)

            if layer.GetUVs() != None:
                data['uvs'].append({'resource_name': layer.GetUVs().GetName(), 'data': []})

            uv_ge = mesh.GetElementUV(i)
            normal_ge = mesh.GetElementNormal(i)

            if uv_ge:
                # Keeping one uv per vert
                verts_uvs = {}
                for j in range(mesh.GetPolygonCount()):
                    for k in range(3):
                        idx = mesh.GetPolygonVertex(j, k)
                        uv = self.get_texture_uv_by_ge(mesh, uv_ge, j, k)
                        if idx not in verts_uvs.keys():
                            verts_uvs[idx] = uv

                for idx in strip_indices:
                    data['uvs'][i]['data'].append(verts_uvs[idx])

            if normal_ge:
                # Keeping one normal per vert
                verts_normals = {}
                for j in range(mesh.GetPolygonCount()):
                    for k in range(3):
                        idx = mesh.GetPolygonVertex(j, k)
                        normal = normal_ge.GetDirectArray().GetAt(j * 3 + k)
                        if idx not in verts_normals.keys():
                            verts_normals[idx] = normal

                for idx in strip_indices:
                    data['normals'][i]['data'].append(verts_normals[idx])

        # Bone weights
        try:
            skin = mesh.GetDeformer(0)

            for i in range(skin.GetClusterCount()):
                cluster = skin.GetCluster(i)

                if cluster.GetControlPointIndicesCount() > 0:
                    bone_name = cluster.GetLink().GetName()
                    bone_idx = ut.search_index_dict(self.bone_names, bone_name)
                    vertex_indices = cluster.GetControlPointIndices()
                    weights = cluster.GetControlPointWeights()

                    data['bone_indices'].append({'data': []})
                    data['bone_weights'].append({'data': []})
                    for j in range(cluster.GetControlPointIndicesCount()):
                        # (olganix) we have duplicated vertices to make false triangles
                        # but we need to target the right vertex indices to link bones.
                        idx = vertex_indices[j]

                        for k in new_vertex_indices[idx]:
                            data['bone_indices'][-1]['data'].append({k: bone_idx})
                            data['bone_weights'][-1]['data'].append({k: weights[j]})
        except Exception as e:
            print(e)
            print(node.GetName())

        for i in range(node.GetMaterialCount()):
            material = node.GetMaterial(i)
            prop = material.FindProperty(fbx.FbxSurfaceMaterial.sDiffuse)
            layered_texture = prop.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxLayeredTexture.ClassId), 0)
            if layered_texture:
                texture_count = \
                    layered_texture.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId))
            for i in range(texture_count):
                texture = layered_texture.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId), i)
                data['materials'].append((texture.GetName(), texture.GetFileName()))

        data = {k: v for k, v in data.items() if v != []}

        return data

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

        # Removing duplicated vertices
        i = 0
        j = 0
        pos_dict = {}
        old_idx_list = []
        for vtx in data['positions'][0]['data']:
            if vtx not in pos_dict.values():
                pos_dict[i] = vtx
                old_idx_list.append(j)
                i += 1
            j += 1

        mesh.InitControlPoints(len(pos_dict))

        # Vertices
        vertex_indices = []
        try:
            for vtx in data['positions'][0]['data']:
                idx = ut.search_index_dict(pos_dict, vtx)
                v = fbx.FbxVector4(vtx[0], vtx[1], vtx[2], vtx[3])
                mesh.SetControlPointAt(v, idx)

            for i in range(0, len(data['positions'][0]['data']) - 2):
                vtx = data['positions'][0]['data'][i]
                vtx1 = data['positions'][0]['data'][i + 1]
                vtx2 = data['positions'][0]['data'][i + 2]

                idx = ut.search_index_dict(pos_dict, vtx)
                idx1 = ut.search_index_dict(pos_dict, vtx1)
                idx2 = ut.search_index_dict(pos_dict, vtx2)

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

        # Normals
        try:
            for i in range(len(data['normals'])):
                normal_le = fbx.FbxLayerElementNormal.Create(mesh, 'normals')
                normal_le.SetMappingMode(fbx.FbxLayerElement.eByPolygonVertex)
                normal_le.SetReferenceMode(fbx.FbxLayerElement.eIndexToDirect)

                layer = mesh.GetLayer(i)
                if (not layer):
                    mesh.CreateLayer()
                    layer = mesh.GetLayer(i)

                for j in range(len(data['normals'][i]['data'])):
                    normal_le.GetDirectArray().Add(fbx.FbxVector4(*data['normals'][i]['data'][j]))

                # Reindexing normals
                for idx in vertex_indices:
                    normal_le.GetIndexArray().Add(idx)

                layer.SetNormals(normal_le)
        except Exception as e:
            print(e)

        # Binormals
        try:
            for i in range(len(data['binormals'])):
                binormal_le = fbx.FbxLayerElementBinormal.Create(mesh, 'binormals')
                binormal_le.SetMappingMode(fbx.FbxLayerElement.eByPolygonVertex)
                binormal_le.SetReferenceMode(fbx.FbxLayerElement.eIndexToDirect)

                layer = mesh.GetLayer(i)
                if (not layer):
                    mesh.CreateLayer()
                    layer = mesh.GetLayer(i)

                for j in range(len(data['binormals'][i]['data'])):
                    binormal_le.GetDirectArray().Add(fbx.FbxVector4(*data['binormals'][i]['data'][j]))

                # Reindexing binormals
                for idx in vertex_indices:
                    binormal_le.GetIndexArray().Add(idx)

                layer.SetBinormals(binormal_le)
        except Exception as e:
            pass

        # UVs
        try:
            for i in range(len(data['uvs'])):
                uv_le = fbx.FbxLayerElementUV.Create(mesh, data['uvs'][i]['resource_name'])
                uv_le.SetMappingMode(fbx.FbxLayerElement.eByPolygonVertex)
                uv_le.SetReferenceMode(fbx.FbxLayerElement.eIndexToDirect)

                layer = mesh.GetLayer(i)
                if (not layer):
                    mesh.CreateLayer()
                    layer = mesh.GetLayer(i)

                for uvs in data['uvs'][i]['data']:
                    uv_le.GetDirectArray().Add(fbx.FbxVector2(uvs[0], -uvs[1] + 1))

                # Reindexing UVs
                for idx in vertex_indices:
                    uv_le.GetIndexArray().Add(idx)

                typeId = fbx.FbxLayerElement.eTextureDiffuse
                layer.SetUVs(uv_le, typeId)
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