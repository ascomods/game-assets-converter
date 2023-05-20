import os, shutil
import core.common as cm
import core.utils as ut
import core.commands as cmd
from io import BytesIO
from .STPK import STPK

class STPZ:
    def __init__(self, name = b''):
        if (name.__class__.__name__ == 'str'):
            name = ut.s2b_name(name)
        self.name = name

    def load(self, path):
        name, ext = os.path.splitext(os.path.basename(path))
        stpk_object = STPK(ut.s2b_name(f"{name}.pak"))
        stpk_object.load(path)
        self.read_stpk_data(stpk_object)

    def read_stpk_data(self, stpk_object):
        stream = BytesIO()
        stpk_object.write(stream)
        stream.seek(0)
        self.data = stream.read()

    def write(self, stream):
        ut.clear_temp_dir()
        temp_file_path = os.path.join(cm.temp_path, ut.b2s_name(self.name))
        temp_stream = open(temp_file_path, 'wb')
        temp_stream.write(self.data)
        temp_stream.flush()
        # Read data from compressed file
        temp_file_out = temp_file_path + ".out"
        open(temp_file_out, 'wb').close()
        cmd.dbrb_compressor(temp_file_path, temp_file_out)
        temp_stream = open(temp_file_out, 'rb')
        data = temp_stream.read()
        stream.write(data)

    def decompress(self, input_path):
        path = ut.copy_to_temp_dir(input_path)
        name, ext = os.path.splitext(os.path.basename(path))
        stpk_path = os.path.join(cm.temp_path, name + '.pak')
        cmd.dbrb_compressor(path, stpk_path)

        base_name, ext = os.path.splitext(ut.b2s_name(self.name))
        stpk_object = STPK(ut.s2b_name(f"{base_name}.pak"))
        stream = open(stpk_path, 'rb')
        stpk_object.read(stream)
        stream.close()
        return stpk_object

    def compress(self, input_path, output_path):
        name, ext = os.path.splitext(os.path.basename(input_path))
        stpz_path = os.path.dirname(input_path)
        stpz_path = os.path.join(stpz_path, name + '.zpak')
        cmd.dbrb_compressor(input_path, stpz_path)
        shutil.move(stpz_path, output_path)