from io import BytesIO
from typing import io
import os
import re
import core.utils as ut
import core.LZCompression as lzc
from core.STPK import STPK
from core.SPRP import SPRP
from core.SPR3 import SPR3

class STPZ:
    def __init__(self):
        self.entries = []

    def read(self, stream: io):
        # Reading data info
        stream.seek(12, os.SEEK_CUR) # ignore unknown bytes     12 ici !!!!!!!!!!
        file_tag = ut.b2s_name(stream.read(4)).replace('0', 'O')
        try:
            entry = eval(file_tag)()
            entry.read(stream)
            self.entries.append(entry)
        except Exception:
            pass

    def compress(self):
        self.entries.clear()
        entry_object = ODCS()
        entry_object.data = self.data
        entry_object.compress()
        print("here")
        stream = open("test.out", "wb")
        self.write(stream)
        print("done")
        exit(0)

        self.entries.append(entry_object)

    def decompress(self, last_entry_name = '', is_root_type = True):
        self.is_root_type = is_root_type
        data = bytearray()
        for entry in self.entries:
            data.extend(entry.decompress())
        data_object = eval(data[:4])()
        data_object.read(BytesIO(data))
        return data_object

    def write(self, stream: io):
        stream.write(ut.s2b_name(self.__class__.__name__))
        stream.write(bytes(8))
        stream.write(ut.i2b(16)) # write start offset

        for entry in self.entries:
            entry.write(stream)

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'\nentry count: {len(self.entries)}\n'
            f'\nentries: {self.entries}\n'
        )

class ODCS:
    def __init__(self):
        self.entries = []
    
    def read(self, stream: io):
        self.uncompressed_size = ut.b2i(stream.read(4))
        self.compressed_size = ut.b2i(stream.read(4))
        self.chunk_size = ut.b2i(stream.read(4))
        # get entry count with // round down
        self.entry_count = -(- self.uncompressed_size // self.chunk_size)

        for i in range(self.entry_count):
            file_tag = ut.b2s_name(stream.read(4)).replace('0', 'O')
            try:
                entry = eval(file_tag)()
                entry.read(stream)
                self.entries.append(entry)
            except Exception as e:
                pass
    
    def compress(self, with_olcs = True, chunk_size = 15360):
        self.entries.clear()
        self.chunk_size = chunk_size
        self.uncompressed_size = len(self.data)
        self.entry_count = -(- len(self.data) // self.chunk_size)
        self.data = lzc.compress_data(self.data)
        self.compressed_size = len(self.data) + 16 # including ODCS header size
        self.entry_size = -(- len(self.data) // self.entry_count)

        for i in range(self.entry_count):
            pos = (i * self.entry_size) % len(self.data)
            chunk = self.data[pos:]
            entry_object = OLCS()
            entry_object.uncompressed_size = self.chunk_size
            entry_object.data = chunk
            entry_object.compressed_size = len(chunk)
            self.entries.append(entry_object)
            self.compressed_size += 16 # including OLCS header size
    
    def decompress(self, last_entry_name = '', is_root_type = False):
        self.is_root_type = is_root_type
        data = bytearray()
        for entry in self.entries:
            entry.decompress()
            data.extend(entry.data)
        if is_root_type:
            try:
                data_object = eval(data[:4])()
                data_object.read(BytesIO(data))
                data = data_object
            except Exception as e:
                self.data = data
                if last_entry_name != '':
                    if re.search(r'\.spr$', last_entry_name) != None:
                        name, ext = os.path.splitext(last_entry_name)
                        self.name = f'{name}.vram'
                return self
        return data

    def write(self, stream: io):
        stream.write(ut.s2b_name(self.__class__.__name__.replace('O', '0')))
        stream.write(ut.i2b(self.uncompressed_size))
        stream.write(ut.i2b(self.compressed_size))
        stream.write(ut.i2b(self.chunk_size))

        for entry in self.entries:
            entry.write(stream)

    def save(self, path):
        stream = open(path + self.name, 'wb')
        stream.write(self.data)
        stream.close()
        date = time.mktime(self.date.timetuple())
        os.utime(path + self.name, (date, date))

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'\nentry count: {len(self.entries)}\n'
            f'\nentries: {self.entries}\n'
        )

class OLCS:   
    def read(self, stream: io):
        self.uncompressed_size = ut.b2i(stream.read(4))
        self.compressed_size = ut.b2i(stream.read(4))
        stream.seek(4, os.SEEK_CUR) # ignore unknown bytes
        self.read_data(stream)
    
    def read_data(self, stream: io):
        self.data = stream.read(self.compressed_size - 16) # minus OLDS header size

    #def compress(self):
    #    self.uncompressed_size = len(self.data)
    #    self.data = lzc.compress_data(self.data)
    #    self.compressed_size = len(self.data)

    def decompress(self):
        try:
            self.data = lzc.decompress_data(self.data)
        except Exception as e:
            pass
    
    def write(self, stream: io):
        stream.write(ut.s2b_name(self.__class__.__name__.replace('O', '0')))
        stream.write(ut.i2b(self.uncompressed_size))
        stream.write(ut.i2b(self.compressed_size))
        stream.write(bytes(4)) # write unknown bytes
        stream.write(self.data)      

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'\ndata size: {len(self.data)}\n'
        )


######## UT_TEST #########


class SCDO:
    def __init__(self):
        self.entries = []
    
    def read(self, stream: io):
        ut.endian = '>'

        self.uncompressed_size = ut.b2i(stream.read(4))
        self.compressed_size = ut.b2i(stream.read(4))
        self.chunk_size = ut.b2i(stream.read(4))
        # get entry count with // round down
        self.entry_count = -(- self.uncompressed_size // self.chunk_size)

        for i in range(self.entry_count):
            file_tag = ut.b2s_name(stream.read(4)).replace('0', 'O')
            
            try:
                entry = eval(file_tag)()
                entry.read(stream)
                self.entries.append(entry)
            except Exception as e:
                pass
        
        ut.endian = '<'
    
    def compress(self, with_olcs = True, chunk_size = 15360):
        self.entries.clear()
        self.chunk_size = chunk_size
        self.uncompressed_size = len(self.data)
        self.entry_count = -(- len(self.data) // self.chunk_size)
        self.data = lzc.compress_data(self.data)
        self.compressed_size = len(self.data) + 16 # including ODCS header size
        self.entry_size = -(- len(self.data) // self.entry_count)

        for i in range(self.entry_count):
            pos = (i * self.entry_size) % len(self.data)
            chunk = self.data[pos:]
            entry_object = OLCS()
            entry_object.uncompressed_size = self.chunk_size
            entry_object.data = chunk
            entry_object.compressed_size = len(chunk)
            self.entries.append(entry_object)
            self.compressed_size += 16 # including OLCS header size
    
    def decompress(self, last_entry_name = '', is_root_type = False):
        ut.endian = '>'

        self.is_root_type = is_root_type
        data = bytearray()
        for entry in self.entries:
            entry.decompress()
            data.extend(entry.data)
        if is_root_type:
            try:
                data_object = eval(data[:4])()
                data_object.read(BytesIO(data))
                data = data_object
            except Exception as e:
                self.data = data
                if last_entry_name != '':
                    if re.search(r'\.spr$', last_entry_name) != None:
                        name, ext = os.path.splitext(last_entry_name)
                        self.name = f'{name}.vram'
                
                ut.endian = '<'

                return self

        ut.endian = '<'
        
        return data

    def write(self, stream: io):
        stream.write(ut.s2b_name(self.__class__.__name__.replace('O', '0')))
        stream.write(ut.i2b(self.uncompressed_size))
        stream.write(ut.i2b(self.compressed_size))
        stream.write(ut.i2b(self.chunk_size))

        for entry in self.entries:
            entry.write(stream)

    def save(self, path):
        stream = open(path + self.name, 'wb')
        stream.write(self.data)
        stream.close()
        date = time.mktime(self.date.timetuple())
        os.utime(path + self.name, (date, date))

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'\nentry count: {len(self.entries)}\n'
            f'\nentries: {self.entries}\n'
        )

class SCLO:   
    def read(self, stream: io):
        ut.endian = '>'

        self.uncompressed_size = ut.b2i(stream.read(4))
        self.compressed_size = ut.b2i(stream.read(4))
        stream.seek(4, os.SEEK_CUR) # ignore unknown bytes
        self.read_data(stream)

        ut.endian = '<'
    
    def read_data(self, stream: io):
        self.data = stream.read(self.compressed_size - 16) # minus OLDS header size

    #def compress(self):
    #    self.uncompressed_size = len(self.data)
    #    self.data = lzc.compress_data(self.data)
    #    self.compressed_size = len(self.data)

    def decompress(self):
        ut.endian = '>'

        try:
            self.data = lzc.decompress_data(self.data)
        except Exception as e:
            pass
        
        ut.endian = '<'
    
    def write(self, stream: io):
        stream.write(ut.s2b_name(self.__class__.__name__.replace('O', '0')))
        stream.write(ut.i2b(self.uncompressed_size))
        stream.write(ut.i2b(self.compressed_size))
        stream.write(bytes(4)) # write unknown bytes
        stream.write(self.data)      

    def __repr__(self):
        return (
            f'\nclass: {self.__class__.__name__}\n'
            f'\ndata size: {len(self.data)}\n'
        )