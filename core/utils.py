from typing import io
import inspect, os
import datetime
import re

endian = 'big'

# endian for struct
def ste():
    return '>' if endian == 'big' else '<'

# bytes to int
def b2i(num):
    return int.from_bytes(num, byteorder=endian)

# int to bytes
def i2b(num, length = 4):
    return num.to_bytes(length, byteorder=endian)

# extend bytes to given size
def extb(bytes, size):
    return bytes + (b'\0' * (size - len(bytes)))

# hex int to byte
def h2b(num):
    return b"0x%0.2X" % num

def search_index_dict(dict, search_val):
    for key, val in dict.items():
        if val == search_val:
            return key
    raise Exception("Key not found in dict")

def keep_cursor_pos(function):
    """
    restores cursor position after function execution
    """
    def wrapper(*args, **kwargs):
        res = b''
        args_name = list(inspect.signature(function).parameters.keys())
        if all(x in args_name for x in ['stream']):
            stream_arg_index = args_name.index('stream')
            stream = args[stream_arg_index]
            previous_pos = stream.tell()
            if 'start_offset' in args_name:
                start_offset_arg_index = args_name.index('start_offset')
                start_offset = args[start_offset_arg_index]
                stream.seek(start_offset)            
            res = function(*args, **kwargs)
            stream.seek(previous_pos)
        else:
            raise Exception("Error with given arguments")
        return res
    return wrapper

@keep_cursor_pos
def read_string_inplace(stream: io, start_offset, max_size = 100):
    return read_string(stream, start_offset, max_size)

def read_string(input: io, start_offset, max_size):
    """
    reads characters until it finds 00
    """
    byte = input.read(1)
    size = 1
    content = b''
    while (size <= max_size) and byte and byte != b'\x00':
        content += byte
        byte = input.read(1)
        size += 1
    return content

def uniquify(path):
    name, ext = os.path.splitext(path)
    count = 0

    while os.path.exists(path):
        path = f'{name}_{count}{ext}'
        count += 1

    return path

def add_padding(num, length = 16):
    if num % length != 0:
        num += length - (num % length)
    return num

# bytes to string name
def b2s_name(bytes):
    return bytes.decode('utf-8').replace('|', '+').replace(':', '-')

# string to bytes name
def s2b_name(string):
    return string.replace('+', '|').replace('-', ':').encode('utf-8')

def get_file_size(path = '.'):
    if os.path.isfile(path):
        return os.path.getsize(path)
    return 0

def get_mod_date(path):
    t = os.path.getmtime(path)
    return datetime.datetime.fromtimestamp(t)

def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [ atoi(c) for c in re.split(r'(\d+)', text) ]