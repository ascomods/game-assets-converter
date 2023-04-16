import os
import core.common as cm
import core.utils as ut
import core.commands as cmd
from .STPK import STPK

class STPZ:
    def decompress(self, input_path):
        path = ut.copy_to_temp_dir(input_path)
        name, ext = os.path.splitext(os.path.basename(path))
        stpk_path = os.path.join(cm.temp_path, name + ".pak")
        cmd.dbrb_compressor(path, stpk_path)
        
        stpk_object = STPK()
        stream = open(stpk_path, 'rb')
        stpk_object.read(stream)
        stream.close()
        return stpk_object

    def compress(self, output_path):
        name, ext = os.path.splitext(os.path.basename(output_path))
        stpk_path = os.path.join(cm.temp_path, name + ".pak")
        cmd.dbrb_compressor(stpk_path, output_path)