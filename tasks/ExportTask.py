import os
import shutil
import json
from io import BytesIO
from tasks.Task import Task
from core.FBX import *
from core.DDS import *
from core.BMP import *
import core.utils as ut

class ExportTask(Task):
    def __init__(self, data, output_path):
        super().__init__()
        self.data = data
        self.output_path = output_path

    def run(self):
        try:
            ut.empty_temp_dir()
            ut.init_temp_dir()
            
            if 'spr_stpk' in self.data.keys():
                spr_entries = self.data['spr_stpk'].search_entries([], 'SPRP')
                output_path = self.output_path
                for spr_object in spr_entries:
                    self.data['spr'] = spr_object
                    name, ext = os.path.splitext(ut.b2s_name(spr_object.name))
                    try:
                        self.data['ioram'] = \
                            self.data['ioram_stpk'].search_entries([], f"{name}.ioram")[0].data
                    except:
                        self.data['ioram'] = None
                    try:
                        self.data['vram'] = \
                            self.data['vram_stpk'].search_entries([], f"{name}.vram")[0].data
                    except:
                        self.data['vram'] = None
                    self.output_path = os.path.join(output_path, ut.b2s_name(spr_object.name))
                    if not os.path.exists(self.output_path):
                        os.mkdir(self.output_path)
                    self.export_spr()

                # Export other files in current STPK (SPR)
                i = 0
                self.output_path = output_path

                for entry in self.data['spr_stpk'].entries:
                    output_path = os.path.join(self.output_path, f"[{i}]{ut.b2s_name(entry.name)}")
                    if b'.spr' not in entry.name:
                        stream = open(output_path, "wb")
                        stream.write(entry.data)
                        stream.close()
                    else:
                        spr_path = os.path.join(self.output_path, ut.b2s_name(entry.name))
                        if os.path.exists(spr_path):
                            if os.path.exists(output_path):
                                shutil.rmtree(output_path)
                            shutil.move(spr_path, output_path)
                    i += 1
            else:
                self.export_spr()

            # return to app dir
            os.chdir(cm.app_path)

            self.result_signal.emit(self.__class__.__name__)
            self.finish_signal.emit()
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()

    def export_spr(self):
        self.send_progress(0)
        #print(self.data['spr'])

        entry_types = []
        for entry in self.data['spr'].entries:
            entry_types.append(ut.b2s_name(entry.data_type))

        vbuf_data = []
        if ('VBUF' in entry_types) and ('ioram' in self.data.keys()):
            entry_types.remove('VBUF')
            vbuf_data = self.data['spr'].search_entries([], 'VBUF')
            if len(vbuf_data) > 0:
                ioram_stream = BytesIO(self.data['ioram'])

                for entry in vbuf_data:
                    entry.data.read_ioram(ioram_stream)
            else:
                raise Exception("No model info found in SPR !")

        tx2d_data = []
        if ('TX2D' in entry_types) and ('vram' in self.data.keys()):
            entry_types.remove('TX2D')
            tx2d_data = self.data['spr'].search_entries([], 'TX2D')
            if len(tx2d_data) > 0:
                vram_stream = BytesIO(self.data['vram'])

                remaining = []
                for entry in tx2d_data:
                    entry.data.read_vram(vram_stream)
                    name, ext = os.path.splitext(ut.b2s_name(entry.name))
                    texture_data = entry.data
                    vram_data = texture_data.get_unswizzled_vram_data()
                    output_class = texture_data.get_output_format()
                    
                    if output_class == 'BMP':
                        output_object = BMP(name, texture_data.width, texture_data.height, vram_data)
                        output_object.save(self.output_path)
                    elif output_class == 'DDS':
                        output_object = DDS(name, texture_data.width, texture_data.height, vram_data, \
                            texture_data.get_texture_type(), texture_data.mipmap_count)
                        output_object.save(self.output_path)
                    remaining.append(output_object.get_name())
            else:
                raise Exception("No texture info found in SPR !")

        bone_data = []
        if 'BONE' in entry_types:
            entry_types.remove('BONE')
            try:
                bone_data = self.data['spr'].search_entries([], 'BONE')
                bone_dict = {}
                bone_entries = bone_data[0].data.bone_entries
                if len(bone_data) > 1:
                    bone_base_data = bone_data[0].get_data()['data']
                    for i in range(len(bone_base_data)):
                        bone_dict[ut.b2s_name(bone_entries[i].name)] = {
                            'data': bone_base_data[i]
                        }

                    for i in range(1, len(bone_data)):
                        child_data = bone_data[i].get_data()['data']['data']
                        child_name = ut.b2s_name(bone_data[i].name)

                        for j in range(len(bone_base_data)):
                            bone_name = ut.b2s_name(bone_entries[j].name)
                            if 'children' not in bone_dict[bone_name]:
                                bone_dict[bone_name]['children'] = {}
                            bone_dict[bone_name]['children'][child_name] = child_data[j]

                json_data = json.dumps(bone_dict, indent=4)
                data_stream = open(os.path.join(self.output_path, "BONE.json"), "w")
                data_stream.write(str(json_data))
            except:
                print('Bone data is missing')

        self.send_progress(10)

        scne_data = []
        if ('SHAP' in entry_types) and ('SCNE' in entry_types):
            entry_types.remove('SHAP')
            entry_types.remove('SCNE')
            shap_data = self.data['spr'].search_entries([], 'SHAP')
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

            scne_data = self.data['spr'].search_entries([], 'SCNE')
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
            name_links = {}
            for scne_shape_name, shape_name in scne_shape_dict.items():
                for scne_mesh_name, mesh_shape in scne_mesh_dict.items():
                    if mesh_shape == shape_name:
                        new_shape_name = scne_mesh_name.rsplit("|", 1)[1]
                        new_shape_name = new_shape_name.rsplit(':', 1)[0]
                        new_shape_name += 'Shape'
                        if new_shape_name not in new_scne_shape_dict.keys():
                            new_scne_shape_dict[new_shape_name] = shap_dict[shape_name]
                            name_links[new_shape_name] = shape_name

            #Try to keep previous SHAP order
            tmp_list = {}
            for name, content in shap_dict.items():
                for new_name, new_content in new_scne_shape_dict.items():
                    if name_links[new_name] == name:
                        tmp_list[new_name] = new_content
                        del new_scne_shape_dict[new_name]
                        break

            for new_name, new_content in new_scne_shape_dict.items():
                tmp_list[new_name] = new_content
            new_scne_shape_dict = tmp_list

            json_data = json.dumps(new_scne_shape_dict, indent=4)
            data_stream = open(os.path.join(self.output_path, "SHAP.json"), "w")
            data_stream.write(str(json_data))

            scne_dict = {}
            if len(scne_data) > 0:
                for child in scne_data[0].children:
                    if child.name == b'DbzEyeInfo':
                        scne_dict['DbzEyeInfo'] = child.get_data()['data']['eye_entries']
                    else:
                        name = ut.b2s_name(child.name)

                        i = 0
                        found = False
                        for key in scne_dict.keys():
                            if (name == key) or ((name in key) and ('|#|' in key)):
                                found = True
                                break

                        if found:
                            if '|#|' not in key:
                                new_name = f"0|#|{name}"
                                scne_dict[new_name] = scne_dict[name]
                                del scne_dict[name]
                            else:
                                i = int(key.rsplit('|#|')[0]) + 1
                                new_name = f"{i}|#|{name}"

                            while new_name in scne_dict.keys():
                                i += 1
                                new_name = f"{i}|#|{name}"
                            scne_dict[new_name] = child.get_data()
                        else:
                            scne_dict[name] = child.get_data()
                if scne_dict != {}:
                    json_data = json.dumps(scne_dict, indent=4)
                    data_stream = open(os.path.join(self.output_path, "SCNE.json"), "w")
                    data_stream.write(str(json_data))

        self.send_progress(40)

        mtrl_data = []
        if 'MTRL' in entry_types:
            entry_types.remove('MTRL')
            mtrl_data = self.data['spr'].search_entries([], 'MTRL')
            mtrl_dict = {}

            # Assigning textures to materials
            # Using first eyeball texture until a proper fix for eyes is implemented
            eyeball_count = 1
            for entry in mtrl_data:
                if entry.__class__.__name__ == "SPRPDataEntry":
                    if not isinstance(entry.data, bytes):
                        entry.data.sort()
                        for layer in entry.data.layers:
                            layer_base_name = layer[1].rsplit(b'.', 1)[0]
                            layer_base_name = layer_base_name.replace(b'.', b'')
                            if b'eyeball' in layer_base_name:
                                layer_base_name = re.split(b'\d+$', layer_base_name, 0)[0]
                                layer_base_name += ut.s2b_name(f".{eyeball_count}")
                            matches = difflib.get_close_matches(ut.b2s_name(layer_base_name), remaining, len(remaining), 0)
                            layer[1] = ut.s2b_name(matches[0])

                    content = entry.get_data()
                    content['data'] = content['data']['data']
                    try:
                        material_name_parts = entry.name.rsplit(b':', 1)[1]
                        if len(material_name_parts) > 2:
                            entry.name = b':'.join(material_name_parts[1:])
                        else:
                            entry.name = material_name_parts[1]
                    except:
                        pass
                    mtrl_dict[ut.b2s_name(entry.name)] = content

            json_data = json.dumps(mtrl_dict, indent=4)
            data_stream = open(os.path.join(self.output_path, "MTRL.json"), "w")
            data_stream.write(str(json_data))
        
        if 'TXAN' in entry_types:
            entry_types.remove('TXAN')
            txan_data = self.data['spr'].search_entries([], 'TXAN', True)
            if txan_data.__class__.__name__ != 'list':
                eye_texture_names = []
                for entry in tx2d_data:
                    if b'eyeball' in entry.name:
                        eye_texture_names.append(entry.name.replace(b'.tga', b'.dds'))
                
                for i in range(len(txan_data.entries)):
                    idx = abs((len(eye_texture_names) - 1) - i) % len(eye_texture_names)
                    txan_data.entries[i].name = eye_texture_names[idx]

                json_data = json.dumps(txan_data.get_data(), indent=4)
                data_stream = open(os.path.join(self.output_path, "TXAN.json"), "w")
                data_stream.write(str(json_data))

            self.send_progress(60)
        
        for entry_type in entry_types:
            spr_entry = self.data['spr'].search_entries([], entry_type, True)
            if spr_entry.__class__.__name__ != 'list':
                json_data = json.dumps(spr_entry.get_data(), indent=4)
                data_stream = open(os.path.join(self.output_path, f"{entry_type}.json"), "w")
                data_stream.write(str(json_data))

        self.send_progress(80)
        
        if (scne_data != []) and (vbuf_data != []):
            fbx_object = FBX()
            fbx_object.data = {
                'bone': bone_data,
                'model': vbuf_data,
                'scene': scne_data,
                'texture': tx2d_data,
                'material': mtrl_data
            }
            fbx_object.save(self.output_path)

        self.send_progress(100)