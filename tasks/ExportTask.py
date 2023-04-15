import os
import json
from tasks.Task import Task
from core.FBX import FBX
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

            bone_data = self.data['spr'].search_entries([], 'BONE')
            scne_data = self.data['spr'].search_entries([], 'SCNE')
            vbuf_data = self.data['spr'].search_entries([], 'VBUF')
            tx2d_data = self.data['spr'].search_entries([], 'TX2D')
            mtrl_data = self.data['spr'].search_entries([], 'MTRL')
            shap_data = self.data['spr'].search_entries([], 'SHAP')
            drvn_data = self.data['spr'].search_entries([], 'DRVN', True)
            txan_data = self.data['spr'].search_entries([], 'TXAN', True)

            # BONE
            try:
                bone_dict = {}
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
            fbx_object.save(self.output_path)

            self.send_progress(100)
            self.result_signal.emit(self.__class__.__name__)
            self.finish_signal.emit()
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()