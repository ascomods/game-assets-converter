import os
import core.utils as ut

class StringTable():
    def __init__(self):
        self.content = {}

    @ut.keep_cursor_pos
    def read(self, stream, size = None, first_offset = 0, padding = 1):
        """
        Inits the string table with read content from input
        """
        stream.seek(self.offset)
        self.first_offset = first_offset
        self.padding = padding
        if size == None:
            stream.seek(0, os.SEEK_END)
            size = stream.tell() - self.offset
            stream.seek(self.offset)
        string_list = stream.read(size).split(b'\x00')
        string_list = [x for x in string_list if x != b'']
        string_list_offsets = self.gen_offsets(string_list)
        self.content = dict(zip(string_list_offsets, string_list))

    def build(self, string_list, first_offset = 0, padding = 1):
        self.first_offset = first_offset
        self.padding = padding
        string_list_offsets = self.gen_offsets(string_list)
        self.content = dict(zip(string_list_offsets, string_list))

    def gen_offsets(self, string_list):
        """
        Generates the offsets pointing to each name in the table
        """
        string_list_offsets = [self.first_offset]
        offset = self.first_offset
        for string in string_list:
            offset += len(string) + (self.padding - (len(string) % self.padding))
            string_list_offsets.append(offset)
        string_list_offsets.pop()
        return string_list_offsets

    def get_size(self):
        last_string = list(self.content.items())[-1]
        size = last_string[0] + len(last_string[1]) + self.padding
        return size

    def write(self, stream):
        self.offset = stream.tell()
        for key, val in self.content.items():
            stream.seek(self.offset + key)
            if isinstance(val, str):
                val = ut.s2b_name(val)
            stream.write(val + b'\x00')
    
    def __repr__(self):
        string = (
            f'\nclass: {self.__class__.__name__}\n'
            f'size: {self.get_size()}\n'
        )
        for key, val in self.content.items():
            string += f'{key} : {val}\n'
        return string