import os
from io import BytesIO
import core.common as cm
import core.utils as ut
import struct

class VBUF:
    info_size = 32
    vertex_decl_size = 20
    vertex_format = {
        2: 'L',  # VTXFMT_UINT1
        7: 'f',  # VTXFMT_FLOAT1
        8: 'f',  # VTXFMT_FLOAT1
        9: 'ff',  # VTXFMT_FLOAT2
        10: 'fff', # VTXFMT_FLOAT3
        11: 'ffff',  # VTXFMT_FLOAT4
        14: 'ffff'  # VTXFMT_FLOAT4
    }
    vertex_format_mapping = {
        'positions': 11,
        'normals': 11,
        'binormals': 11,
        'uvs': 9,
        'bone_weights': 8,
        'bone_indices': 2
    }
    format_size = {
        'f': 4,
        'L': 4
    }
    vertex_usage = {
        0: 'VTXUSAGE_POSITION',
        1: 'VTXUSAGE_COLOR',
        2: 'VTXUSAGE_NORMAL',
        3: 'VTXUSAGE_BINORMAL',
        4: 'VTXUSAGE_TANGENT',
        5: 'VTXUSAGE_TEXCOORD',
        6: 'VTXUSAGE_BONE_WEIGHTS',
        7: 'VTXUSAGE_BONE_INDICES'
    }
    vertex_usage_mapping = {
        0: 'positions',
        1: 'colors',
        2: 'normals',
        3: 'binormals',
        4: 'tangents',
        5: 'uvs',
        6: 'bone_weights',
        7: 'bone_indices'
    }
    vertex_ordered_keys = [
        'positions',
        'colors',
        'normals',
        'binormals',
        'tangents',
        'bone_weights',
        'bone_indices',
        'uvs'
    ]

    def __init__(self, type = '', name = '', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table
        self.unknown0x00 = 68
        self.unknown0x04 = 0
        self.unknown0x14 = 6
        self.unknown0x16 = 0
        self.data = {}
        self.vertex_decl = []
        if cm.selected_game == 'dbut':
            self.info_size = 40

    def get_size(self, include_vertex_decl = True):
        size = self.info_size
        if include_vertex_decl:
            size += len(self.vertex_decl) * self.vertex_decl_size
        return size
    
    def read(self, stream, data_offset = 0, read_data = True):
        # Reading data info
        self.data_offset = data_offset
        self.unknown0x00 = ut.b2i(stream.read(4))
        self.unknown0x04 = ut.b2i(stream.read(4))
        self.ioram_data_offset = ut.b2i(stream.read(4))
        self.ioram_data_size = ut.b2i(stream.read(4))
        if cm.selected_game == 'dbut':
            self.index_count = ut.b2i(stream.read(4))
        self.vertex_count = ut.b2i(stream.read(4))
        self.unknown0x14 = ut.b2i(stream.read(2))
        self.unknown0x16 = ut.b2i(stream.read(2))
        self.vertex_decl_count = ut.b2i(stream.read(2))
        self.vertex_decl_count_2 = ut.b2i(stream.read(2))
        self.vertex_decl_offset = ut.b2i(stream.read(4))
        if cm.selected_game == 'dbut':
            self.ioram_index_offset = ut.b2i(stream.read(4))
        if read_data:
            self.read_data(stream)
    
    @ut.keep_cursor_pos
    def read_data(self, stream):
        stream.seek(self.data_offset + self.vertex_decl_offset)
        for i in range(self.vertex_decl_count):
            unknown0x00, resource_name_offset, vertex_usage, \
                index, vertex_format, stride, offset = struct.unpack(f">LLHHHHL", \
                    stream.read(self.vertex_decl_size))
            try:
                resource_name = self.string_table.content[resource_name_offset]
            except Exception:
                resource_name = ''
            self.vertex_decl.append((unknown0x00, resource_name, vertex_usage, \
                index, vertex_format, stride, offset))

    def read_ioram(self, stream):
        stream.seek(self.ioram_data_offset)
        self.ioram_data = stream.read(self.ioram_data_size)
    
    def get_ioram(self):
        return self.ioram_data

    def write(self, stream, write_data = True):
        # Writing data info
        self.vertex_decl_offset = ut.add_padding(abs(stream.tell() + \
            self.info_size - self.data_offset))
        stream.write(ut.i2b(self.unknown0x00))
        stream.write(ut.i2b(self.unknown0x04))
        stream.write(ut.i2b(self.ioram_data_offset))
        stream.write(ut.i2b(len(self.ioram_data)))
        stream.write(ut.i2b(self.vertex_count))
        if cm.selected_game == 'dbut':
            stream.write(ut.i2b(self.index_count))
        stream.write(ut.i2b(self.unknown0x14, 2))
        stream.write(ut.i2b(self.unknown0x16, 2))
        stream.write(ut.i2b(self.vertex_decl_count, 2))
        stream.write(ut.i2b(self.vertex_decl_count_2, 2))
        stream.write(ut.i2b(self.vertex_decl_offset))
        if cm.selected_game == 'dbut':
            stream.write(ut.i2b(self.ioram_index_offset))
        if write_data:
            return self.write_data(stream)
        return stream.tell()
        
    def write_data(self, stream):
        stream.seek(self.data_offset + self.vertex_decl_offset)
        for decl in self.vertex_decl:
            unknown0x00, resource_name, vertex_usage, \
                index, vertex_format, stride, offset = decl
            try:
                resource_name_offset = ut.search_index_dict(self.string_table.content, resource_name)
            except Exception:
                resource_name_offset = 0
            decl = (unknown0x00, resource_name_offset, vertex_usage, \
                index, vertex_format, stride, offset)
            stream.write(struct.pack(f">LLHHHHL", *decl))
        return stream.tell()

    def load_data(self):       
        self.vertex_count = len(self.data['positions'][0]['data'])
        if cm.selected_game == 'dbut':
            self.index_count = len(self.face_indices)
        ioram_stream = BytesIO()
        vertex_usages = {}
        total_chunk_size = 0
        previous_stride = 0
        previous_usage = 0
        previous_offset = 0
        highest_offset = 0
        offset = 0

        self.vertex_decl_count = 0
        for decl_list in self.data.values():
            self.vertex_decl_count += len(decl_list)
        self.vertex_decl_count_2 = self.vertex_decl_count

        self.vertex_decl = []

        # Reorder keys
        data = {}
        for key in self.vertex_ordered_keys:
            if key in self.data.keys():
                data[key] = self.data[key]
        self.data = data

        # Fix weights and indices padding
        if 'bone_weights' in self.data.keys():
            if len(self.data['bone_weights']) < 4:
                for i in range(len(self.data['bone_weights']), 4):
                    self.data['bone_weights'].append({
                        'unknown0x00': '0', 
                        'resource_name': '', 
                        'vertex_usage': 'VTXUSAGE_BONE_WEIGHTS', 
                        'index': i, 
                        'vertex_format': 'f',
                        'data': [(0.0,)] * len(self.data['bone_weights'][0]['data']),
                        'unmapped': True
                    })
                    self.data['bone_indices'].append({
                        'unknown0x00': '0', 
                        'resource_name': '',
                        'vertex_usage': 'VTXUSAGE_BONE_INDICES', 
                        'index': i, 
                        'vertex_format': 'L',
                        'data': [(0,)] * len(self.data['bone_indices'][0]['data']),
                        'unmapped': True
                    })

        # Calculate stride
        stride = 0
        stride_list = []
        for key, data in self.data.items():
            if key in ['bone_weights', 'uvs']:
                stride_list.append(stride)
                stride = 0
            format_num = self.vertex_format_mapping[key]
            format = self.vertex_format[format_num]
            stride += len(data) * len(format) * self.format_size[format[0]]
        stride_list.append(stride)

        i = 0
        for key, decl_list in self.data.items():
            if key in ['bone_weights', 'uvs']:
                i += 1
            stride = stride_list[i]
            for decl in decl_list:
                decl['stride'] = stride

        for key, decl_list in self.data.items():
            index = 0

            for decl in decl_list:
                try:
                    vertex_usage = ut.search_index_dict(self.vertex_usage, decl['vertex_usage'])
                except Exception:
                    vertex_usage = int(decl['vertex_usage'])
                try:
                    vertex_usages[vertex_usage] += 1
                except Exception:
                    vertex_usages[vertex_usage] = 0
                
                format = decl['vertex_format']
                data_type = 'float' if 'f' in format else 'int'
                chunk_size = len(format) * self.format_size[format[0]]
                vertex_format = ut.search_index_dict(self.vertex_format, format)
                stride = decl['stride']

                if (previous_stride - total_chunk_size) == 0:
                    if previous_usage != vertex_usage:
                        offset = highest_offset
                    else:
                        offset = previous_offset
                    ioram_stream.seek(offset)
                    total_chunk_size = 0
                else:
                    ioram_stream.seek(offset + total_chunk_size)
                if 'unmapped' not in decl:
                    self.vertex_decl.append((int(decl['unknown0x00']), decl['resource_name'], vertex_usage, \
                        index, vertex_format, stride, ioram_stream.tell()))

                i = 0
                for data in decl['data']:
                    vertex = (eval(data_type)(x) for x in data)
                    vertex = struct.pack(f">{format}", *vertex)
                    ioram_stream.write(vertex)
                    if i < len(decl['data']) - 1:
                        nextOffset = stride - chunk_size
                        ioram_stream.seek(nextOffset, os.SEEK_CUR)
                    i += 1

                total_chunk_size += chunk_size
                previous_stride = stride
                previous_usage = vertex_usage
                previous_offset = ioram_stream.tell()
                if previous_offset > highest_offset:
                    highest_offset = ut.add_padding(previous_offset + (stride - total_chunk_size))
                index += 1

        if cm.selected_game == 'dbut':
            self.ioram_index_offset = ioram_stream.tell()
            for idx in self.face_indices:
                idx = struct.pack(f">h", idx)
                ioram_stream.write(idx)

        ioram_stream.seek(0)
        self.ioram_data = ioram_stream.read()
        self.ioram_data_size = len(self.ioram_data)

    def retrieve_decl_data(self):
        decl_data = []

        current_offset = 0
        for i in range(len(self.vertex_decl)):
            unknown0x00, resource_name, vertex_usage, \
                index, vertex_format, stride, offset = self.vertex_decl[i]

            try:
                try:
                    vertex_usage_txt = self.vertex_usage[vertex_usage]
                except Exception:
                    vertex_usage_txt = vertex_usage

                format = self.vertex_format[vertex_format]
                chunk_size = len(format) * self.format_size[format[0]]
                data = []

                for i in range(self.vertex_count):
                    current_offset = offset + (stride * i)
                    chunk = self.ioram_data[current_offset:current_offset + chunk_size]
                    data.append(struct.unpack(f">{format}", chunk))
                current_offset += chunk_size

                data = {
                    'unknown0x00': unknown0x00, 
                    'resource_name': resource_name,
                    'vertex_usage': vertex_usage_txt,
                    'index': index,
                    'vertex_format': format,
                    'stride': stride,
                    'data': data
                }

                # Fix for inverted UV set order
                if (vertex_usage_txt == 'VTXUSAGE_TEXCOORD') and \
                   (resource_name in [b'uvSet']):
                    if resource_name == b'uvSet':
                        data['resource_name'] = b'map1'
                    decl_data.insert(0, data)
                else:
                    decl_data.append(data)
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                print(e)
                pass

        if cm.selected_game == 'dbut':
            face_indices = []
            
            for i in range(self.vertex_count):
                face_indices.append(
                    struct.unpack('>h', 
                    self.ioram_data[current_offset:current_offset + 2])[0]
                )
                current_offset += 2

            for decl in decl_data:
                new_decl_data = []
                for index in face_indices:
                    new_decl_data.append(decl['data'][index])
                decl['data'] = new_decl_data

        return decl_data

    def handle_data(self, decl_data):
        self.data = {}
        
        for decl in decl_data:
            try:
                vertex_usage = \
                    ut.search_index_dict(self.vertex_usage, decl['vertex_usage'])
            except Exception:
                vertex_usage = 'others'
            try:
                self.data[self.vertex_usage_mapping[vertex_usage]].append(decl)
            except Exception:
                try:
                    self.data[self.vertex_usage_mapping[vertex_usage]] = [decl]
                except Exception:
                    self.data[vertex_usage] = [decl]

    def get_data(self):
        decl_data = self.retrieve_decl_data()
        self.handle_data(decl_data)

        return self.data
    
    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
        )