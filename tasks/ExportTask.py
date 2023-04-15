import os
import json
from tasks.Task import Task
from core.FBX import FBX
import core.utils as ut
import numpy as np

class ExportTask(Task):
    def __init__(self, data, output_path):
        super().__init__()
        self.data = data
        self.output_path = output_path

    def run(self):
        try:
            ut.empty_temp_dir()
            ut.init_temp_dir()

            bone_data = self.data['spr'].search_entries([], 'BONE')
            scne_data = self.data['spr'].search_entries([], 'SCNE')
            vbuf_data = self.data['spr'].search_entries([], 'VBUF')
            tx2d_data = self.data['spr'].search_entries([], 'TX2D')
            mtrl_data = self.data['spr'].search_entries([], 'MTRL')
            shap_data = self.data['spr'].search_entries([], 'SHAP')
            drvn_data = self.data['spr'].search_entries([], 'DRVN', True)
            txan_data = self.data['spr'].search_entries([], 'TXAN', True)

            

            # BONE
            bone_dict = {}
            try:
                bone_entries = bone_data[0].data.bone_entries
                if len(bone_data) > 1:
                    bone_base_data = bone_data[0].get_data()['data']
                    bone_info_data = bone_data[1].get_data()['data']['data']

                    if len(bone_data) > 2:
                        bone_char_info_data = bone_data[2].get_data()['data']['data']
                    
                    for i in range(len(bone_info_data)):
                        data = {
                            'data': bone_base_data[i],
                            'DbzBoneInfo': bone_info_data[i]
                        }
                        if len(bone_data) > 2:
                            data[ut.b2s_name(bone_data[2].name)] = bone_char_info_data[i]
                        bone_name = ut.b2s_name(bone_entries[i].name)
                        bone_dict[bone_name] = data

                json_data = json.dumps(bone_dict, indent=4)
                data_stream = open(f"{self.output_path}\BONE.json", "w")
                data_stream.write(str(json_data))
            except:
                print('Bone data is missing')

            self.send_progress(10)

            # SHAP
            shap_dict = {}
            for data in shap_data:
                if data.__class__.__name__ == "SPRPDataEntry":
                    content = data.get_data()
                    content['data'] = content['data']['data']
                    if 'children' in content.keys():
                        edge_info_entries = data.search_entries([], 'DbzEdgeInfo')
                        if len(edge_info_entries) > 0:
                            content['DbzEdgeInfo'] = edge_info_entries[0].get_data()['data']
                            if 'source_name' in content['DbzEdgeInfo'].keys():
                                content['DbzEdgeInfo']['source_name'] = \
                                    content['DbzEdgeInfo']['source_name'].replace('.tga', '.dds')
                        del content['children']
                    shap_dict[ut.b2s_name(data.name)] = content

            self.send_progress(20)

            scne_mesh_dict = {}
            scne_shape_dict = {}       
            for node in scne_data[0].children[1].children:
                if node.data.data_type == b'mesh':
                    scne_mesh_dict[ut.b2s_name(node.name)] = ut.b2s_name(node.data.parent_name)
                elif node.data.data_type == b'shape':
                    scne_shape_dict[ut.b2s_name(node.data.name)] = ut.b2s_name(node.data.name)
            
            for node in scne_data[0].children[1].children:
                for key, val in scne_mesh_dict.items():
                    if val == ut.b2s_name(node.name):
                        scne_mesh_dict[key] = ut.b2s_name(node.data.name)
            
            # Rebuilding shapes to match new mesh names
            new_scne_shape_dict = {}
            namesLinks = {}
            for scne_shape_name, shape_name in scne_shape_dict.items():
                for scne_mesh_name, mesh_shape in scne_mesh_dict.items():
                    if mesh_shape == shape_name:
                        new_shape_name = scne_mesh_name.rsplit("|", 1)[1]
                        new_shape_name = new_shape_name.rsplit(':', 1)[0]
                        new_shape_name += 'Shape'
                        if new_shape_name not in new_scne_shape_dict.keys():
                            new_scne_shape_dict[new_shape_name] = shap_dict[shape_name]
                            namesLinks[new_shape_name] = shape_name

            #Try to keep previous SHAP order            #hard to make the diff
            tmp_list = {}
            for name, content in shap_dict.items():

                for new_name, new_content in new_scne_shape_dict.items():
                    if namesLinks[new_name] == name:
                        tmp_list[new_name] = new_content
                        del new_scne_shape_dict[new_name]
                        break

            for new_name, new_content in new_scne_shape_dict.items():
                tmp_list[new_name] = new_content
            new_scne_shape_dict = tmp_list

            json_data = json.dumps(new_scne_shape_dict, indent=4)          
            data_stream = open(f"{self.output_path}\SHAP.json", "w")
            data_stream.write(str(json_data))

            self.send_progress(40)

            # MTRL
            mtrl_dict = {}
            for data in mtrl_data:
                if data.__class__.__name__ == "SPRPDataEntry":
                    content = data.get_data()
                    content['data'] = content['data']['data']
                    if 'children' in content.keys():
                        content['DbzCharMtrl'] = content['children'][0]
                        del content['children']
                    try:
                        material_name_parts = data.name.rsplit(b':', 1)[1]
                        if len(material_name_parts) > 2:
                            data.name = b':'.join(material_name_parts[1:])
                        else:
                            data.name = material_name_parts[1]
                    except:
                        pass
                    mtrl_dict[ut.b2s_name(data.name)] = content

            json_data = json.dumps(mtrl_dict, indent=4)
            data_stream = open(f"{self.output_path}\MTRL.json", "w")
            data_stream.write(str(json_data))

            # DRVN
            if drvn_data.__class__.__name__ != 'list':
                json_data = json.dumps(drvn_data.get_data(), indent=4)
                data_stream = open(f"{self.output_path}\DRVN.json", "w")
                data_stream.write(str(json_data))

            self.send_progress(60)

            # TXAN
            if txan_data.__class__.__name__ != 'list':
                eye_texture_names = []
                for entry in tx2d_data:
                    if b'eyeball' in entry.name:
                        eye_texture_names.append(entry.name.replace(b'.tga', b'.dds'))
                
                for i in range(len(txan_data.entries)):
                    idx = abs((len(eye_texture_names) - 1) - i) % len(eye_texture_names)
                    txan_data.entries[i].name = eye_texture_names[idx]

                json_data = json.dumps(txan_data.get_data(), indent=4)
                data_stream = open(f"{self.output_path}\TXAN.json", "w")
                data_stream.write(str(json_data))
            
            self.send_progress(80)

            # Export other files in current STPK (SPR)
            i = 0
            if 'spr_stpk' in self.data.keys():
                if not os.path.exists(f"{self.output_path}\\pak_files"):
                    os.mkdir(f"{self.output_path}\\pak_files")

                for entry in self.data['spr_stpk'].entries:
                    if b'.spr' not in entry.name:
                        stream = open(f"{self.output_path}\\pak_files\\[{i}]{ut.b2s_name(entry.name)}", "wb")
                        stream.write(entry.data)
                        stream.close()
                        i += 1

            # DbzEyeInfo
            if len(scne_data[0].children) > 2:
                scne_dict = {}
                scne_dict['DbzEyeInfo'] = scne_data[0].children[2].get_data()['data']['eye_entries']
                json_data = json.dumps(scne_dict, indent=4)
                data_stream = open(f"{self.output_path}\SCNE.json", "w")
                data_stream.write(str(json_data))
            











            # -------------------------- create full BONE.xml
            global incBone
            global debugMeshs
            incBone = 0
            debugMeshs = []

            def createBoneNodeXml_recur(node_tmp, indentation, matrixToDisplay, boneList):
                global incBone
                global debugMeshs

                indent = ""
                for i in range(indentation):
                    indent += "\t"
                indentation += 1

                name = ut.b2s_name(node_tmp.name)
                extraAttributsStr = ""
                data = bone_dict[name] 


                node_TagName = "Bone"
                datasXml = ""
                if(indentation==0):
                    node_TagName = "Bones"
                else:
                    extraAttributsStr += ' index="'+ str(node_tmp.index) +'" '
                    #extraAttributsStr += '  hierarchy_bytes="'+ str(node_tmp.hierarchy_bytes) +'" unknown0x24="'+ str(node_tmp.unknown0x24) +'" '
                    #Todo better display of 0xxxx (that break the string)
                    # group_idx="'+ str(node_tmp.group_idx) +'"  => it's just the deep level in tree
                    
                    def createBoneNodeXml_recur_Matrix(name, t):
                        datasXml = ""
                        if((t[0][0]==1) and (t[1][1]==1) and (t[2][2]==1) and (t[3][3]==1) and (t[0][1]==0) and (t[0][2]==0) and (t[0][3]==0)  and (t[1][0]==0) and (t[1][2]==0) and (t[1][3]==0) and (t[2][0]==0)and (t[2][1]==0)and (t[2][3]==0) and (t[3][0]==0)and (t[3][1]==0)and (t[3][2]==0)):
                            datasXml += indent +'\t<'+ name +' IsIddentity="true" />\n'    
                        elif((t[0][0]==0) and (t[1][1]==0) and (t[2][2]==0) and (t[3][3]==0) and (t[0][1]==0) and (t[0][2]==0) and (t[0][3]==0)  and (t[1][0]==0) and (t[1][2]==0) and (t[1][3]==0) and (t[2][0]==0)and (t[2][1]==0)and (t[2][3]==0) and (t[3][0]==0)and (t[3][1]==0)and (t[3][2]==0)):
                            datasXml += indent +'\t<'+ name +' IsEmpty="true" />\n'    
                        else:
                            # here we take the transposed to get position on the last line as in Xenoverse ESK.xml
                            datasXml += indent +'\t<'+ name +'>\n'
                            for i in range(4):
                                datasXml += indent +'\t\t<Line x="'+ str(t[0][i]) +'" y="'+ str(t[1][i]) +'" z="'+ str(t[2][i]) +'" w="'+ str(t[3][i]) +'" />\n'
                            datasXml += indent +'\t</'+ name +'>\n'
                        return datasXml
                    
                    if(matrixToDisplay["abs_transform"]):
                        datasXml += createBoneNodeXml_recur_Matrix("AbsoluteTransformMatrix", node_tmp.abs_transform)
                    if(matrixToDisplay["inv_transform"]):
                        datasXml += createBoneNodeXml_recur_Matrix("InverseTransform", node_tmp.inv_transform)
                    if(matrixToDisplay["rel_transform"]):
                        datasXml += createBoneNodeXml_recur_Matrix("RelativeTransform", node_tmp.rel_transform)
                    if(matrixToDisplay["transform1"]):
                        t = node_tmp.transform1
                        minV3 = [t[0][0], t[1][0], t[2][0]]
                        maxV3 = [t[3][0], t[0][1], t[1][1]]
                        matrix3x3 = [[t[2][1], t[3][1], t[0][2]], [t[1][2], t[2][2], t[3][2]], [t[0][3], t[1][3], t[2][3]] ]
                        scale = t[3][3]
                        datasXml = ""
                        datasXml += indent +'\t<Transf_1>\n'
                        datasXml += indent +'\t\t<MinRotAngles x="'+ str(np.rad2deg(minV3[0])) +'" y="'+ str(np.rad2deg(minV3[1])) +'" z="'+ str(np.rad2deg(minV3[2])) +'" />\n'
                        datasXml += indent +'\t\t<MaxRotAngles x="'+ str(np.rad2deg(maxV3[0])) +'" y="'+ str(np.rad2deg(maxV3[1])) +'" z="'+ str(np.rad2deg(maxV3[2])) +'" />\n'
                        datasXml += indent +'\t\t<Matrix3>\n'
                        datasXml += indent +'\t\t\t<Line x="'+ str(matrix3x3[0][0]) +'" y="'+ str(matrix3x3[0][1]) +'" z="'+ str(matrix3x3[0][2]) +'" />\n'
                        datasXml += indent +'\t\t\t<Line x="'+ str(matrix3x3[1][0]) +'" y="'+ str(matrix3x3[1][1]) +'" z="'+ str(matrix3x3[1][2]) +'" />\n'
                        datasXml += indent +'\t\t\t<Line x="'+ str(matrix3x3[2][0]) +'" y="'+ str(matrix3x3[2][1]) +'" z="'+ str(matrix3x3[2][2]) +'" />\n'
                        datasXml += indent +'\t\t</Matrix3>\n'
                        datasXml += indent +'\t\t<UnknowScale value="'+ str(scale) +'" />\n'
                        datasXml += indent +'\t</Transf_1>\n'


                        def createBoneNodeXml_recur_CreateRotatedCube(minV3, maxV3, matrix3x3, scale, node_tmp, suffix):
                            global debugMeshs

                            debugMesh = {"name": ut.b2s_name(node_tmp.name)+ suffix, "vertices": [], "faces": []}
                            #if(debugMesh["name"] !="HAIR01_T1"):
                            #    return
                            
                            debugMeshs.append( debugMesh )
            
                            
                            #simple Cube, center on bottom center  Todo Remove
                            minV3 = [-0.5, -0.5, -0.5]
                            maxV3 = [0.5, 0.5, 0.5]


                            vertices = debugMesh["vertices"]
                            faces = debugMesh["faces"]
                            startVIndex = len(vertices)
                            startFIndex = len(faces)
                            
                            cubeVertex = [  [minV3[0], minV3[1], minV3[2]],\
                                            [maxV3[0], minV3[1], minV3[2]],\
                                            [maxV3[0], minV3[1], maxV3[2]],\
                                            [minV3[0], minV3[1], maxV3[2]],\
                                            [minV3[0], maxV3[1], minV3[2]],\
                                            [maxV3[0], maxV3[1], minV3[2]],\
                                            [maxV3[0], maxV3[1], maxV3[2]],\
                                            [minV3[0], maxV3[1], maxV3[2]] ]  # 0:A, 1:B, 2:C, 3:D, 4:E, 5:F, 6:G, 7:H
                            
                            #RotZ=-90 : X = -y, Y= x Z=Z
                            # cubeVertex = [  [minV3[1], -minV3[0], minV3[2]],\
                            #                 [minV3[1], -maxV3[0], minV3[2]],\
                            #                 [minV3[1], -maxV3[0], maxV3[2]],\
                            #                 [minV3[1], -minV3[0], maxV3[2]],\
                            #                 [maxV3[1], -minV3[0], minV3[2]],\
                            #                 [maxV3[1], -maxV3[0], minV3[2]],\
                            #                 [maxV3[1], -maxV3[0], maxV3[2]],\
                            #                 [maxV3[1], -minV3[0], maxV3[2]] ]  # 0:A, 1:B, 2:C, 3:D, 4:E, 5:F, 6:G, 7:H

                            #multiply by the Absolute Transform of Bone and matrix3x3
                            t = node_tmp.abs_transform
                            bone_AbsTf_Matrix4x4 = []
                            for i in range(4):
                                bone_AbsTf_Matrix4x4.append( [ t[0][i], t[1][i], t[2][i], t[3][i] ] )

                            t = node_tmp.inv_transform
                            bone_invTf_Matrix4x4 = []
                            for i in range(4):
                                bone_invTf_Matrix4x4.append( [ t[0][i], t[1][i], t[2][i], t[3][i] ] )

                            node_pos = ut.getPositionFromMat4(bone_AbsTf_Matrix4x4)

                            for i in range(len(cubeVertex)):
                                v = cubeVertex[i]

                                v = ut.multiply_Vect3_float(v, scale)

                                v = ut.multiply_Mat3_Vect3(ut.transpose_Mat3(matrix3x3), v)
                                v = ut.multiply_Mat4_Vect3(ut.transpose_Mat4(bone_AbsTf_Matrix4x4), v)
                                #v = ut.multiply_Mat4_Vect3(ut.transpose_Mat4(bone_invTf_Matrix4x4), v)
                                #v = ut.addVect3(v, node_pos)

                                vertices.append( {"position": {"x": v[0], "y": v[1], "z": v[2], "w": 1.0}, "bone_indices": node_tmp.index, "bone_weights": 1.0  } )    #Todo check how node_tmp.index is done in FBX.py
                            
                            #multiplcation with T1.UnkowwFloat ?

                            # Bottom ABCD
                            faces.append( [startFIndex + 0, startFIndex + 2, startFIndex + 1] )     # ACB
                            faces.append( [startFIndex + 0, startFIndex + 3, startFIndex + 2] )     # ADC
                            # Up EFGH
                            faces.append( [startFIndex + 4, startFIndex + 5, startFIndex + 6] )     # EFG
                            faces.append( [startFIndex + 4, startFIndex + 6, startFIndex + 7] )     # EGH
                            # Side ADHE
                            faces.append( [startFIndex + 0, startFIndex + 3, startFIndex + 7] )     # ADH
                            faces.append( [startFIndex + 0, startFIndex + 7, startFIndex + 4] )     # AHE
                            # Side FEAB
                            faces.append( [startFIndex + 5, startFIndex + 4, startFIndex + 0] )     # FEA
                            faces.append( [startFIndex + 5, startFIndex + 0, startFIndex + 1] )     # FAB
                            # Side GFBC
                            faces.append( [startFIndex + 6, startFIndex + 5, startFIndex + 1] )     # GFB
                            faces.append( [startFIndex + 6, startFIndex + 1, startFIndex + 2] )     # GBC
                            # Side HGCD
                            faces.append( [startFIndex + 7, startFIndex + 6, startFIndex + 2] )     # HGC
                            faces.append( [startFIndex + 7, startFIndex + 2, startFIndex + 3] )     # HCD
                        
                        
                        if(scale!=0):
                            createBoneNodeXml_recur_CreateRotatedCube(minV3, maxV3, matrix3x3, scale, node_tmp, "_T1")


                            

                            


                            


                        

                    if(matrixToDisplay["transform2"]):
                        datasXml += createBoneNodeXml_recur_Matrix("Transf_2", node_tmp.transform2)
                    

                    if((data) and (data["DbzBoneInfo"]) and (matrixToDisplay["DbzBoneInfo"])):
                        dbzBoneInfo = data["DbzBoneInfo"]
                        #datasXml += indent +'\t<DbzBoneInfo  unk0="'+ str(dbzBoneInfo["unknown0x00"]) +'" >\n'     # Todo solve display
                        #Todo better display of 0xxxx (that break the string)
                        datasXml += indent +'\t<DbzBoneInfo >\n'
                        listV3 = dbzBoneInfo["data"]
                        datasXml += indent +'\t\t<unk0 x="'+ str(listV3[0]) +'" y="'+ str(listV3[1]) +'" z="'+ str(listV3[2]) +'" >\n'
                        datasXml += indent +'\t\t<unk1 x="'+ str(listV3[3]) +'" y="'+ str(listV3[4]) +'" z="'+ str(listV3[5]) +'" >\n'
                        datasXml += indent +'\t\t<unk2 x="'+ str(listV3[6]) +'" y="'+ str(listV3[7]) +'" z="'+ str(listV3[8]) +'" >\n'
                        datasXml += indent +'\t</DbzBoneInfo>\n'
                        # => it's vextor3_sero, + negative Translation of RelativeMatrix  (twice vector, but why ?)

                    # Todo add traduction into position rotation scale (Absolute and relative)
                    # Todo look at the differencies with Inv and Abs Matrix (only position but why ?)
                

                haveChilds = ((node_tmp.children)and (len(node_tmp.children)))
                haveDatas = (datasXml!="")

                xmlStr = ""
                #xmlStr += indent +'<!--Index: '+ str(incBone) +'-->'
                incBone += 1
                xmlStr += indent +'<'+ node_TagName +' '+ ((' name="'+ name +'" ') if(name!="") else "") + extraAttributsStr + (">\n" if(haveChilds or haveDatas) else "/>\n")
                xmlStr += datasXml

                if(haveChilds):
                    
                    for i in range(len(node_tmp.children)):
                        xmlStr += createBoneNodeXml_recur(node_tmp.children[i], indentation, matrixToDisplay, boneList)
                    
                if(haveChilds or haveDatas):
                    xmlStr += (indent) +'</'+ node_TagName +'>\n'
                return xmlStr
            
            for i in range(len(bone_data[0].data.bone_entries)):
                bone_data[0].data.bone_entries[i].index = i

            incBone = 0
            debugMeshs = []
            matrixToDisplay = {"abs_transform": True, "inv_transform": True, "rel_transform": True, "transform1": True, "transform2": True, "DbzBoneInfo": False}
            xmlStr = createBoneNodeXml_recur(bone_data[0].data.bone_entries[0], 0, matrixToDisplay, bone_data[0].data.bone_entries)
            data_stream = open(f"{self.output_path}\BONE.xml", "w")
            data_stream.write(str(xmlStr))














            # -------------------------- create full SCEN.xml
            def createSceneNodeXml_recur(node_tmp, indentation):
                indent = ""
                for i in range(indentation):
                    indent += "\t"
                indentation += 1

                name = ut.b2s_name(node_tmp.name)
                
                realName = node_tmp.realName if(node_tmp.realName) else ""
                path = ""
                if(realName!=""):
                    path = name
                    name = realName
                    

                node_TagName = "Node"
                haveChildsTags = True
                datasXml = ""
                if(indentation==0):
                    node_TagName = "Scene"
                    haveChildsTags = False
                elif(name=="[LAYERS]"):
                    node_TagName = "LAYERS"
                    name = ""
                    haveChildsTags = False
                elif(name=="[NODES]"):
                    node_TagName = "NODES"
                    name = ""
                    haveChildsTags = False
                elif(name=="DbzEyeInfo"):
                    node_TagName = "DbzEyeInfo"
                    name = ""
                    haveChildsTags = False
                #elif(name=="[MATERIAL]"):      # Todo detect ":" for having the MaterialName (in that case haveChildsTags=false)
                #    aa= 42
                                                # todo make the 
                elif(name=="[MATERIAL]"):
                    node_TagName = "Material"
                    name = ut.b2s_name(node_tmp.data.name)
                    haveChildsTags = False

                    infos = node_tmp.data.infos
                    datasXml += indent +'\t<Mapping>\n'
                    for i in range(len(infos)):
                        info = infos[i]
                        datasXml += indent +'\t\t<Map name="'+ ut.b2s_name(info[0]) +'" map="'+ ut.b2s_name(info[1]) +'" sub="'+ str(info[2]) +'" />\n'
                    datasXml += indent +'\t</Mapping>\n'
                
                elif((node_tmp.data) and (ut.b2s_name(node_tmp.data.data_type)=="mesh")):
                    name_tmp = ut.b2s_name(node_tmp.data.name)
                    datasXml += indent +'\t<Mesh name="'+ name_tmp  +'" >\n'
                    haveChildsTags = False
                elif((node_tmp.data) and (ut.b2s_name(node_tmp.data.data_type)=="shape")):
                    name_tmp = ut.b2s_name(node_tmp.data.name)
                    datasXml += indent +'\t<Shape name="'+ name_tmp  +'" >\n'
                    haveChildsTags = False
                
                elif((node_tmp.data) and (ut.b2s_name(node_tmp.data.data_type)=="transform")):
                    datasXml += indent +'\t<Transform />\n'
                

                haveChilds = ((node_tmp.children)and (len(node_tmp.children)))
                haveDatas = (datasXml!="")

                xmlStr = indent +'<'+ node_TagName +' '+ ((' name="'+ name +'" ') if(name!="") else "") + ((' path="'+ path +'" ') if(path!="") else "") + (">\n" if(haveChilds or haveDatas) else "/>\n")
                xmlStr += datasXml

                if(haveChilds):
                    if(haveChildsTags):
                        xmlStr += indent +'\t<Childs>\n'
                        indentation += 1
                    for i in range(len(node_tmp.children)):
                        #xmlStr += createSceneNodeXml_recur(node_tmp.children[i], indentation)
                        xmlStr += createSceneNodeXml_recur(node_tmp.children[ (len(node_tmp.children) - 1) - i ], indentation)
                        if node_TagName == "NODES" :    #on Node , we take only the first (others should be children normaly)
                            break
                    
                    if(haveChildsTags):
                        xmlStr += indent +'\t</Childs>\n'

                if(haveChilds or haveDatas):
                    xmlStr += (indent) +'</'+ node_TagName +'>\n'
                return xmlStr


            #Try to get the tree version
            listNodes = scne_data[0].children[1].children
            listNodes_ToRemove = []

            for i in range(len(listNodes)):
                index = (len(listNodes) - 1) - i
                node_tmp = listNodes[ index ]            # hierarchy is inversed (but shape is in the same order as list, and may be VBuuf also.)

                realName = ut.b2s_name(node_tmp.name)
                parentName = realName
                
                sv = realName.split(":")
                if(len(sv)!=1):
                    parentName = sv[0]
                    realName = sv[1]
                else:
                    sv = realName.split("|")
                    if(len(sv)!=1):
                        tmp = sv[ len(sv) - 1]
                        parentName = realName[0:( len(realName) - (len(tmp) + 1) )]
                        realName = tmp
                
                node_tmp.realName = realName

                for j in range(index + 1, len(listNodes)):
                    if(ut.b2s_name(listNodes[j].name) == parentName):
                        listNodes[j].children.append( node_tmp )
                        listNodes_ToRemove.append( index )
                        break
            
            #for j in range(len(listNodes_ToRemove)):
            #    listNodes.pop(listNodes_ToRemove[j])                      # as listNodes_ToRemove is decroissante, it should be good
            
            xmlStr = createSceneNodeXml_recur(scne_data[0], 0)
            data_stream = open(f"{self.output_path}\SCNE.xml", "w")
            data_stream.write(xmlStr)

            

            











            # -------------------------- 

            # create a json vBuff.json file to get vbuuf in the same order to repack (and make comparaison with fbx txt or binary version of spr)
            vbuf_list = []
            for data in vbuf_data:
                if data.__class__.__name__ == "SPRPDataEntry":
                    vbuf_list.append(ut.b2s_name(data.name))
            json_data = json.dumps(vbuf_list, indent=4)
            data_stream = open(f"{self.output_path}\VBUF.json", "w")
            data_stream.write(str(json_data))
            


            fbx_object = FBX()
            fbx_object.data = {
                'bone': bone_data,
                'model': vbuf_data,
                'scene': scne_data,
                'texture': tx2d_data,
                'material': mtrl_data
            }
            fbx_object.save(self.output_path, debugMeshs)

            self.send_progress(100)
            self.result_signal.emit(self.__class__.__name__)
            self.finish_signal.emit()
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()