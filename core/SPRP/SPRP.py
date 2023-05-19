import os
import core.utils as ut
import copy
from natsort import natsorted
from core.TX2D import *
from core.VBUF import *
from core.MTRL import *
from core.SHAP import *
from core.SCNE import *
from core.BONE import *
from core.StringTable import StringTable

class SPRP:
    header_size = 64
    header_entry_size = 12

    ordered_types = [
        'TX2D', 'VSHD', 'PSHD',
        'MTRL', 'SHAP', 'VBUF',
        'SCNE', 'ANIM', 'BONE',
        'DRVN', 'TXAN'
    ]

    def __init__(self, name, size = 0):
        if (name.__class__.__name__ == 'str'):
            name = ut.s2b_name(name)
        self.name = name
        self.size = size
        self.string_table = StringTable()
        self.entries = []
        self.start_offset = 0
        self.ioram_data_size = 0
        self.vram_data_size = 0

    def get_size(self):
        return self.size

    def read(self, stream, start_offset):
        self.start_offset = start_offset
        stream.seek(self.start_offset)
        stream.seek(8, os.SEEK_CUR) # skip tag + unknown bytes
        entry_count = ut.b2i(stream.read(4))
        stream.seek(4, os.SEEK_CUR) # skip unknown bytes

        # Reading header
        header_name_offset = ut.b2i(stream.read(4))
        self.entry_info_size = ut.b2i(stream.read(4))
        string_table_size = ut.b2i(stream.read(4))
        self.data_info_size = ut.b2i(stream.read(4))
        self.data_block_size = ut.b2i(stream.read(4))
        ioram_name_offset = ut.b2i(stream.read(4))
        self.ioram_data_size = ut.b2i(stream.read(4))
        vram_name_offset = ut.b2i(stream.read(4))
        self.vram_data_size = ut.b2i(stream.read(4))
        stream.seek(12, os.SEEK_CUR) # skip unknown bytes
        entry_info_offset = self.start_offset + self.header_size
        string_table_offset = entry_info_offset + self.entry_info_size
        self.string_table = StringTable()
        self.string_table.offset = string_table_offset
        self.string_table.read(stream, string_table_size, 1)

        try:
            self.header_name = self.string_table.content[header_name_offset]
        except:
            self.header_name = ''
        try:
            self.ioram_name = self.string_table.content[ioram_name_offset]
        except:
            self.ioram_name = ''
        try:
            self.vram_name = self.string_table.content[vram_name_offset]
        except:
            self.vram_name = ''

        self.info_offset = string_table_offset + string_table_size
        data_offset = self.info_offset + self.data_info_size
        entry_offset = 0

        for i in range(entry_count):
            entry_object = SPRPEntry(self.string_table)
            entry_offset += entry_object.read(stream, 
                self.info_offset + entry_offset, data_offset)
            self.entries.append(entry_object)
    
    def write(self, stream):
        self.start_offset = stream.tell()
        # Writing header
        stream.write(self.__class__.__name__.encode('utf-8'))
        stream.write(ut.i2b(1, 2)) # write unknown bytes
        stream.write(ut.i2b(1, 2)) # write unknown bytes
        stream.write(ut.i2b(len(self.entries)))
        stream.write(bytes(4))

        try:
            header_name_offset = ut.search_index_dict(self.string_table.content, self.header_name)
        except:
            header_name_offset = 0
        try:
            ioram_name_offset = ut.search_index_dict(self.string_table.content, self.ioram_name)
        except:
            ioram_name_offset = 0
        try:
            vram_name_offset = ut.search_index_dict(self.string_table.content, self.vram_name)
        except:
            vram_name_offset = 0

        stream.write(ut.i2b(header_name_offset))
        self.entry_info_size = ut.add_padding(len(self.entries) * self.header_entry_size)
        stream.write(ut.i2b(self.entry_info_size))
        string_table_size_offset = stream.tell()
        stream.seek(4, os.SEEK_CUR)
        self.data_info_size = 0
        for entry in self.entries:
            self.data_info_size += SPRPEntry.data_entry_size * len(entry.entries)
        stream.write(ut.i2b(self.data_info_size))
        data_block_size_offset = stream.tell()
        stream.seek(4, os.SEEK_CUR)
        stream.write(ut.i2b(ioram_name_offset))
        stream.write(ut.i2b(self.ioram_data_size))
        stream.write(ut.i2b(vram_name_offset))
        stream.write(ut.i2b(self.vram_data_size))
        stream.write(bytes(12))
        
        for entry in self.entries:
            entry.write(stream)
        # Padding after info block
        stream.seek(ut.add_padding(stream.tell()))
        self.string_table.write(stream)
        self.info_offset = ut.add_padding(stream.tell())
        string_table_size = self.info_offset - self.string_table.offset
        stream.seek(string_table_size_offset)
        stream.write(ut.i2b(string_table_size))
        stream.seek(self.info_offset)
        
        last_data_pos = self.info_offset + self.data_info_size
        offset = 0
        for entry in self.entries:
            last_data_pos = entry.write_data(stream, self.info_offset + self.data_info_size, offset)
            offset = abs(self.info_offset + self.data_info_size - last_data_pos)
        
        current_pos = last_data_pos
        data_offset = self.info_offset + self.data_info_size
        self.data_block_size = abs(current_pos - data_offset)
        stream.seek(data_block_size_offset)
        stream.write(ut.i2b(self.data_block_size))
        
        stream.seek(0, os.SEEK_END)
        self.size = stream.tell() - self.start_offset

    def search_entries(self, entry_list, entry_class, get_group = False):
        for entry in self.entries:
            if get_group and entry.data_type == ut.s2b_name(entry_class):
                return entry
            if entry.__class__.__name__ == entry_class:
                entry_list.append(entry)
            else:
                entry_list = entry.search_entries(entry_list, entry_class)
        return entry_list

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'entries', 'string_table']
        for key in to_remove:
            del data[key]
        for entry in self.entries:
            data[ut.b2s_name(entry.data_type)] = entry.get_data()
        
        return data

    def load(self, path):
        from .SPRPImporter import SPRPImporter
        importer = SPRPImporter()
        importer.start(self, path)

    def save(self, path):
        from .SPRPExporter import SPRPExporter
        exporter = SPRPExporter()
        exporter.start(self, path)

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'size: {self.size}\n'
            f'entries: {self.entries}'
        )

class SPRPEntry:
    data_entry_size = 32

    def __init__(self, string_table, data_type = b''):
        self.string_table = string_table
        self.data_type = data_type
        self.entries = []
        self.size = 0

    def get_size(self, include_children = True, with_padding = False):
        size = 0
        for entry in self.entries:
            entry_size = entry.get_size(include_children)
            if with_padding:
                entry_size = ut.add_padding(entry_size)
            size += entry_size
        return size

    def read(self, stream, info_offset, data_offset):
        self.info_offset = info_offset
        self.data_offset = data_offset
        # read info entry
        self.data_type = stream.read(4)
        stream.seek(4, os.SEEK_CUR) # skip unknown bytes
        self.data_count = ut.b2i(stream.read(4))
        self.read_data(stream)
        # return block size for next info offset
        return self.data_entry_size * self.data_count
    
    @ut.keep_cursor_pos
    def read_data(self, stream):
        stream.seek(self.info_offset)

        for i in range(self.data_count):
            stream.seek(8, os.SEEK_CUR) # skip data_type + index number
            name_offset = ut.b2i(stream.read(4))
            name = self.string_table.content[name_offset]
            data_object = SPRPDataEntry(self.data_type, name, 
                self.string_table, True)
            data_object.read(stream, self.data_offset)
            self.entries.append(data_object)
    
    def write(self, stream):
        # writing info entry
        stream.write(self.data_type)
        stream.write(bytes(4)) # skip unknown bytes
        stream.write(ut.i2b(len(self.entries)))

    def write_data(self, stream, data_offset, offset = 0):
        last_data_pos = data_offset
        
        for i in range(len(self.entries)):
            stream.write(self.data_type)
            stream.write(ut.i2b(i))
            name_offset = ut.search_index_dict(self.string_table.content, 
                self.entries[i].name)
            stream.write(ut.i2b(name_offset))
            last_data_pos = self.entries[i].write(stream, True, data_offset, offset)
            offset += ut.add_padding(self.entries[i].get_size(True))
        
        return ut.add_padding(last_data_pos)

    def search_entries(self, entry_list, criteria):
        for entry in self.entries:
            if (entry.__class__.__name__ == criteria) or \
               (criteria in ut.b2s_name(entry.name)):
                entry_list.append(entry)
            else:
                entry.search_entries(entry_list, criteria)
        return entry_list

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['data_type', 'entries', 'string_table', 'size', 
                     'data_offset', 'info_offset', 'data_count']
        for key in to_remove:
            del data[key]
        
        for entry in self.entries:
            name = ut.b2s_name(entry.name)

            i = 0
            found = False
            for key in data.keys():
                if (name == key) or ((name in key) and ('|#|' in key)):
                    found = True
                    break

            if found:
                if '|#|' not in key:
                    new_name = f"0|#|{name}"
                    data[new_name] = data[name]
                    del data[name]
                else:
                    i = int(key.rsplit('|#|')[0]) + 1
                    new_name = f"{i}|#|{name}"

                while new_name in data.keys():
                    i += 1
                    new_name = f"{i}|#|{name}"
                data[new_name] = entry.get_data()
            else:
                data[name] = entry.get_data()
        
        return data

    def sort(self):
        names = []
        for entry in self.entries:
            names.append(entry.name)
        names = natsorted(names)

        entries = []
        for name in names:
            for entry in self.entries:
                if entry.name == name:
                    entries.append(entry)
        self.entries = entries

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'type: {self.data_type}\n'
            f'content: {self.entries}'
        )

class SPRPDataEntry:
    info_entry_size = 20

    def __init__(self, data_type, name, string_table, is_main_type = False):
        self.type = data_type
        self.name = name
        self.string_table = string_table
        self.is_main_type = is_main_type
        self.children = []
        self.size = 0
        self.child_offset = 0
        
    def get_size(self, include_children = False, add_gap = True):
        size = 0
        if include_children:
            for child in self.children:
                child_size = child.get_size(include_children)
                size += child_size
                if add_gap:
                    size += self.info_entry_size
        
        if hasattr(self, 'data'):
            if (self.data.__class__.__name__ != 'bytes'):
                if self.data.__class__.__name__ == 'VBUF':
                    size += self.data.get_size(include_children)
                else:
                    size += self.data.get_size()
            else:
                size += len(self.data)
        return size
        
    def read(self, stream, data_offset):
        # Reading data info
        self.data_offset = data_offset
        self.offset = ut.b2i(stream.read(4))
        self.size = ut.b2i(stream.read(4))
        child_count = ut.b2i(stream.read(4))
        self.child_offset = ut.b2i(stream.read(4))
        stream.seek(4, os.SEEK_CUR) # skip unknown bytes
        self.read_data(stream, child_count)
    
    @ut.keep_cursor_pos
    def read_data(self, stream, child_count):
        stream.seek(self.data_offset + self.offset)

        try:
            if self.type == b'SCNE':
                if len(self.name.rsplit(b'|')) > 1:
                    data_object = SCNE('', b'', self.string_table)
                elif b'[MATERIAL]' == self.name:
                    data_object = SCNE_MATERIAL('', b'', self.string_table)
                elif b'DbzEyeInfo' in self.name:
                    data_object = SCNE_EYE_INFO('', b'', self.string_table, self.size)
            elif self.type == b'TX2D':
                self.name = ut.format_jap_name(self.name)
                data_object = TX2D('', self.name, self.string_table)
            elif self.type == b'MTRL':
                if b'Dbz' in self.name:
                    data_object = MTRL_PROP('', self.name, self.string_table)
                else:
                    data_object = MTRL('', self.name, self.string_table)
            elif self.type == b'SHAP':
                data_object = SHAP('', self.name, self.string_table)
            elif self.type == b'BONE':
                if b'NULL' in self.name:
                    data_object = BONE('', self.name)
                elif self.name == b'DbzBoneInfo':
                    data_object = BONE_INFO('', b'', self.size)
                else:
                    data_object = BONE_INFO('', self.name, self.size)
                    data_object.info_size = 20
            else:
                data_object = eval(self.type)('', b'', self.string_table)
            data_object.read(stream, self.data_offset)

            self.data = data_object
        except Exception as e:
            self.data = stream.read(self.size)

        if child_count > 0:
            for i in range(child_count):
                stream.seek(self.data_offset + self.child_offset + 
                    (self.info_entry_size * i))
                name_offset = ut.b2i(stream.read(4))
                name = self.string_table.content[name_offset]
                
                try:
                    child_class = ut.b2s_name(self.type)
                    if child_class not in ['BONE', 'SCNE']:
                        if b'Dbz' not in name:
                            child_object = eval(child_class)(self.type, name, self.string_table)
                        else:
                            raise Exception()
                    else:
                        raise Exception()
                except Exception as e:
                    child_object = self.__class__(self.type, name, self.string_table)
                
                child_object.read(stream, self.data_offset)
                self.children.append(child_object)
    
    def write(self, stream, with_data = True, data_offset = -1, offset = -1):
        if data_offset != -1:
            self.data_offset = data_offset
        if not self.is_main_type:
            name_offset = ut.search_index_dict(self.string_table.content, self.name)
            stream.write(ut.i2b(name_offset))
        if offset != -1:
            self.offset = offset
        if hasattr(self, 'data'):
            if hasattr(self.data, 'has_padding') and self.data.has_padding:
                self.offset = ut.add_padding(self.offset)
        stream.write(ut.i2b(self.offset))
        self.size = self.get_size()
        stream.write(ut.i2b(self.size))
        stream.write(ut.i2b(len(self.children)))
        if len(self.children) > 0:
            self.child_offset = self.offset + self.size
        stream.write(ut.i2b(self.child_offset))

        if self.is_main_type:
            stream.write(bytes(4)) # skip unknown bytes
        
        last_pos = stream.tell()
        if with_data:
            last_pos = self.write_data(stream)
        
        return last_pos

    @ut.keep_cursor_pos
    def write_data(self, stream):
        stream.seek(self.data_offset + self.offset)

        try:
            self.data.data_offset = self.data_offset
            self.data.offset = self.offset
            self.data.child_offset = self.child_offset
            last_pos = self.data.write(stream)
        except Exception as e:
            if hasattr(self, 'data'):
                stream.seek(self.data_offset + self.offset)
                stream.write(self.data)
            last_pos = stream.tell()

        if len(self.children) > 0:
            stream.seek(self.data_offset + self.child_offset)
            # Update offsets for each child
            for i in range(len(self.children)):
                self.children[i].data_offset = self.data_offset
                self.children[i].offset = self.child_offset
                if i > 0:
                    self.children[i].offset = self.children[i - 1].offset + \
                        self.children[i - 1].get_size(True)
                else:
                    self.children[i].offset += 20 * len(self.children)
                if self.type == b'BONE' or self.children[i].name == b'DbzEyeInfo':
                    self.children[i].offset = ut.add_padding(self.children[i].offset)
                self.children[i].write(stream, False)
            for i in range(len(self.children)):
                last_pos = self.children[i].write_data(stream)
        
        return last_pos

    def get_data(self):
        data = copy.deepcopy(vars(self))
        to_remove = ['name', 'type', 'size', 'is_main_type', 'string_table', 'offset',
                     'data_offset', 'child_offset', 'children']
        for key in to_remove:
            del data[key]

        if hasattr(self, 'data'):
            if self.data.__class__.__name__ != 'bytes':
                if hasattr(self.data, 'get_data'):
                    data['data'] = self.data.get_data()
            else:
                data['data'] = self.data.decode('latin-1')
        if len(self.children) > 0:
            data['children'] = {}

            for child in self.children:
                name = ut.b2s_name(child.name)

                i = 0
                found = False
                for key in data['children'].keys():
                    if (name == key) or ((name in key) and ('|#|' in key)):
                        found = True
                        break

                if found:
                    if '|#|' not in key:
                        new_name = f"0|#|{name}"
                        data['children'][new_name] = data['children'][name]
                        del data['children'][name]
                    else:
                        i = int(key.rsplit('|#|')[0]) + 1
                        new_name = f"{i}|#|{name}"

                    while new_name in data['children'].keys():
                        i += 1
                        new_name = f"{i}|#|{name}"
                    data['children'][new_name] = child.get_data()
                else:
                    data['children'][name] = child.get_data()

        return data

    def search_entries(self, entry_list, criteria):
        if ut.b2s_name(self.name) == criteria:
            entry_list.append(self)
        elif ut.b2s_name(self.type) == criteria and (criteria == 'SCNE' or criteria == 'BONE'):
            entry_list.append(self)
        elif hasattr(self, 'data'):
            if self.data.__class__.__name__ == criteria:
                entry_list.append(self)
            elif (self.data.__class__.__name__ == self.__class__.__name__):
                entry_list = self.data.search_entries(entry_list, criteria)
        if (criteria != 'TX2D') and (criteria != 'MTRL'):
            # Fix for ZB SPR files
            for child in self.children:
                if (child.__class__.__name__ == criteria) or (ut.b2s_name(child.name) == criteria):
                    entry_list.append(child)
                if (child.__class__.__name__ == self.__class__.__name__):
                    entry_list = child.search_entries(entry_list, criteria)
        
        return entry_list

    def sort(self, reverse = False):
        names = []
        for child in self.children:
            if child.name not in names:
                names.append(child.name)
        names = natsorted(names, reverse=reverse)

        children = []
        for name in names:
            for child in self.children:
                if child.name == name:
                    children.append(child)
        self.children = children

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'type: {self.type}\n'
            f'name: {self.name}\n'
            f'size: {self.size}\n'
            f'offset: {hex(self.offset)}\n'
            f'data_class: {self.data.__class__.__name__}\n'
            f'data: {self.data}\n'
            f'children: {self.children}\n'
        )