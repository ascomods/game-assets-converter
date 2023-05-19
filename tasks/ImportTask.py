import os
import shutil
import json
import numpy as np
from natsort import natsorted
from copy import deepcopy
from tasks.Task import Task
from core.STPZ import *
from core.STPK import *
from core.SPRP.SPRP import *
from core.TX2D import *
from core.MTRL import *
from core.BMP import *
from core.BONE import *
from core.DDS import *
from core.SCNE import *
from core.SHAP import *
from core.VBUF import *
from core.FBX import *
import core.utils as ut
import core.common as cm

class ImportTask(Task):
    def run(self):
        try:
            ut.empty_temp_dir()
            ut.init_temp_dir()

            cm.data = dict(zip(['spr', 'ioram', 'vram'], [{} for i in range(3)]))

            for filename in os.listdir(cm.input_path):
                file_path = os.path.join(cm.input_path, filename)
                input_name = os.path.basename(file_path)
                base_input_name, input_ext = os.path.splitext(input_name)

                if (os.path.isdir(file_path)):
                    entry_class = ut.search_index_dict_list(cm.ext_map, input_ext)
                    entry_obj = eval(entry_class)(filename)
                    entry_obj.load(file_path)
                    output = os.path.join(cm.output_path, input_name)
                    self.write(output, entry_obj)

                # If multiple SPR files are imported back, add all ioram and vram files in output folder
                self.write_data('ioram', input_ext)
                self.write_data('vram', input_ext)

            # return to app dir
            os.chdir(cm.app_path)

            self.result_signal.emit(self.__class__.__name__)
            self.finish_signal.emit()
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()

    def write_data(self, ext, file_ext, add_padding = True):
        for key, data in cm.data[ext].items():
            full_name = f"{key}.{ext}"

            if ('pak' in file_ext):
                stpk_obj = STPK(b'', 0, add_padding)
                stpk_obj.add_entry(full_name, data)
                stpk_name = f"{key}_{ext[0]}.pak"

                if cm.selected_game == 'dbrb':
                    op_stpk_obj = STPK(b'', 0, add_padding)
                    op_stpk_obj.add_entry(stpk_name, stpk_obj)
                    stpk_obj = op_stpk_obj
                path = os.path.join(cm.output_path, stpk_name)
                self.write(path, stpk_obj)
            else:
                path = os.path.join(cm.output_path, full_name)
                self.write(path, data)

    def write(self, path, data = None):
        stream = open(path, 'wb')
        if (data.__class__.__name__ in ['bytes', 'bytearray']):
            stream.write(data)
        else:
            data.write(stream)
        stream.close()