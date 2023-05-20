import os
from tasks.Task import Task
import core.utils as ut
import core.common as cm
from core.SPRP.SPRP import *
from core.STPZ import STPZ
from core.STPK import STPK

class ExportTask(Task):
    def run(self):
        try:
            ut.clear_temp_dir()

            cm.data = dict(zip(['spr', 'ioram', 'vram'], [{} for i in range(3)]))

            cm.data['spr_stpk'] = self.get_stpk_file(cm.spr_path)
            if cm.data['spr_stpk'] == None:
                del cm.data['spr_stpk']
                stream = open(cm.spr_path, "rb")
                data_tag = stream.read(4)
                stream.seek(0)
                if data_tag in cm.class_map:
                    data_tag = cm.class_map[data_tag]
                name = os.path.basename(cm.spr_path)
                spr_object = eval(data_tag)(ut.s2b_name(name))
                if spr_object == None:
                    raise Exception('Invalid file provided')
                else:
                    cm.data['spr'] = spr_object
                    cm.data['spr'].read(stream, 0)
                stream.close()

            cm.data['ioram_stpk'] = self.get_stpk_file(cm.ioram_path)
            if cm.data['ioram_stpk'] == None:
                stream = open(cm.ioram_path, "rb")
                cm.ioram_data = stream.read()
                stream.close()

            cm.data['vram_stpk'] = self.get_stpk_file(cm.vram_path)
            if cm.data['vram_stpk'] == None:
                stream = open(cm.vram_path, "rb")
                cm.vram_data = stream.read()
                stream.close()

            if 'spr_stpk' in cm.data.keys():
                cm.output_path = \
                    os.path.join(cm.output_path, ut.b2s_name(cm.data['spr_stpk'].name))
                cm.data['spr_stpk'].save(cm.output_path)
            else:
                cm.output_path = \
                    os.path.join(cm.output_path, ut.b2s_name(cm.data['spr'].name))
                cm.data['spr'].save(cm.output_path)

            # return to app dir
            os.chdir(cm.app_path)

            self.result_signal.emit(self.__class__.__name__)
            self.finish_signal.emit()
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()

    def get_stpk_file(self, path):
        stream = open(path, 'rb')
        data_type = stream.read(4)
        stream.close()
        
        stpk_object = None
        if data_type == b'STPZ':
            stpz_object = STPZ(os.path.basename(path))
            stpk_object = stpz_object.decompress(path)
        elif data_type == b'STPK':
            stpk_object = STPK(os.path.basename(path))
            stream = open(path, "rb")
            stpk_object.read(stream)
            stream.close()
        return stpk_object