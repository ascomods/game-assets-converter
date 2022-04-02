import difflib
import fbx
import FbxCommon
import numpy as np
import math
import re
import os
import glob
import core.utils as ut
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
        null_node = root_node.FindChild('NULL')
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

                # Handling nodes with same name
                if name in self.mesh_data:
                    other_data = self.mesh_data[name]
                    other_node = self.mesh_nodes[name]
                    shape_name = name.rsplit(':')[0]
                    parent_name = other_node.GetParent().GetName()
                    del self.mesh_data[name]
                    del self.mesh_nodes[name]
                    other_name = f"{parent_name}|{shape_name}|{name}"
                    self.mesh_data[other_name] = other_data
                    self.mesh_nodes[other_name] = other_node

                    shape_name = name.rsplit(':')[0]
                    parent_name = node.GetParent().GetName()
                    name = f"{parent_name}|{shape_name}|{name}"
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
        bone_entries = self.data['bone'][0].data.bone_entries
        self.bone_nodes = []
        self.bind_pose = fbx.FbxPose.Create(scene, "Default")
        self.bind_pose.SetIsBindPose(True)

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

        # Build nodes
        for model in self.data['model']:
            self.add_mesh_node(manager, scene, model, mesh_parents, layered_mesh_names)

        nodes = []
        for i in range(root_node.GetChildCount()):
            model_node = root_node.GetChild(i)
            if 'model' in model_node.GetName():
                break
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

    def add_node_recursively(self, nodeArray, node):
        if node:
            self.add_node_recursively(nodeArray, node.GetParent())
            found = False
            for elt in nodeArray:
                if elt.GetName() == node.GetName():
                    found = True
            if not found and (node.GetName() != 'RootNode'):
                # If node is not in the list, add it
                nodeArray += [node]

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

        flip_last = False
        for i in range(mesh.GetPolygonCount()):
            idx = mesh.GetPolygonVertex(i, 0)
            data['positions'][0]['data'].append(tuple(mesh.GetControlPointAt(idx)))
            if i == (mesh.GetPolygonCount() - 1):
                if  (((len(data['positions'][0]['data']) + 2) % 4 == 0) or \
                    (((len(data['positions'][0]['data']) + 2) % 2 == 0) and \
                    ((len(data['positions'][0]['data']) + 2) % 10 != 0))):
                        flip_last = True
                        idx = mesh.GetPolygonVertex(i, 2)
                        data['positions'][0]['data'].append(tuple(mesh.GetControlPointAt(idx)))
                        idx = mesh.GetPolygonVertex(i, 1)
                        data['positions'][0]['data'].append(tuple(mesh.GetControlPointAt(idx)))
                else:
                    idx = mesh.GetPolygonVertex(i, 1)
                    data['positions'][0]['data'].append(tuple(mesh.GetControlPointAt(idx)))
                    idx = mesh.GetPolygonVertex(i, 2)
                    data['positions'][0]['data'].append(tuple(mesh.GetControlPointAt(idx)))

        for i in range(mesh.GetLayerCount()):
            layer = mesh.GetLayer(i)

            # if layer.GetNormals() != None:
            #    data['normals'].append({'data': []})
            
            # if layer.GetBinormals() != None:
            #    data['binormals'].append({'resource_name': layer.GetBinormals().GetName(), 'data': []})

            if layer.GetUVs() != None:
                data['uvs'].append({'resource_name': layer.GetUVs().GetName(), 'data': []})

            uv_ge = mesh.GetElementUV(i)
            #binormal_ge = mesh.GetElementBinormal(i)
            normal_ge = mesh.GetElementNormal(i)

            for j in range(mesh.GetPolygonCount()):
                # if binormal_ge:
                #     binormal = binormal_ge.GetDirectArray().GetAt(j * 3)
                #     data['binormals'][i]['data'].append(binormal)
                if normal_ge:
                    normal = normal_ge.GetDirectArray().GetAt(j * 3)
                    data['normals'][i]['data'].append(normal)
                if uv_ge:
                    uv = self.get_texture_uv_by_ge(mesh, uv_ge, j, 0)
                    data['uvs'][i]['data'].append(uv)
                
                if j == (mesh.GetPolygonCount() - 1):
                    # if binormal_ge:
                    #     if flip_last:
                    #         binormal = binormal_ge.GetDirectArray().GetAt(j * 3 + 2)
                    #         data['binormals'][i]['data'].append(binormal)
                    #         binormal = binormal_ge.GetDirectArray().GetAt(j * 3 + 1)
                    #         data['binormals'][i]['data'].append(binormal)
                    #     else:
                    #         binormal = binormal_ge.GetDirectArray().GetAt(j * 3 + 1)
                    #         data['binormals'][i]['data'].append(binormal)
                    #         binormal = binormal_ge.GetDirectArray().GetAt(j * 3 + 2)
                    #         data['binormals'][i]['data'].append(binormal)
                    if normal_ge:
                        if flip_last:
                            normal = normal_ge.GetDirectArray().GetAt(j * 3 + 2)
                            data['normals'][i]['data'].append(normal)
                            normal = normal_ge.GetDirectArray().GetAt(j * 3 + 1)
                            data['normals'][i]['data'].append(normal)
                        else:
                            normal = normal_ge.GetDirectArray().GetAt(j * 3 + 1)
                            data['normals'][i]['data'].append(normal)
                            normal = normal_ge.GetDirectArray().GetAt(j * 3 + 2)
                            data['normals'][i]['data'].append(normal)
                    if uv_ge:
                        if flip_last:
                            uv = self.get_texture_uv_by_ge(mesh, uv_ge, j, 2)
                            data['uvs'][i]['data'].append(uv)
                            uv = self.get_texture_uv_by_ge(mesh, uv_ge, j, 1)
                            data['uvs'][i]['data'].append(uv)
                        else:
                            uv = self.get_texture_uv_by_ge(mesh, uv_ge, j, 1)
                            data['uvs'][i]['data'].append(uv)
                            uv = self.get_texture_uv_by_ge(mesh, uv_ge, j, 2)
                            data['uvs'][i]['data'].append(uv)

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
                        data['bone_indices'][-1]['data'].append({vertex_indices[j]: bone_idx})
                        data['bone_weights'][-1]['data'].append({vertex_indices[j]: weights[j]})
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
        mesh.InitControlPoints(len(data['positions'][0]['data']))

        # Vertices
        try:
            i = 0
            for vtx in data['positions'][0]['data']:
                v = fbx.FbxVector4(vtx[0], vtx[1], vtx[2], vtx[3])
                mesh.SetControlPointAt(v, i)
                i += 1

            flip = True
            for i in range(0, len(data['positions'][0]['data']) - 2):
                mesh.BeginPolygon()
                mesh.AddPolygon(i)
                if flip:
                    mesh.AddPolygon(i + 1)
                    mesh.AddPolygon(i + 2)
                else:
                    mesh.AddPolygon(i + 2)
                    mesh.AddPolygon(i + 1)
                mesh.EndPolygon()

                flip = not flip
        except Exception as e:
            print(e)

        # Bone weights
        try:
            scene = mesh.GetScene()
            skin = fbx.FbxSkin.Create(scene, "")
            nodeMat = node.EvaluateGlobalTransform()
            bone_indices = []
            bone_weights = []
            bone_mats = []
            
            for bone in self.bone_nodes:
                bone_mats.append(bone.EvaluateGlobalTransform())
            
            cluster_dict = {}
            for i in range(0, len(data['bone_indices'][0]['data'])):
                for j in range(0, len(data['bone_indices'])): 
                    bone_indices.append(data['bone_indices'][j]['data'][i][0])
                    bone_weights.append(data['bone_weights'][j]['data'][i][0])
                
                for k in range(0, len(bone_indices)):
                    bone_idx = bone_indices[k]
                    if bone_idx not in cluster_dict:
                        cluster_dict[bone_idx] = fbx.FbxCluster.Create(scene, "")
                        cluster_dict[bone_idx].SetLinkMode(fbx.FbxCluster.eTotalOne)
                        boneNode = self.bone_nodes[bone_idx]
                        cluster_dict[bone_idx].SetLink(boneNode)
                        cluster_dict[bone_idx].SetTransformMatrix(nodeMat)
                        cluster_dict[bone_idx].SetTransformLinkMatrix(bone_mats[bone_idx])
                        skin.AddCluster(cluster_dict[bone_idx])
                    cluster_dict[bone_idx].AddControlPointIndex(i, bone_weights[k])
                
                bone_indices = []
                bone_weights = []
            mesh.AddDeformer(skin)
            self.bind_pose.Add(node, fbx.FbxMatrix(node.EvaluateGlobalTransform()))
        except Exception as e:
            print(e)

        # Normals
        try:
            for i in range(len(data['normals'])):
                normal_le = fbx.FbxLayerElementNormal.Create(mesh, 'normals')
                normal_le.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                normal_le.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                layer = mesh.GetLayer(i)
                if (not layer):
                    mesh.CreateLayer()
                    layer = mesh.GetLayer(i)
                for j in range(len(data['normals'][i]['data'])):
                    normal_le.GetDirectArray().Add(fbx.FbxVector4(*data['normals'][i]['data'][j]))
                layer.SetNormals(normal_le)
        except Exception as e:
            print(e)

        # Binormals
        try:
            for i in range(len(data['binormals'])):
                binormal_le = fbx.FbxLayerElementBinormal.Create(mesh, 'binormals')
                binormal_le.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                binormal_le.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                layer = mesh.GetLayer(i)
                if (not layer):
                    mesh.CreateLayer()
                    layer = mesh.GetLayer(i)
                for j in range(len(data['binormals'][i]['data'])):
                    binormal_le.GetDirectArray().Add(fbx.FbxVector4(*data['binormals'][i]['data'][j]))
                layer.SetBinormals(binormal_le)
        except Exception as e:
            pass

        # UVs
        try:
            for i in range(len(data['uvs'])):
                uv_le = fbx.FbxLayerElementUV.Create(mesh, data['uvs'][i]['resource_name'])
                uv_le.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                uv_le.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                layer = mesh.GetLayer(i)
                if (not layer):
                    mesh.CreateLayer()
                    layer = mesh.GetLayer(i)
                for uvs in data['uvs'][i]['data']:
                    uv_le.GetDirectArray().Add(fbx.FbxVector2(uvs[0], -uvs[1] + 1))
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