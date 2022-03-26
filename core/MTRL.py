import core.utils as ut
import struct
import copy
import numpy as np
from natsort import natsorted

class MTRL:
    layers_decl_data_size = 80

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table
        self.data = bytes(112)
        self.layers = []

    def get_size(self, specific_include = True):
        if specific_include:
            return len(self.data) + self.layers_decl_data_size
        return len(self.data)
    
    def read(self, stream, data_offset = 0):
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset
        self.read_data(stream)
    
    @ut.keep_cursor_pos
    def read_data(self, stream):
        self.data = stream.read(112) # reading unknown bytes

        for i in range(10):
            try:
                layer_name = self.string_table.content[ut.b2i(stream.read(4))]
                source_name = self.string_table.content[ut.b2i(stream.read(4))]
                self.layers.append([layer_name, source_name])
            except Exception as e:
                pass

    def write(self, stream, write_data = True):
        self.offset = abs(stream.tell() - self.data_offset)
        self.name_offset = ut.search_index_dict(self.string_table.content, self.name)
        return self.write_data(stream)
    
    def write_data(self, stream):
        stream.seek(self.data_offset + self.offset)
        stream.write(self.data)
        for i in range(10):
            try:
                layer = self.layers[i]
                layer_name_offset = ut.search_index_dict(self.string_table.content, layer[0])
                stream.write(ut.i2b(layer_name_offset))
                source_name_offset = ut.search_index_dict(self.string_table.content, layer[1])
                stream.write(ut.i2b(source_name_offset))
            except:
                stream.write(bytes(8))
        return stream.tell()

    def load_data(self, content):
        self.data = np.array(content['data'], dtype='>f4').tobytes()

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'type', 'string_table', 'offset', 'layers', 'data_offset']
        for key in to_remove:
            del data[key]
        data['data'] = np.frombuffer(data['data'], dtype='>f').tolist()
        return data

    def sort(self, color_map_first = False):
        """
        Sort layers by putting colormaps either first or last
        """
        sortedLayers = []
        
        if color_map_first:
            names = []
            for layer in self.layers:
                names.append(layer[0])
            names = natsorted(names)

            for layer_name in names:
                for layer in self.layers:
                    if layer[0] == layer_name:
                        sortedLayers.append(layer)
                        break
        else:
            for layer in self.layers:
                if layer[0] not in [b'COLORMAP', b'COLORMAP0']:
                    sortedLayers.append(layer)

            for layer in self.layers:
                if layer[0] in [b'COLORMAP', b'COLORMAP0']:
                    sortedLayers.append(layer)
        
        self.layers = sortedLayers

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'data_size: {self.data_size}\n'
            f'data_offset: {self.data_offset}\n'
            f'offset: {self.offset}\n'
            f'layers: {self.layers}\n'
        )

class MTRL_PROP:
    # Credits to adsl14 for attributes infos
    data_size = 96

    def __init__(self, type = '', name = b'DbzCharMtrl', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.string_table = string_table
        self.has_padding = True

        self.illumination_shadow_orientation = 1.0e-01
        self.illumination_light_orientation_glow = 1.7e-01

        self.unknown0x08 = (1.0e+00, 7.0e-01)

        self.brightness_purple_light_glow = 7.0e-01
        self.saturation_glow = 2.0e-01
        self.saturation_base = 0.0e+00

        self.brightness_toonmap_active_some_positions = 0.0e+00
        self.brightness_toonmap = 0.0e+00
        self.brightness_toonmap_active_other_positions = 0.0e+00

        self.brightness_incandescence_active_some_positions = 4.0e-01
        self.brightness_incandescence = 1.0e+00
        self.brightness_incandescence_active_other_positions = 0.0e+00

        self.border_rgba = (4.0e-01, 4.0e-01, 4.0e-01, 8.0e-01)
        self.unknown0x44 = (2.0e-01, 2.0e-01, 2.0e-01)
        self.unknown0x50 = (0.0, 0.0, 0.0, 0.0)

    def get_size(self, specific_include = True):
        return self.data_size
    
    def read(self, stream, data_offset = 0):
        self.offset = ut.add_padding(stream.tell() - data_offset)
        self.data_offset = data_offset

        self.illumination_shadow_orientation = struct.unpack('>f', stream.read(4))[0]
        self.illumination_light_orientation_glow = struct.unpack('>f', stream.read(4))[0]

        self.unknown0x08 = struct.unpack('>ff', stream.read(8))

        self.brightness_purple_light_glow = struct.unpack('>f', stream.read(4))[0]
        self.saturation_glow = struct.unpack('>f', stream.read(4))[0]
        self.saturation_base = struct.unpack('>f', stream.read(4))[0]

        self.brightness_toonmap_active_some_positions = struct.unpack('>f', stream.read(4))[0]
        self.brightness_toonmap = struct.unpack('>f', stream.read(4))[0]
        self.brightness_toonmap_active_other_positions = struct.unpack('>f', stream.read(4))[0]

        self.brightness_incandescence_active_some_positions = struct.unpack('>f', stream.read(4))[0]
        self.brightness_incandescence = struct.unpack('>f', stream.read(4))[0]
        self.brightness_incandescence_active_other_positions = struct.unpack('>f', stream.read(4))[0]

        self.border_rgba = struct.unpack('>ffff', stream.read(16))
        self.unknown0x44 = struct.unpack('>fff', stream.read(12))
        self.unknown0x50 = struct.unpack('>ffff', stream.read(16))

    def write(self, stream, write_data = True):
        self.offset = abs(stream.tell() - self.data_offset)
        self.name_offset = ut.search_index_dict(self.string_table.content, self.name)
        stream.seek(self.data_offset + self.offset)

        stream.write(struct.pack('>f', self.illumination_shadow_orientation))
        stream.write(struct.pack('>f', self.illumination_light_orientation_glow))

        stream.write(struct.pack('>ff', *self.unknown0x08))

        stream.write(struct.pack('>f', self.brightness_purple_light_glow))
        stream.write(struct.pack('>f', self.saturation_glow))
        stream.write(struct.pack('>f', self.saturation_base))

        stream.write(struct.pack('>f', self.brightness_toonmap_active_some_positions))
        stream.write(struct.pack('>f', self.brightness_toonmap))
        stream.write(struct.pack('>f', self.brightness_toonmap_active_other_positions))

        stream.write(struct.pack('>f', self.brightness_incandescence_active_some_positions))
        stream.write(struct.pack('>f', self.brightness_incandescence))
        stream.write(struct.pack('>f', self.brightness_incandescence_active_other_positions))

        stream.write(struct.pack('>ffff', *self.border_rgba))
        stream.write(struct.pack('>fff', *self.unknown0x44))
        stream.write(struct.pack('>ffff', *self.unknown0x50))

        return stream.tell()

    def load_data(self, content):
        data = content['data']
        self.illumination_shadow_orientation = data['illumination_shadow_orientation']
        self.illumination_light_orientation_glow = data['illumination_light_orientation_glow']

        self.unknown0x08 = data['unknown0x08']

        self.brightness_purple_light_glow = data['brightness_purple_light_glow']
        self.saturation_glow = data['saturation_glow']
        self.saturation_base = data['saturation_base']

        self.brightness_toonmap_active_some_positions = data['brightness_toonmap_active_some_positions']
        self.brightness_toonmap = data['brightness_toonmap']
        self.brightness_toonmap_active_other_positions = data['brightness_toonmap_active_other_positions']

        self.brightness_incandescence_active_some_positions = data['brightness_incandescence_active_some_positions']
        self.brightness_incandescence = data['brightness_incandescence']
        self.brightness_incandescence_active_other_positions = data['brightness_incandescence_active_other_positions']

        self.border_rgba = data['border_rgba']
        self.unknown0x44 = data['unknown0x44']
        self.unknown0x50 = data['unknown0x50']

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'type', 'has_padding', 'string_table', 'offset', 'data_offset']
        for key in to_remove:
            del data[key]
        
        return data