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
        self.settings = None

    def load(self, path):
        global fbx_manager
        fbx_manager = fbx.FbxManager.Create()
        ios = fbx.FbxIOSettings.Create(fbx_manager, fbx.IOSROOT)
        fbx_manager.SetIOSettings(ios)
        importer = fbx.FbxImporter.Create(fbx_manager, '')

        importer.Initialize(path, -1, fbx_manager.GetIOSettings())
        scene = fbx.FbxScene.Create(fbx_manager, '')
        importer.Import(scene)

        # RB axis system
        axis_system = scene.GetGlobalSettings().GetAxisSystem()
        new_axis_system = fbx.FbxAxisSystem(
            fbx.FbxAxisSystem.eYAxis, 
            fbx.FbxAxisSystem.eParityOdd, 
            fbx.FbxAxisSystem.eRightHanded
        )   # OpenGL == Yup Xleft Zfront ( notice: we are in Yup Xright Zfront, but we consider we have x on left, because it's complex to deal with leftHanded with FBX and Blender/3dsmax)
        if (axis_system != new_axis_system):
            new_axis_system.ConvertScene(scene)
        axis_system = scene.GetGlobalSettings().GetAxisSystem()
        
        unit_system = scene.GetGlobalSettings().GetSystemUnit()
        if(unit_system != fbx.FbxSystemUnit.m):
            fbx.FbxSystemUnit.m.ConvertScene(scene)
        
        #Test Todo remove.
        # C++ version :
        # const int lNodeCount = lScene->GetSrcObjectCount<FbxNode>();
        # for (int lIndex = 0; lIndex < lNodeCount; lIndex++)
		#    fbxNode = lScene->GetSrcObject<FbxNode>(lIndex);
        listFbxNodes = []
        nbFbxNodes = scene.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxNode.ClassId))
        for i in range(nbFbxNodes):
            fbxNode = scene.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxNode.ClassId), i)
            listFbxNodes.append(fbxNode)


        root_node = scene.GetRootNode()
        nodes = []
        self.get_children(root_node, nodes, ['FbxNull', 'FbxSkeleton'])     #get all children FbxNull or FbxSkeleton
        

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


        #search for first RootNode child named 'NULL'
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







    def save(self, path, debugMeshs):
        buildDebugMeshXml = (ut.getSettingsOrAddDefault(self.settings, "BuildDebugMeshXml", False) == 'true')

        if not os.path.exists(path):
            os.mkdir(path)
        os.chdir(path)

        (fbx_manager, scene) = FbxCommon.InitializeSdkObjects()

        # with radits, we know : the game +Y up, +X right, +Z from 
        # => it's a leftHanded 
        # but blender don't give the good result.
        # Solution : apply a scale.x = -1.0 on NULL in blender before edit.
        axis_system = fbx.FbxAxisSystem(
            fbx.FbxAxisSystem.eYAxis, 
            fbx.FbxAxisSystem.eParityOdd, 
            fbx.FbxAxisSystem.eRightHanded
        )   
        scene.GetGlobalSettings().SetAxisSystem(axis_system)
        #scene.GetGlobalSettings().SetSystemUnit(fbx.FbxSystemUnit(100.0, 1.0)) # 1 unit in spr == 100m in game/blender/3dsmax/others games
        scene.GetGlobalSettings().SetSystemUnit(fbx.FbxSystemUnit.m)
        scene.GetGlobalSettings().SetTimeMode = fbx.FbxTime.eFrames60  # 60 Fps (Frames by Second) => not in python
        #fbx_manager.GetIOSettings().SetIntProp(fbx.EXP_FBX_COMPRESS_LEVEL, 9)  #Todo uncomment


        self.handle_data(fbx_manager, scene, path, debugMeshs)

        FbxCommon.SaveScene(fbx_manager, scene, "output.fbx", 0, False)

        if(buildDebugMeshXml) :          # Fbx Txt debug 
            FbxCommon.SaveScene(fbx_manager, scene, "output.fbx.txt", 1)

        fbx_manager.Destroy()
        del scene
        del fbx_manager

        os.chdir('..')

        return









    def handle_data(self, manager, scene, path, debugMeshs):
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


        # -------------- 
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

        # add debugMesh
        for i in range(len(debugMeshs)):
            self.add_debug_mesh_node(manager, scene, debugMeshs[i], "dg_")

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
                    if((len(class_names)==0) or (child.GetNodeAttribute().GetClassId().GetName() in class_names)):
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
        buildDebugMeshXml = (ut.getSettingsOrAddDefault(self.settings, "BuildDebugMeshXml", False) == 'true')
        removeDuplicateVertexOnPerPolygoneCase = (ut.getSettingsOrAddDefault(self.settings, "RemoveDuplicateVertexOnPerPolygoneCase", True) == 'true')
        completeBinormalTangent = (ut.getSettingsOrAddDefault(self.settings, "CompleteBinormalTangent", True) == 'true')
        
        mesh = node.GetMesh()

        data = {
            'positions': [],
            'colors': [],
            'normals': [],
            'binormals': [],
            'tangents': [],
            'uvs': [],
            'bone_weights': [],
            'bone_indices': [],
            'materials': []
        }




        # ------------------------------------------------ 
        # Merge all vertex informations to get just a list of vertex (more easy to deal with)
        # ------------------------------------------------ 

        name = mesh.GetName()
        vertices = []
        nbVertex = mesh.GetControlPointsCount()

        nbLayers = mesh.GetLayerCount()
        colors_layers = []
        normals_layers = []
        binormals_layers = []
        tangents_layers = []
        uvs_layers = []
        for i in range(nbLayers):
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

        nbColorLy = len(colors_layers)
        nbNormalLy = len(normals_layers)
        nbBinormalLy = len(binormals_layers)
        nbTangentLy = len(tangents_layers)
        nbUvLy = len(uvs_layers)
        

        

        # Notice: the list of colors (or normals) don't depend of MappingMode: eByControlPoint or eByPolygon. 
        # it's just the number of values will be not the same. 
        
        # VertexColor 
        colors = []
        for i in range(nbColorLy):
            colors_Fbx = colors_layers[i]

            listColors = []
            if(colors_Fbx.GetReferenceMode()==fbx.FbxLayerElement.eIndexToDirect):      # Take care about eIndexToDirect or eDirect (two common way to do)
                listIndex = colors_Fbx.GetIndexArray()
                listValues = colors_Fbx.GetDirectArray()

                nbElements = listIndex.GetCount()
                defaultVal = [0,0,0,1.0]                    #Todo look values (in xeno convertion by v_copy.setColorFromRGBAFloat((float)color.mRed, (float)color.mGreen, (float)color.mBlue, (float)color.mAlpha);)

                nbValues = listValues.GetCount()
                for j in range(nbElements):
                    index = listIndex.GetAt(j)
                    if (index < nbValues):
                        listColors.append(listValues.GetAt(index))
                    else:
                        listColors.append( defaultVal )
            else:
                for val in colors_Fbx.GetDirectArray():
                    listColors.append(val)
            colors.append( {"list": listColors, "mapping": colors_Fbx.GetMappingMode()} )


        # Normals
        normals = []
        for i in range(nbNormalLy):
            normals_Fbx = normals_layers[i]

            listNormals = []
            if(normals_Fbx.GetReferenceMode()==fbx.FbxLayerElement.eIndexToDirect):
                listIndex = normals_Fbx.GetIndexArray()
                listValues = normals_Fbx.GetDirectArray()

                nbElements = listIndex.GetCount()
                defaultVal = [0,0,0,0]

                nbValues = listValues.GetCount()
                for j in range(nbElements):
                    index = listIndex.GetAt(j)
                    if (index < nbValues):
                        listNormals.append(listValues.GetAt(index))
                    else:
                        listNormals.append( defaultVal )
            else:
                for val in normals_Fbx.GetDirectArray():
                    listNormals.append(val)
            normals.append( {"list": listNormals, "mapping": normals_Fbx.GetMappingMode()} )


        # Binormal
        binormals = []
        for i in range(nbBinormalLy):
            binormals_Fbx = binormals_layers[i]

            listBinormals = []
            if(binormals_Fbx.GetReferenceMode()==fbx.FbxLayerElement.eIndexToDirect):
                listIndex = binormals_Fbx.GetIndexArray()
                listValues = binormals_Fbx.GetDirectArray()

                nbElements = listIndex.GetCount()
                defaultVal = [0,0,0,0]

                nbValues = listValues.GetCount()
                for j in range(nbElements):
                    index = listIndex.GetAt(j)
                    if (index < nbValues):
                        listBinormals.append(listValues.GetAt(index))
                    else:
                        listBinormals.append( defaultVal )
            else:
                for val in binormals_Fbx.GetDirectArray():
                    listBinormals.append(val)
            binormals.append( {"list": listBinormals, "mapping": binormals_Fbx.GetMappingMode()} )


        # Tangent
        tangents = []
        for i in range(nbTangentLy):
            tangents_Fbx = tangents_layers[i]

            listTangents = []
            if(tangents_Fbx.GetReferenceMode()==fbx.FbxLayerElement.eIndexToDirect):
                listIndex = tangents_Fbx.GetIndexArray()
                listValues = tangents_Fbx.GetDirectArray()

                nbElements = listIndex.GetCount()
                defaultVal = [0,0,0,0]

                nbValues = listValues.GetCount()
                for j in range(nbElements):
                    index = listIndex.GetAt(j)
                    if (index < nbValues):
                        listTangents.append(listValues.GetAt(index))
                    else:
                        listTangents.append( defaultVal )
            else:
                for val in tangents_Fbx.GetDirectArray():
                    listTangents.append(val)
            tangents.append( {"list": listTangents, "mapping": tangents_Fbx.GetMappingMode()} )

        # UV
        uvs = []
        for i in range(nbUvLy):
            uvs_Fbx = uvs_layers[i]

            listUvs = []
            if(uvs_Fbx.GetReferenceMode()==fbx.FbxLayerElement.eIndexToDirect):
                listIndex = uvs_Fbx.GetIndexArray()
                listValues = uvs_Fbx.GetDirectArray()

                nbElements = listIndex.GetCount()
                defaultVal = [0,0,0,0]

                nbValues = listValues.GetCount()
                for j in range(nbElements):
                    index = listIndex.GetAt(j)
                    if (index < nbValues):
                        listUvs.append(listValues.GetAt(index))
                    else:
                        listUvs.append( defaultVal )
            else:
                for val in uvs_Fbx.GetDirectArray():
                    listUvs.append(val)
            uvs.append( {"list": listUvs, "mapping": uvs_Fbx.GetMappingMode()} )


        # Bones's Blend
        nbBoneLayer = 0
        blend_byVertex = []
        for i in range(nbVertex):
            blend_byVertex.append( [] )

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
                        blend_byVertex[vertex_indices[j]].append( {"indexBone": bone_idx, "weight": weights[j] } )
                        nbTmp = len(blend_byVertex[vertex_indices[j]])
                        nbBoneLayer = nbTmp if(nbTmp>nbBoneLayer) else nbBoneLayer



        havePerPolygoneValues = False
        for i in range(nbVertex):
            vertices.append( {} )
            vertices[i]["color"] = []
            vertices[i]["normal"] = []
            vertices[i]["binormal"] = []
            vertices[i]["tangent"] = []
            vertices[i]["uv"] = []
            vertices[i]["blendIndices"] = []
            vertices[i]["blendWeights"] = []

            #TODO: if someone move/rotate/scale the mesh's node instead of doing it on vertex, you got to deal with transform of Node

            vect4_tmp = mesh.GetControlPointAt(i)
            vertices[i]["position"] = {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': 1.0}   # vect4_tmp.w = 1.0 because it's lost in FBX
            
            # here we only do the eByControlPoint (or fill default value), eByPolygon will be done after.
            if nbColorLy :
                for j in range(len(colors)):
                    if(colors[j]["mapping"]==fbx.FbxLayerElement.eByControlPoint):
                        vect4_tmp = colors[j]["list"][i]
                        vertices[i]["color"].append( {'r': vect4_tmp[0], 'g': vect4_tmp[1], 'b': vect4_tmp[2], 'a': vect4_tmp[3]} )
                    else:
                        vertices[i]["color"].append( {'r': 0.0, 'g': 0.0, 'b': 0.0, 'a': 0.0} )
                        havePerPolygoneValues = ((havePerPolygoneValues) or (colors[j]["mapping"]==fbx.FbxLayerElement.eByPolygon))
                    
            if nbNormalLy :
                for j in range(len(normals)):
                    if(normals[j]["mapping"]==fbx.FbxLayerElement.eByControlPoint):
                        vect4_tmp = normals[j]["list"][i]
                        vertices[i]["normal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )
                    else:
                        vertices[i]["normal"].append( {'x': 0, 'y': 0, 'z': 0, 'w': 0} )
                        havePerPolygoneValues = ((havePerPolygoneValues) or (normals[j]["mapping"]==fbx.FbxLayerElement.eByPolygon))
                    
            if nbBinormalLy :
                for j in range(len(binormals)):
                    if(binormals[j]["mapping"]==fbx.FbxLayerElement.eByControlPoint):
                        vect4_tmp = binormals[j]["list"][i]
                        vertices[i]["binormal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]})
                    else:
                        vertices[i]["binormal"].append( {'x': 0, 'y': 0, 'z': 0, 'w': 0})
                        havePerPolygoneValues = ((havePerPolygoneValues) or (binormals[j]["mapping"]==fbx.FbxLayerElement.eByPolygon))
                    
            if nbTangentLy :
                for j in range(len(tangents)):
                    if(tangents[j]["mapping"]==fbx.FbxLayerElement.eByControlPoint):
                        vect4_tmp = tangents[j]["list"][i]
                        vertices[i]["tangent"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]})
                    else:
                        vertices[i]["tangent"].append( {'x': 0, 'y': 0, 'z': 0, 'w': 0})
                        havePerPolygoneValues = ((havePerPolygoneValues) or (tangents[j]["mapping"]==fbx.FbxLayerElement.eByPolygon))

            if nbUvLy:
                for j in range(len(uvs)):
                    if(uvs[j]["mapping"]==fbx.FbxLayerElement.eByControlPoint):
                        vect4_tmp = uvs[j]["list"][i]
                        vertices[i]["uv"].append( {'u': vect4_tmp[0], 'v': (1.0 - vect4_tmp[1]) } )
                    else:
                        vertices[i]["uv"].append( {'u': 0, 'v': 0} )
                        havePerPolygoneValues = ((havePerPolygoneValues) or (uvs[j]["mapping"]==fbx.FbxLayerElement.eByPolygon))

            if nbBoneLayer:
                blends = blend_byVertex[i]

                #apparently we have to order by weight (bigger first), and for the same weight, order by index
                blends.sort(key=lambda x: x.get('indexBone'))               #cheating by order by index first
                blends.sort(key=lambda x: x.get('weight'), reverse=True)    #rewritted by order by weight (but index's order will be correct for same weight)

                vertices[i]["blendIndices"] = []
                vertices[i]["blendWeights"] = []

                for j in range(nbBoneLayer):                    #fill if not defined to always have nbBoneLayer values
                    blend = blends[j] if(j<len(blends)) else {"indexBone": 0, "weight": 0.0}
                    vertices[i]["blendIndices"].append( blend["indexBone"] )
                    vertices[i]["blendWeights"].append( blend["weight"] )

        faces_triangles = []
        new_vertices_PerPoly = []
        for i in range(mesh.GetPolygonCount()):
            face = [mesh.GetPolygonVertex(i, 0), mesh.GetPolygonVertex(i, 1), mesh.GetPolygonVertex(i, 2)]

            # here we do the eByPolygon
            if(havePerPolygoneValues):
                for k in range(3):
                    vertexindex = face[k]
                    newVertex = self.cloneVertex(vertices[vertexindex])

                    if nbColorLy :
                        for j in range(len(colors)):
                            if(colors[j]["mapping"]==fbx.FbxLayerElement.eByPolygon):
                                vect4_tmp = colors[j]["list"][i * 3 + k]
                                newVertex["color"][j] = {'r': vect4_tmp[0], 'g': vect4_tmp[1], 'b': vect4_tmp[2], 'a': vect4_tmp[3]}
                            
                    if nbNormalLy :
                        for j in range(len(normals)):
                            if(normals[j]["mapping"]==fbx.FbxLayerElement.eByPolygon):
                                vect4_tmp = normals[j]["list"][i * 3 + k]
                                newVertex["normal"][j] = {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]}
                            
                    if nbBinormalLy :
                        for j in range(len(binormals)):
                            if(binormals[j]["mapping"]==fbx.FbxLayerElement.eByPolygon):
                                vect4_tmp = binormals[j]["list"][i * 3 + k]
                                newVertex["binormal"][j] = {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]}
                            
                    if nbTangentLy :
                        for j in range(len(tangents)):
                            if(tangents[j]["mapping"]==fbx.FbxLayerElement.eByPolygon):
                                vect4_tmp = tangents[j]["list"][i * 3 + k]
                                newVertex["tangent"][j] = {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]}

                    if nbUvLy:
                        for j in range(len(uvs)):
                            if(uvs[j]["mapping"]==fbx.FbxLayerElement.eByPolygon):
                                vect4_tmp = uvs[j]["list"][i * 3 + k]
                                newVertex["uv"][j] = {'u': vect4_tmp[0], 'v': (1.0 - vect4_tmp[1]) }
                    
                    
                    # here a optimisation witch could take time (compare all vertex made by faces), 
                    # but It necessary because face could make lot of duplicate vertex
                    newIndex = None

                    if(removeDuplicateVertexOnPerPolygoneCase):
                        for m in range(len(new_vertices_PerPoly)):                          
                            if(self.equalVertex(newVertex, new_vertices_PerPoly[m])):
                                newIndex = m
                                break
                    if(newIndex==None):
                        newIndex = len(new_vertices_PerPoly)
                        new_vertices_PerPoly.append(newVertex)
                    face[k] = newIndex
                    
            faces_triangles.append( face )
        
        if(havePerPolygoneValues):
            vertices = new_vertices_PerPoly

        

        if(buildDebugMeshXml):
            self.createMeshDebugXml("10_ImportedFromFbx", name.replace(":", "_"), vertices, faces_triangles)





        # Todo may be add a part to optimize the vertex and face before making triangle strip (depend of optimisation of 3dsmax/blender)



        # ------------------------------------------------ 
        # Complet Normal Binormal Tangent
        # Notice: Normal Binormal Tangent are used for NormalMapping (rgb = xyz in the TNB repere)
        #         Same if sound the Rb2 game create the tangents in shaders from normal and binormals,
        #         others game like xenoverse prefer to make Binormal from Normal and Tangent.
        #         so if you get mesh for others game, or create one with export only 2 of them
        #         you need to build the third.
        # ------------------------------------------------ 
        
        nbVertex = len(vertices)
        if ((completeBinormalTangent) and (nbVertex)):
            
            # Yup, Xfront, Zright (Right Handed)
            axisXYZ = [{"name": "tangent", "nb": 0}, {"name": "normal", "nb": 0}, {"name": "binormal", "nb": 0}]

            isModified = False
            minCommonLayers = -1
            for i in range(3):
                axisXYZ[i]["nb"] = len(vertices[0][ axisXYZ[i]["name"] ]) if(vertices[0][ axisXYZ[i]["name"] ]) else 0
                minCommonLayers = axisXYZ[i]["nb"] if((axisXYZ[i]["nb"]) and ( (minCommonLayers<0) or (axisXYZ[i]["nb"]>minCommonLayers))) else minCommonLayers

            if (minCommonLayers>=1) :
                axisToFills = []
                for i in range(1, minCommonLayers + 1):
                    if  ((axisXYZ[0]["nb"]<i) and (axisXYZ[1]["nb"]>=i) and (axisXYZ[2]["nb"]>=i)):   #If only miss tangents, add it
                        axisToFills.append( 0 )
                    elif((axisXYZ[0]["nb"]>=i) and (axisXYZ[1]["nb"]>=i) and (axisXYZ[2]["nb"]<i)):   #If only miss binormals, add it
                        axisToFills.append( 2 )
                    elif((axisXYZ[0]["nb"]>=i) and (axisXYZ[1]["nb"]<i) and (axisXYZ[2]["nb"]>=i)):   #If only miss normals (should be a never case), add it
                        axisToFills.append( 1 )
                    else:
                        axisToFills.append( -1 )
                
                for i in range(minCommonLayers):
                    axisToFill = axisToFills[i]
                    if(axisToFill==-1):
                        continue
                    
                    isModified = True
                    
                    srcAxis = []
                    for j in range(2):
                        srcAxis.append((axisToFill + j + 1) % 3)             # Ex: for Tangent, you need Normal + Binormal in this order. and for binormal, you need tangent and normal in this order
                    
                    for j in range(nbVertex):
                        vertex = vertices[j]
                        vertex[ axisXYZ[ axisToFill ]["name"] ].append( ut.crossProd_Vect4_XYZW( vertex[ axisXYZ[ srcAxis[0] ]["name"] ][i], vertex[ axisXYZ[ srcAxis[1] ]["name"] ][i] ) )

            if((isModified) and (buildDebugMeshXml)):
                self.createMeshDebugXml("11_CompleteBinormalTangent", name.replace(":", "_"), vertices, faces_triangles)
        
        
        


        # ------------------------------------------------ 
        # Transform Triangle list -> Triangle Strip 
        # ------------------------------------------------ 

        # Using NviTriStripper to generate the strip indices then build the strip
        flat_tri = sum(faces_triangles, [])
        tri_indices_text = str(flat_tri).replace(" ", "").replace("[", "").replace("]", "")
        
        tri_input = open(f"{cm.temp_path}/triangles.txt", "w")
        tri_input.write(tri_indices_text)
        tri_input.flush()

        cmd.nvtri_stripper(f"{cm.temp_path}\\triangles.txt", f"{cm.temp_path}\\triangles_out.txt")
        tri_output = open(f"{cm.temp_path}\\triangles_out.txt", "r")
        strip_indices = eval(tri_output.readline().strip())

        
        newFaces_triangles = []
        nbStripsIndices = len(strip_indices)
        for i in range(0, nbStripsIndices, 3):
            newFaces_triangles.append( [ strip_indices[i], strip_indices[ ((i + 1) if(i+1<nbStripsIndices) else (nbStripsIndices-1)) ], strip_indices[ ((i + 2) if(i+2<nbStripsIndices) else (nbStripsIndices-1)) ] ] )

        faces_triangles = newFaces_triangles
        if(buildDebugMeshXml):
            self.createMeshDebugXml("12_MakingTriangleStrip", name.replace(":", "_"), vertices, faces_triangles)











        # ------------------------------------------------ 
        # Apply Triangle Strip  on Vertex (Game's logic  / bad logic : they don't have faceIndex, but duplicate Vertex)
        # ------------------------------------------------ 
        
        new_vertices = []
        for i in range(len(strip_indices)):
            new_vertices.append(vertices[ strip_indices[i] ])
        

        newFaces_triangles = []
        for i in range(len(new_vertices) - 2):               # triangle strips logic
            if (i % 2 == 0):
                newFaces_triangles.append( [i, i+1, i+2] )
            else:
                newFaces_triangles.append( [i, i+2, i+1] )
        
        vertices = new_vertices
        faces_triangles = newFaces_triangles
        if(buildDebugMeshXml):
            self.createMeshDebugXml("13_TriangleStripOnVertex", name.replace(":", "_"), vertices, faces_triangles)






        # ------------------------------------------------ 
        # Fill internal data for making spr
        # ------------------------------------------------ 

        nbVertex = len(vertices)
        nbColorLy = len(vertices[0]["color"]) if(vertices[0]["color"]) else 0
        nbNormalLy = len(vertices[0]["normal"]) if(vertices[0]["normal"]) else 0
        nbBinormalLy = len(vertices[0]["binormal"]) if(vertices[0]["binormal"]) else 0
        nbTangentLy = len(vertices[0]["tangent"]) if(vertices[0]["tangent"]) else 0
        nbUvLy = len(vertices[0]["uv"]) if(vertices[0]["uv"]) else 0
        nbBoneLayer = len(vertices[0]["blendIndices"]) if(vertices[0]["blendIndices"]) else 0

        data['positions'] = [{'data': []}]
        for i in range(nbColorLy):
            data['colors'].append({'data': []})
        for i in range(nbNormalLy):
            data['normals'].append({'data': []})
        for i in range(nbBinormalLy):
            data['binormals'].append({'data': []})
        for i in range(nbTangentLy):
            data['tangents'].append({'data': []})
        for i in range(nbUvLy):
            data['uvs'].append({'resource_name': ("map"+ str(i +1 )), 'data': []})  #Todo Check if it's always "mapX"
        for i in range(nbBoneLayer):
            data['bone_indices'].append({'data': []})
            data['bone_weights'].append({'data': []})

        for i in range(nbVertex):
            vertex = vertices[i]
            
            data['positions'][0]['data'].append([vertex["position"]["x"], vertex["position"]["y"], vertex["position"]["z"], vertex["position"]["w"] ])
            for j in range(nbColorLy):
                data['colors'][j]['data'].append([vertex["color"][j]["r"], vertex["color"][j]["g"], vertex["color"][j]["b"], vertex["color"][j]["a"] ])
            for j in range(nbNormalLy):
                data['normals'][j]['data'].append([vertex["normal"][j]["x"], vertex["normal"][j]["y"], vertex["normal"][j]["z"], vertex["normal"][j]["w"] ])
            for j in range(nbBinormalLy):
                data['binormals'][j]['data'].append([vertex["binormal"][j]["x"], vertex["binormal"][j]["y"], vertex["binormal"][j]["z"], vertex["binormal"][j]["w"] ])
            for j in range(nbTangentLy):
                data['tangents'][j]['data'].append([vertex["tangent"][j]["x"], vertex["tangent"][j]["y"], vertex["tangent"][j]["z"], vertex["tangent"][j]["w"] ])
            for j in range(nbUvLy):
                data['uvs'][j]['data'].append( [vertex["uv"][j]["u"], vertex["uv"][j]["v"] ])
            for j in range(nbBoneLayer):
                data['bone_indices'][j]['data'].append( vertex["blendIndices"][j] )
                data['bone_weights'][j]['data'].append( vertex["blendWeights"][j] )

        for i in range(node.GetMaterialCount()):
                material = node.GetMaterial(i)
                prop = material.FindProperty(fbx.FbxSurfaceMaterial.sDiffuse)
                layered_texture = prop.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxLayeredTexture.ClassId), 0)
                if layered_texture:
                    texture_count = layered_texture.GetSrcObjectCount(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId))
                for i in range(texture_count):
                    texture = layered_texture.GetSrcObject(fbx.FbxCriteria.ObjectType(fbx.FbxTexture.ClassId), i)
                    data['materials'].append((texture.GetName(), texture.GetFileName()))
        
        data = {k: v for k, v in data.items() if v != []}
        return data









    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ################################################################################### 
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################

    def add_mesh_node(self, manager, scene, content, mesh_parents, layered_mesh_names):
        buildDebugMeshXml = (ut.getSettingsOrAddDefault(self.settings, "BuildDebugMeshXml", False) == 'true')
        removeDuplicateVertex = (ut.getSettingsOrAddDefault(self.settings, "RemoveSprDuplicateVertex", True) == 'true')
        removeTriangleStrip = (ut.getSettingsOrAddDefault(self.settings, "RemoveTriangleStrip", True) == 'true')
        useFbxFaceOptimisation = (ut.getSettingsOrAddDefault(self.settings, "UseFbxFaceOptimisation", True) == 'true')


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


        # todo reduce the key's names (ex "position" -> "p") for reduce memory and speed up.
        vertices = []
        nbVertex = len(data['positions'][0]['data'])
        nbColorLy = len(data['colors']) if ('colors' in data) else 0
        nbNormalLy = len(data['normals']) if ('normals' in data) else 0
        nbBinormalLy = len(data['binormals']) if ('binormals' in data) else 0
        nbTangentLy = len(data['tangents']) if ('tangents' in data) else 0
        nbUvLy = len(data['uvs']) if ('uvs' in data) else 0
        nbBoneLayer = len(data['bone_weights']) if ('bone_weights' in data) else 0

        for i in range(nbVertex):
            vertices.append( {} )
            vertices[i]["color"] = []
            vertices[i]["normal"] = []
            vertices[i]["binormal"] = []
            vertices[i]["tangent"] = []
            vertices[i]["uv"] = []
            vertices[i]["blendIndices"] = []
            vertices[i]["blendWeights"] = []

            vect4_tmp = data['positions'][0]['data'][i]
            vertices[i]["position"] = {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]}
            
            if nbColorLy :
                for j in range(len(data['colors'])):
                    vect4_tmp = data['colors'][j]['data'][i]
                    vertices[i]["color"].append( {'r': vect4_tmp[0], 'g': vect4_tmp[1], 'b': vect4_tmp[2], 'a': vect4_tmp[3]} )                
            
            if nbNormalLy :
                for j in range(len(data['normals'])):
                    vect4_tmp = data['normals'][j]['data'][i]
                    vertices[i]["normal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )
                    
            if nbBinormalLy :
                for j in range(len(data['binormals'])):
                    vect4_tmp = data['binormals'][j]['data'][i]
                    vertices[i]["binormal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )

            if nbTangentLy :
                for j in range(len(data['tangents'])):
                    vect4_tmp = data['tangents'][j]['data'][i]
                    vertices[i]["tangent"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )
                    
            if nbUvLy:
                for j in range(len(data['uvs'])):
                    vect4_tmp = data['uvs'][j]['data'][i]
                    vertices[i]["uv"].append( {'u': vect4_tmp[0], 'v': vect4_tmp[1]} )
                    
            if nbBoneLayer:
                for j in range(nbBoneLayer):
                    vertices[i]["blendIndices"].append( data['bone_indices'][j]['data'][i][0] )
                    vertices[i]["blendWeights"].append( data['bone_weights'][j]['data'][i][0] )
                

            
        # Faces from Triangle Strips algorythme
        faces_triangles = []
        nbVertex = len(vertices)
        for i in range(nbVertex - 2):               # triangle strips logic
            if (i % 2 == 0):
                faces_triangles.append( [i, i+1, i+2] )
            else:
                faces_triangles.append( [i, i+2, i+1] )
        if(buildDebugMeshXml):
            self.createMeshDebugXml("00_SprOriginal", mesh.GetName().replace(":", "_"), vertices, faces_triangles)





        
        



        # ------------------------------------------------ 
        # removing duplicate unnecessary vertex 
        #    (because a good triangle strip is must be on face index, not vertex)
        # Notice: that will change nothing except having less Vertex in Fbx
        # ------------------------------------------------ 

        if removeDuplicateVertex:
            listVertexIdRedirection = []
            newVertices = []
            for i in range(nbVertex):
                vertex = vertices[i]

                isFound = -1
                for j in range(len(newVertices)):
                    vertex_tmp = newVertices[j]

                    if(self.equalVertex(vertex, vertex_tmp)):
                        isFound = j
                        break
                
                listVertexIdRedirection.append( isFound if(isFound!=-1) else len(newVertices) )
                if isFound == -1:
                    newVertices.append(vertex)

            # Now we have just to change index for faces to get the same.
            newFaces_triangles = []
            for i in range(len(faces_triangles)): 
                newTriangle = []
                for j in range(3): 
                    newTriangle.append( listVertexIdRedirection[ faces_triangles[i][j] ] )
                newFaces_triangles.append( newTriangle )


            vertices = newVertices
            faces_triangles = newFaces_triangles
            # so now the triangle strip is only on faceIndex, we got the same, but we reduce Vertex number

            if(buildDebugMeshXml):
                self.createMeshDebugXml("01_VertexReduced", mesh.GetName().replace(":", "_"), vertices, faces_triangles)






        # ------------------------------------------------
        # Remove Triangle degenerate strip 
        # ------------------------------------------------
        # notice : after delete duplicate vertex, the Fbx's function 
        #    mesh.RemoveBadPolygons() detect the bad Triangle, 
        #    so this step is not really necessary, just to have the debug on it

        if removeTriangleStrip :
            newFaces_triangles = []
            for i in range(len(faces_triangles)):
                triangle = [ faces_triangles[i][0], faces_triangles[i][1], faces_triangles[i][2] ]

                # in Triangle strip algo, a degenerative strip (for cut the list) is done with 2 same vertex index in triangle.
                if((triangle[0]!=triangle[1]) and (triangle[0]!=triangle[2]) and (triangle[1]!=triangle[2])):
                    newFaces_triangles.append( triangle )        #so keep only triangle with 3 differents index.
            
            faces_triangles = newFaces_triangles
            if(buildDebugMeshXml):
                self.createMeshDebugXml("02_RemoveStripDegen", mesh.GetName().replace(":", "_"), vertices, faces_triangles)
        

        
        # ------------------------------------------------
        # Fbx Construction
        # ------------------------------------------------
        
        # Notice : due to games's way to do, the best case here is to create eByControlPoint FbxElement.
        #           using eByPolygon will duplicate vertex list for nothing (and there is allready duplication because of triangle strips). so it's the wrong case.
        scene = mesh.GetScene()

        # Vertices
        nbVertex = len(vertices)
        mesh.InitControlPoints(nbVertex)

        fbx_colors = []
        fbx_normals = []
        fbx_binormals = []
        fbx_tangents = []
        fbx_uvs = []

        skin = None
        fbx_boneCluster = []                        # one cluster per Bone USED
        nbBones = 0
        if hasattr(self, 'bone_nodes'):
            nbBones = len(self.bone_nodes)
            for i in range(nbBones):
                fbx_boneCluster.append(None)


        for i in range(nbVertex):
            vertex = vertices[i]
            
            # Position
            v = fbx.FbxVector4(vertex["position"]["x"], vertex["position"]["y"], vertex["position"]["z"], vertex["position"]["w"])
            mesh.SetControlPointAt(v, i)

            # Color                 # Todo a test
            for j in range(len(vertex["color"])):
                color = vertex["color"][j]

                if (j>=len(fbx_colors)):
                    paramName = "color_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_color = fbx.FbxLayerElementVertexColor.Create(mesh, paramName)
                    fbx_color.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_color.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_colors.append(fbx_color)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetColors(fbx_color)
                
                fbx_color = fbx_colors[j]
                fbx_color.GetDirectArray().Add(fbx.FbxVector4(color["r"], color["g"], color["b"], color["a"]))


            # Normal
            for j in range(len(vertex["normal"])):
                normal = vertex["normal"][j]

                if (j>=len(fbx_normals)):
                    paramName = "normal_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_normal = fbx.FbxLayerElementNormal.Create(mesh, paramName)
                    fbx_normal.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_normal.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_normals.append(fbx_normal)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetNormals(fbx_normal)
                
                fbx_normal = fbx_normals[j]
                fbx_normal.GetDirectArray().Add(fbx.FbxVector4(normal["x"], normal["y"], normal["z"], normal["w"]))

            # Binormal
            for j in range(len(vertex["binormal"])):
                binormal = vertex["binormal"][j]

                if (j>=len(fbx_binormals)):
                    paramName = "binormal_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_binormal = fbx.FbxLayerElementBinormal.Create(mesh, paramName)
                    fbx_binormal.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_binormal.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_binormals.append(fbx_binormal)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetBinormals(fbx_binormal)
                
                fbx_binormal = fbx_binormals[j]
                fbx_binormal.GetDirectArray().Add(fbx.FbxVector4(binormal["x"], binormal["y"], binormal["z"], binormal["w"]))
            

            # Tangent
            for j in range(len(vertex["tangent"])):
                tangent = vertex["tangent"][j]

                if (j>=len(fbx_tangents)):
                    paramName = "tangent_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_tangent = fbx.FbxLayerElementTangent.Create(mesh, paramName)
                    fbx_tangent.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_tangent.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_tangents.append(fbx_tangent)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetTangents(fbx_tangent)
                
                fbx_tangent = fbx_tangents[j]
                fbx_tangent.GetDirectArray().Add(fbx.FbxVector4(tangent["x"], tangent["y"], tangent["z"], tangent["w"]))


            # Uv
            for j in range(len(vertex["uv"])):
                uv = vertex["uv"][j]

                if (j>=len(fbx_uvs)):
                    paramName = "uv_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_uv = fbx.FbxLayerElementUV.Create(mesh, paramName)
                    fbx_uv.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_uv.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_uvs.append(fbx_uv)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetUVs(fbx_uv)
                
                fbx_uv = fbx_uvs[j]
                fbx_uv.GetDirectArray().Add(fbx.FbxVector2(uv["u"], 1.0 - uv["v"]))


            # Bone Blend
            if(nbBones):
                for j in range(len(vertex["blendIndices"])):
                    indexBone = vertex["blendIndices"][j]
                    weight = vertex["blendWeights"][j]

                    if (indexBone>=nbBones):            # Todo Warning
                        indexBone = 0
                    

                    if (fbx_boneCluster[indexBone] == None):
                        cluster = fbx.FbxCluster.Create(scene, "bone_"+ str(indexBone) +"_cluster")
                        cluster.SetLinkMode(fbx.FbxCluster.eTotalOne)
                        bone_node = self.bone_nodes[indexBone]
                        cluster.SetLink(bone_node)
                        cluster.SetTransformMatrix(node.EvaluateGlobalTransform()) # Node  support the mesh
                        cluster.SetTransformLinkMatrix(bone_node.EvaluateGlobalTransform())

                        if(skin == None):
                            skin = fbx.FbxSkin.Create(scene, "skin_"+ name)
                            mesh.AddDeformer(skin)
                        skin.AddCluster(cluster)
                        fbx_boneCluster[indexBone] = cluster
                    cluster = fbx_boneCluster[indexBone]

                    cluster.AddControlPointIndex(i, weight)


        # Faces
        nbTriangles = len(faces_triangles)
        for i in range(nbTriangles):
            mesh.BeginPolygon()
            for j in range(3):
                mesh.AddPolygon(faces_triangles[i][j])
            mesh.EndPolygon()
        
        
        # Materials
        lMaterialElement = fbx.FbxLayerElementNormal.Create(mesh, 'normals')
        lMaterialElement.SetMappingMode(fbx.FbxLayerElement.eByPolygon)
        lMaterialElement.SetReferenceMode(fbx.FbxLayerElement.eIndexToDirect)


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
        if useFbxFaceOptimisation:
            mesh.RemoveBadPolygons()

        return node









    

    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ################################################################################### 
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################
    ###################################################################################

    def add_debug_mesh_node(self, manager, scene, debugMesh, prefixName):

        name = prefixName + debugMesh["name"]
        root_node = scene.GetRootNode()
        
        node = fbx.FbxNode.Create(root_node, name)
        attr = fbx.FbxNull.Create(manager, '')
        node.AddNodeAttribute(attr)

        node.LclTranslation.Set(fbx.FbxDouble3(0, 0, 0))
        node.LclRotation.Set(fbx.FbxDouble3(0, 0, 0))
        node.LclScaling.Set(fbx.FbxDouble3(1, 1, 1))
        root_node.AddChild(node)

        gt = node.EvaluateGlobalTransform()
        self.bind_pose.Add(node, fbx.FbxMatrix(gt))

        mesh = fbx.FbxMesh.Create(manager, f"{name}_mesh")
        node.SetNodeAttribute(mesh)



        vertices = debugMesh["vertices"]
        faces_triangles = debugMesh["faces"]









        # ------------------------------------------------
        # Fbx Construction
        # ------------------------------------------------

        scene = mesh.GetScene()

        # Vertices
        nbVertex = len(vertices)
        mesh.InitControlPoints(nbVertex)

        fbx_colors = []
        fbx_normals = []
        fbx_binormals = []
        fbx_tangents = []
        fbx_uvs = []

        skin = None
        fbx_boneCluster = []                        # one cluster per Bone USED
        nbBones = 0
        if hasattr(self, 'bone_nodes'):
            nbBones = len(self.bone_nodes)
            for i in range(nbBones):
                fbx_boneCluster.append(None)


        for i in range(nbVertex):
            vertex = vertices[i]

            if(not("color" in vertices[i])):
                vertices[i]["color"] = []
            if(not("normal" in vertices[i])):
                vertices[i]["normal"] = []
            if(not("binormal" in vertices[i])):
                vertices[i]["binormal"] = []
            if(not("tangent" in vertices[i])):
                vertices[i]["tangent"] = []
            if(not("uv" in vertices[i])):
                vertices[i]["uv"] = []
            if(not("blendIndices" in vertices[i])):
                vertices[i]["blendIndices"] = []
                vertices[i]["blendWeights"] = []

            
            # Position
            v = fbx.FbxVector4(vertex["position"]["x"], vertex["position"]["y"], vertex["position"]["z"], vertex["position"]["w"])
            mesh.SetControlPointAt(v, i)

            # Color                 # Todo a test
            for j in range(len(vertex["color"])):
                color = vertex["color"][j]

                if (j>=len(fbx_colors)):
                    paramName = "color_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_color = fbx.FbxLayerElementVertexColor.Create(mesh, paramName)
                    fbx_color.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_color.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_colors.append(fbx_color)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetColors(fbx_color)
                
                fbx_color = fbx_colors[j]
                fbx_color.GetDirectArray().Add(fbx.FbxVector4(color["r"], color["g"], color["b"], color["a"]))


            # Normal
            for j in range(len(vertex["normal"])):
                normal = vertex["normal"][j]

                if (j>=len(fbx_normals)):
                    paramName = "normal_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_normal = fbx.FbxLayerElementNormal.Create(mesh, paramName)
                    fbx_normal.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_normal.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_normals.append(fbx_normal)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetNormals(fbx_normal)
                
                fbx_normal = fbx_normals[j]
                fbx_normal.GetDirectArray().Add(fbx.FbxVector4(normal["x"], normal["y"], normal["z"], normal["w"]))

            # Binormal
            for j in range(len(vertex["binormal"])):
                binormal = vertex["binormal"][j]

                if (j>=len(fbx_binormals)):
                    paramName = "binormal_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_binormal = fbx.FbxLayerElementBinormal.Create(mesh, paramName)
                    fbx_binormal.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_binormal.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_binormals.append(fbx_binormal)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetBinormals(fbx_binormal)
                
                fbx_binormal = fbx_binormals[j]
                fbx_binormal.GetDirectArray().Add(fbx.FbxVector4(binormal["x"], binormal["y"], binormal["z"], binormal["w"]))
            

            # Tangent
            for j in range(len(vertex["tangent"])):
                tangent = vertex["tangent"][j]

                if (j>=len(fbx_tangents)):
                    paramName = "tangent_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_tangent = fbx.FbxLayerElementTangent.Create(mesh, paramName)
                    fbx_tangent.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_tangent.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_tangents.append(fbx_tangent)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetTangents(fbx_tangent)
                
                fbx_tangent = fbx_tangents[j]
                fbx_tangent.GetDirectArray().Add(fbx.FbxVector4(tangent["x"], tangent["y"], tangent["z"], tangent["w"]))


            # Uv
            for j in range(len(vertex["uv"])):
                uv = vertex["uv"][j]

                if (j>=len(fbx_uvs)):
                    paramName = "uv_"+ (("_"+ str(j)) if (j!=0) else "") 
                    fbx_uv = fbx.FbxLayerElementUV.Create(mesh, paramName)
                    fbx_uv.SetMappingMode(fbx.FbxLayerElement.eByControlPoint)
                    fbx_uv.SetReferenceMode(fbx.FbxLayerElement.eDirect)
                    fbx_uvs.append(fbx_uv)

                    layer = mesh.GetLayer(j)
                    if (not layer):
                        mesh.CreateLayer()
                        layer = mesh.GetLayer(j)
                    layer.SetUVs(fbx_uv)
                
                fbx_uv = fbx_uvs[j]
                fbx_uv.GetDirectArray().Add(fbx.FbxVector2(uv["u"], 1.0 - uv["v"]))


            # Bone Blend
            if(nbBones):
                for j in range(len(vertex["blendIndices"])):
                    indexBone = vertex["blendIndices"][j]
                    weight = vertex["blendWeights"][j]

                    if (indexBone>=nbBones):            # Todo Warning
                        indexBone = 0
                    

                    if (fbx_boneCluster[indexBone] == None):
                        cluster = fbx.FbxCluster.Create(scene, "bone_"+ str(indexBone) +"_cluster")
                        cluster.SetLinkMode(fbx.FbxCluster.eTotalOne)
                        bone_node = self.bone_nodes[indexBone]
                        cluster.SetLink(bone_node)
                        cluster.SetTransformMatrix(node.EvaluateGlobalTransform()) # Node  support the mesh
                        cluster.SetTransformLinkMatrix(bone_node.EvaluateGlobalTransform())

                        if(skin == None):
                            skin = fbx.FbxSkin.Create(scene, "skin_"+ name)
                            mesh.AddDeformer(skin)
                        skin.AddCluster(cluster)
                        fbx_boneCluster[indexBone] = cluster
                    cluster = fbx_boneCluster[indexBone]

                    cluster.AddControlPointIndex(i, weight)


        # Faces
        nbTriangles = len(faces_triangles)
        for i in range(nbTriangles):
            mesh.BeginPolygon()
            for j in range(3):
                mesh.AddPolygon(faces_triangles[i][j])
            mesh.EndPolygon()
        
        
        # Materials
        lMaterialElement = fbx.FbxLayerElementNormal.Create(mesh, name)
        lMaterialElement.SetMappingMode(fbx.FbxLayerElement.eByPolygon)
        lMaterialElement.SetReferenceMode(fbx.FbxLayerElement.eIndexToDirect)
        mat = self.add_material(scene, name)
        node.AddMaterial(mat)
        
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

    def resize(self, array, new_size, new_value=0):                   # https://stackoverflow.com/questions/30503792/resize-an-array-with-a-specific-value
        # """Resize to biggest or lesser size."""
        element_size = len(array[0]) #Quantity of new elements equals to quantity of first element
        if new_size > len(array):
            new_size = new_size - 1
            while len(array)<=new_size:
                n = tuple(new_value for i in range(element_size))
                array.append(n)
        else:
            array = array[:new_size]
        return array







    def cloneVertex(self, vertex):
        vect = vertex["position"]
        newVertex = {"position": {"x": vect["x"], "y": vect["y"], "z": vect["z"], "w": vect["w"]} }

        if("color" in vertex):
            newVertex["color"] = []
            for i in range(len(vertex["color"])):
                vect = vertex["color"][i]
                newVertex["normal"].append( {"r": vect["r"], "g": vect["g"], "b": vect["b"], "a": vect["a"]} )

        if("normal" in vertex):
            newVertex["normal"] = []
            for i in range(len(vertex["normal"])):
                vect = vertex["normal"][i]
                newVertex["normal"].append( {"x": vect["x"], "y": vect["y"], "z": vect["z"], "w": vect["w"]} )

        if("binormal" in vertex):
            newVertex["binormal"] = []
            for i in range(len(vertex["binormal"])):
                vect = vertex["binormal"][i]
                newVertex["binormal"].append( {"x": vect["x"], "y": vect["y"], "z": vect["z"], "w": vect["w"]} )

        if("tangent" in vertex):
            newVertex["tangent"] = []
            for i in range(len(vertex["tangent"])):
                vect = vertex["tangent"][i]
                newVertex["tangent"].append( {"x": vect["x"], "y": vect["y"], "z": vect["z"], "w": vect["w"]} )

        if("uv" in vertex):
            newVertex["uv"] = []
            for i in range(len(vertex["uv"])):
                vect = vertex["uv"][i]
                newVertex["uv"].append( {"u": vect["u"], "v": vect["v"]} )

        if("blendIndices" in vertex):
            newVertex["blendIndices"] = []
            newVertex["blendWeights"] = []
            for i in range(len(vertex["blendIndices"])):
                newVertex["blendIndices"].append( vertex["blendIndices"][i] )
                newVertex["blendWeights"].append( vertex["blendWeights"][i] )

        return newVertex
    

    def equalVertex(self, vA, vB):
        if( (vA["position"]["x"]!=vB["position"]["x"]) or \
            (vA["position"]["y"]!=vB["position"]["y"]) or \
            (vA["position"]["z"]!=vB["position"]["z"]) or \
            (vA["position"]["w"]!=vB["position"]["w"]) ):
            return False
        
        listParams = [{"paramName": "normal", "nb": 4}, {"paramName": "binormal", "nb": 4}, {"paramName": "uv", "nb": 2}, {"paramName": "blendIndices", "nb": 1}, {"paramName": "blendWeights", "nb": 1}]
        for k in range(len(listParams)):
            param = listParams[k]
            paramName = param["paramName"]
            nb = param["nb"]
            listComponents = ["x", "y", "z", "w"] if (paramName != "uv") else ["u", "v"]
            isDirectArray = False if ((paramName!="blendIndices") and (paramName!="blendWeights")) else True

            if(len(vA[paramName])!=len(vB[paramName])):
                return False
            
            for m in range(len(vA[paramName])):
                for n in range(nb):
                    if ( ((not isDirectArray) and (vA[paramName][m][ listComponents[n] ] != vB[paramName][m][ listComponents[n] ]) ) or\
                        ((isDirectArray)  and (vA[paramName][m] != vB[paramName][m]) ) ):
                        return False
        return True











    def createMeshDebugXml(self, folderName = "debugMesh", name = "", vertices = [], faces_triangles = []):   
        #Hyp : all vertices have the same nbLayers for each normals, uv, etc .. (bone blend indices and weight are fill by 0 ,0.0 to complete)

        nbVertex = len(vertices)
        nbColorLy = len(vertices[0]['color']) if((nbVertex) and (vertices[0]['color'])) else 0
        nbNormalLy = len(vertices[0]['normal']) if((nbVertex) and (vertices[0]['normal'])) else 0
        nbBinormalLy = len(vertices[0]['binormal']) if((nbVertex) and (vertices[0]['binormal'])) else 0
        nbTangentLy = len(vertices[0]['tangent']) if((nbVertex) and (vertices[0]['tangent'])) else 0
        nbUvLy = len(vertices[0]['uv']) if((nbVertex) and (vertices[0]['uv'])) else 0
        nbBoneLayer = len(vertices[0]['blendIndices']) if((nbVertex) and (vertices[0]['blendIndices'])) else 0

        debug_str = '<Mesh name="'+ name +'" nbVertex="'+ str(nbVertex) +'" nbColorLy="'+ str(nbColorLy) +'" nbNormalLy="'+ str(nbNormalLy) +'" nbBinormalLy="'+ str(nbBinormalLy) +'" nbTangentLy="'+ str(nbTangentLy) +'" nbUvLy="'+ str(nbUvLy) +'" nbBoneLayer="'+ str(nbBoneLayer) +'" >\n'
        debug_str += '\t<Vertices>\n'
        for i in range(nbVertex):
            vertex = vertices[i]

            debug_str += '\t\t<Vertex index="'+ str(i) +'">\n'
            debug_str += '\t\t\t<Position x="'+ str(vertex["position"]["x"]) +'"\ty="'+ str(vertex["position"]["y"]) +'"\tz="'+ str(vertex["position"]["z"]) +'"\tw="'+ str(vertex["position"]["w"]) +'" />\n'
            
            for j in range(nbColorLy):
                paramName = "color"+ (("_"+ str(j)) if (j!=0) else "") 
                debug_str += '\t\t\t<'+ paramName  +' r="'+ str(vertex["color"][j]["r"]) +'"\tg="'+ str(vertex["color"][j]["g"]) +'"\tb="'+ str(vertex["color"][j]["b"]) +'"\ta="'+ str(vertex["color"][j]["a"]) +'" />\n'
            
            for j in range(nbNormalLy):
                paramName = "normal"+ (("_"+ str(j)) if (j!=0) else "") 
                debug_str += '\t\t\t<'+ paramName  +' x="'+ str(vertex["normal"][j]["x"]) +'"\ty="'+ str(vertex["normal"][j]["y"]) +'"\tz="'+ str(vertex["normal"][j]["z"]) +'"\tw="'+ str(vertex["normal"][j]["w"]) +'" />\n'
            
            for j in range(nbBinormalLy):
                paramName = "binormal"+ (("_"+ str(j)) if (j!=0) else "") 
                debug_str += '\t\t\t<'+ paramName  +' x="'+ str(vertex["binormal"][j]["x"]) +'"\ty="'+ str(vertex["binormal"][j]["y"]) +'"\tz="'+ str(vertex["binormal"][j]["z"]) +'"\tw="'+ str(vertex["binormal"][j]["w"]) +'" />\n'
            
            for j in range(nbTangentLy):
                paramName = "tangent"+ (("_"+ str(j)) if (j!=0) else "") 
                debug_str += '\t\t\t<'+ paramName  +' x="'+ str(vertex["tangent"][j]["x"]) +'"\ty="'+ str(vertex["tangent"][j]["y"]) +'"\tz="'+ str(vertex["tangent"][j]["z"]) +'"\tw="'+ str(vertex["tangent"][j]["w"]) +'" />\n'

            for j in range(nbUvLy):
                paramName = "uv"+ (("_"+ str(j)) if (j!=0) else "") 
                debug_str += '\t\t\t<'+ paramName  +' u="'+ str(vertex["uv"][j]["u"]) +'"\tv="'+ str(vertex["uv"][j]["v"]) +'" />\n'

            if nbBoneLayer:
                debug_indices_Str = ""
                debug_weight_Str = ""
                for j in range(nbBoneLayer):
                    debug_indices_Str += (", " if(j!=0) else "") + str(vertex["blendIndices"][j]) 
                    debug_weight_Str  += (", " if(j!=0) else "") + str(vertex["blendWeights"][j])
                debug_str += '\t\t\t<Blend indices="'+ debug_indices_Str +'" weights="'+ debug_weight_Str +'" />\n'

            debug_str += '\t\t</Vertex>\n'
        debug_str += '\t</Vertices>\n'


        #Faces
        nbFaces = len(faces_triangles)
        debug_str += '\t<Faces nbFaces="'+ str(nbFaces) +'" >\n'
        for i in range(len(faces_triangles)):
            triangle = faces_triangles[i]
            debug_str += '\t\t<Triangle a="'+ str(triangle[0]) +'"\tb="'+ str(triangle[1]) +'"\tc="'+ str(triangle[2]) +'" />\n'
        debug_str += '\t</Faces>\n'

        debug_str += '</Mesh>\n'

        lastWorkingDir = os.getcwd()
        if not os.path.exists(folderName):
            os.mkdir(folderName)
        os.chdir(folderName)

        data_stream = open(name +".xml", "w")
        data_stream.write(str(debug_str))

        os.chdir(lastWorkingDir)
    

        