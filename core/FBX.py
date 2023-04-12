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
        )   # == Yup Xfront Zright ?

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
        #fbx_manager.GetIOSettings().SetIntProp(fbx.EXP_FBX_COMPRESS_LEVEL, 9)  #Todo uncomment

        #Todo miss axis orientation, unit and Framefrequency

        FbxCommon.SaveScene(fbx_manager, scene, "output.fbx", 0, False)

        if(True) :          # Fbx Txt debug 
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
        #         
        #todo : do the version with data from PerPolygon (not only from Pervertex)

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


                    
        
        # Take care about eIndexToDirect or eDirect
        colors = []
        for i in range(nbColorLy):
            colors_Fbx = colors_layers[i]

            listColors = []
            if(colors_Fbx.GetReferenceMode()==fbx.FbxLayerElement.eIndexToDirect):
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
            colors.append( listColors )


        # same for normals
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
            normals.append( listNormals )


        # same for Binormal
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
            binormals.append( listBinormals )


        # same for Tangent
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
            tangents.append( listTangents )

        # same for UV
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
            uvs.append( listUvs )

        

        for i in range(nbVertex):
            vertices.append( {} )
            vertices[i]["color"] = []
            vertices[i]["normal"] = []
            vertices[i]["binormal"] = []
            vertices[i]["tangent"] = []
            vertices[i]["uv"] = []
            vertices[i]["blendIndices"] = []
            vertices[i]["blendWeights"] = []

            vect4_tmp = mesh.GetControlPointAt(i)
            vertices[i]["position"] = {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': 1.0}   # vect4_tmp.w = 1.0 because it's lost in FBX
            
            if nbColorLy :
                for j in range(len(colors)):
                    vect4_tmp = colors[j][i]
                    paramName = "color"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["color"].append( {'r': vect4_tmp[0], 'g': vect4_tmp[1], 'b': vect4_tmp[2], 'a': vect4_tmp[3]} )
                    
            if nbNormalLy :
                for j in range(len(normals)):
                    vect4_tmp = normals[j][i]
                    paramName = "normal"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["normal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )
                    
            if nbBinormalLy :
                for j in range(len(binormals)):
                    vect4_tmp = binormals[j][i]
                    paramName = "binormal"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["binormal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]})
                    
            if nbTangentLy :
                for j in range(len(tangents)):
                    vect4_tmp = tangents[j][i]
                    paramName = "tangent"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["tangent"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]})

            if nbUvLy:
                for j in range(len(uvs)):
                    vect4_tmp = uvs[j][i]
                    paramName = "uv"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["uv"].append( {'u': vect4_tmp[0], 'v': (1.0 - vect4_tmp[1]) } )

            if nbBoneLayer:
                blends = blend_byVertex[i]

                #apparently we have to order by weight (bigger first), and for the same weight, order by index
                blends.sort(key=lambda x: x.get('indexBone'))               #cheating by order by index first
                blends.sort(key=lambda x: x.get('weight'), reverse=True)    #rewritted by order by weight (but index's order will be correct for same weight)

                vertices[i]["blendIndices"] = []
                vertices[i]["blendWeights"] = []

                for j in range(nbBoneLayer):                    #fill if not defined to always have nbBoneLayer values
                    blend = blends[j] if(j<nbBoneLayer) else {"indexBone": 0, "weight": 0.0}
                    vertices[i]["blendIndices"].append( blend["indexBone"] )
                    vertices[i]["blendWeights"].append( blend["weight"] )

        faces_triangles = []
        for i in range(mesh.GetPolygonCount()):
            faces_triangles.append( [mesh.GetPolygonVertex(i, 0), mesh.GetPolygonVertex(i, 1), mesh.GetPolygonVertex(i, 2)] )


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
        completeBinormalTangent = True
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
                        vertex[ axisXYZ[ axisToFill ]["name"] ].append( ut.crossProd_Vect4( vertex[ axisXYZ[ srcAxis[0] ]["name"] ][i], vertex[ axisXYZ[ srcAxis[1] ]["name"] ][i] ) )

            if isModified :
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
        self.createMeshDebugXml("13_TriangleStripOnVertex", name.replace(":", "_"), vertices, faces_triangles)






        # ------------------------------------------------ 
        # Fill internal data for making spr
        # ------------------------------------------------ 


        versionFromVerticeList = True
        if versionFromVerticeList:
            
            #Todo case no Vertex

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
            
            

            

            


        # ------------------------------------------------------------------- Old version todo remove
        else: 
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
                    paramName = "color"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["color"].append( {'r': vect4_tmp[0], 'g': vect4_tmp[1], 'b': vect4_tmp[2], 'a': vect4_tmp[3]} )                
            
            if nbNormalLy :
                for j in range(len(data['normals'])):
                    vect4_tmp = data['normals'][j]['data'][i]
                    paramName = "normal"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["normal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )
                    
            if nbBinormalLy :
                for j in range(len(data['binormals'])):
                    vect4_tmp = data['binormals'][j]['data'][i]
                    paramName = "binormal"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["binormal"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )

            if nbTangentLy :
                for j in range(len(data['tangents'])):
                    vect4_tmp = data['tangents'][j]['data'][i]
                    paramName = "tangent"+ (("_"+ str(j)) if (j!=0) else "") 
                    vertices[i]["tangent"].append( {'x': vect4_tmp[0], 'y': vect4_tmp[1], 'z': vect4_tmp[2], 'w': vect4_tmp[3]} )
                    
            if nbUvLy:
                for j in range(len(data['uvs'])):
                    vect4_tmp = data['uvs'][j]['data'][i]
                    paramName = "uv"+ (("_"+ str(j)) if (j!=0) else "") 
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
        
        self.createMeshDebugXml("00_SprOriginal", mesh.GetName().replace(":", "_"), vertices, faces_triangles)





        # Todo put somewhere as Options
        removeDuplicateVertex = True
        removeTriangleStrip = True
        useFbxFaceOptimisation = False
        



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

                    if( (vertex["position"]["x"]!=vertex_tmp["position"]["x"]) or \
                        (vertex["position"]["y"]!=vertex_tmp["position"]["y"]) or \
                        (vertex["position"]["z"]!=vertex_tmp["position"]["z"]) or \
                        (vertex["position"]["w"]!=vertex_tmp["position"]["w"]) ):
                        continue
                    
                    listParams = [{"paramName": "normal", "nb": 4}, {"paramName": "binormal", "nb": 4}, {"paramName": "uv", "nb": 2}, {"paramName": "blendIndices", "nb": 1}, {"paramName": "blendWeights", "nb": 1}]
                    isDiff = False
                    for k in range(len(listParams)):
                        param = listParams[k]
                        paramName = param["paramName"]
                        nb = param["nb"]
                        listComponents = ["x", "y", "z", "w"] if (paramName != "uv") else ["u", "v"]
                        isDirectArray = False if ((paramName!="blendIndices") and (paramName!="blendWeights")) else True

                        if(len(vertex[paramName])!=len(vertex_tmp[paramName])):
                            isDiff = True
                            break
                        
                        for m in range(len(vertex[paramName])):
                            for n in range(nb):
                                if ( ((not isDirectArray) and (vertex[paramName][m][ listComponents[n] ] != vertex_tmp[paramName][m][ listComponents[n] ]) ) or\
                                    ((isDirectArray)  and (vertex[paramName][m] != vertex_tmp[paramName][m]) ) ):
                                    isDiff = True
                                    break
                            if isDiff: 
                                break
                        if isDiff: 
                            break
                        
                    if not isDiff:
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
            self.createMeshDebugXml("02_RemoveStripDegen", mesh.GetName().replace(":", "_"), vertices, faces_triangles)
        

        # ------------------------------------------------
        # Fbx Construction
        # ------------------------------------------------

        usePerVertex = True         # Test trying to do Per Vertex buffers, intead of perFace witch complexify for nothing the FBX
        if(usePerVertex):
            
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





            #-------------------------------------------------------
        else:


            # Removing duplicated vertices
            i = 0
            pos_dict = {}
            old_idx_list = []
            link_newIndex = []
            for j in range(len(data['positions'][0]['data'])):
                vtx = data['positions'][0]['data'][j]

                #isfound = ut.search_index_dict(pos_dict, vtx)      # could use that but create exception when not found value.
                isfound = -1
                for i in range(len(pos_dict.values())):
                    vtx_b = pos_dict[i]
                    if(vtx == vtx_b) :
                        isfound = i
                        break

                if isfound == -1 :
                    isfound = len(pos_dict)
                    pos_dict[isfound] = vtx
                    old_idx_list.append(j)
                link_newIndex.append(isfound)

            mesh.InitControlPoints(len(pos_dict))

            # Vertices
            vertex_indices = []
            try:
                for idx in range(len(data['positions'][0]['data'])):
                    vtx = data['positions'][0]['data'][idx]
                    #idx = ut.search_index_dict(pos_dict, vtx)
                    v = fbx.FbxVector4(vtx[0], vtx[1], vtx[2], vtx[3])
                    mesh.SetControlPointAt(v, idx)

                for i in range(0, len(data['positions'][0]['data']) - 2):
                    vtx = data['positions'][0]['data'][i]
                    vtx1 = data['positions'][0]['data'][i + 1]
                    vtx2 = data['positions'][0]['data'][i + 2]

                    #idx = ut.search_index_dict(pos_dict, vtx)
                    #idx1 = ut.search_index_dict(pos_dict, vtx1)
                    #idx2 = ut.search_index_dict(pos_dict, vtx2)
                    idx =  link_newIndex[i]
                    idx1 = link_newIndex[i + 1]
                    idx2 = link_newIndex[i + 2]

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
                        uv_le.GetDirectArray().Add(fbx.FbxVector2(uvs[0], 1.0 -uvs[1]))

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
    

        