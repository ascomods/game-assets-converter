import core.utils as ut
import numpy as np
import struct
import copy

class SHAP:
    data_size = 48
    edge_info_size = 76

    def __init__(self, type = '', name = b'', string_table = ''):
        if type == '':
            self.type = self.__class__.__name__
        else:
            self.type = type
        self.name = name
        self.string_table = string_table
        if self.name == b'DbzEdgeInfo':
            self.has_padding = True
            data = np.array([
                (0.0, 0.0, 0.0, 5.0e-01),
                (0.0, 0.0, 0.0, 5.0e-01),
                (0.0, 0.0, 0.0, 0.0),
                (1.401298e-45, 1.0e-03, 5.0e-03, 3.0e-02)
            ], dtype='>f4')
            self.data = data.tobytes()
            self.source_name = b''
            self.source_type = b''
            self.unknown0x48 = 0
            self.data_size = 64
        elif self.name == b'DbzShapeInfo':
            self.data = struct.pack('>i', 0)
            self.data_size = 4
        else:
            self.data = bytes(self.data_size)
    
    def get_size(self, specific_include = True):
        if self.name == b'DbzEdgeInfo':
            return self.edge_info_size
        return len(self.data)

    def read(self, stream, data_offset = 0):
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset
        stream.seek(self.data_offset + self.offset)
        self.data = stream.read(self.data_size)

        if self.name == b'DbzEdgeInfo':
            source_name_offset = ut.b2i(stream.read(4))
            if source_name_offset != 0:
                self.source_name = self.string_table.content[source_name_offset]
            
            source_type_offset = ut.b2i(stream.read(4))
            if source_type_offset != 0:
                self.source_type = self.string_table.content[source_type_offset]
            self.unknown0x48 = ut.b2i(stream.read(4))
    
    def write(self, stream, write_data = True):
        self.offset = abs(stream.tell() - self.data_offset)
        stream.seek(self.data_offset + self.offset)
        stream.write(self.data)

        if self.name == b'DbzEdgeInfo':
            if self.source_name != b'':
                source_name_offset = ut.search_index_dict(self.string_table.content, self.source_name)
            else:
                source_name_offset = 0
            stream.write(ut.i2b(source_name_offset))
            if self.source_type != b'':
                source_type_offset = ut.search_index_dict(self.string_table.content, self.source_type)
            else:
                source_type_offset = 0
            stream.write(ut.i2b(source_type_offset))
            stream.write(ut.i2b(self.unknown0x48))
        return stream.tell()

    def load_data(self, content):
        self.data = np.array(content['data'], dtype='>f4').tobytes()
        
        if self.name == b'DbzEdgeInfo':
            self.source_name = ut.s2b_name(content['source_name'])
            self.source_type = ut.s2b_name(content['source_type'])
        
    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'data_size', 'has_padding', 'type', 'string_table', 'offset', 'data_offset']
        for key in to_remove:
            if key in data.keys():
                del data[key]
        if 'source_name' in data.keys():
            data['source_name'] = ut.b2s_name(self.source_name)
        if 'source_type' in data.keys():
            data['source_type'] = ut.b2s_name(self.source_type)
        data['data'] = np.frombuffer(self.data, dtype='>f').tolist()
        
        return data