import os
import struct

class TGA:
    def __init__(self, name, width, height, data):
        self.name = name
        # Header
        self.id_length = 0
        self.color_map_type = 0
        self.image_type = 2
        # Colormap specification
        self.first_index_entry = 0
        self.color_map_length = 0
        self.color_map_entry_size = 0
        # Image specification
        self.x_origin = 0
        self.y_origin = 0
        self.width = width
        self.height = height
        self.pixel_depth = 32
        self.image_descriptor = 0
        self.data = data
    
    def write(self, stream):
        stream.write(struct.pack('B', self.id_length))
        stream.write(struct.pack('B', self.color_map_type))
        stream.write(struct.pack('B', self.image_type))

        stream.write(struct.pack('h', self.first_index_entry))
        stream.write(struct.pack('h', self.color_map_length))
        stream.write(struct.pack('B', self.color_map_entry_size))

        stream.write(struct.pack('h', self.x_origin))
        stream.write(struct.pack('h', self.y_origin))
        stream.write(struct.pack('h', self.width))
        stream.write(struct.pack('h', self.height))
        stream.write(struct.pack('B', self.pixel_depth))
        stream.write(struct.pack('B', self.image_descriptor))
        stream.write(self.data)

    def save(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        
        stream = open(f"{path}/{self.name}.tga", 'wb')
        self.write(stream)
        stream.close()