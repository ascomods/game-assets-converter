import os
import shutil
import re
import json
import glob
import numpy as np
from natsort import natsorted
from copy import deepcopy
from tasks.Task import Task
from core.STPZ import *
from core.STPK import *
from core.SPRP import *
from core.TX2D import *
from core.MTRL import *
from core.BMP import *
from core.BONE import *
from core.DDS import *
from core.SCNE import *
from core.SHAP import *
from core.VBUF import *
from core.FBX import *
import core.utils as ut
import core.common as cm

class ImportTask(Task):
    version_from_vertices_list = True

    def __init__(self, data, input_path, spr_path, ioram_path, vram_path, other_files):
        super().__init__()
        self.data = data
        self.input_path = input_path
        self.spr_path = spr_path
        self.ioram_path = ioram_path
        self.vram_path = vram_path
        self.other_files = other_files

    def run(self):
        try:
            ut.empty_temp_dir()
            ut.init_temp_dir()

            fbx_object = FBX()
            fbx_object.load(self.input_path)

            fbx_name = os.path.basename(self.input_path).rsplit('.', 1)[0]
            spr_name = os.path.basename(self.spr_path).rsplit('.', 1)[0]
            ioram_name = os.path.basename(self.ioram_path).rsplit('.', 1)[0]
            vram_name = os.path.basename(self.vram_path).rsplit('.', 1)[0]

            string_list = []
            spr_object = SPRP(ut.s2b_name(f"{spr_name}.spr"))
            spr_object.header_name = ut.s2b_name(f"{fbx_name}.xmb")
            spr_object.ioram_name = ut.s2b_name(f"{ioram_name}.ioram")
            spr_object.vram_name = ut.s2b_name(f"{vram_name}.vram")
            string_list.extend([spr_object.header_name, spr_object.ioram_name, spr_object.vram_name])

            spr = {
                'TX2D': SPRPEntry(spr_object.string_table, b'TX2D'),
                'MTRL': SPRPEntry(spr_object.string_table, b'MTRL'),
                'SHAP': SPRPEntry(spr_object.string_table, b'SHAP'),
                'VBUF': SPRPEntry(spr_object.string_table, b'VBUF'),
                'SCNE': SPRPEntry(spr_object.string_table, b'SCNE'),
                'BONE': SPRPEntry(spr_object.string_table, b'BONE'),
                'DRVN': SPRPEntry(spr_object.string_table, b'DRVN'),
                'TXAN': SPRPEntry(spr_object.string_table, b'TXAN')
            }

            # Load data from JSON files
            try:
                path = os.path.join(os.path.dirname(self.input_path), "MTRL.json")
                stream = open(path, "r")
                mtrl_dict = json.load(stream)
                stream.close()
            except:
                mtrl_dict = {}

            try:
                path = os.path.join(os.path.dirname(self.input_path), "SHAP.json")
                stream = open(path, "r")
                shap_dict = json.load(stream)
                stream.close()
            except:
                shap_dict = {}

            try:
                path = os.path.join(os.path.dirname(self.input_path), "VBUF.json")
                stream = open(path, "r")
                vbuf_dict = json.load(stream)
                stream.close()
            except:
                vbuf_dict = {}

            try:
                path = os.path.join(os.path.dirname(self.input_path), "SCNE.json")
                stream = open(path, "r")
                scne_dict = json.load(stream)
                stream.close()
            except:
                scne_dict = {}

            try:
                path = os.path.join(os.path.dirname(self.input_path), "BONE.json")
                stream = open(path, "r")
                loaded_bone_dict = json.load(stream)
                stream.close()
            except:
                loaded_bone_dict = {}

            try:
                path = os.path.join(os.path.dirname(self.input_path), "DRVN.json")
                stream = open(path, "r")
                drvn_dict = json.load(stream)
                stream.close()
            except:
                drvn_dict = {}

            try:
                path = os.path.join(os.path.dirname(self.input_path), "TXAN.json")
                stream = open(path, "r")
                txan_dict = json.load(stream)
                stream.close()
            except:
                txan_dict = {}

            self.send_progress(10)

            # Bones
            bone_object = BONE()
            bone_names = []
            bone_dict = {}

            for node in fbx_object.bone_nodes.values():
                bone_entry_object = BONE_DATA(bone_object.bone_string_table)
                bone_entry_object.name = ut.s2b_name(node.GetName())
                bone_names.append(bone_entry_object.name)
                
                gt = node.EvaluateGlobalTransform()
                it = node.EvaluateGlobalTransform().Inverse()
                lt = node.EvaluateLocalTransform()

                bone_entry_object.abs_transform = np.array([
                    tuple(gt.GetRow(0)),
                    tuple(gt.GetRow(1)),
                    tuple(gt.GetRow(2)),
                    tuple(gt.GetRow(3))
                ]).transpose()

                bone_entry_object.inv_transform = np.array([
                    tuple(it.GetRow(0)),
                    tuple(it.GetRow(1)),
                    tuple(it.GetRow(2)),
                    tuple(it.GetRow(3))
                ]).transpose()

                bone_entry_object.rel_transform = np.array([
                    tuple(lt.GetRow(0)),
                    tuple(lt.GetRow(1)),
                    tuple(lt.GetRow(2)),
                    tuple(lt.GetRow(3))
                ]).transpose()

                try:
                    bone_entry_object.transform1 = \
                        np.array(loaded_bone_dict[node.GetName()]['data']['transform1'])
                    bone_entry_object.transform2 = \
                        np.array(loaded_bone_dict[node.GetName()]['data']['transform2'])
                except:
                    pass

                bone_object.bone_entries.append(bone_entry_object)
                bone_dict[bone_entry_object.name] = bone_entry_object

            processed_bones = [ut.s2b_name(fbx_object.bone_names[0])]
            for node in fbx_object.bone_nodes.values():
                bone_name = ut.s2b_name(node.GetName())
                child_names = []
                
                for i in range(node.GetChildCount()):
                    child_name = ut.s2b_name(node.GetChild(i).GetName())
                    child_names.append(child_name)
                    if child_name not in processed_bones:
                        processed_bones.append(child_name)

                for bone in bone_object.bone_entries:
                    if bone.name == bone_name:
                        for child in bone_object.bone_entries:
                            if child.name in child_names:
                                bone.children.append(child)
            
            # Bone merging if multiple armatures
            remaining_bones = list(set(bone_names) - set(processed_bones))
            for bone_name in remaining_bones:
                idx = ut.search_index_dict(fbx_object.bone_names, ut.b2s_name(bone_name))
                node = fbx_object.bone_nodes[idx]
                bone = bone_dict[bone_name]
                parent_name = ut.s2b_name(node.GetParent().GetName())
                if parent_name != b'RootNode':
                    parentBone = bone_dict[parent_name]
                    parentBone.children.append(bone)

            bone_object.bone_string_table.build(bone_names)
            bone_object.sort_bones()
            string_list.append(bone_object.bone_entries[0].name)
            spr_data_entry = SPRPDataEntry(b'BONE', bone_object.bone_entries[0].name, spr_object.string_table, True)
            spr_data_entry.data = bone_object

            string_list.append(b'DbzBoneInfo')
            bone_info_object = BONE_INFO()

            try:
                first_bone_dict = list(loaded_bone_dict.values())[0]
                bone_char_info_name = list(first_bone_dict.keys())[2]
                string_list.append(ut.s2b_name(bone_char_info_name))
                bone_char_info_object = BONE_INFO()
                bone_char_info_object.info_size = 20
            except Exception as e:
                pass

            new_bone_info_dict = {}
            new_bone_char_info_dict = {}
            for bone in bone_object.bone_entries:
                try:
                    new_bone_info_dict[ut.b2s_name(bone.name)] = \
                        loaded_bone_dict[ut.b2s_name(bone.name)]['DbzBoneInfo']
                except:
                    new_bone_info_dict[ut.b2s_name(bone.name)] = {
                        'unknown0x00': "\u0000\u0000\u0000\u0000",
                        'data': [ 0.0, 0.0, 0.0,
                                  0.0, 0.0, 0.0,
                                  0.0, 0.0, 0.0 ]
                    }
                try:
                    new_bone_char_info_dict[ut.b2s_name(bone.name)] = \
                        loaded_bone_dict[ut.b2s_name(bone.name)][bone_char_info_name]
                except:
                    pass

            bone_info_object.load_data(new_bone_info_dict)
            spr_child_data_entry = SPRPDataEntry(b'BONE', b'DbzBoneInfo', spr_object.string_table)
            spr_child_data_entry.data = bone_info_object
            spr_data_entry.children.append(spr_child_data_entry)

            if new_bone_char_info_dict != {}:
                bone_char_info_object.load_data(new_bone_char_info_dict)
                spr_child_data_entry = SPRPDataEntry(b'BONE', 
                    ut.s2b_name(bone_char_info_name), spr_object.string_table)
                spr_child_data_entry.data = bone_char_info_object
                spr_data_entry.children.append(spr_child_data_entry)

            spr['BONE'].entries.append(spr_data_entry)

            self.send_progress(30)

            # Meshes
            materials = {}
            texture_names = []
            shapes = {}
            scne_parts = {}
            scene_layers = {}

            for mesh_name, data in fbx_object.mesh_data.items():
                layered_mesh_name = mesh_name
                layer_name, mesh_name = self.format_name(mesh_name, '', '')
                base_mesh_name = mesh_name
                try:
                    mesh_name = mesh_name.rsplit('|', 1)[1]
                except IndexError:
                    pass
                mesh_name = ut.s2b_name(mesh_name)

                try:
                    if layer_name != '':
                        scene_layers[mesh_name] = ut.s2b_name(layer_name)

                    vbuf_object = VBUF('', '', spr_object.string_table)

                    if not self.version_from_vertices_list:       
                        # Adjusting weights and indices data from FBX to RB format 
                        #  -> there are listed by bone/cluster and after by vertex, so you need to inverse lists, and get back layer notion
                        # it's already done into mode version_from_vertices_list
                        weights = data['bone_weights']
                        indices = data['bone_indices']
                        
                        all_weights = {}
                        all_indices = {}
                        for i in range(len(indices)):
                            for j in range(len(indices[i]['data'])):
                                key = list(indices[i]['data'][j].keys())[0]
                                if key not in all_indices:
                                    all_indices[key] = [indices[i]['data'][j][key]]
                                    all_weights[key] = [weights[i]['data'][j][key]]
                                else:
                                    all_indices[key].append(indices[i]['data'][j][key])
                                    all_weights[key].append(weights[i]['data'][j][key])

                        data_lists_count = 0
                        for i in range(len(data['positions'][0]['data'])):
                            if i not in all_indices.keys():
                                all_indices[i] = [0]
                                all_weights[i] = [0.0]
                            elif data_lists_count < len(all_indices[i]):
                                data_lists_count = len(all_indices[i])

                        # Adjusting lists to the same size
                        for i in range(len(data['positions'][0]['data'])):
                            if len(all_indices[i]) < data_lists_count:
                                for j in range(len(all_indices[i]), data_lists_count):
                                    all_indices[i].append(0)
                                    all_weights[i].append(0.0)
                        
                        data['bone_weights'] = []
                        data['bone_indices'] = []
                        
                        for i in range(data_lists_count):
                            data['bone_indices'].append({'data': []})
                            data['bone_weights'].append({'data': []})
                        
                        for i in range(len(all_indices)):
                            for j in range(len(all_indices[i])):
                                data['bone_indices'][j]['data'].append((all_indices[i][j],))
                                data['bone_weights'][j]['data'].append((all_weights[i][j],))

                    # Handle data from FBX
                    for vtx_usage, vtx_data_entries in data.items():
                        if vtx_usage in VBUF.vertex_usage_mapping.values():
                            index = 0
                            vbuf_object.data[vtx_usage] = []
                            
                            for vtx_data in vtx_data_entries:
                                decl_data = {}
                                decl_data['unknown0x00'] = '0'
                                try:
                                    decl_data['resource_name'] = ut.s2b_name(vtx_data['resource_name'])
                                    string_list.append(decl_data['resource_name'])
                                except:
                                    decl_data['resource_name'] = ''
                                vertex_usage_num = ut.search_index_dict(VBUF.vertex_usage_mapping, vtx_usage)
                                decl_data['vertex_usage'] = VBUF.vertex_usage[vertex_usage_num]
                                format_num = VBUF.vertex_format_mapping[vtx_usage]
                                decl_data['index'] = index
                                format = VBUF.vertex_format[format_num]
                                decl_data['vertex_format'] = format
                                decl_data['data'] = vtx_data['data']
                                
                                # Adjusting vertices positions and normals to RB format
                                if vtx_usage == 'positions':
                                    for i in range(len(decl_data['data'])):
                                        vtx = decl_data['data'][i]
                                        decl_data['data'][i] = (vtx[0], vtx[1], vtx[2], 1.0)
                                elif vtx_usage == 'normals':
                                    for i in range(len(decl_data['data'])):
                                        vtx = decl_data['data'][i]
                                        decl_data['data'][i] = (vtx[0], vtx[1], vtx[2], 0.0)
                                elif vtx_usage == 'binormals':
                                    for i in range(len(decl_data['data'])):
                                        vtx = decl_data['data'][i]
                                        decl_data['data'][i] = (vtx[0], vtx[1], vtx[2], 0.0)

                                elif ((self.version_from_vertices_list) and (vtx_usage == 'uvs')):
                                    for i in range(len(decl_data['data'])):
                                        vtx = decl_data['data'][i]
                                        decl_data['data'][i] = (vtx[0], vtx[1])

                                elif ((self.version_from_vertices_list) and (vtx_usage in ['bone_indices', 'bone_weights'])):
                                    for i in range(len(decl_data['data'])):
                                        decl_data['data'][i] = [decl_data['data'][i]]

                                vbuf_object.data[vtx_usage].append(decl_data)
                                index += 1
                    try:
                        material_name_parts = mesh_name.rsplit(b':')
                        if len(material_name_parts) > 2:
                            material_name = b':'.join(material_name_parts[1:])
                        else:
                            material_name = material_name_parts[1]
                    except Exception as e:
                        print(mesh_name)
                        print(e)
                        material_name = mesh_name + b'_mat'
                    string_list.append(material_name)

                    try:
                        mtrl_data = mtrl_dict[ut.b2s_name(material_name)]
                    except:
                        mtrl_data = None
                    
                    # Materials
                    if material_name not in materials.keys():
                        mtrl_object = MTRL('', material_name, spr_object.string_table)
                        if mtrl_data != None:
                            mtrl_object.load_data(mtrl_data)
                        for layer in data['materials']:
                            # Textures
                            layer_name, source_name, texture_names, spr_data_entry = \
                                self.add_texture(spr_object, texture_names, layer[0], layer[1])
                            if spr_data_entry != None:
                                spr['TX2D'].entries.append(spr_data_entry)
                            string_list.append(layer_name)

                            # name_parts = source_name.rsplit(b'.')
                            # if len(name_parts) > 2:
                            #     # source_name = name_parts[0]
                            #     # if b'EYEBALL1' in material_name:
                            #     #     source_name += ut.s2b_name('11')
                            #     num = int(name_parts[1])
                            #     if b'EYEBALL1' in material_name:
                            #         num += 1
                            #     source_name = \
                            #         b'.'.join([name_parts[0], ut.s2b_name(str(num)), name_parts[2]])
                            string_list.append(source_name)
                            mtrl_object.layers.append((layer_name, source_name))

                            # Textures not in materials
                            name_parts = layer[1].rsplit('.')
                            if len(name_parts) > 2:
                                num = int(name_parts[1]) + 1
                                texture_path = '.'.join([name_parts[0], str(num), name_parts[2]])
                                while os.path.exists(texture_path):
                                    layer_name, source_name, texture_names, spr_data_entry = \
                                        self.add_texture(spr_object, texture_names, '', texture_path)
                                    if spr_data_entry != None:
                                        spr['TX2D'].entries.append(spr_data_entry)
                                    string_list.append(source_name)
                                    num += 1
                                    texture_path = '.'.join([name_parts[0], str(num), name_parts[2]])
                        mtrl_object.sort(True)
                        
                        spr_data_entry = SPRPDataEntry(b'MTRL', material_name, spr_object.string_table, True)
                        spr_data_entry.data = mtrl_object

                        string_list.append(b'DbzCharMtrl')
                        mtrl_prop_object = MTRL_PROP('', b'DbzCharMtrl', spr_object.string_table)
                        if mtrl_data != None:
                            if 'DbzCharMtrl' in mtrl_data.keys():
                                mtrl_prop_object.load_data(mtrl_data['DbzCharMtrl'])
                        spr_child_data_entry = SPRPDataEntry(b'MTRL', b'DbzCharMtrl', spr_object.string_table)
                        spr_child_data_entry.data = mtrl_prop_object
                        spr_data_entry.children.append(spr_child_data_entry)

                        spr['MTRL'].entries.append(spr_data_entry)
                        materials[material_name] = spr_data_entry

                    # Shapes
                    try:
                        if base_mesh_name != ut.b2s_name(mesh_name):
                            shape_name = ut.s2b_name(base_mesh_name.split(':')[0])
                        else:
                            shape_name = mesh_name.split(b':')[0]
                    except:
                        shape_name = mesh_name
                    shap_name = shape_name + b'Shape'
                    string_list.append(shap_name)

                    try:
                        shap_data = shap_dict[ut.b2s_name(shap_name)]
                    except:
                        shap_data = None

                    if shape_name not in shapes.keys():
                        shape_object = SHAP('', shap_name, spr_object.string_table)
                        if shap_data:
                            shape_object.load_data(shap_data)
                        spr_data_entry = SPRPDataEntry(b'SHAP', shap_name, spr_object.string_table, True)
                        spr_data_entry.data = shape_object

                        string_list.append(b'DbzEdgeInfo')
                        shape_object = SHAP('', b'DbzEdgeInfo', spr_object.string_table)
                        if shap_data and 'DbzEdgeInfo' in shap_data.keys():
                            shape_object.load_data(shap_data['DbzEdgeInfo'])
                            if shape_object.source_name != b'':
                                string_list.append(shape_object.source_name)
                                # Add source texture if its missing
                                if shape_object.source_name not in texture_names:
                                    texture_name = ut.b2s_name(shape_object.source_name)
                                    texture_path = os.path.join(os.path.dirname(self.input_path), f"*{texture_name}")
                                    texture_path = glob.glob(texture_path)[0]
                                    layer_name, source_name, texture_names, texture_spr_data_entry = \
                                        self.add_texture(spr_object, texture_names, '', texture_path)
                                    if texture_spr_data_entry != None:
                                        spr['TX2D'].entries.append(texture_spr_data_entry)
                            if shape_object.source_type != b'':
                                string_list.append(shape_object.source_type)

                        spr_child_data_entry = SPRPDataEntry(b'SHAP', b'DbzEdgeInfo', spr_object.string_table)
                        spr_child_data_entry.data = shape_object
                        spr_data_entry.children.append(spr_child_data_entry)

                        string_list.append(b'DbzShapeInfo')
                        shape_object = SHAP('', b'DbzShapeInfo', spr_object.string_table)
                        spr_child_data_entry = SPRPDataEntry(b'SHAP', b'DbzShapeInfo', spr_object.string_table)
                        spr_child_data_entry.data = shape_object
                        spr_data_entry.children.append(spr_child_data_entry)

                        spr['SHAP'].entries.append(spr_data_entry)
                        shapes[shape_name] = spr_data_entry
                except Exception as e:
                    print(mesh_name)
                    print(e)
                    import traceback
                    print(traceback.format_exc())

                vbuf_object.load_data()
                if b'EYE' in mesh_name:
                    for i in range(len(vbuf_object.vertex_decl)):
                        if b'test1' in vbuf_object.vertex_decl[i]:
                            decl_list = list(vbuf_object.vertex_decl[i])
                            index = decl_list.index(b'test1')
                            decl_list[index] = b'eyeball'
                            vbuf_object.vertex_decl[i] = tuple(decl_list)

                if base_mesh_name != ut.b2s_name(mesh_name):
                    vbuf_name = ut.s2b_name(base_mesh_name)
                else:
                    mesh_name_parts = mesh_name.rsplit(b':')
                    if len(mesh_name_parts) > 2:
                        name = b':'.join(mesh_name_parts[1:])
                    else:
                        name = mesh_name_parts[1]
                    vbuf_name = ut.s2b_name(f"{ut.b2s_name(shap_name)}:{ut.b2s_name(name)}")
                string_list.append(vbuf_name)
                spr_data_entry = SPRPDataEntry(b'VBUF', vbuf_name, spr_object.string_table, True)
                spr_data_entry.data = vbuf_object
                spr['VBUF'].entries.append(spr_data_entry)

                mesh_node = fbx_object.mesh_nodes[layered_mesh_name]
                parents = []
                fbx_object.add_node_recursively(parents, mesh_node.GetParent())
                parents = parents[::-1]
                parent_names = []

                # SCNE Transform
                for i in range(len(parents)):
                    name = parents[i].GetName()
                    layer_name, full_name = self.format_name(name)

                    if (i + 1 < len(parents)):
                        for j in range(i + 1, len(parents)):
                            name = parents[j].GetName()
                            layer, full_name = self.format_name(name, full_name)
                    
                    parent_names.append(full_name)
                    if full_name not in scne_parts.keys():
                        full_name = ut.s2b_name(full_name)
                        string_list.append(full_name)
                        scne_transform_object = SCNE('', b'', spr_object.string_table)

                        if not parents[i].Show.Get():
                            scne_transform_object.unknown0x00 = 3
                        scne_transform_object.data_type = b'transform'
                        if layer_name != '':
                            layer_name = ut.s2b_name(layer_name)
                            scene_layers[full_name] = layer_name
                            scne_transform_object.layer_name = layer_name
                        parent_name = full_name.rsplit(b'|', 1)[0]
                        scne_transform_object.parent_name = parent_name
                        string_list.append(b'transform')

                        spr_data_entry = SPRPDataEntry(b'SCNE', full_name, spr_object.string_table)
                        spr_data_entry.data = scne_transform_object
                        scne_parts[full_name] = spr_data_entry

                # SCNE Mesh
                scene_mesh_name  = ut.s2b_name(f"{parent_names[0]}|{ut.b2s_name(mesh_name)}")
                if base_mesh_name != ut.b2s_name(mesh_name):
                    name = ut.b2s_name(shape_name).rsplit('|', 1)[1]
                    scene_shape_name = ut.s2b_name(f"{parent_names[0]}|{name}")
                else:
                    scene_shape_name = ut.s2b_name(f"{parent_names[0]}|{ut.b2s_name(shape_name)}")
                string_list.append(scene_mesh_name)
                scne_mesh_object = SCNE('', vbuf_name, spr_object.string_table)
                scne_mesh_object.data_type = b'mesh'

                if mesh_name in scene_layers.keys():
                    scne_mesh_object.layer_name = scene_layers[mesh_name]
                string_list.append(b'mesh')
                scne_mesh_object.parent_name = scene_shape_name

                # SCNE Material
                scne_material_object = SCNE_MATERIAL('', materials[material_name].name, spr_object.string_table)
                for layer in materials[material_name].data.layers:
                    if b'EYE' in mesh_name:
                        if layer[0] == b'COLORMAP0':
                            mat_type = b'eyeball'
                        elif layer[0] == b'COLORMAP1':
                            mat_type = b'map1'
                    elif layer[0] == b'COLORMAP1':
                        mat_type = b'damage'
                    elif layer[0] == b'NORMALMAP':
                        mat_type = b'normal'
                    else:
                        mat_type = b'map1'
                    string_list.append(mat_type)
                    scne_material_object.infos.append((layer[0], mat_type, 0))

                spr_data_entry = SPRPDataEntry(b'SCNE', scene_mesh_name, spr_object.string_table)
                spr_data_entry.data = scne_mesh_object
                spr_child_entry = SPRPDataEntry(b'SCNE', b'[MATERIAL]', spr_object.string_table)
                string_list.append(b'[MATERIAL]')
                spr_child_entry.data = scne_material_object
                spr_data_entry.children.append(spr_child_entry)
                scne_parts[scene_mesh_name] = spr_data_entry

                # SCNE Shape
                if scene_shape_name not in scne_parts.keys():
                    string_list.append(scene_shape_name)
                    scne_shape_object = SCNE('', shapes[shape_name].name, spr_object.string_table)
                    scne_shape_object.data_type = b'shape'
                    if mesh_name in scene_layers.keys():
                        scne_shape_object.layer_name = scene_layers[mesh_name]
                    string_list.append(b'shape')
                    scne_shape_object.parent_name = ut.s2b_name(parent_names[0])

                    spr_data_entry = SPRPDataEntry(b'SCNE', scene_shape_name, spr_object.string_table)
                    spr_data_entry.data = scne_shape_object
                    scne_parts[scene_shape_name] = spr_data_entry

            self.send_progress(60)

            string_list.append(b'[LAYERS]')
            scne_layers_entry = SPRPDataEntry(b'SCNE', b'[LAYERS]', spr_object.string_table)
            layer_names = set(scene_layers.values())

            for name in layer_names:
                string_list.append(name)
                layer_node = SPRPDataEntry(b'SCNE', name, spr_object.string_table)
                scne_layers_entry.children.append(layer_node)
            scne_layers_entry.sort()

            string_list.append(b'[NODES]')
            scne_nodes_entry = SPRPDataEntry(b'SCNE', b'[NODES]', spr_object.string_table)
            scne_nodes_entry.children = scne_parts.values()
            scne_nodes_entry.sort(True)

            if 'DbzEyeInfo' in scne_dict.keys():
                string_list.append(b'DbzEyeInfo')
                scne_eye_info_object = SCNE_EYE_INFO('', b'DbzEyeInfo', spr_object.string_table)
                scne_eye_info_object.load_data(scne_dict['DbzEyeInfo'])
                for entry in scne_eye_info_object.eye_entries:
                    if entry.name != b'':
                        string_list.append(entry.name)
                scne_eye_info_entry = SPRPDataEntry(b'SCNE', b'DbzEyeInfo', spr_object.string_table)
                scne_eye_info_entry.data = scne_eye_info_object

            scene_name = ut.s2b_name(f"{fbx_name}.fbx")
            string_list.append(scene_name)
            scne_main_entry = SPRPDataEntry(b'SCNE', scene_name, spr_object.string_table, True)
            scne_main_entry.children.append(scne_layers_entry)
            scne_main_entry.children.append(scne_nodes_entry)
            if 'DbzEyeInfo' in scne_dict.keys():
                scne_main_entry.children.append(scne_eye_info_entry)
            spr['SCNE'].entries.append(scne_main_entry)

            for name, content in drvn_dict.items():
                name = ut.s2b_name(name)
                string_list.append(name)
                spr_data_entry = SPRPDataEntry(b'DRVN', name, spr_object.string_table, True)
                spr_data_entry.data = content['data'].encode('latin-1')
                spr['DRVN'].entries.append(spr_data_entry)

            for name, content in txan_dict.items():
                name = ut.s2b_name(name)
                string_list.append(name)
                spr_data_entry = SPRPDataEntry(b'TXAN', name, spr_object.string_table, True)
                spr_data_entry.data = content['data'].encode('latin-1')
                spr['TXAN'].entries.append(spr_data_entry)

            for entry in spr.values():
                entry.sort()
                if len(entry.entries) > 0:
                    spr_object.entries.append(entry)

            #Try to keep previous MTRL order
            tmp_list = []
            for name, content in mtrl_dict.items():
                name = ut.s2b_name(name)

                for entry in spr['MTRL'].entries:
                    if entry.name == name:
                        tmp_list.append(entry)
                        spr['MTRL'].entries.remove(entry)
                        break

            for entry in spr['MTRL'].entries:
                tmp_list.append(entry)
            spr['MTRL'].entries = tmp_list

            #Same for Shape
            tmp_list = []
            for name, content in shap_dict.items():
                name = ut.s2b_name(name)

                for entry in spr['SHAP'].entries:
                    if entry.name == name:
                        tmp_list.append(entry)
                        spr['SHAP'].entries.remove(entry)
                        break

            for entry in spr['SHAP'].entries:
                tmp_list.append(entry)
            spr['SHAP'].entries = tmp_list

            #Same for VBUF
            tmp_list = []
            for name in vbuf_dict:
                name = ut.s2b_name(name)
            
                for entry in spr['VBUF'].entries:
                    if entry.name == name:
                        tmp_list.append(entry)
                        spr['VBUF'].entries.remove(entry)
                        break
            
            for entry in spr['VBUF'].entries:
                tmp_list.append(entry)
            spr['VBUF'].entries = tmp_list
            

            # Build ioram
            ioram_data = bytearray()
            for entry in spr['VBUF'].entries:
                vbuf_object = entry.data

                data = deepcopy(vbuf_object.get_data())
                for first_key, val in data.items():
                    i = 0
                    for elt in val:
                        for k, v in elt.items():
                            if isinstance(v, bytes):
                                data[first_key][i][k] = ut.b2s_name(v)
                        i += 1

                vbuf_object.ioram_data_offset = len(ioram_data)
                data = vbuf_object.get_ioram()
                padding = ut.add_padding(len(data))
                ioram_data.extend(data)
                ioram_data.extend(bytes(padding - len(data)))
                vbuf_object.load_data()
            self.data['ioram'] = ioram_data
            spr_object.ioram_data_size = len(ioram_data)

            # Build vram    
            vram_data = bytearray()
            for entry in spr['TX2D'].entries:
                tx2d_object = entry.data
                tx2d_object.vram_data_offset = len(vram_data)
                data = tx2d_object.get_vram()
                padding = ut.add_padding(len(data))
                vram_data.extend(data)
                padding_lenght = padding - len(data)

                if cm.selected_platform == 'ps3':
                    if cm.selected_game == 'dbrb2':
                        if tx2d_object.get_texture_type() == 'DXT1':
                            if tx2d_object.width == tx2d_object.height:
                                padding_lenght += 80
                            else:
                                padding_lenght += 32
                        elif tx2d_object.get_texture_type() in ['DXT5', 'ATI2']:
                            if tx2d_object.width == tx2d_object.height:
                                padding_lenght += 48
                            else:
                                padding_lenght += 80

                vram_data.extend(bytes(padding_lenght))

            self.data['vram'] = vram_data
            spr_object.vram_data_size = len(vram_data)

            # Remove duplicates from string table and build it
            string_list = natsorted(list(set(string_list)))
            spr_object.string_table.build(string_list, 1)
            self.data['spr'] = spr_object

            self.send_progress(80)

            if (self.data['spr'] != None) and (self.data['ioram'] != None) and (self.data['vram'] != None):
                self.save_file('spr', self.spr_path, self.other_files)
                self.save_file('ioram', self.ioram_path, [], True)
                self.save_file('vram', self.vram_path, [], True)
            else:
                raise Exception("Files couldn't be saved properly !")

            self.send_progress(100)
            self.result_signal.emit(self.__class__.__name__)
            self.finish_signal.emit()
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()

    def save_file(self, key, path, other_files = [], add_extra_bytes = False):
        name, ext = os.path.splitext(os.path.basename(path))
        if ext[-3:] == 'pak':
            stpk_key = f"{key}_stpk"
            self.data[stpk_key] = STPK(f"{name}.pak", 0, add_extra_bytes)

            self.data[stpk_key].add_entry(f"{name}.{key}", self.data[key])
            for other_file_path in other_files:
                filename = os.path.basename(other_file_path)
                filename = re.sub('^\[\d+\]', '', filename)
                stream = open(other_file_path, 'rb')
                self.data[stpk_key].add_entry(filename, stream.read())
                stream.close()

            if cm.selected_game == 'dbrb':
                operate_stpk = STPK(f"{name}.pak", 0, add_extra_bytes)
                operate_stpk.add_entry(f"op_{name}.pak", self.data[stpk_key])
                self.data[stpk_key] = operate_stpk
            
            stpk_path = os.path.join(cm.temp_path, f"{name}.pak")
            stream = open(stpk_path, 'wb')
            self.data[stpk_key].write(stream)
            stream.close()

            if ext == '.zpak':
                stpz_object = STPZ()
                stpz_object.compress(path)
            elif ext == '.pak':
                shutil.move(stpk_path, path)
        else:
            stream = open(path, 'wb')
            try:
                self.data[key].write(stream)
            except Exception:
                stream.write(self.data[key])
            stream.close()

    def format_name(self, name, full_name = '', sep = '|'):
        layer_name = re.findall(r'^\[(.*?)\]', name)
        if layer_name != []:
            layer_name = layer_name[0]
            name = name.replace(f"[{layer_name}]", '')
        else:
            layer_name = ''
        return layer_name, f"{sep}{name}{full_name}"

    def add_texture(self, spr_object, texture_names, source_layer_name = '', source_path = ''):
        layer_name, ext = os.path.splitext(source_layer_name)
        layer_name = ut.s2b_name(layer_name)

        source_name, ext = os.path.splitext(os.path.basename(source_path))
        source_name = ut.s2b_name(f"{source_name}{ext}")

        spr_data_entry = None

        if source_name not in texture_names:
            # Textures
            if ext[1:].upper() == 'BMP':
                tex_object = BMP(ut.b2s_name(source_name))
            elif ext[1:].upper() == 'DDS':
                tex_object = DDS(ut.b2s_name(source_name))
            else:
                raise Exception("Unknown texture format")
            stream = open(source_path, 'rb')
            tex_object.read(stream)
            tx2d_object = TX2D('', b'', spr_object.string_table)

            if ext[1:].upper() == 'BMP':
                tx2d_object.texture_type = 0
                tx2d_object.height = tex_object.bi_height
                tx2d_object.width = tex_object.bi_width
            elif ext[1:].upper() == 'DDS':
                if tex_object.type == b'DXT1':
                    tx2d_object.texture_type = int('0x8000000', base=16)
                elif tex_object.type == b'DXT5':
                    tx2d_object.unknown0x00 = ut.b2i(b'\x22')
                    tx2d_object.texture_type = int('0x18000000', base=16)
                elif tex_object.type == b'ATI2':
                    tx2d_object.texture_type = int('0x20000000', base=16)
                tx2d_object.mipmap_count = tex_object.mipmap_count
                tx2d_object.height = tex_object.height
                tx2d_object.width = tex_object.width
            
            if (b'TOONMAP' in layer_name) or (b'_RAMP' in layer_name):
                if cm.selected_platform == 'x360':
                    tx2d_object.unknown0x00 = ut.b2i(b'\x82')
                tx2d_object.unknown0x1C = ut.b2i(b'\xA7\x2D\x0A\x80')
            else:
                tx2d_object.unknown0x1C = ut.b2i(b'\xA7\x28\x0A\x80')

            # Setting data + swizzling if needed
            tx2d_object.vram_data = tex_object.data
            tx2d_object.vram_data = tx2d_object.get_swizzled_vram_data()
            tx2d_object.vram_data_size = len(tx2d_object.vram_data)

            spr_data_entry = SPRPDataEntry(b'TX2D', source_name, spr_object.string_table, True)
            spr_data_entry.data = tx2d_object
            texture_names.append(source_name)

        return layer_name, source_name, texture_names, spr_data_entry