from typing import io
import os, re
import core.utils as ut
from .TGA import TGA

class TX2D:
    info_size = 36

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table

    def update_offsets(self, data_offset, offset):
        self.data_offset = data_offset
        self.offset = ut.add_padding(offset)

    def get_size(self, specific_include = True):
        return self.info_size
    
    def read(self, stream: io, data_offset = 0):
        # Reading data info
        self.data_offset = data_offset
        self.unknown0x00 = ut.b2i(stream.read(4))
        self.vram_data_offset = ut.b2i(stream.read(4))
        self.unknown0x08 = ut.b2i(stream.read(4))
        self.vram_data_size = ut.b2i(stream.read(4))
        self.width = ut.b2i(stream.read(2))
        self.height = ut.b2i(stream.read(2))
        self.unknown0x14 = ut.b2i(stream.read(2))
        self.mipmapCount = ut.b2i(stream.read(2))
        self.unknown0x18 = ut.b2i(stream.read(4))
        self.unknown0x1C = ut.b2i(stream.read(4))
        self.unknown0x20 = ut.b2i(stream.read(4))

    def read_vram(self, stream: io):
        stream.seek(self.vram_data_offset)
        self.vram_data = stream.read(self.vram_data_size)
    
    def get_vram(self):
        return self.vram_data

    def write(self, stream: io, write_data = True):
        stream.write(ut.i2b(self.unknown0x00))
        stream.write(ut.i2b(self.vram_data_offset))
        stream.write(ut.i2b(self.unknown0x08))
        stream.write(ut.i2b(self.vram_data_size))
        stream.write(ut.i2b(self.width))
        stream.write(ut.i2b(self.height))
        stream.write(ut.i2b(self.unknown0x14))
        stream.write(ut.i2b(self.mipmapCount))
        stream.write(ut.i2b(self.unknown0x18))
        stream.write(ut.i2b(self.unknown0x1C))
        stream.write(ut.i2b(self.unknown0x20))

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

    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)

        output_object = TGA()
        output_object.data = self.data
        output_object.save(path)

        self.save_info_data(path, output_object.__class__.__name__)

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