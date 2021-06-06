from typing import io
import os, glob, re
import core.utils as ut
from .SPRP import SPRP

class STPK:
    entry_size = 48
    start_offset = ut.b2i(b'\x10')
    ext_to_class = {b'SPR': b'SPRP'}

    def __init__(self, name = '', size = ''):
        self.entries = []
        self.name = name
        self.size = size
    
    def get_header_size(self):
        return self.start_offset + (self.entry_size * len(self.entries))

    def read(self, input: io, data_offset = 0):
        input.seek(4, os.SEEK_CUR) # skip unknown bytes
        entry_count = ut.b2i(input.read(4))
        input.seek(4, os.SEEK_CUR) # skip unknown bytes
        self.start_offset += data_offset
        
        for i in range(entry_count):
            input.seek(self.start_offset + (i * self.entry_size))
            data_offset = ut.b2i(input.read(4))
            data_size = ut.b2i(input.read(4))
            input.seek(8, os.SEEK_CUR) # skip unknown bytes
            data_name = ut.read_string(input, 32, 32)
            
            # start reading entry's header
            input.seek(data_offset)
            data_tag = input.read(4)

            # try to use the data_tag to guess the class
            # use extension otherwise and if it is still not identified
            # use generic entry if unknown class
            try:
                entry_object = eval(data_tag)(data_name, data_size)
            except Exception as e:
                try:
                    data_tag = data_name.decode('utf-8').split('.')[1].upper()
                    entry_object = eval(data_tag)(data_name, data_size)
                except Exception:
                    data_tag = 'STPKEntry'
                    entry_object = eval(data_tag)(data_name, data_size)
            entry_object.read(input, data_offset)

            self.entries.append(entry_object)

    def write(self, stream: io):
        # Writing header
        stream.write(ut.s2b_name(self.__class__.__name__))
        stream.write(ut.i2b(1)) # write unknown bytes
        stream.write(ut.i2b(len(self.entries)))
        stream.write(ut.i2b(self.start_offset)) # write start offset

        stream.write(bytes(self.entry_size * len(self.entries)))
        self.write_data(stream)

        # Writing entries info
        stream.seek(self.start_offset)
        for entry in self.entries:
            stream.write(ut.i2b(entry.offset))
            size = entry.get_size()
            stream.write(ut.extb(ut.i2b(size), 12))
            stream.write(ut.extb(entry.name, 32))
    
    def write_data(self, stream: io):
        offset = stream.tell()
        for entry in self.entries:
            entry.offset = offset
            entry.write(stream)
            offset = ut.add_padding(stream.tell())

    def load(self, path):
        os.chdir(path)

        paths = glob.glob("*")
        paths.sort(key=lambda e: ut.natural_keys(e))

        for elt in paths:
            filename = ut.s2b_name(elt)
            name, ext = os.path.splitext(filename)
            size = ut.get_file_size(elt)
            data_class = ext[1:].upper()
            if data_class != "":
                # try finding class in ext_to_class map
                try:
                    data_class = self.ext_to_class[data_class]
                except Exception:
                    pass
            #try to load the class
            try:
                data_object = eval(data_class)(filename, size)
            except Exception:
                data_object = STPKEntry(filename, size)
            self.entries.append(data_object)

        entry_info_size = self.entry_size * len(self.entries)
        entry_info_offset = self.start_offset + entry_info_size

        for entry in self.entries:
            entry.start_offset = entry_info_offset
            entry.load()
            entry_info_offset += ut.add_padding(entry.get_size())

        os.chdir("..")

    def save(self, path):
        if self.name.__class__.__name__ == 'bytes':
            self.name = ut.b2s_name(self.name)
        path += self.name + '/'
        os.mkdir(path)
        for i in range(len(self.entries)):
            entry_name = ut.b2s_name(self.entries[i].name)
            if not re.match(r'^\[\d+\]', entry_name):
                entry_name = f'[{i}]{entry_name}'
            self.entries[i].save(path, entry_name)

    def add_entry(self, entry_name, entry_data):
        if entry_name.__class__.__name__ == 'str':
            entry_name = ut.s2b_name(entry_name)
        entry_object = STPKEntry(entry_name, len(entry_data))
        entry_object.data = entry_data
        self.entries.append(entry_object)

    def search_entries(self, entry_class):
        entry_list = []

        for entry in self.entries:
            if entry.__class__.__name__ == entry_class:
                entry_list.append(entry)
            else:
                entry.search_entries(entry_list, entry_class)
        
        return entry_list

    def __str__(self):
        return (
            f'class: {self.__class__.__name__}\n'
            f'entry size: {self.entry_size}\n'
            f'entry count: {len(self.entries)}\n'
            f'entries: \n{self.entries}'
        )

class STPKEntry():
    def __init__(self, name, size):
        self.name = name
        self.size = size
    
    def get_size(self):
        return len(self.data)

    def read(self, stream: io, start_offset):
        stream.seek(start_offset)
        self.data = stream.read(self.size)

    def write(self, stream: io):
        stream.seek(self.offset)
        stream.write(self.data)
    
    def load(self):
        data = open(self.name, "rb")
        self.name = ut.s2b_name(re.sub('^\[\d+\]', '', ut.b2s_name(self.name)))
        self.data = data.read()
    
    def save(self, path, name):
        path += name
        output = open(path, 'wb')
        output.write(self.data)

    def search_entries(self, entry_list, entry_class):
        return

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'size: {self.size}'
        )