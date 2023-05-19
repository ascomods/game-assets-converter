import os, shutil
import core.common as cm
import core.utils as ut
import core.commands as cmd
from .STPK import STPK

class STPZ:
    def __init__(self, name = b''):
        if (name.__class__.__name__ == 'str'):
            name = ut.s2b_name(name)
        self.name = name

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