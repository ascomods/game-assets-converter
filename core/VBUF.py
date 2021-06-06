from typing import io
import os
from io import BytesIO
import core.utils as ut
from .OBJ import OBJ
import struct
from .StringTable import StringTable

class VBUF:
    info_size = 32
    vertex_decl_size = 20
    vertex_format = {
        2: 'L',  # VTXFMT_ULONG1
        8: 'f',  # VTXFMT_FLOAT1
        9: 'ff',  # VTXFMT_FLOAT2
        10: 'fff', # VTXFMT_FLOAT3
        11: 'ffff'  # VTXFMT_FLOAT4
    }
    format_size = {
        'f': 4,
        'L': 4
    }
    vertex_usage = {
        0: 'VTXUSAGE_POSITION',
        2: 'VTXUSAGE_NORMAL',
        5: 'VTXUSAGE_TEXCOORD',
        6: 'VTXUSAGE_WEIGHTS',
        7: 'VTXUSAGE_INDICES'
    }
    vertex_usage_mapping = {
        0: 'positions',
        2: 'normals',
        5: 'uvs',
        6: 'weights',
        7: 'indices'
    }

    def __init__(self, type = '', name = '', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table
        self.vertex_decl = []

    def update_offsets(self, data_offset, offset):
        self.data_offset = data_offset
        self.vertex_decl_offset = offset + self.info_size

    def get_size(self, include_vertex_decl = True):
        size = self.info_size
        if include_vertex_decl:
            size += len(self.vertex_decl) * self.vertex_decl_size
        return size
    
    def read(self, stream: io, data_offset = 0, read_data = True):
        # Reading data info
        self.data_offset = data_offset
        self.unknown0x00 = ut.b2i(stream.read(4))
        self.unknown0x04 = ut.b2i(stream.read(4))
        self.ioram_data_offset = ut.b2i(stream.read(4))
        self.ioram_data_size = ut.b2i(stream.read(4))
        self.vertex_count = ut.b2i(stream.read(4))
        self.unknown0x14 = ut.b2i(stream.read(2))
        self.unknown0x16 = ut.b2i(stream.read(2))
        self.vertex_decl_count = ut.b2i(stream.read(2))
        self.vertex_decl_count_2 = ut.b2i(stream.read(2))
        self.vertex_decl_offset = ut.b2i(stream.read(4))
        if read_data:
            self.read_data(stream)
    
    @ut.keep_cursor_pos
    def read_data(self, stream: io):
        stream.seek(self.data_offset + self.vertex_decl_offset)
        for i in range(self.vertex_decl_count):
            self.vertex_decl.append(struct.unpack(f"{ut.ste()}LLHHHHL", 
                stream.read(self.vertex_decl_size)))

    def read_ioram(self, stream: io):
        stream.seek(self.ioram_data_offset)
        self.ioram_data = stream.read(self.ioram_data_size)
    
    def get_ioram(self):
        return self.ioram_data

    def write(self, stream: io, write_data = True):
        # Writing data info
        stream.write(ut.i2b(self.unknown0x00))
        stream.write(ut.i2b(self.unknown0x04))
        stream.write(ut.i2b(self.ioram_data_offset))
        stream.write(ut.i2b(self.ioram_data_size))
        stream.write(ut.i2b(self.vertex_count))
        stream.write(ut.i2b(self.unknown0x14, 2))
        stream.write(ut.i2b(self.unknown0x16, 2))
        stream.write(ut.i2b(self.vertex_decl_count, 2))
        stream.write(ut.i2b(self.vertex_decl_count_2, 2))
        stream.write(ut.i2b(self.vertex_decl_offset))
        if write_data:
            self.write_data(stream)
        
    def write_data(self, stream: io):
        stream.seek(self.data_offset + self.vertex_decl_offset)
        for decl in self.vertex_decl:
            stream.write(struct.pack(f"{ut.ste()}LLHHHHL", *decl))
    
    def load(self, path = ''):
        prev_path = os.getcwd()

        if os.path.exists(path):
            os.chdir(path)
        
        input_object = OBJ()
        input_object.load(path)
        self.data = input_object.data
        self.load_data(path)
        
        if os.path.exists(path):
            os.chdir(prev_path)

    def load_data(self, path):
        stream = open(path + 'data.txt', 'r')
        lines = stream.readlines()
        lines = [line[:-1] for line in lines]
        
        self.vertex_count = len(self.data['positions'][0]['data'])
        ioram_stream = BytesIO()
        vertex_usages = {}
        total_chunk_size = 0
        previous_chunk_size = 0
        previous_stride = 0
        previous_offset = 0
        offset = 0

        for i in range(len(lines)):
            if '# START INFO' in lines[i]:
                self.unknown0x00 = int(lines[i + 1])
                self.unknown0x04 = int(lines[i + 2])
                self.unknown0x14 = int(lines[i + 3])
                self.unknown0x16 = int(lines[i + 4])
                self.vertex_decl_count = int(lines[i + 5])
                self.vertex_decl_count_2 = int(lines[i + 6])
                i += 7
            if '# START DECL' in lines[i]:
                unknown0x00 = int(lines[i + 1])
                try:
                    resource_name_offset = ut.search_index_dict(self.string_table.content, 
                        ut.s2b_name(lines[i + 2]))
                except Exception:
                    resource_name_offset = 0
                try:
                    vertex_usage = ut.search_index_dict(self.vertex_usage, lines[i + 3])
                except Exception:
                    vertex_usage = int(lines[i + 3])
                try:
                    vertex_usages[vertex_usage] += 1
                except Exception:
                    vertex_usages[vertex_usage] = 0
                index = int(lines[i + 4])

                format = lines[i + 5]
                data_type = 'float' if 'f' in format else 'int'
                chunk_size = len(format) * self.format_size[format[0]]
                vertex_format = ut.search_index_dict(self.vertex_format, format)
                stride = int(lines[i + 6])

                if (previous_stride - total_chunk_size) == 0:
                    offset = previous_offset
                    ioram_stream.seek(previous_offset)
                    total_chunk_size = 0
                else:
                    if vertex_usage != 5:
                        if vertex_usage == 7 and vertex_usages[vertex_usage] == 0:
                            offset = ut.add_padding(offset + previous_chunk_size)
                            ioram_stream.seek(offset)
                            total_chunk_size = 0
                        else:
                            ioram_stream.seek(offset + total_chunk_size)
                    else:
                        if vertex_usages[vertex_usage] == 0:
                            offset = ut.add_padding(ioram_stream.tell())
                            ioram_stream.seek(offset)
                            total_chunk_size = 0
                        else:
                            ioram_stream.seek(offset + total_chunk_size)

                self.vertex_decl.append((unknown0x00, resource_name_offset, vertex_usage, \
                    index, vertex_format, stride, ioram_stream.tell()))
                i += 7
                
                count = 0
                if '# START DATA' in lines[i]:
                    i += 1
                    while '# END DATA' not in lines[i]:
                        data = (eval(data_type)(x) for x in lines[i].split())
                        data = struct.pack(f"{ut.ste()}{format}", *data)
                        ioram_stream.write(data)
                        i += 1
                        count += 1
                        if '# END DATA' not in lines[i]:
                            ioram_stream.seek(stride - chunk_size, os.SEEK_CUR)
                    i += 1
                else:
                    usage_type = self.vertex_usage_mapping[vertex_usage]
                    raw_data = self.data[usage_type][vertex_usages[vertex_usage]]['data']
                    for j in range(len(raw_data)):
                        data = (eval(data_type)(x) for x in raw_data[j])
                        data = struct.pack(f"{ut.ste()}{format}", *data)
                        ioram_stream.write(data)
                        count += 1
                        if j < len(raw_data) - 1:
                            ioram_stream.seek(stride - chunk_size, os.SEEK_CUR)
                    i += 1

                for j in range(count, self.vertex_count):
                    data = bytes(chunk_size)
                    if j < self.vertex_count - 1:
                        ioram_stream.seek(stride - chunk_size, os.SEEK_CUR)
                i += 1
                total_chunk_size += chunk_size
                previous_chunk_size = chunk_size
                previous_stride = stride
                previous_offset = ioram_stream.tell()
        ioram_stream.seek(0)
        self.ioram_data = ioram_stream.read()
        self.ioram_data_size = len(self.ioram_data)

    def retrieve_decl_data(self):
        decl_data = []

        for i in range(len(self.vertex_decl)):
            unknown0x00, resource_name_offset, vertex_usage, \
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
                    data.append(struct.unpack(f"{ut.ste()}{format}", chunk))
                
                try:
                    resource_name = ut.b2s_name(self.
                        string_table.content[resource_name_offset])
                except Exception:
                    resource_name = ''
                decl_data.append({
                    'unknown0x00': unknown0x00, 
                    'resource_name': resource_name,
                    'vertex_usage': vertex_usage_txt,
                    'index': index,
                    'vertex_format': format,
                    'stride': stride,
                    'data': data
                })
            except Exception:
                pass
        
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

    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)

        decl_data = self.retrieve_decl_data()
        self.handle_data(decl_data)

        output_object = OBJ()
        output_object.data = self.data
        output_object.save(path)

        self.save_info_data(path, output_object.__class__.__name__)
    
    def save_info_data(self, path, output_object_class):
        stream = open(path + 'data.txt', 'w')

        stream.write("# START INFO\n")
        stream.write(f"{self.unknown0x00}\n")
        stream.write(f"{self.unknown0x04}\n")
        stream.write(f"{self.unknown0x14}\n")
        stream.write(f"{self.unknown0x16}\n")
        stream.write(f"{self.vertex_decl_count}\n")
        stream.write(f"{self.vertex_decl_count_2}\n")
        stream.write("# END INFO\n")
        
        vertex_usages = {}
        for key, val in self.data.items():
            for decl in val:
                stream.write("# START DECL\n")
                stream.write(f"{decl['unknown0x00']}\n")
                stream.write(f"{decl['resource_name']}\n")
                stream.write(f"{decl['vertex_usage']}\n")
                try:
                    vertex_usages[decl['vertex_usage']] += 1
                except Exception:
                    vertex_usages[decl['vertex_usage']] = 0
                stream.write(f"{decl['index']}\n")
                stream.write(f"{decl['vertex_format']}\n")
                stream.write(f"{decl['stride']}\n")
                if key in eval(output_object_class).supported_data and \
                    vertex_usages[decl['vertex_usage']] == 0:
                    stream.write("file\n")
                else:
                    stream.write("# START DATA\n")
                    for elt in decl['data']:
                        stream.write(' '.join(map(str, elt)) + '\n')
                    stream.write("# END DATA\n")
                stream.write("# END DECL\n")
    
    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'ioram_data_size: {hex(len(self.ioram_data))}\n'
        )