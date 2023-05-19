import os
import shutil
import json
import numpy as np
from natsort import natsorted
from copy import deepcopy
from core.STPZ import *
from core.STPK import *
from core.SPRP.SPRP import *
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

class SPRPImporter:
    version_from_vertices_list = True

    def start(self, spr_object, spr_folder_path):
        cm.main_handler.task.send_progress(0)

        fbx_found = True
        if not os.path.exists(os.path.join(spr_folder_path, "output.fbx")):
            print(
                f"output.fbx is missing in: {spr_folder_path}\n"
                f"No model data will be imported back for this folder."
            )
            fbx_found = False

        if fbx_found:
            fbx_object = FBX()
            fbx_object.load(os.path.join(spr_folder_path, "output.fbx"))

        string_list = []
        base_name, ext = os.path.splitext(ut.b2s_name(spr_object.name))
        spr_object.header_name = ut.s2b_name(f"{base_name}.xmb")
        spr_object.vram_name = ut.s2b_name(f"{base_name}.vram")
        string_list.extend([spr_object.header_name, spr_object.vram_name])
        if fbx_found:
            spr_object.ioram_name = ut.s2b_name(f"{base_name}.ioram")
            string_list.append(spr_object.ioram_name)

        spr = {}
        loaded_dict = {}
        for filename in os.listdir(spr_folder_path):
            name, ext = os.path.splitext(filename)
            if ext.lower() == '.json':
                stream = open(os.path.join(spr_folder_path, filename), "r")
                loaded_dict[name] = json.load(stream)
                stream.close()

        cm.main_handler.task.send_progress(20)

        if fbx_found:
            # Bones
            if hasattr(fbx_object, 'bone_nodes'):
                self.build_bones(spr, spr_object, fbx_object, loaded_dict, string_list)
            
            cm.main_handler.task.send_progress(30)

            # Meshes
            materials = {}
            texture_names = []
            shapes = {}
            scne_parts = {}
            scene_layers = {}
            scne_mesh_full_names = {}

            for mesh_name, data in fbx_object.mesh_data.items():
                layered_mesh_name = mesh_name
                layer_name, mesh_name = self.format_name(mesh_name, '', '')
                mesh_name = ut.s2b_name(mesh_name)
                mesh_name = mesh_name.rsplit(b'|', 1)[-1]

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
                        elif ((cm.selected_game in ['dbut', 'dbzb']) and (vtx_usage == 'face_indices')):
                            vbuf_object.face_indices = vtx_data_entries

                    # Materials
                    for material_name, material_data in data['materials'].items():
                        mtrl_data = None
                        if ('MTRL' in loaded_dict):
                            if (material_name in loaded_dict['MTRL']):
                                mtrl_data = loaded_dict['MTRL'][material_name]
                        
                        if len(material_data) > 0:
                            if 'TX2D' not in spr.keys():
                                spr['TX2D'] = SPRPEntry(spr_object.string_table, b'TX2D')
                            if 'MTRL' not in spr.keys():
                                spr['MTRL'] = SPRPEntry(spr_object.string_table, b'MTRL')

                        material_name = ut.s2b_name(material_name)
                        if material_name not in materials.keys():
                            mtrl_object = MTRL('', material_name, spr_object.string_table)
                            if mtrl_data != None:
                                mtrl_object.load_data(mtrl_data)
                            for layer in material_data:
                                # Textures
                                layer_name, source_name, texture_names, spr_data_entry = \
                                    self.add_texture(spr_object, texture_names, layer[0], layer[1])
                                if spr_data_entry != None:
                                    spr['TX2D'].entries.append(spr_data_entry)
                                string_list.append(layer_name)
                                string_list.append(source_name)
                                mtrl_object.layers.append((layer_name, source_name))

                                # Textures not in materials
                                folder_path, name = os.path.split(layer[1])
                                name_parts = name.rsplit('.')
                                if len(name_parts) > 2:
                                    num = int(name_parts[1]) + 1
                                    texture_path = '.'.join([name_parts[0], str(num), name_parts[2]])
                                    texture_path = os.path.join(folder_path, texture_path)
                                    while os.path.exists(texture_path):
                                        layer_name, source_name, texture_names, spr_data_entry = \
                                            self.add_texture(spr_object, texture_names, '', texture_path)
                                        if spr_data_entry != None:
                                            spr['TX2D'].entries.append(spr_data_entry)
                                        string_list.append(source_name)
                                        num += 1
                                        texture_path = '.'.join([name_parts[0], str(num), name_parts[2]])
                                        texture_path = os.path.join(folder_path, texture_path)
                            mtrl_object.sort(True)
                            
                            spr_data_entry = SPRPDataEntry(b'MTRL', material_name, spr_object.string_table, True)
                            spr_data_entry.data = mtrl_object

                            has_char_mtrl = False
                            if mtrl_data != None:
                                if 'children' in mtrl_data.keys():
                                    for child_name, child_data in mtrl_data['children'].items():
                                        if child_name == 'DbzCharMtrl':
                                            has_char_mtrl = True
                                        string_list.append(ut.s2b_name(child_name))
                                        mtrl_prop_object = \
                                            MTRL_PROP('', ut.s2b_name(child_name), spr_object.string_table)
                                        mtrl_prop_object.load_data(mtrl_data['children'][child_name])

                                        spr_child_data_entry = \
                                            SPRPDataEntry(b'MTRL', ut.s2b_name(child_name), spr_object.string_table)
                                        spr_child_data_entry.data = mtrl_prop_object
                                        spr_data_entry.children.append(spr_child_data_entry)
                            
                            if not has_char_mtrl:
                                string_list.append(b'DbzCharMtrl')
                                mtrl_prop_object = MTRL_PROP('', b'DbzCharMtrl', spr_object.string_table)
                                spr_child_data_entry = \
                                    SPRPDataEntry(b'MTRL', b'DbzCharMtrl', spr_object.string_table)
                                spr_child_data_entry.data = mtrl_prop_object
                                spr_data_entry.children.append(spr_child_data_entry)

                            spr['MTRL'].entries.append(spr_data_entry)
                            materials[material_name] = spr_data_entry
                            string_list.append(material_name)

                    if 'SHAP' not in spr.keys():
                        spr['SHAP'] = SPRPEntry(spr_object.string_table, b'SHAP')

                    # Shapes
                    try:
                        shape_name = mesh_name.split(b':')[0]
                    except:
                        shape_name = mesh_name
                    shap_name = shape_name + b'Shape'
                    string_list.append(shap_name)

                    try:
                        shap_data = loaded_dict['SHAP'][ut.b2s_name(shap_name)]
                    except:
                        shap_data = None

                    if shape_name not in shapes.keys():
                        spr_data_entry = self.build_shape(spr, spr_object, texture_names,
                            string_list, shap_name, shap_data, spr_folder_path)
                        spr['SHAP'].entries.append(spr_data_entry)
                        shapes[shape_name] = spr_data_entry
                except Exception as e:
                    print(mesh_name)
                    import traceback
                    traceback.print_exc()
                    print(e)
                
                if 'VBUF' not in spr.keys():
                    spr['VBUF'] = SPRPEntry(spr_object.string_table, b'VBUF')

                vbuf_object.load_data()
                if b'EYE' in mesh_name:
                    for i in range(len(vbuf_object.vertex_decl)):
                        if b'test1' in vbuf_object.vertex_decl[i]:
                            decl_list = list(vbuf_object.vertex_decl[i])
                            index = decl_list.index(b'test1')
                            decl_list[index] = b'eyeball'
                            vbuf_object.vertex_decl[i] = tuple(decl_list)

                mesh_name_parts = mesh_name.rsplit(b':')
                if len(mesh_name_parts) > 2:
                    name = b':'.join(mesh_name_parts[1:])
                else:
                    name = mesh_name_parts[-1]
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

                if 'SCNE' not in spr.keys():
                    spr['SCNE'] = SPRPEntry(spr_object.string_table, b'SCNE')

                # SCNE Transform
                for i in range(len(parents)):
                    name = parents[i].GetName()
                    layer_name, full_name = self.format_name(name)

                    if (i + 1 < len(parents)):
                        for j in range(i + 1, len(parents)):
                            name = parents[j].GetName()
                            layer, full_name = self.format_name(name, full_name)
                    
                    parent_names.append(full_name)
                    full_name = ut.s2b_name(full_name)
                    if full_name not in scne_parts.keys():
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
                if len(parent_names) == 0:
                    parent_names = ['']
                scene_mesh_name  = ut.s2b_name(f"{parent_names[0]}|{ut.b2s_name(mesh_name)}")
                scene_shape_name = ut.s2b_name(f"{parent_names[0]}|{ut.b2s_name(shape_name)}")
                string_list.append(scene_mesh_name)
                scne_mesh_object = SCNE('', vbuf_name, spr_object.string_table)
                scne_mesh_object.data_type = b'mesh'

                if mesh_name in scene_layers.keys():
                    scne_mesh_object.layer_name = scene_layers[mesh_name]
                string_list.append(b'mesh')
                scne_mesh_object.parent_name = scene_shape_name

                # SCNE Material
                scne_material_object = \
                    SCNE_MATERIAL('', material_name, spr_object.string_table)
                for layer in materials[material_name].data.layers:
                    mat_type = b'map1'
                    if b'EYE' in mesh_name:
                        if layer[0] == b'COLORMAP0':
                            mat_type = b'eyeball'
                        elif layer[0] == b'COLORMAP1':
                            mat_type = b'map1'
                    elif layer[0] == b'COLORMAP1':
                        mat_type = b'damage'
                    elif layer[0] == b'NORMALMAP':
                        mat_type = b'normal'
                    string_list.append(mat_type)
                    scne_material_object.infos.append((layer[0], mat_type, 0))

                spr_data_entry = SPRPDataEntry(b'SCNE', scene_mesh_name, spr_object.string_table)
                spr_data_entry.data = scne_mesh_object
                spr_child_entry = SPRPDataEntry(b'SCNE', b'[MATERIAL]', spr_object.string_table)
                string_list.append(b'[MATERIAL]')
                spr_child_entry.data = scne_material_object
                spr_data_entry.children.append(spr_child_entry)
                scne_parts[scene_mesh_name] = spr_data_entry
                # Store mesh name from fbx node to do a matching
                #scene_mesh_name = re.sub('_#\d+', '', ut.b2s_name(scene_mesh_name))
                #scene_mesh_name = ut.s2b_name(scene_mesh_name)
                mesh_full_name = mesh_node.GetMesh().GetName().replace('_mesh', '')
                #if (scene_mesh_name not in scne_mesh_full_names):
                #    scne_mesh_full_names[scene_mesh_name] = []
                #scne_mesh_full_names[scene_mesh_name].append(mesh_full_name)
                scne_mesh_full_names[scene_mesh_name] = mesh_full_name

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

            cm.main_handler.task.send_progress(60)

            # TODO: check and clean SCNE import code

            if ('SCNE' in loaded_dict) and ('SCNE' in spr.keys()):
                string_list.append(b'[LAYERS]')
                scne_layers_entry = SPRPDataEntry(b'SCNE', b'[LAYERS]', spr_object.string_table)
                layer_names = set(scene_layers.values())

                for name in layer_names:
                    string_list.append(name)
                    layer_node = SPRPDataEntry(b'SCNE', name, spr_object.string_table)
                    scne_layers_entry.children.append(layer_node)
                # Adding missing layers using SCNE.json
                if '[LAYERS]' in loaded_dict['SCNE'].keys():
                    if 'children' in loaded_dict['SCNE']['[LAYERS]'].keys():
                        for key, content in loaded_dict['SCNE']['[LAYERS]']['children'].items():
                            key = ut.s2b_name(key)
                            if key not in layer_names:
                                string_list.append(key)
                                layer_node = SPRPDataEntry(b'SCNE', key, spr_object.string_table)
                                scne_layers_entry.children.append(layer_node)
                scne_layers_entry.sort()

                for node_name, node in fbx_object.other_nodes.items():
                    layered_mesh_name = node_name
                    layer_name, node_name = self.format_name(node_name, '', '')
                    base_node_name = node_name
                    try:
                        node_name = node_name.rsplit('|', 1)[1]
                    except IndexError:
                        pass
                    node_name = ut.s2b_name(node_name)

                    try:
                        if base_node_name != ut.b2s_name(node_name):
                            shape_name = ut.s2b_name(base_node_name.split(':')[0])
                        else:
                            shape_name = node_name.split(b':')[0]
                    except:
                        shape_name = node_name

                    if layer_name != '':
                        scene_layers[node_name] = ut.s2b_name(layer_name)
                        string_list.append(scene_layers[node_name])
                    
                    parents = []
                    fbx_object.add_node_recursively(parents, node.GetParent())
                    parents = parents[::-1]
                    parent_names = []

                    if 'SCNE' not in spr.keys():
                        spr['SCNE'] = SPRPEntry(spr_object.string_table, b'SCNE')

                    # # SCNE Transform
                    # for i in range(len(parents)):
                    #     name = parents[i].GetName()
                    #     layer_name, full_name = self.format_name(name)
                    #     string_list.append(ut.s2b_name(layer_name))

                    #     if (i + 1 < len(parents)):
                    #         for j in range(i + 1, len(parents)):
                    #             name = parents[j].GetName()
                    #             layer, full_name = self.format_name(name, full_name)
                        
                    #     parent_names.append(full_name)
                    #     if full_name not in scne_parts.keys():
                    #         full_name = ut.s2b_name(full_name)
                    #         string_list.append(full_name)
                    #         scne_transform_object = SCNE('', b'', spr_object.string_table)

                    #         if not parents[i].Show.Get():
                    #             scne_transform_object.unknown0x00 = 3
                    #         scne_transform_object.data_type = b'transform'
                    #         if layer_name != '':
                    #             layer_name = ut.s2b_name(layer_name)
                    #             scene_layers[full_name] = layer_name
                    #             scne_transform_object.layer_name = layer_name
                    #         parent_name = full_name.rsplit(b'|', 1)[0]
                    #         scne_transform_object.parent_name = parent_name
                    #         string_list.append(b'transform')

                    #         spr_data_entry = SPRPDataEntry(b'SCNE', full_name, spr_object.string_table)
                    #         spr_data_entry.data = scne_transform_object
                    #         scne_parts[full_name] = spr_data_entry

                    # # SCNE Node
                    # if len(parent_names) == 0:
                    #     parent_names = ['']
                    # scene_node_name  = ut.s2b_name(f"{parent_names[0]}|{ut.b2s_name(node_name)}")
                    # string_list.append(node_name)
                    # if base_node_name != ut.b2s_name(node_name):
                    #     name = ut.b2s_name(shape_name).rsplit('|', 1)[1]
                    #     scene_shape_name = ut.s2b_name(f"{parent_names[0]}|{name}")
                    # else:
                    #     scene_shape_name = ut.s2b_name(f"{parent_names[0]}|{ut.b2s_name(shape_name)}")
                    # #scene_shape_name = ut.s2b_name(parent_names[0])
                    # string_list.append(scene_node_name)
                    # string_list.append(scene_shape_name)
                    # scne_node_object = SCNE('', node_name, spr_object.string_table)
                    # scne_node_object.data_type = b'shape'
                    # if scene_shape_name in scene_layers.keys():
                    #     scne_node_object.layer_name = scene_layers[node_name]
                    # string_list.append(b'shape')

                    # if parent_names != ['']:
                    #     string_list.append(ut.s2b_name(parent_names[0]))
                    #     scne_node_object.parent_name = ut.s2b_name(parent_names[0])
                    # spr_data_entry = SPRPDataEntry(b'SCNE', scene_shape_name, spr_object.string_table)
                    # spr_data_entry.data = scne_node_object
                    # scne_parts[scene_node_name] = spr_data_entry

                    # if ut.b2s_name(scene_node_name) in \
                    #     loaded_dict['SCNE']['[NODES]']['children'].keys():
                    #     content = loaded_dict['SCNE']['[NODES]'] \
                    #         ['children'][ut.b2s_name(scene_node_name)]
                    #     scne_node_object.load_data(content['data'])
                    #     string_list.append(scne_node_object.data_type)

                    #     if 'children' in content.keys():
                    #         for key, child in content['children'].items():
                    #             if '|#|' in key:
                    #                 key = key.rsplit('|#|')[1]
                    #             string_list.append(ut.s2b_name(key))
                    #             spr_child_entry = \
                    #                 SPRPDataEntry(b'SCNE', ut.s2b_name(key), spr_object.string_table)
                    #             try:
                    #                 spr_child_entry.data = child['data'].encode('latin-1')
                    #                 spr_data_entry.children.append(spr_child_entry)
                    #             except Exception as e:
                    #                 print(e)
                    #                 pass

                    # if scne_node_object.data_type == b'shape':
                    #     if shape_name not in shapes.keys():
                    #         string_list.append(shape_name)
                    #         spr_shape_entry = \
                    #             self.build_shape(spr, spr_object, texture_names, string_list, shape_name)
                    #         spr['SHAP'].entries.append(spr_shape_entry)
                    #         shapes[shape_name] = spr_shape_entry


                    # # SCNE Shape
                    # print(scene_shape_name)
                    # if (scene_shape_name != b'') and (scene_shape_name not in scne_parts.keys()):
                    #     string_list.append(shape_name)
                    #     scne_shape_object = SCNE('', shape_name, spr_object.string_table)
                    #     scne_shape_object.data_type = b'shape'
                    #     if node_name in scene_layers.keys():
                    #         scne_shape_object.layer_name = scene_layers[node_name]
                    #     string_list.append(b'shape')
                    #     scne_shape_object.parent_name = ut.s2b_name(parent_names[0])
                    #     string_list.append(scne_shape_object.parent_name)

                    #     spr_data_entry = SPRPDataEntry(b'SCNE', scene_shape_name, spr_object.string_table)
                    #     spr_data_entry.data = scne_shape_object
                    #     scne_parts[scene_shape_name] = spr_data_entry
                    # if shape_name != b'':
                    #     shapes[shape_name] = ''

                string_list.append(b'[NODES]')
                scne_nodes_entry = SPRPDataEntry(b'SCNE', b'[NODES]', spr_object.string_table)
                
                if '[NODES]' in loaded_dict['SCNE'].keys():
                    #scne_nodes = []

                    # Use nodes from SCNE.json to fix blender scene nodes
                    if cm.use_blender:
                        new_scne_parts = {}
                        scne_names_to_remove = []
                        for loaded_key, loaded_node in loaded_dict['SCNE']['[NODES]']['children'].items():
                            loaded_key = ut.s2b_name(loaded_key)
                            # Complete node information
                            for scne_key, scne_node in scne_parts.items():
                                if (scne_node.data.data_type == b'mesh') and \
                                   (scne_mesh_full_names[scne_key] == loaded_node['data']['name']):
                                    scne_shape_name = scne_node.data.parent_name
                                    new_scne_parts[loaded_key] = scne_node
                                    new_scne_parts[loaded_key].name = loaded_key
                                    new_scne_parts[loaded_key].data.load_data(loaded_node['data'])
                                    string_list.append(loaded_key)
                                    string_list.append(new_scne_parts[loaded_key].data.data_type)
                                    string_list.append(new_scne_parts[loaded_key].data.parent_name)
                                    string_list.remove(scne_key)
                                    del scne_parts[scne_key]
                                    # Update shape name if it exists
                                    if (scne_shape_name in scne_parts):
                                        shape_node_name = ut.b2s_name(new_scne_parts[loaded_key].data.parent_name)
                                        loaded_shape_node = loaded_dict['SCNE']['[NODES]']['children'][shape_node_name]
                                        loaded_shape_node['data']['name'] = ut.b2s_name(scne_parts[scne_shape_name].data.name)
                                        scne_names_to_remove.append(scne_shape_name)
                                        del scne_parts[scne_shape_name]
                                        string_list.remove(scne_shape_name)
                                        for scne_node in scne_parts.values():
                                            if scne_node.data.parent_name == scne_shape_name:
                                                scne_node.data.parent_name = new_scne_parts[loaded_key].data.parent_name
                                    break
                            if (loaded_key not in new_scne_parts):
                                for scne_key, scne_node in scne_parts.items():
                                    name_part = b'|' + loaded_key.split(b'|')[-1]
                                    if ((scne_key == name_part) and (loaded_key not in new_scne_parts)):
                                        new_scne_parts[loaded_key] = scne_node
                                        new_scne_parts[loaded_key].name = loaded_key
                                        new_scne_parts[loaded_key].data.load_data(loaded_node['data'])
                                        string_list.append(loaded_key)
                                        string_list.append(new_scne_parts[loaded_key].data.data_type)
                                        string_list.append(new_scne_parts[loaded_key].data.parent_name)
                                        string_list.remove(scne_key)
                                        del scne_parts[scne_key]
                                        break
                            # Adding missing nodes
                            if (loaded_key not in new_scne_parts) and \
                               (loaded_key not in scne_parts) and \
                               (loaded_node['data']['data_type'] != 'mesh'):
                                name = b''
                                found = False
                                # Add node only if it is used already
                                for scne_key, scne_node in new_scne_parts.items():
                                    if (loaded_key == scne_node.data.parent_name):
                                        if (loaded_node['data']['data_type'] == 'shape'):
                                            name = loaded_key.split(b'|')[-1] + b'Shape'
                                        found = True
                                        break
                                if found:
                                    string_list.append(name)
                                    new_scne_parts[loaded_key] = \
                                        SPRPDataEntry(b'SCNE', loaded_key, spr_object.string_table)
                                    new_scne_parts[loaded_key].data = SCNE('', name, spr_object.string_table)
                                    new_scne_parts[loaded_key].data.load_data(loaded_node['data'])
                                    string_list.append(loaded_key)
                                    string_list.append(new_scne_parts[loaded_key].data.data_type)
                                    string_list.append(new_scne_parts[loaded_key].data.parent_name)
                        # Fix missing transform nodes for new model parts
                        if (b'|model' in new_scne_parts):
                            for scne_node in scne_parts.values():
                                if (scne_node.data.data_type == b'shape') and (scne_node.data.parent_name == b''):
                                    scne_node.data.parent_name = b'|model'
                        # Merge nodes that weren't found in existing nodes from SCNE.json
                        scne_parts.update(new_scne_parts)
                        # Fix missing transform string
                        string_list.append(b'transform')

                    # Try to keep original scene hierarchy
                    # If new nodes are found,they are inserted at the beggining
                    new_scne_parts = {}
                    for node_name in loaded_dict['SCNE']['[NODES]']['children'].keys():
                        node_name = ut.s2b_name(node_name)
                        for name, part in scne_parts.items():
                            if (name == node_name) and (name not in new_scne_parts):
                                new_scne_parts[name] = part
                                break

                    remaining_scne_parts = {}
                    for name in scne_parts.keys():
                        if name not in new_scne_parts:
                            remaining_scne_parts[name] = scne_parts[name]
                    scne_parts = {**remaining_scne_parts, **new_scne_parts}

                scne_nodes_entry.children = list(scne_parts.values())
                #scne_nodes_entry.sort(True)

                # if '[NODES]' in loaded_dict['SCNE'].keys():
                #     scne_nodes = []
                #     for key, content in loaded_dict['SCNE']['[NODES]']['children'].items():
                #         key = ut.s2b_name(key)
                #         if key in scne_parts.keys():
                #             if content['data']['data_type'] != 'mesh':
                #                 string_list.append(key)
                #                 scne_object = scne_parts[key].data
                #                 scne_object.load_data(content['data'])

                #                 if scne_object.data_type == b'shape':
                #                     name = scne_parts[key].data.name
                #                     # for shape_key in shapes.keys():
                #                     #     if shape_key in name:
                #                     #         name = shape_key
                #                     #         break
                #                     if name not in shapes.keys():
                #                         string_list.append(name)
                #                         spr_data_entry = \
                #                             self.build_shape(spr, spr_object, string_list, name)
                #                         spr['SHAP'].entries.append(spr_data_entry)
                #                         shapes[name] = spr_data_entry
                #                 string_list.extend([scne_object.data_type, scne_object.name,
                #                     scne_object.layer_name, scne_object.parent_name])
                                
                #                 spr_data_entry = scne_parts[key]
                #                     #SPRPDataEntry(b'SCNE', key, spr_object.string_table)
                #                 spr_data_entry.data = scne_object
                #                 if 'children' in content.keys():
                #                     for key, child in content['children'].items():
                #                         if '|#|' in key:
                #                             key = key.rsplit('|#|')[1]
                #                         string_list.append(ut.s2b_name(key))
                #                         spr_child_entry = \
                #                             SPRPDataEntry(b'SCNE', ut.s2b_name(key), spr_object.string_table)
                #                         spr_child_entry.data = child['data'].encode('latin-1')
                #                         spr_data_entry.children.append(spr_child_entry)


                                #scne_nodes.append(spr_data_entry)
                    #scne_nodes_entry.children = scne_nodes + scne_nodes_entry.children
                scene_name = ut.s2b_name(f"{base_name}.fbx")
                string_list.append(scene_name)
                scne_main_entry = SPRPDataEntry(b'SCNE', scene_name, spr_object.string_table, True)
                scne_main_entry.children.append(scne_layers_entry)
                scne_main_entry.children.append(scne_nodes_entry)

                if 'DbzEyeInfo' in loaded_dict['SCNE'].keys():
                    string_list.append(b'DbzEyeInfo')
                    scne_eye_info_object = SCNE_EYE_INFO('', b'DbzEyeInfo', spr_object.string_table)
                    scne_eye_info_object.load_data(loaded_dict['SCNE']['DbzEyeInfo'])
                    del loaded_dict['SCNE']['DbzEyeInfo']
                    for entry in scne_eye_info_object.eye_entries:
                        if entry.name != b'':
                            string_list.append(entry.name)
                    scne_child_entry = SPRPDataEntry(b'SCNE', b'DbzEyeInfo', spr_object.string_table)
                    scne_child_entry.data = scne_eye_info_object
                    scne_main_entry.children.append(scne_child_entry)

                # for key, content in loaded_dict['SCNE'].items():
                #     if key != '[NODES]':
                #         if '|#|' in key:
                #             key = key.rsplit('|#|')[1]
                #         key = ut.s2b_name(key)
                #         string_list.append(key)
                #         scne_child_entry = SPRPDataEntry(b'SCNE', key, spr_object.string_table)
                #         scne_child_entry.data = content['data'].encode('latin-1')
                #         scne_main_entry.children.append(scne_child_entry)

                spr['SCNE'].entries.append(scne_main_entry)

            # Other JSON files
            for key, data in loaded_dict.items():
                entry_type = ut.s2b_name(key)
                if key not in spr.keys():
                    spr[key] = SPRPEntry(spr_object.string_table, entry_type)
                    for name, content in data.items():
                        name = ut.s2b_name(name)
                        string_list.append(name)
                        spr_data_entry = \
                            SPRPDataEntry(entry_type, name, spr_object.string_table, True)
                        spr_data_entry.data = content['data'].encode('latin-1')
                        spr[key].entries.append(spr_data_entry)
        else:
            spr = {
                'TX2D': SPRPEntry(spr_object.string_table, b'TX2D')
            }
            texture_names = []

            for filename in os.listdir(spr_folder_path):
                name, ext = os.path.splitext(filename)
                if ext.lower() in ['.bmp', '.dds']:
                    layer_name, source_name, texture_names, spr_data_entry = \
                        self.add_texture(spr_object, texture_names,
                            '', os.path.join(spr_folder_path, filename))
                    if spr_data_entry != None:
                        spr['TX2D'].entries.append(spr_data_entry)
            string_list.extend(texture_names)

        # Temporary fix for UT crash on reload: 
        # Removing edge_mask or any texture used in SHAP when importing back
        for entry in spr['SHAP'].entries:
            for child in entry.children:
                if hasattr(child.data, 'source_name'):
                    child.data.source_name = b''

        self.sort_entries(spr, spr_object)
        self.build_ram_data(spr, spr_object, base_name)

        # Remove duplicates from string table and build it
        string_list = natsorted(list(set(string_list)))
        spr_object.string_table.build(string_list)
        cm.data['spr'][base_name] = spr_object

        cm.main_handler.task.send_progress(100)

    def build_bones(self, spr_dict, spr_object, fbx_object, loaded_dict, string_list):
        spr_dict['BONE'] = SPRPEntry(spr_object.string_table, b'BONE')
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
                    np.array(loaded_dict['BONE'][node.GetName()]['data']['transform1'])
                bone_entry_object.transform2 = \
                    np.array(loaded_dict['BONE'][node.GetName()]['data']['transform2'])
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

        bone_children = {}
        for loaded_bone_name, loaded_bone_data in loaded_dict['BONE'].items():
            if 'children' in loaded_bone_data.keys():
                for child_name, child_data in loaded_bone_data['children'].items():
                    if child_name not in bone_children.keys():
                        bone_children[child_name] = {}
                    bone_children[child_name][loaded_bone_name] = child_data
        
        if 'DbzBoneInfo' not in bone_children.keys():
            bone_children['DbzBoneInfo'] = {}
                
        for bone in bone_object.bone_entries:
            if ut.b2s_name(bone.name) not in bone_children['DbzBoneInfo'].keys():
                bone_children['DbzBoneInfo'][ut.b2s_name(bone.name)] = {
                    'unknown0x00': "\u0000\u0000\u0000\u0000",
                    'data': [ 0.0, 0.0, 0.0,
                              0.0, 0.0, 0.0,
                              0.0, 0.0, 0.0 ]
                }
        
        for child_name, child_data in bone_children.items():
            child_name = ut.s2b_name(child_name)
            bone_child_object = BONE_INFO('', child_name)
            if child_name != b'DbzBoneInfo':
                bone_child_object.info_size = 20
            string_list.append(child_name)
            bone_child_object.load_data(child_data)

            spr_child_data_entry = \
                SPRPDataEntry(b'BONE', child_name, spr_object.string_table)
            spr_child_data_entry.data = bone_child_object
            spr_data_entry.children.append(spr_child_data_entry)

        spr_dict['BONE'].entries.append(spr_data_entry)

    def build_shape(self, spr_dict, spr_object, texture_names, string_list, shap_name, 
                    shap_data = None, spr_folder_path = ''):
        shape_object = SHAP('', b'', spr_object.string_table)
        if shap_data:
            shape_object.load_data(shap_data)
        spr_data_entry = SPRPDataEntry(b'SHAP', shap_name, spr_object.string_table, True)
        spr_data_entry.data = shape_object

        string_list.append(b'DbzEdgeInfo')
        shape_object = SHAP('', b'DbzEdgeInfo', spr_object.string_table)
        shape_object.source_type = b'map1'
        if shap_data and 'DbzEdgeInfo' in shap_data.keys():
            shape_object.load_data(shap_data['DbzEdgeInfo'])
            if shape_object.source_name != b'':
                string_list.append(shape_object.source_name)
                # Add source texture if its missing
                if shape_object.source_name not in texture_names:
                    texture_name = ut.b2s_name(shape_object.source_name)
                    texture_path = os.path.join(spr_folder_path, texture_name)
                    layer_name, source_name, texture_names, texture_spr_data_entry = \
                        self.add_texture(spr_object, texture_names, '', texture_path)
                    if texture_spr_data_entry != None:
                        spr_dict['TX2D'].entries.append(texture_spr_data_entry)
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

        return spr_data_entry

    def sort_entries(self, spr_dict, spr_object, not_to_sort = ['MTRL', 'SCNE', 'VBUF']):
        # Sorting entries and removing empty ones
        # Materials aren't sorted by default
        entries = {}
        for key, entry in spr_dict.items():
            if key not in not_to_sort:
                entry.sort()
            if len(entry.entries) > 0:
                entries[key] = entry

        for entry_type in spr_object.ordered_types:
            for key, entry in entries.items():
                if key == entry_type:
                    spr_object.entries.append(entry)
                    break
        
        for key, entry in entries.items():
            if key not in spr_object.ordered_types:
                spr_object.entries.append(entry)

    def build_ram_data(self, spr_dict, spr_object, base_name):
        # Build ioram
        if 'VBUF' in spr_dict.keys():
            ioram_data = bytearray()
            for entry in spr_dict['VBUF'].entries:
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

            cm.data['ioram'][base_name] = ioram_data
            spr_object.ioram_data_size = len(ioram_data)

        # Build vram
        if 'TX2D' in spr_dict.keys():
            vram_data = bytearray()
            for entry in spr_dict['TX2D'].entries:
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

            cm.data['vram'][base_name] = vram_data
            spr_object.vram_data_size = len(vram_data)

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