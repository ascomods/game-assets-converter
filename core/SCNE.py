from typing import io
import os
import core.utils as ut

class SCNE_MODEL:
    data_size = 20

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table
        self.has_info = False
        self.data_type = b''
        self.linked_obj_name = b''
        self.parent_name = b''

    def update_offsets(self, data_offset, offset):
        self.data_offset = data_offset
        self.offset = offset

    def get_size(self, specific_include = True):
        return self.data_size
    
    def read(self, stream: io, data_offset = 0):
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset

        self.unknown0x00 = ut.b2i(stream.read(4))
        data_type_offset = ut.b2i(stream.read(4))
        if data_type_offset != 0:
            self.data_type = self.string_table.content[data_type_offset]
        name_offset = ut.b2i(stream.read(4))
        if name_offset != 0:
            self.name = self.string_table.content[name_offset]
        linked_obj_name_offset = ut.b2i(stream.read(4))
        if linked_obj_name_offset != 0:
            self.linked_obj_name = self.string_table.content[linked_obj_name_offset]
        parent_name_offset = ut.b2i(stream.read(4))
        if parent_name_offset != 0:
            self.parent_name = self.string_table.content[parent_name_offset]

    def write(self, stream: io, write_data = True):
        stream.seek(self.data_offset + self.offset)
        stream.write(ut.i2b(self.unknown0x00)) # Write unknown offset
        data_type_offset = ut.search_index_dict(self.string_table.content, self.data_type)
        stream.write(ut.i2b(data_type_offset))
        if self.name != b'':
            name_offset = ut.search_index_dict(self.string_table.content, self.name)
            stream.write(ut.i2b(name_offset))
        else:
            stream.write(bytes(4))
        if self.linked_obj_name != b'':
            linked_obj_name_offset = \
                ut.search_index_dict(self.string_table.content, self.linked_obj_name)
            stream.write(ut.i2b(linked_obj_name_offset))
        else:
            stream.write(bytes(4))
        if self.parent_name != b'':
            parent_name_offset = ut.search_index_dict(self.string_table.content, self.parent_name)
            stream.write(ut.i2b(parent_name_offset))
        else:
            stream.write(bytes(4))

    def load(self):
        has_data_dir = False
        if os.path.isdir("data"):
            os.chdir("data")
            has_data_dir = True
        data_lines = open("data.txt", 'r').read().splitlines()
        self.data_type = ut.s2b_name(data_lines[0])
        self.name = ut.s2b_name(data_lines[1])
        self.linked_obj_name = ut.s2b_name(data_lines[2])
        self.parent_name = ut.s2b_name(data_lines[3])

        if has_data_dir:
            os.chdir("..")

    def save(self, path, name = ''):
        if not os.path.exists(path):
            os.mkdir(path)

        output = open(path + 'data.txt', 'a')
        output.write(f'{ut.b2s_name(self.data_type)}\n')
        output.write(f'{ut.b2s_name(self.name)}\n')
        output.write(f'{ut.b2s_name(self.linked_obj_name)}\n')
        output.write(f'{ut.b2s_name(self.parent_name)}\n')

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'data_type: {self.data_type}\n'
            f'name: {self.name}\n'
            f'linked_obj_name: {self.linked_obj_name}\n'
            f'parent_name: {self.parent_name}\n'
        )