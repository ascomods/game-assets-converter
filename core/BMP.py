import os
import struct
import core.utils as ut

class BMP:
    def __init__(self, name, width = 0, height = 0, data = b''):
        self.name = name
        self.ext = f".{self.__class__.__name__.lower()}"

        # File header
        self.bf_size = 0
        self.bf_reserved1 = 0
        self.bf_reserved2 = 0
        self.bf_off_bits = 54

        # Info header
        self.bi_size = 40
        self.bi_width = width
        self.bi_height = height
        self.bi_plane = 1
        self.bi_bit_count = 32
        self.bi_compression = 0
        self.bi_size_image = 0
        self.bi_x_pels_per_meter = 2834
        self.bi_y_pels_per_meter = 2834
        self.bi_clr_used = 0
        self.bi_clr_important = 0
        self.data = data
    
    def get_name(self):
        name = self.name
        if self.ext not in name:
            name += self.ext
        return name        
    
    def read(self, stream):
        if stream.read(2) != ut.s2b_name('BM'): # check data tag
            raise Exception("Not a bitmap file")
        self.bf_size = struct.unpack('<i', stream.read(4))[0]
        self.bf_reserved1 = struct.unpack('<h', stream.read(2))[0]
        self.bf_reserved2 = struct.unpack('<h', stream.read(2))[0]
        self.bf_off_bits = struct.unpack('<i', stream.read(4))[0]

        self.bi_size = struct.unpack('<i', stream.read(4))[0]
        self.bi_width = struct.unpack('<l', stream.read(4))[0]
        self.bi_height = struct.unpack('<l', stream.read(4))[0]
        self.bi_plane = struct.unpack('<h', stream.read(2))[0]
        self.bi_bit_count = struct.unpack('<h', stream.read(2))[0]
        self.bi_compression = struct.unpack('<i', stream.read(4))[0]
        self.bi_size_image = struct.unpack('<i', stream.read(4))[0]
        self.bi_x_pels_per_meter = struct.unpack('<l', stream.read(4))[0]
        self.bi_y_pels_per_meter = struct.unpack('<l', stream.read(4))[0]
        self.bi_clr_used = struct.unpack('<i', stream.read(4))[0]
        self.bi_clr_important = struct.unpack('<i', stream.read(4))[0]
        self.data = stream.read()

    def write(self, stream):
        stream.write(ut.s2b_name('BM')) # data tag
        self.bf_size = self.bf_off_bits + len(self.data)
        stream.write(struct.pack('<i', self.bf_size))
        stream.write(struct.pack('<h', self.bf_reserved1))
        stream.write(struct.pack('<h', self.bf_reserved2))
        stream.write(struct.pack('<i', self.bf_off_bits))

        stream.write(struct.pack('<i', self.bi_size))
        stream.write(struct.pack('<l', self.bi_width))
        stream.write(struct.pack('<l', self.bi_height))
        stream.write(struct.pack('<h', self.bi_plane))
        stream.write(struct.pack('<h', self.bi_bit_count))
        stream.write(struct.pack('<i', self.bi_compression))
        stream.write(struct.pack('<i', self.bi_size_image))
        stream.write(struct.pack('<l', self.bi_x_pels_per_meter))
        stream.write(struct.pack('<l', self.bi_y_pels_per_meter))
        stream.write(struct.pack('<i', self.bi_clr_used))
        stream.write(struct.pack('<i', self.bi_clr_important))
        stream.write(self.data)

    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        
        stream = open(f"{path}/{self.name}{self.ext}", 'wb')
        self.write(stream)
        stream.close()