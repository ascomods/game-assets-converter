import os
import core.utils as ut
import struct

class DDS:
    header_size = 124

    def __init__(self, name, width = 0, height = 0, data = b'', dds_format = '', mipmaps=0):
        self.name = name
        self.ext = f".{self.__class__.__name__.lower()}"

        # DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT | DDSD_LINEARSIZE
        self.flags = b'\x07\x10\x0A\x00'
        self.height = height
        self.width = width
        self.pitch_or_linear_size = len(data)
        self.depth = 1
        self.mipmap_count = mipmaps
        self.reserved = bytes(44)

        # DDS Pixel format
        self.pix_size = 32
        # DDPF_FOURCC
        self.pix_flags = b'\x04\x00\x00\x00'
        self.type = ut.s2b_name(dds_format)
        self.rgb_bit_count = 0
        self.r_bit_mask = 0
        self.g_bit_mask = 0
        self.b_bit_mask = 0
        self.a_bit_mask = 0

        # DDSCAPS_COMPLEX | DDSCAPS_TEXTURE | DDSCAPS_MIPMAP
        self.caps = b'\x08\x10\x40\x00'
        self.caps2 = 0
        self.caps3 = 0
        self.caps4 = 0
        self.reserved2 = 0

        self.data = data

    def get_name(self):
        name = self.name
        if self.ext not in name:
            name += self.ext
        return name 

    def read(self, stream):
        if stream.read(4) != ut.s2b_name('DDS '): # check data tag
            raise Exception("Not a DDS file")
        
        self.header_size = struct.unpack('<i', stream.read(4))[0]
        self.flags = stream.read(4)
        self.height = struct.unpack('<i', stream.read(4))[0]
        self.width = struct.unpack('<i', stream.read(4))[0]
        self.depth = struct.unpack('<i', stream.read(4))[0]
        self.pitch_or_linear_size = struct.unpack('<i', stream.read(4))[0]
        self.mipmap_count = struct.unpack('<i', stream.read(4))[0]
        self.reserved = stream.read(44)
        
        self.pix_size = struct.unpack('<i', stream.read(4))[0]
        self.pix_flags = stream.read(4)
        self.type = stream.read(4)
        self.rgb_bit_count = struct.unpack('<i', stream.read(4))[0]
        self.r_bit_mask = struct.unpack('<i', stream.read(4))[0]
        self.g_bit_mask = struct.unpack('<i', stream.read(4))[0]
        self.b_bit_mask = struct.unpack('<i', stream.read(4))[0]
        self.a_bit_mask = struct.unpack('<i', stream.read(4))[0]

        self.caps = stream.read(4)
        self.caps2 = struct.unpack('<i', stream.read(4))[0]
        self.caps3 = struct.unpack('<i', stream.read(4))[0]
        self.caps4 = struct.unpack('<i', stream.read(4))[0]
        self.reserved2 = struct.unpack('<i', stream.read(4))[0]

        self.data = stream.read()
    
    def write(self, stream):
        stream.write(ut.s2b_name('DDS ')) # data tag
        stream.write(struct.pack('<i', self.header_size))
        stream.write(self.flags)
        stream.write(struct.pack('<i', self.height))
        stream.write(struct.pack('<i', self.width))
        self.pitch_or_linear_size = len(self.data)
        stream.write(struct.pack('<i', self.pitch_or_linear_size))
        stream.write(struct.pack('<i', self.depth))
        stream.write(struct.pack('<i', self.mipmap_count))
        stream.write(self.reserved)

        stream.write(struct.pack('<i', self.pix_size))
        stream.write(self.pix_flags)
        stream.write(self.type)
        stream.write(struct.pack('<i', self.rgb_bit_count))
        stream.write(struct.pack('<i', self.r_bit_mask))
        stream.write(struct.pack('<i', self.g_bit_mask))
        stream.write(struct.pack('<i', self.b_bit_mask))
        stream.write(struct.pack('<i', self.a_bit_mask))

        stream.write(self.caps)
        stream.write(struct.pack('<i', self.caps2))
        stream.write(struct.pack('<i', self.caps3))
        stream.write(struct.pack('<i', self.caps4))
        stream.write(struct.pack('<i', self.reserved2))

        stream.write(self.data)
    
    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        stream = open(f"{path}/{self.name}{self.ext}", 'wb')
        self.write(stream)