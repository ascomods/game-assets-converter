import core.utils as ut
import numpy as np
import struct
import copy

class SCNE:
    data_size = 20

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.unknown0x00 = 1
        self.string_table = string_table
        self.data_type = b''
        self.layer_name = b''
        self.parent_name = b''

    def get_size(self, specific_include = True):
        return self.data_size
    
    def read(self, stream, data_offset = 0):
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset

        self.unknown0x00 = ut.b2i(stream.read(4))
        data_type_offset = ut.b2i(stream.read(4))
        if data_type_offset != 0:
            self.data_type = self.string_table.content[data_type_offset]
        name_offset = ut.b2i(stream.read(4))
        if name_offset != 0:
            self.name = self.string_table.content[name_offset]
        layer_name_offset = ut.b2i(stream.read(4))
        if layer_name_offset != 0:
            self.layer_name = self.string_table.content[layer_name_offset]
        parent_name_offset = ut.b2i(stream.read(4))
        if parent_name_offset != 0:
            self.parent_name = self.string_table.content[parent_name_offset]

    def write(self, stream, write_data = True):
        stream.seek(self.data_offset + self.offset)
        stream.write(ut.i2b(self.unknown0x00)) # Write unknown offset
        data_type_offset = ut.search_index_dict(self.string_table.content, self.data_type)
        stream.write(ut.i2b(data_type_offset))
        if self.name != b'':
            name_offset = ut.search_index_dict(self.string_table.content, self.name)
            stream.write(ut.i2b(name_offset))
        else:
            stream.write(bytes(4))
        if self.layer_name != b'':
            layer_name_offset = \
                ut.search_index_dict(self.string_table.content, self.layer_name)
            stream.write(ut.i2b(layer_name_offset))
        else:
            stream.write(bytes(4))
        if self.parent_name != b'':
            parent_name_offset = ut.search_index_dict(self.string_table.content, self.parent_name)
            stream.write(ut.i2b(parent_name_offset))
        else:
            stream.write(bytes(4))
        
        return stream.tell()

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'unknown0x00: {self.unknown0x00}\n'
            f'data_type: {self.data_type}\n'
            f'name: {self.name}\n'
            f'layer_name: {self.layer_name}\n'
            f'parent_name: {self.parent_name}\n'
        )

class SCNE_MATERIAL:
    header_size = 12
    info_size = 12

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.unknown0x04 = 0
        self.string_table = string_table
        self.infos = []
    
    def get_size(self, specific_include = True):
        return self.header_size + len(self.infos) * self.info_size

    def read(self, stream, data_offset = 0):
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset
        
        self.name_offset = ut.b2i(stream.read(4))
        self.name = self.string_table.content[self.name_offset]
        self.unknown0x04 = ut.b2i(stream.read(4))
        self.material_infos_count = ut.b2i(stream.read(4))

        for i in range(self.material_infos_count):
            info_name_offset = ut.b2i(stream.read(4))
            info_name = self.string_table.content[info_name_offset]
            info_type_offset = ut.b2i(stream.read(4))
            info_type = self.string_table.content[info_type_offset]
            info_unknown_0x08 = ut.b2i(stream.read(4))
            self.infos.append((info_name, info_type, info_unknown_0x08))

    def write(self, stream, write_data = True):
        stream.seek(self.data_offset + self.offset)

        self.name_offset = ut.search_index_dict(self.string_table.content, self.name)
        stream.write(ut.i2b(self.name_offset))
        stream.write(ut.i2b(self.unknown0x04))
        self.material_infos_count = len(self.infos)
        stream.write(ut.i2b(self.material_infos_count))

        for info in self.infos:
            info_name_offset = ut.search_index_dict(self.string_table.content, info[0])
            info_type_offset = ut.search_index_dict(self.string_table.content, info[1])
            stream.write(struct.pack('>iii', info_name_offset, info_type_offset, info[2]))

        return stream.tell()

    def __repr__(self):
        return (
            f'class: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'infos: {self.infos}\n'
        )

class SCNE_EYE_INFO:
    def __init__(self, type = '', name = b'DbzEyeInfo', string_table = '', size = 0):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table
        self.eye_count = int(size / SCNE_EYE_DATA.data_size)
        self.eye_entries = []

    def get_size(self, specific_include = True):
        return len(self.eye_entries) * SCNE_EYE_DATA.data_size

    def read(self, stream, data_offset = 0):
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset

        for i in range(self.eye_count):
            eye_data = SCNE_EYE_DATA(b'', self.string_table)
            eye_data.read(stream)
            self.eye_entries.append(eye_data)

    def write(self, stream, write_data = True):
        self.eye_count = len(self.eye_entries)
        for eye_entry in self.eye_entries:
            eye_entry.write(stream)
        
        return stream.tell()

    def load_data(self, data):
        for content_name, content_data in data.items():
            eye_data = SCNE_EYE_DATA(ut.s2b_name(content_name), self.string_table)
            eye_data.load_data(content_data['data'])
            self.eye_entries.append(eye_data)

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'offset', 'data_offset', 'type', \
                    'eye_count', 'eye_entries', 'string_table']
        for key in to_remove:
            del data[key]
        data['eye_entries'] = {}
        for entry in self.eye_entries:
            data['eye_entries'][ut.b2s_name(entry.name)] = entry.get_data()
        
        return data

class SCNE_EYE_DATA:
    data_size = 112

    def __init__(self, name = b'', string_table = ''):
        self.name = name
        self.string_table = string_table

    def read(self, stream):
        name_offset = ut.b2i(stream.read(4))
        if name_offset != 0:
            self.name = self.string_table.content[name_offset]

        self.data = []
        for i in range(9):
            self.data.append(struct.unpack('>fff', stream.read(12)))
        self.data = np.array(self.data)
    
    def write(self, stream):
        if self.name != b'':
            name_offset = ut.search_index_dict(self.string_table.content, self.name)
        else:
            name_offset = 0
        stream.write(ut.i2b(name_offset))
        for i in range(9):
            stream.write(struct.pack('>fff', *self.data[i]))

    def load_data(self, data):
        self.data = data

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'string_table']
        for key in to_remove:
            del data[key]
        data['data'] = self.data.tolist()
        
        return data