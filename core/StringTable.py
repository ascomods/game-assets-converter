from typing import io
import os, re
import core.utils as ut

class StringTable():
    @ut.keep_cursor_pos
    def init(self, stream: io, start_offset, size):
        """
        Inits the string table with read content from input
        """
        string_list = stream.read(size).split(b'\x00')
        string_list = [x for x in string_list if x != b'']
        string_list_offsets = self.gen_offsets(string_list)
        self.content = dict(zip(string_list_offsets, string_list))
    
    def build(self, root_name, skip_current_subfolders = False):
        """
        Creates string table recursively starting from current directory
        """
        name_list = []
        self.excluded_list = ['data', 'vertex_decl_data', 'ioram_data', 'data.txt']
        self.read_list = ['data.txt']

        for dir_path, dir_names, file_names in os.walk("."):
            if skip_current_subfolders:
                skip_current_subfolders = False
                continue
            self.add_filtered_string(dir_names, name_list)
            self.add_filtered_string(file_names, name_list)
            for file_name in file_names:
                if file_name in self.read_list:
                    lines = open(dir_path + '\\' + file_name, 'r').read().splitlines()
                    self.add_filtered_string(lines, name_list)
        root_name = re.sub('^\[\d+\]', '', root_name)
        name_list.append(ut.s2b_name(f'{root_name}.xmb'))
        name_list.append(ut.s2b_name(f'{root_name}.vram'))
        name_list.append(ut.s2b_name(f'{root_name}.ioram'))
        string_list_offsets = self.gen_offsets(name_list)
        self.content = dict(zip(string_list_offsets, name_list))
    
    def add_filtered_string(self, string_list, dest_list):
        string_list.sort(key=lambda e: ut.natural_keys(e))
        for string in string_list:
            string = re.sub('^\[\d+\]', '', string)
            string = ut.s2b_name(string)
            if string not in self.excluded_list and string not in dest_list:
                dest_list.append(string)

    def gen_offsets(self, string_list):
        """
        Generates the offsets pointing to each name in the table
        """
        string_list_offsets = [1]
        offset = 1
        for string in string_list:
            offset += len(string) + 1
            string_list_offsets.append(offset)
        string_list_offsets.pop()
        return string_list_offsets
    
    def get_size(self):
        last_string = list(self.content.items())[-1]
        size = last_string[0] + len(last_string[1])
        if size % 16 != 0:
            size += 16 - (size % 16)
        return size
    
    def write(self, output: io):
        for key, val in self.content.items():
            output.write(b'\x00' + val)
        last_string = list(self.content.items())[-1]
        real_size = last_string[0] + len(last_string[1])
        output.write(bytes(self.get_size() - real_size))
    
    def __repr__(self):
        string = (
            f'\nclass: {self.__class__.__name__}\n'
            f'size: {self.get_size()}\n'
        )
        for key, val in self.content.items():
            string += f'{key} : {val}\n'
        return string