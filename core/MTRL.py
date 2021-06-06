from typing import io
import os, re
import core.utils as ut

class MTRL:
    layers_decl_data_size = 80

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table
        self.has_info = False
        self.child_count = 0
        self.child_offset = 0
        self.layers = []

    def update_offsets(self, data_offset, offset):
        self.data_offset = data_offset
        self.offset = ut.add_padding(offset)
        self.layers_decl_offset = offset + len(self.data)

    def get_size(self, specific_include = True):
        if specific_include:
            return len(self.data) + self.layers_decl_data_size
        return len(self.data)
    
    def read(self, stream: io, data_offset = 0):
        # Reading data info
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset
        if self.has_info:
            self.name_offset = ut.search_index_dict(self.string_table.content, 
                self.name)
            self.offset = ut.b2i(stream.read(4))
            self.data_size = ut.b2i(stream.read(4))
            self.child_count = ut.b2i(stream.read(4))
            self.child_offset = ut.b2i(stream.read(4))
        self.read_data(stream)
    
    @ut.keep_cursor_pos
    def read_data(self, stream: io):
        if self.has_info:
            stream.seek(self.data_offset + self.offset)
            self.data = stream.read(96)
            stream.seek(16, os.SEEK_CUR)
        else:
            self.data = stream.read(112) # reading unknown bytes

        self.layers_decl_offset = stream.tell() - self.data_offset
        for i in range(self.layers_decl_data_size // 8):
            try:
                layer_name = self.string_table.content[ut.b2i(stream.read(4))]
                source_name = self.string_table.content[ut.b2i(stream.read(4))]
                self.layers.append([layer_name, source_name])
            except Exception as e:
                pass

    def write(self, stream: io, write_data = True):

        if self.has_info:
            stream.write(ut.i2b(self.name_offset))
            stream.write(ut.i2b(self.offset))
            stream.write(ut.i2b(self.data_size))
            stream.write(ut.i2b(self.child_count))
            stream.write(ut.i2b(self.child_offset))
        self.write_data(stream)
    
    def write_data(self, stream: io):
        stream.seek(self.data_offset + self.offset)
        stream.write(self.data)

        if self.has_info:
            stream.seek(16, os.SEEK_CUR)
        else:
            stream.seek(self.data_offset + self.layers_decl_offset)
        
        for layer in self.layers:
            layer_name_offset = ut.search_index_dict(self.string_table.content, layer[0])
            stream.write(ut.i2b(layer_name_offset))
            source_name_offset = ut.search_index_dict(self.string_table.content, layer[1])
            stream.write(ut.i2b(source_name_offset))
        
        # Complete with zeros
        trailing_zeros = self.layers_decl_data_size - (len(self.layers) * 8)
        stream.write(bytes(trailing_zeros))

    def load(self):
        is_dir = False
        if os.path.isdir(self.name):
            os.chdir(self.name)
            is_dir = True
        elif os.path.isdir("data"):
            os.chdir("data")
            is_dir = True

        self.name = ut.s2b_name(re.sub('^\[\d+\]', '', ut.b2s_name(self.name)))
        data = open("data", "rb")
        self.data = data.read()
        self.data_size = ut.get_file_size("data")

        layers_data_lines = open("data.txt", 'r').read().splitlines()
        for i in range (0, len(layers_data_lines) - 1, 2):
            self.layers.append([ut.s2b_name(layers_data_lines[i]), 
                ut.s2b_name(layers_data_lines[i + 1])])

        if self.name != b'':
            self.name_offset = ut.search_index_dict(self.string_table.content, self.name)

        if is_dir:
            os.chdir("..")

    def save(self, path, name = ''):
        if self.has_info:
            path += ut.b2s_name(self.name) + '/'
        if not os.path.exists(path):
            os.mkdir(path)
        
        data_path = path + 'data'
        output = open(data_path, 'wb')
        output.write(self.data)

        layers_decl_data_path = path + 'data.txt'
        output = open(layers_decl_data_path, 'a')
        for layer in self.layers:
            output.write(f'{ut.b2s_name(layer[0])}\n')
            output.write(f'{ut.b2s_name(layer[1])}\n')

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
        )