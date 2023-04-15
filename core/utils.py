import os, stat
import shutil
import inspect
import core.common as cm

endian = 'big'

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
    raise KeyError("Key not found in dict: " + str(search_val))

# Search value in list values of dict
def search_index_dict_list(dict, search_val):
    for key, search_list in dict.items():
        if (isinstance(search_list, list) and (search_val in search_list)):
            return key

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
def read_string_inplace(stream, start_offset, max_size = 100):
    return read_string(stream, start_offset, max_size)

def read_string(input, start_offset, max_size):
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
    return bytes.decode('latin1')

# string to bytes name
def s2b_name(string):
    return string.encode('latin1')

def format_jap_name(string):
    try:
        string.decode('utf-8')
    except:
        name_parts = string.rsplit(b'_')[1:]
        string = b'_'.join(name_parts)
    return string

def read_until(stream, offset, endChar = b'\x00'):
    initial_pos = stream.tell()
    stream.seek(offset)
    res = bytearray(stream.read(1))
    current_byte = b''
    while current_byte != endChar:
        res += current_byte
        current_byte = stream.read(1)
    stream.seek(initial_pos)
    return bytes(res)

def init_temp_dir():
    if not os.path.exists(cm.temp_path):
        os.mkdir(cm.temp_path)

def copy_to_temp_dir(path):
    init_temp_dir()
    name, ext = os.path.splitext(os.path.basename(path))
    shutil.copy2(path, cm.temp_path)
    return f"{cm.temp_path}/{name}{ext}"

def empty_temp_dir():
    path = os.path.abspath(cm.temp_path)
    if os.path.exists(path):
        shutil.rmtree(path, onerror = on_rm_error)

def on_rm_error(func, path, exc_info):
    os.chmod( path, stat.S_IWRITE )
    os.unlink( path )

def print_hex(data):
    print(''.join(r' '+hex(letter)[2:] for letter in data))