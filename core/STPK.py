import os
import core.utils as ut
from .SPRP import SPRP

class STPK:
    header_size = 16
    entry_size = 48
    ext_to_class = {b'SPR': b'SPRP'}

    def __init__(self, name = '', size = 0, add_extra_bytes = False):
        self.entries = []
        self.name = name
        self.size = size
        self.add_extra_bytes = add_extra_bytes

    def get_size(self):
        size = self.header_size + len(self.entries) * self.entry_size
        for entry in self.entries:
            size += entry.get_size()
        return size

    def read(self, stream, data_offset = 0):
        self.start_offset = stream.tell()
        stream.seek(8, os.SEEK_CUR) # skip unknown bytes
        entry_count = ut.b2i(stream.read(4))
        stream.seek(4, os.SEEK_CUR) # skip unknown bytes
        self.entries_offset = self.start_offset + self.header_size

        for i in range(entry_count):
            stream.seek(self.entries_offset + (i * self.entry_size))
            data_offset = ut.b2i(stream.read(4))
            data_size = ut.b2i(stream.read(4))
            stream.seek(8, os.SEEK_CUR) # skip unknown bytes
            data_name = ut.read_string(stream, 32, 32)
            
            # start reading entry's header
            stream.seek(self.start_offset + data_offset)
            data_tag = stream.read(4)
            stream.seek(-4, os.SEEK_CUR)

            # try to use the data_tag to guess the class
            # use extension otherwise and if it is still not identified
            # use generic entry if unknown class
            try:
                entry_object = eval(data_tag)(data_name, data_size)
            except Exception as e:
                try:
                    data_tag = data_name.rsplit(b'.', 1)[1].upper()
                    data_tag = self.ext_to_class[data_tag]
                    entry_object = eval(data_tag)(data_name, data_size)
                except Exception:
                    data_tag = 'STPKEntry'
                    entry_object = eval(data_tag)(data_name, data_size)
            entry_object.read(stream, self.start_offset + data_offset)

            self.entries.append(entry_object)

    def write(self, stream):
        # Writing header
        self.start_offset = stream.tell()
        stream.write(ut.s2b_name(self.__class__.__name__))
        stream.write(ut.i2b(1)) # write unknown bytes
        stream.write(ut.i2b(len(self.entries)))
        stream.write(ut.i2b(self.header_size))

        stream.write(bytes(self.entry_size * len(self.entries)))
        if self.add_extra_bytes:
            stream.write(bytes(64)) # Extra bytes for console support
        self.write_data(stream)

        # Writing entries info
        stream.seek(self.start_offset + self.header_size)
        for entry in self.entries:
            stream.write(ut.i2b(entry.offset - self.start_offset))
            size = entry.get_size()
            stream.write(ut.extb(ut.i2b(size), 12))
            stream.write(ut.extb(entry.name, 32))
    
    def write_data(self, stream):
        offset = stream.tell()
        for entry in self.entries:
            entry.offset = offset
            entry.write(stream)
            offset = ut.add_padding(stream.tell())

    def add_entry(self, entry_name, entry_data):
        if entry_name.__class__.__name__ == 'str':
            entry_name = ut.s2b_name(entry_name)
        if 'byte' in entry_data.__class__.__name__:
            entry_object = STPKEntry(entry_name, len(entry_data))
        else:
            entry_object = STPKEntry(entry_name, entry_data.get_size())
        entry_object.data = entry_data
        self.entries.append(entry_object)

    def search_entries(self, entry_list = [], criteria = ''):
        for entry in self.entries:
            if (entry.__class__.__name__ == criteria) or \
               (criteria in ut.b2s_name(entry.name)):
                entry_list.append(entry)
            else:
                entry.search_entries(entry_list, criteria)
        
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
        if 'byte' not in self.data.__class__.__name__:
            return self.data.get_size()
        return len(self.data)

    def read(self, stream, start_offset):
        stream.seek(start_offset)
        self.data = stream.read(self.size)

    def write(self, stream):
        stream.seek(self.offset)
        if 'byte' in self.data.__class__.__name__:
            stream.write(self.data)
        else:
            self.data.write(stream)

    def search_entries(self, entry_list, entry_class):
        return

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'name: {self.name}\n'
            f'size: {self.size}'
        )