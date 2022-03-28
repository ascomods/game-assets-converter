import core.utils as ut
import struct

class TX2D:
    info_size = 36

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.unknown0x00 = 2
        self.unknown0x08 = 0
        self.depth = 1
        self.mipmap_count = 1
        self.unknown0x18 = 0
        self.string_table = string_table

    def get_size(self, specific_include = True):
        return self.info_size
    
    def read(self, stream, data_offset = 0):
        # Reading data info
        self.data_offset = data_offset
        self.unknown0x00 = ut.b2i(stream.read(4))
        self.vram_data_offset = ut.b2i(stream.read(4))
        self.unknown0x08 = ut.b2i(stream.read(4))
        self.vram_data_size = ut.b2i(stream.read(4))
        self.width = ut.b2i(stream.read(2))
        self.height = ut.b2i(stream.read(2))
        self.depth = ut.b2i(stream.read(2))
        self.mipmap_count = ut.b2i(stream.read(2))
        self.unknown0x18 = ut.b2i(stream.read(4))
        self.unknown0x1C = ut.b2i(stream.read(4))
        self.texture_type = ut.b2i(stream.read(4))

    def write(self, stream, write_data = True):
        stream.write(ut.i2b(self.unknown0x00))
        stream.write(ut.i2b(self.vram_data_offset))
        stream.write(ut.i2b(self.unknown0x08))
        stream.write(ut.i2b(len(self.vram_data)))
        stream.write(ut.i2b(self.width, 2))
        stream.write(ut.i2b(self.height, 2))
        stream.write(ut.i2b(self.depth, 2))
        stream.write(ut.i2b(self.mipmap_count, 2))
        stream.write(ut.i2b(self.unknown0x18))
        stream.write(ut.i2b(self.unknown0x1C))
        stream.write(ut.i2b(self.texture_type))
        return stream.tell()

    def read_vram(self, stream):
        stream.seek(self.vram_data_offset)
        self.vram_data = stream.read(self.vram_data_size)

    def get_vram(self):
        return self.vram_data
    
    def get_texture_type(self):
        if hex(self.texture_type) == '0x8000000':
            return 'DXT1'
        elif (hex(self.texture_type) == '0x18000000') or \
             (hex(self.texture_type) == '0x20000000'):
            return 'DXT5'
        elif self.texture_type == 0: # r8g8b8a8_typeless
            return '27'
        return '0'

    def get_swizzled_vram_data(self):
        data = self.vram_data
        if self.get_texture_type() == '27':
            data = bytearray()
            for i in range(0, len(self.vram_data), 4):
                elt = self.vram_data[i:i+4]
                # Swap bytes
                data.extend(struct.pack("<I", struct.unpack(">I", elt)[0]))
        return data

    def get_unswizzled_vram_data(self):
        data = self.vram_data
        if self.get_texture_type() == '27':
            data = bytearray()
            for i in range(0, len(self.vram_data), 4):
                elt = self.vram_data[i:i+4]
                # Swap bytes
                data.extend(struct.pack("<I", struct.unpack(">I", elt)[0]))
        return data
    
    def get_output_format(self):
        texture_type = self.get_texture_type()
        if (texture_type == 'DXT1') or (texture_type == 'DXT5'):
            return 'DDS'
        elif (texture_type == '27'):
            return 'BMP'
        return 'unknown'

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'vram_data_size: {self.vram_data_size}\n'
            f'resolution: {self.width}x{self.height}\n'
            f'mipmap_count: {self.mipmap_count}\n'
            f'texture_type: {hex(self.texture_type)}\n'
        )