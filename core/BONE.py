import core.utils as ut
import struct
import numpy as np
import copy
from .StringTable import StringTable

class BONE:
    info_entry_size = 36

    def __init__(self, type = '', name = b''):
        if type == '':
            self.type = self.__class__.__name__
        self.name = name
        self.unknown0x00 = 0
        self.unknown0x08 = 0
        self.unknown0x20 = 0
        self.bone_string_table = StringTable()
        self.bone_entries = []

    def get_size(self, include_entries = True):
        size = self.info_entry_size
        if include_entries:
            size += BONE_DATA.entry_size * len(self.bone_entries)
            # transforms size
            size += (BONE_DATA.transform_size * 3) * len(self.bone_entries)
            # raw data size
            size += 4 * len(self.bone_entries)
            # children offsets size
            size += 4 * len(self.bone_entries)
            # string table size
            size += ut.add_padding(self.bone_string_table.get_size())
        size = ut.add_padding(size)

        return size
    
    @ut.keep_cursor_pos
    def read(self, stream, data_offset = 0):
        self.base_offset = stream.tell()
        self.data_offset = data_offset   
        self.unknown0x00 = ut.b2i(stream.read(4))
        self.joint_count = ut.b2i(stream.read(4))
        self.unknown0x08 = ut.b2i(stream.read(4))
        self.offset = ut.b2i(stream.read(4))
        self.rel_transform_offset = ut.b2i(stream.read(4))
        self.abs_transform_offset = ut.b2i(stream.read(4))
        self.inv_transform_offset = ut.b2i(stream.read(4))
        self.hierarchy_data_offset = ut.b2i(stream.read(4))
        self.unknown0x20 = ut.b2i(stream.read(4))

        name_list = []
        for i in range(self.joint_count):
            bone_entry = BONE_DATA(self.bone_string_table)
            bone_entry.base_offset = self.base_offset
            bone_entry.read(stream)
            name_list.append(bone_entry.name)
            self.bone_entries.append(bone_entry)
        self.bone_string_table.build(name_list)
        
        # Setting parent bone for each bone
        for bone_entry in self.bone_entries:
            children = []
            for child_name in bone_entry.children_names:
                for bone in self.bone_entries:
                    if child_name == bone.name:
                        bone.parent = bone_entry
                        children.append(bone)
                        break
            bone_entry.children = children
    
    def sort_bones(self):
        root_bone = self.bone_entries[0]
        bone_list = [root_bone]
        bone_list.extend(root_bone.get_children(True))
        steps = root_bone.build_steps()

        i = 0
        for bone in bone_list:
            bone.index = i
            bone.group_idx = steps[i]
            i += 1
        self.bone_entries = bone_list

    def write(self, stream, write_data = True):
        # Rebuild bone hierarchy
        self.sort_bones()

        self.base_offset = stream.tell()
        stream.write(ut.i2b(self.unknown0x00))
        self.joint_count = len(self.bone_entries)
        stream.write(ut.i2b(self.joint_count))
        stream.write(ut.i2b(self.unknown0x08))
        self.offset = self.info_entry_size
        stream.write(ut.i2b(self.offset))
        self.rel_transform_offset = ut.add_padding(self.offset + \
            BONE_DATA.entry_size * self.joint_count)
        self.abs_transform_offset = self.rel_transform_offset + \
            BONE_DATA.transform_size * len(self.bone_entries)
        self.inv_transform_offset = self.abs_transform_offset + \
            BONE_DATA.transform_size * len(self.bone_entries)
        stream.write(ut.i2b(self.rel_transform_offset))
        stream.write(ut.i2b(self.abs_transform_offset))
        stream.write(ut.i2b(self.inv_transform_offset))
        self.hierarchy_data_offset = self.inv_transform_offset + \
            BONE_DATA.transform_size * len(self.bone_entries)
        stream.write(ut.i2b(self.hierarchy_data_offset))
        stream.write(bytes(4)) # unknown0x20
        
        if write_data:
            return self.write_data(stream)
        return stream.tell()
        
    def write_data(self, stream):
        children_offset = self.hierarchy_data_offset + 4 * len(self.bone_entries)
        rel_transform_offset = self.rel_transform_offset
        abs_transform_offset = self.abs_transform_offset
        inv_transform_offset = self.inv_transform_offset

        offset = stream.tell()
        node_count = 0
        for entry in self.bone_entries:
            entry.base_offset = self.base_offset
            entry.offset = offset
            offset += BONE_DATA.entry_size
            node_count += len(entry.children)
        
        steps = self.bone_entries[0].build_steps()
        for i in range(len(steps) - 1):
            # next bone has a child node
            if steps[i + 1] > steps[i]:
                self.bone_entries[i].hierarchy_bytes = b'\xFF\xFF\xFF\xFF'
            # next bone has no child node
            elif steps[i + 1] == steps[i]:
                self.bone_entries[i].hierarchy_bytes = bytes(4)
            # get back to higher node
            elif steps[i + 1] < steps[i]:
                self.bone_entries[i].hierarchy_bytes = ut.i2b(steps[i] - steps[i + 1])
        # steps to root bone
        self.bone_entries[-1].hierarchy_bytes = ut.i2b(steps[i + 1])

        self.bone_string_table.offset = children_offset + 4 * node_count
        resume_offset = stream.tell()
        stream.seek(self.base_offset + self.bone_string_table.offset)
        self.bone_string_table.write(stream)
        self.bone_string_table.offset = children_offset + 4 * node_count
        last_data_pos = ut.add_padding(stream.tell())
        if last_data_pos > stream.tell():
            stream.write(bytes(last_data_pos - stream.tell()))
        stream.seek(resume_offset)

        for entry in self.bone_entries:
            entry.children_offset = children_offset
            entry.rel_transform_offset = rel_transform_offset
            entry.abs_transform_offset = abs_transform_offset
            entry.inv_transform_offset = inv_transform_offset
            entry.write(stream)
            children_offset += 4 * len(entry.children)
            rel_transform_offset += BONE_DATA.transform_size
            abs_transform_offset += BONE_DATA.transform_size
            inv_transform_offset += BONE_DATA.transform_size
        
        stream.seek(self.base_offset + self.hierarchy_data_offset)

        for i in range(len(steps) - 1):
            # next bone has a child node
            if steps[i + 1] > steps[i]:
                stream.write(b'\xFF\xFF\xFF\xFF')
            # next bone has no child node
            elif steps[i + 1] == steps[i]:
                stream.write(bytes(4))
            # get back to higher node
            elif steps[i + 1] < steps[i]:
                stream.write(ut.i2b(steps[i] - steps[i + 1]))
        # steps to root bone
        stream.write(ut.i2b(steps[i + 1]))

        return last_data_pos

    def load_data(self, content):
        bytes_data = bytearray()
        for elt in content.values():
            bytes_data.extend(elt['unknown0x00'].encode('latin-1'))
            bytes_data.extend(np.array(elt['data'], dtype='>f').tobytes())
        self.data = bytes_data
        self.data_size = len(self.data)

    def get_data(self):
        data = []
        for entry in self.bone_entries:
            data.append({
                'transform1': entry.transform1.tolist(),
                'transform2': entry.transform2.tolist()
            })
        
        return data

class BONE_DATA:
    entry_size = 172
    transform_size = 64

    def __init__(self, bone_string_table):
        self.transform1 = np.array([
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0)
        ])
        self.transform2 = np.array([
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0)
        ])
        self.bone_string_table = bone_string_table
        self.children_names = []
        self.children = []
        self.parent = None
    
    def get_children(self, recursive = False):
        if recursive:
            children = []
            for bone in self.children:
                children.append(bone)
                children.extend(bone.get_children(recursive))
        else:
            return self.children
        return children

    def build_steps(self, level = 0):
        data = []
        data.append(level)
        for bone in self.children:
            data.extend(bone.build_steps(level + 1))
        return data

    def read(self, stream):
        self.index = ut.b2i(stream.read(4))
        self.name_offset = ut.b2i(stream.read(4))
        self.name = ut.read_until(stream, self.base_offset + self.name_offset)

        self.child_count = ut.b2i(stream.read(4))
        self.children_offset = ut.b2i(stream.read(4))

        resume_offset = stream.tell()
        if self.child_count > 0:
            stream.seek(self.base_offset + self.children_offset)
            for i in range (self.child_count):
                child_offset = ut.b2i(stream.read(4))
                next_child_offset = stream.tell()
                stream.seek(self.base_offset + child_offset + 4)
                child_name_offset = ut.b2i(stream.read(4))
                child_name = ut.read_until(stream, self.base_offset + child_name_offset)
                self.children_names.append(child_name)
                stream.seek(next_child_offset)
        
        stream.seek(resume_offset)
        self.rel_transform_offset = ut.b2i(stream.read(4))
        stream.seek(self.base_offset + self.rel_transform_offset)
        self.rel_transform = np.array([
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16))
        ]).transpose()

        stream.seek(resume_offset + 4)
        self.abs_transform_offset = ut.b2i(stream.read(4))
        stream.seek(self.base_offset + self.abs_transform_offset)
        self.abs_transform = np.array([
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16))
        ]).transpose()

        stream.seek(resume_offset + 8)
        self.inv_transform_offset = ut.b2i(stream.read(4))
        stream.seek(self.base_offset + self.inv_transform_offset)
        self.inv_transform = np.array([
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16))
        ], dtype=float).transpose()

        stream.seek(resume_offset + 12)
        self.group_idx = ut.b2i(stream.read(4))
        self.hierarchy_bytes = stream.read(4)
        self.unknown0x24 = stream.read(8)

        self.transform1 = np.array([
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16))
        ]).transpose()

        self.transform2 = np.array([
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16)),
            struct.unpack('>ffff', stream.read(16))
        ]).transpose()
    
    def write(self, stream):
        stream.write(ut.i2b(self.index))
        self.name_offset = self.bone_string_table.offset + \
            ut.search_index_dict(self.bone_string_table.content, self.name)
        stream.write(ut.i2b(self.name_offset))

        self.child_count = len(self.children)
        stream.write(ut.i2b(self.child_count))
        stream.write(ut.i2b(self.children_offset))

        resume_offset = stream.tell()
        if self.child_count > 0:
            stream.seek(self.base_offset + self.children_offset)
            for child in self.children:
                stream.write(ut.i2b(abs(child.offset - self.base_offset)))
        
        stream.seek(resume_offset)
        stream.write(ut.i2b(self.rel_transform_offset))
        stream.seek(self.base_offset + self.rel_transform_offset)
        rel_transform = self.rel_transform.transpose()

        stream.write(struct.pack('>ffff', *rel_transform[0]))
        stream.write(struct.pack('>ffff', *rel_transform[1]))
        stream.write(struct.pack('>ffff', *rel_transform[2]))
        stream.write(struct.pack('>ffff', *rel_transform[3]))
        
        stream.seek(resume_offset + 4)
        stream.write(ut.i2b(self.abs_transform_offset))
        stream.seek(self.base_offset + self.abs_transform_offset)
        abs_transform = self.abs_transform.transpose()
        stream.write(struct.pack('>ffff', *abs_transform[0]))
        stream.write(struct.pack('>ffff', *abs_transform[1]))
        stream.write(struct.pack('>ffff', *abs_transform[2]))
        stream.write(struct.pack('>ffff', *abs_transform[3]))

        stream.seek(resume_offset + 8)
        stream.write(ut.i2b(self.inv_transform_offset))
        stream.seek(self.base_offset + self.inv_transform_offset)
        inv_transform = self.inv_transform.transpose()
        stream.write(struct.pack('>ffff', *inv_transform[0]))
        stream.write(struct.pack('>ffff', *inv_transform[1]))
        stream.write(struct.pack('>ffff', *inv_transform[2]))
        stream.write(struct.pack('>ffff', *inv_transform[3]))

        stream.seek(resume_offset + 12)
        stream.write(ut.i2b(self.group_idx))
        stream.write(self.hierarchy_bytes)
        self.unknown0x24 = bytes(8)
        stream.write(self.unknown0x24)

        transform1 = self.transform1.transpose()
        stream.write(struct.pack('>ffff', *transform1[0]))
        stream.write(struct.pack('>ffff', *transform1[1]))
        stream.write(struct.pack('>ffff', *transform1[2]))
        stream.write(struct.pack('>ffff', *transform1[3]))

        transform2 = self.transform2.transpose()
        stream.write(struct.pack('>ffff', *transform2[0]))
        stream.write(struct.pack('>ffff', *transform2[1]))
        stream.write(struct.pack('>ffff', *transform2[2]))
        stream.write(struct.pack('>ffff', *transform2[3]))

        return stream.tell()

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'index: {self.index}\n'
            f'group_idx: {self.group_idx}\n'
            f'children: {self.children}\n'
        )

class BONE_INFO:
    info_size = 40

    def __init__(self, type = '', name = b'DbzBoneInfo', size = 0):
        if type == '':
            self.type = self.__class__.__name__
        else:
            self.type = type
        self.name = name
        self.data_size = size
    
    def get_size(self, specific_include = True):
        return len(self.data)

    def read(self, stream, data_offset = 0):
        self.offset = stream.tell() - data_offset
        self.data_offset = data_offset
        stream.seek(self.data_offset + self.offset)
        self.data = stream.read(self.data_size)
    
    def write(self, stream, write_data = True):
        self.offset = abs(stream.tell() - self.data_offset)
        stream.seek(self.data_offset + self.offset)
        stream.write(self.data)

        return stream.tell()

    def load_data(self, content):
        bytes_data = bytearray()
        for elt in content.values():
            bytes_data.extend(elt['unknown0x00'].encode('latin-1'))
            bytes_data.extend(np.array(elt['data'], dtype='>f').tobytes())
        self.data = bytes_data
        self.data_size = len(self.data)

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'type', 'data_size', 'offset', 'data_offset']
        for key in to_remove:
            if key in data.keys():
                del data[key]
        
        data['data'] = []
        bone_count = int(self.data_size / self.info_size)
        for i in range(bone_count):
            data_chunk = self.data[i * self.info_size:(i + 1) * self.info_size] 
            data['data'].append({
                'unknown0x00': data_chunk[:4].decode('latin-1'),
                'data': np.frombuffer(data_chunk[4:], dtype='>f').tolist()
            })
        
        return data