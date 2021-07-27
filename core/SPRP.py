from typing import io
import os, glob, re
import core.utils as ut
#from .TX2D import TX2D
from .VBUF import VBUF
from .MTRL import MTRL
from .SCNE import SCNE_MODEL
from .StringTable import StringTable

class SPRP:
    header_size = 64
    header_entry_size = 12

    def __init__(self, name, size = 0):
        self.name = name
        self.size = size
        self.entries = []

    def update_offsets(self):
        data_offset = self.info_offset + self.data_info_size

        offset = 0
        for entry in self.entries:
            entry.update_offsets(self.info_offset, data_offset, ut.add_padding(offset))
            size = entry.get_size(True, True)
            if entry.data_type == b'MTRL':
                offset += size // 2
            else:
                offset += size
            self.size += size
    
    def get_size(self):
        return self.size

    def read(self, input: io, start_offset):
        self.start_offset = start_offset
        input.seek(self.start_offset)
        input.seek(8, os.SEEK_CUR) # skip tag + unknown bytes
        entry_count = ut.b2i(input.read(4))
        input.seek(4, os.SEEK_CUR) # skip unknown bytes

        # Reading header
        header_name_offset = ut.b2i(input.read(4))
        self.entry_info_size = ut.b2i(input.read(4))
        string_table_size = ut.b2i(input.read(4))
        self.data_info_size = ut.b2i(input.read(4))
        self.data_block_size = ut.b2i(input.read(4))
        ioram_name_offset = ut.b2i(input.read(4))
        self.ioram_data_size = ut.b2i(input.read(4))
        vram_name_offset = ut.b2i(input.read(4))
        self.vram_data_size = ut.b2i(input.read(4))
        input.seek(12, os.SEEK_CUR) # skip unknown bytes
        entry_info_offset = self.start_offset + self.header_size
        string_table_offset = entry_info_offset + self.entry_info_size
        self.string_table = StringTable()
        self.string_table.init(input, string_table_offset, string_table_size)

        self.header_name = self.string_table.content[header_name_offset]
        self.ioram_name = self.string_table.content[ioram_name_offset]
        self.vram_name = self.string_table.content[vram_name_offset]

        self.info_offset = string_table_offset + string_table_size
        data_offset = self.info_offset + self.data_info_size
        entry_offset = 0

        for i in range(entry_count):
            entry_object = SPRPEntry(self.string_table)
            entry_offset += entry_object.read(input, 
                self.info_offset + entry_offset, data_offset)
            self.entries.append(entry_object)
        
        #self.update_offsets()

    def load(self):
        os.chdir(self.name)
        
        self.string_table = StringTable()
        name, ext = os.path.splitext(self.name)
        self.string_table.build(ut.b2s_name(name), True)
        self.name = ut.s2b_name(re.sub('^\[\d+\]', '', ut.b2s_name(self.name)))
        name = ut.s2b_name(re.sub('^\[\d+\]', '', ut.b2s_name(name)))
        
        self.header_name = name + b'.xmb'
        self.ioram_name = name + b'.ioram'
        self.vram_name = name + b'.vram'

        self.data_info_size = 0
        self.data_block_size = 0
        self.ioram_data_size = 0
        self.vram_data_size = 0
        self.entry_info_size = 0

        paths = glob.glob("*")
        paths.sort(key=lambda e: ut.natural_keys(e))

        for elt in paths:
            data_object = SPRPEntry(self.string_table)
            data_object.data_type = ut.s2b_name(elt)
            data_object.load()
            self.entries.append(data_object)
            self.data_info_size += data_object.data_entry_size * data_object.data_count
            self.data_block_size += data_object.size
        
        self.entry_info_size = self.header_entry_size * len(self.entries)
        entry_info_offset = self.start_offset + self.header_size
        string_table_offset = entry_info_offset + self.entry_info_size
        self.info_offset = string_table_offset + self.string_table.get_size()
        self.update_offsets()

        os.chdir("..")

    def save(self, path, name):
        path += name + '/'
        os.mkdir(path)
        for i in range(len(self.entries)):
            entry_name = ut.b2s_name(self.entries[i].data_type)
            if not re.match(r'^\[\d+\]', entry_name):
                entry_name = f'[{i}]{entry_name}'
            self.entries[i].save(path, entry_name)
    
    def write(self, output: io):
        # Writing header
        output.write(self.__class__.__name__.encode('utf-8'))
        output.write(ut.i2b(1, 2)) # write unknown bytes
        output.write(ut.i2b(1, 2)) # write unknown bytes
        output.write(ut.i2b(len(self.entries)))
        output.write(bytes(4))
        
        header_name_offset = ut.search_index_dict(self.string_table.content, self.header_name)
        ioram_name_offset = ut.search_index_dict(self.string_table.content, self.ioram_name)
        vram_name_offset = ut.search_index_dict(self.string_table.content, self.vram_name)

        output.write(ut.i2b(header_name_offset))
        output.write(ut.i2b(len(self.entries) * self.header_entry_size))
        output.write(ut.i2b(self.string_table.get_size()))
        output.write(ut.i2b(self.data_info_size))
        output.write(ut.i2b(self.data_block_size))
        output.write(ut.i2b(ioram_name_offset))
        output.write(ut.i2b(self.ioram_data_size))
        output.write(ut.i2b(vram_name_offset))
        output.write(ut.i2b(self.vram_data_size))
        output.write(bytes(12))
        for entry in self.entries:
            entry.write(output)

        self.string_table.write(output)
        output.write(bytes(self.data_info_size + self.data_block_size))
        output.seek(self.info_offset)
        
        for entry in self.entries:
            entry.write_data(output)
        
        # Temporarily correcting offsets here
        output.seek(0, os.SEEK_END)
        self.size = output.tell() - self.start_offset
        data_offset = self.info_offset + self.data_info_size
        self.data_block_size = output.tell() - data_offset

    def search_entries(self, entry_list, entry_class):
        for entry in self.entries:
            if entry.__class__.__name__ == entry_class:
                entry_list.append(entry)
            else:
                entry.search_entries(entry_list, entry_class)

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'size: {self.size}\n'
            f'entries: {self.entries}'
        )

class SPRPEntry:
    data_entry_size = 32

    def __init__(self, string_table):
        self.string_table = string_table
        self.entries = []
        self.size = 0
    
    def update_offsets(self, info_offset, data_offset, offset):
        self.info_offset = info_offset
        self.data_offset = data_offset

        for i in range(len(self.entries)):
            self.entries[i].update_offsets(self.data_offset, offset)
            size = 0
            if self.entries[i].type == b'MTRL':
                size += self.entries[i].get_size(True) // 2
            else:
                size += self.entries[i].get_size(True)
            offset += ut.add_padding(size)

    def get_size(self, include_children = True, with_padding = False):
        size = 0
        for entry in self.entries:
            entry_size = entry.get_size(include_children)
            if with_padding:
                entry_size = ut.add_padding(entry_size)
            size += entry_size
        return size

    def read(self, input: io, info_offset, data_offset):
        self.info_offset = info_offset
        self.data_offset = data_offset
        # read info entry
        self.data_type = input.read(4)
        input.seek(4, os.SEEK_CUR) # skip unknown bytes
        self.data_count = ut.b2i(input.read(4))
        self.read_data(input)
        # return block size for next info offset
        return self.data_entry_size * self.data_count
    
    @ut.keep_cursor_pos
    def read_data(self, stream: io):
        stream.seek(self.info_offset)
        # read data info entry
        for i in range(self.data_count):
            stream.seek(8, os.SEEK_CUR) # skip data_type + index number
            name_offset = ut.b2i(stream.read(4))
            name = self.string_table.content[name_offset]
            data_object = SPRPDataEntry(self.data_type, name, 
                self.string_table, True)
            data_object.read(stream, self.data_offset)
            self.entries.append(data_object)
    
    def write(self, stream: io):
        # writing info entry
        stream.write(self.data_type)
        stream.write(bytes(4)) # skip unknown bytes
        stream.write(ut.i2b(self.data_count))

    def write_data(self, stream: io):
        for i in range(len(self.entries)):
            stream.write(self.data_type)
            stream.write(ut.i2b(i))
            name_offset = ut.search_index_dict(self.string_table.content, 
                self.entries[i].name)
            stream.write(ut.i2b(name_offset))
            self.entries[i].write(stream)

    def load(self):
        os.chdir(self.data_type)

        self.data_type = ut.s2b_name(re.sub('^\[\d+\]', '', ut.b2s_name(self.data_type)))
        self.size = 0

        paths = glob.glob("*")
        paths.sort(key=lambda e: ut.natural_keys(e))

        for elt in paths:
            data_object = SPRPDataEntry(self.data_type, ut.s2b_name(elt), 
                self.string_table, True)
            data_object.load()
            self.size += data_object.get_size()        
            self.entries.append(data_object)
        self.data_count = len(self.entries)
        self.info_size = self.data_count * self.data_entry_size
        os.chdir("..")

    def save(self, path, name):
        path += name + '/'
        if not os.path.exists(path):
            os.mkdir(path)
        for i in range(len(self.entries)):
            entry_name = ut.b2s_name(self.entries[i].name)
            if not re.match(r'^\[\d+\]', entry_name):
                entry_name = f'[{i}]{entry_name}'
            self.entries[i].save(path, entry_name)

    def search_entries(self, entry_list, entry_class):
        for entry in self.entries:
            if entry.__class__.__name__ == entry_class:
                entry_list.append(entry)
            else:
                entry.search_entries(entry_list, entry_class)

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'type: {self.data_type}\n'
            f'content: {self.entries}'
        )

class SPRPDataEntry:
    info_entry_size = 20

    def __init__(self, type, name, string_table, is_main_type = False):
        self.type = type
        self.name = name
        self.string_table = string_table
        self.is_main_type = is_main_type
        self.children = []
        self.size = 0
        self.child_offset = 0
        self.has_info = False
    
    def update_offsets(self, data_offset, offset):
        self.data_offset = data_offset

        self.size = self.get_size()
        self.offset = ut.add_padding(offset)

        if len(self.children) > 0:
            self.child_offset = ut.add_padding(self.offset + self.size)
        
            child_offset = self.child_offset + len(self.children) * 20
            child_block_offset = child_offset

            for i in range(len(self.children)):
                self.children[i].update_offsets(self.data_offset, child_block_offset)
                child_block_offset += self.children[i].get_size(True)
                child_block_offset = ut.add_padding(child_block_offset)

            if not self.is_main_type and not self.type == b'SCNE':
                self.child_offset = child_offset

        if hasattr(self, 'data'):
            if self.data.__class__.__name__ != 'bytes':
                offset = self.offset
                if self.type != b'MTRL' and self.type != b'VBUF' and self.type != b'SCNE':
                    self.offset += self.size
                offset = ut.add_padding(offset)
                self.data.update_offsets(self.data_offset, offset)
        
        if self.type == b'VBUF':
            self.size = VBUF.info_size
        
    def get_size(self, include_children = False, add_gap = True):
        size = 0

        if self.has_info and self.type == b'MTRL':
            size += 8
        
        if include_children:
            for child in self.children:
                if child.__class__.__name__ == self.__class__.__name__:
                    child_size = child.get_size(include_children)
                else:
                    child_size = child.get_size()
                size += child_size
                if add_gap:
                    size += 32
        
        if hasattr(self, 'data'):
            if (self.data.__class__.__name__ != 'bytes'):
                size += size + self.data.get_size()
            else:
                size += len(self.data)

        return size
        
    def read(self, input: io, data_offset):
        # Reading data info
        self.data_offset = data_offset
        self.offset = ut.b2i(input.read(4))
        self.size = ut.b2i(input.read(4))
        child_count = ut.b2i(input.read(4))
        self.child_offset = ut.b2i(input.read(4))
        input.seek(4, os.SEEK_CUR) # skip unknown bytes
        self.read_data(input, child_count)
    
    @ut.keep_cursor_pos
    def read_data(self, stream: io, child_count):
        stream.seek(self.data_offset + self.offset)

        try:
            if self.type == b'SCNE':
                if b'|model' in self.name:
                    data_object = SCNE_MODEL('', b'', self.string_table)
                else:
                    raise Exception("unknown SCNE Object")
            elif self.type == b'TX2D':
                data_object = TX2D('', self.name, self.string_table)
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
                    child_class = self.type.decode('utf-8')
                    child_object = eval(child_class)(self.type, name, self.string_table)
                    child_object.has_info = True
                except Exception as e:
                    child_object = self.__class__(self.type, name, self.string_table)
                
                child_object.read(stream, self.data_offset)
                self.children.append(child_object)
    
    def write(self, stream: io, with_data = True):
        if not self.is_main_type:
            name_offset = ut.search_index_dict(self.string_table.content, 
            self.name)
            stream.write(ut.i2b(name_offset))
        stream.write(ut.i2b(self.offset))
        stream.write(ut.i2b(self.size))
        stream.write(ut.i2b(len(self.children)))
        stream.write(ut.i2b(self.child_offset))

        if self.is_main_type:
            stream.write(bytes(4)) # skip unknown bytes
        
        if with_data:
            self.write_data(stream)

    @ut.keep_cursor_pos
    def write_data(self, stream: io):
        if not self.has_info:
            stream.seek(self.data_offset + self.offset)

        try:
            self.data.write(stream)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(e)
            #exit()
            if hasattr(self, 'data'):
                stream.seek(self.data_offset + self.offset)
                stream.write(self.data)

        if len(self.children) > 0:
            stream.seek(self.data_offset + self.child_offset)
            for i in range(len(self.children)):
                self.children[i].write(stream, False)
            for i in range(len(self.children)):
                self.children[i].write_data(stream)

    def load(self):
        is_dir = False

        excluded = ['data.txt', 'vertex_decl_data', 'ioram_data']

        if os.path.isdir(ut.b2s_name(self.name)):
            is_dir = True
            os.chdir(ut.b2s_name(self.name))

            self.name = ut.s2b_name(re.sub('^\[\d+\]', '', ut.b2s_name(self.name)))
            paths = glob.glob("*")
            paths.sort(key=lambda e: ut.natural_keys(e))

            for elt in paths:
                try:
                    if self.type == b'SCNE':
                        print(elt)
                        if b'|model' in self.name:
                            data_object = SCNE_MODEL('', b'', self.string_table)
                        else:
                            if elt == 'data':
                                continue
                            raise Exception("unknown SCNE Object")
                        data_object.load()
                        self.data = data_object
                except Exception as e:
                    print(e)
                    pass
                if self.type == b'SCNE' and elt == 'data':
                    continue
                if elt == 'data' and not os.path.isdir(elt):
                    try:
                        data_object = eval(self.type)(self.type, 
                            self.name, self.string_table)
                        data_object.load()
                        self.data = data_object
                    except Exception as e:
                        data = open(elt, "rb")
                        self.data = data.read()
                        self.size = ut.get_file_size(elt)
                elif elt not in excluded:
                    try:
                        if elt == 'data':
                            if not os.path.isdir("data"):
                                name = self.name
                            else:
                                name = b''
                        else:
                            name = ut.s2b_name(elt)

                        if os.path.exists("data") and not os.path.isdir("data"):
                            child_class = self.__class__.__name__
                            child_object = eval(child_class)(self.type, 
                                name, self.string_table)
                            child_object.has_info = True
                            self.children.append(child_object)
                            child_object.load()
                        else:
                            child_class = ut.b2s_name(self.type)
                            child_object = eval(child_class)(self.type, 
                                name, self.string_table)
                            self.data = child_object
                            child_object.load()
                    except Exception as e:
                        child_class = self.__class__.__name__
                        child_object = eval(child_class)(self.type, 
                            ut.s2b_name(elt), self.string_table)
                        child_object.load()
                        self.children.append(child_object)
        else:
            try:
                data_object = eval(self.type)(self.type, 
                    self.name, self.string_table)
                data_object.load()
                self.data = data_object
            except Exception as e:
                data = open(ut.b2s_name(self.name), "rb")
                self.data = data.read()
                self.size = ut.get_file_size(ut.b2s_name(self.name))
        if is_dir:
            os.chdir("..")
        else:
            self.name = ut.s2b_name(re.sub('^\[\d+\]', '', ut.b2s_name(self.name)))

    def save(self, path, name):
        path += name

        if len(self.children) > 0:
            os.mkdir(path)
            # data dump
            data_path = path + '/' + 'data'
            for i in range(len(self.children)):
                child_name = ut.b2s_name(self.children[i].name)
                if not re.match(r'^\[\d+\]', child_name):
                    child_name = f'[{i}]{child_name}'
                self.children[i].save(path + '/', child_name)
        else:
            data_path = path
        try:
            self.data.save(data_path + '/')
        except Exception as e:
            output = open(data_path, 'wb')
            output.write(self.data)

    def search_entries(self, entry_list, criteria):
        if hasattr(self, 'data') and self.data.__class__.__name__ == criteria:
            entry_list.append(self)
        elif ut.b2s_name(self.name) == criteria:
            entry_list.append(self)
        for child in self.children:
            if child.__class__.__name__ == criteria:
                entry_list.append(child)

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