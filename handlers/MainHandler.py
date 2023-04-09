import os
from io import BytesIO
from PyQt5.QtCore import QThread
from natsort import natsorted
from core.STPZ import *
from core.STPK import *
from tasks.ImportTask import *
from tasks.ExportTask import *
import core.utils as ut
import core.common as cm
import ui.handlers.ViewHandler as vh
from PyQt5.QtCore import QSettings
from PyQt5.QtCore import QUrl

class MainHandler():
    def init(self, view_handler = None):
        self.paths = {}
        self.data = {}
        self.settings = QSettings("settings.ini", QSettings.IniFormat)

        if view_handler != None:
            self.view_handler = view_handler
        else:
            self.view_handler = vh.ViewHandler()
        
        self.view_handler.add_observers({
            'WindowHandler': {
                'notify_exit_action': self.close_action
            },
            'ListWindowHandler': {
                'notify_add_action' : self.add_files_action,
                'notify_done_action' : self.import_action
            },
            'MainWindowHandler': {
                'notify_import_action' : self.select_input_action,
                'notify_export_action' : self.export_action
            },
            'MessageWindowHandler': {
                'notify_yes_action' : self.yes_action,
                'notify_no_action' : self.close_action
            }
        })
        self.view_handler.load_window('MainWindowHandler')

    def run_task(self, task_class, args, error_message = 'Error while processing data'):
        try:
            self.thread = QThread()
            self.task = eval(task_class)(self.data, *args)
            self.task.moveToThread(self.thread)
            self.task.progress_signal.connect(
                self.view_handler.window_handler.set_progress
            )
            self.task.result_signal.connect(self.task_done_action)
            self.task.finish_signal.connect(self.thread.quit)
            self.thread.started.connect(self.task.run)
            self.thread.finished.connect(self.task.deleteLater)
            self.thread.start()
        except Exception as e:
            self.view_handler.show_message_dialog(error_message, 'critical')

    def task_done_action(self, task_class):
        self.view_handler.close_window()
        self.view_handler.enable_elements()
        self.view_handler.show_message_dialog('Task done !')

    def yes_action(self, observed, callback):
        self.view_handler.close_window()
        if callback != None:
            self.view_handler.disable_elements()
            self.view_handler.load_window('ProgressWindowHandler', False)

            if callback == 'ExportTask':
                self.run_task('ExportTask', (self.output_path,))
            elif hasattr(self, f"{callback}"):
                eval(f"self.{callback}()")

    def close_action(self, observed = None, args = None):
        self.view_handler.close_window()

    def select_input_action(self, observed, args):
		# Saving last loaded FBX file into .ini
        last = self.settings.value("LastFbxLoaded")
        self.fbx_path = self.view_handler.open_file_dialog('file', 'Select the FBX file', 'FBX (*.fbx)', False, last)[0]
        if not self.fbx_path:
            return        
        self.settings.setValue("LastFbxLoaded", QUrl(self.fbx_path).adjusted(QUrl.RemoveFilename).toString())

        
        # Output files
        last = self.settings.value("LastSprSaved")
        self.spr_path = self.view_handler.open_file_dialog('save-file', 
            'Save the SPR file', 'SPR (*.spr *.pak *.zpak);;All files (*.*)', False, last)[0]
        if not self.spr_path:
            return
        self.settings.setValue("LastSprSaved", QUrl(self.spr_path).adjusted(QUrl.RemoveFilename).toString())


        self.ioram_path = None
        self.vram_path = None
        if self.spr_path :
            if self.spr_path.endswith("_s.zpak") :
                self.ioram_path = self.spr_path[:-7] + "_i.zpak"
                self.vram_path = self.spr_path[:-7] + "_v.zpak"
            if self.spr_path.endswith("_s.pak"):
                self.ioram_path = self.spr_path[:-6] + "_i.pak"
                self.vram_path = self.spr_path[:-6] + "_v.pak"
            if self.spr_path.endswith(".spr"):
                self.ioram_path = self.spr_path[:-4] + ".ioram"
                self.vram_path = self.spr_path[:-4] + ".vram"

				
        if not self.ioram_path:
            self.ioram_path = self.view_handler.open_file_dialog('save-file', 
            'Save the IORAM file', 'IORAM (*.ioram *.pak *.zpak);;All files (*.*)')[0]
        if not self.ioram_path:
            return
        
        if not self.vram_path:
            self.vram_path = self.view_handler.open_file_dialog('save-file', 
            'Save the VRAM file', 'VRAM (*.vram *.pak *.zpak);;All files (*.*)')[0]
        if not self.vram_path:
            return

        ext = self.spr_path.rsplit('.', 1)[1].lower()
        if (ext == 'zpak') or (ext == 'pak'):
            fbx_dir_path = os.path.split(self.fbx_path)[0]
            if os.path.exists(f"{fbx_dir_path}\\pak_files"):
                self.view_handler.disable_elements()
                self.view_handler.load_window('ListWindowHandler', False, 
                    f"Other files to include in SPR {ext} file")
                
                self.other_files = {}
                for path in natsorted(glob.glob(f"{fbx_dir_path}\\pak_files\\*")):
                    filename = os.path.basename(path)
                    filename = re.sub('^\[\d+\]', '', filename)
                    self.other_files[filename] = path
                self.view_handler.set_entries('file_list_model', self.other_files.keys())
                return
        self.import_action()

    def add_files_action(self, observed = None, args = None):
        files = self.view_handler.open_file_dialog('file', 'Select files to add', '', True)[0]
        if not files:
            return
        
        for path in files:
            filename = os.path.basename(path)
            filename = re.sub('^\[\d+\]', '', filename)
            self.other_files[filename] = path
        self.view_handler.set_entries('file_list_model', self.other_files.keys())
    
    def import_action(self, observed = None, args = []):
        if self.view_handler.window_handler.__class__.__name__ != 'MainWindowHandler':
            self.close_action()

        self.view_handler.disable_elements()
        self.view_handler.load_window('ProgressWindowHandler')

        other_files = []
        for filename in args:
            other_files.append(self.other_files[filename])
        self.run_task('ImportTask', (self.fbx_path, self.spr_path, self.ioram_path, 
            self.vram_path, other_files))

    def export_action(self, observed, args):
        try:
            ut.empty_temp_dir()
            self.open_action()

            if ('spr' in self.data.keys()) and ('ioram' in self.data.keys()) and ('vram' in self.data.keys()):
                
                last = self.settings.value("LastExportFolder")
                self.output_path = self.view_handler.open_file_dialog('folder', 'Select the destination folder', False, last)
                if not self.output_path:
                    return
                self.settings.setValue("LastExportFolder", QUrl(self.output_path).adjusted(QUrl.RemoveFilename).toString())

                if len(os.listdir(self.output_path)) > 0:
                    self.view_handler.show_message_dialog(
                        "Folder is not empty, data may be overwritten, Proceed ?", 'question', '', 'ExportTask'
                    )
                else:
                    self.view_handler.disable_elements()
                    self.view_handler.load_window('ProgressWindowHandler')
                    self.run_task('ExportTask', (self.output_path,))
        except Exception as e:
            self.view_handler.show_message_dialog("Error during convertion", 'critical')

    def get_stpk_file(self, path):
        stream = open(path, 'rb')
        data_type = stream.read(4)
        stream.close()
        
        stpk_object = None
        if data_type == b'STPZ':
            stpz_object = STPZ()
            stpk_object = stpz_object.decompress(path)
        elif data_type == b'STPK':
            stpk_object = STPK()
            stream = open(path, "rb")
            stpk_object.read(stream)
            stream.close()
        return stpk_object
    
    def open_action(self):
        try:
            
            last = self.settings.value("LastSprLoaded")
            spr_path = self.view_handler.open_file_dialog('file', 'Select the SPR file', \
                'SPR (*.spr *.pak *.zpak);;All files (*.*)', False, last)[0]            
            if spr_path :
                self.settings.setValue("LastSprLoaded", QUrl(spr_path).adjusted(QUrl.RemoveFilename).toString())

            ioram_path = None
            vram_path = None
            if spr_path :
                if spr_path.endswith("_s.zpak"):
                    ioram_path = spr_path[:-7] + "_i.zpak"
                    vram_path = spr_path[:-7] + "_v.zpak"
                if spr_path.endswith("_s.pak"):
                    ioram_path = spr_path[:-6] + "_i.pak"
                    vram_path = spr_path[:-6] + "_v.pak"
                if spr_path.endswith(".spr"):
                    ioram_path = spr_path[:-4] + ".ioram"
                    vram_path = spr_path[:-4] + ".vram"
                
                if ((ioram_path) and (not os.path.exists(ioram_path))) :
                    ioram_path = None
                if ((vram_path) and (not os.path.exists(vram_path))) :
                    vram_path = None
                
            if spr_path:
                self.data['spr_stpk'] = self.get_stpk_file(spr_path)
                if self.data['spr_stpk'] == None:
                    del self.data['spr_stpk']
                    stream = open(spr_path, "rb")
                    data_tag = stream.read(4)
                    stream.seek(0)
                    if data_tag in cm.class_map:
                        data_tag = cm.class_map[data_tag]
                    name = os.path.basename(spr_path)
                    spr_object = eval(data_tag)(ut.s2b_name(name))
                    if spr_object == None:
                        raise Exception('Invalid file provided')
                    else:
                        self.data['spr'] = spr_object
                        self.data['spr'].read(stream, 0)
                    stream.close()
                else:
                    if cm.selected_game == 'dbrb':
                        # RB1 nested STPK
                        self.data['spr_stpk'] = self.data['spr_stpk'].entries[0]
                    self.data['spr'] = self.data['spr_stpk'].search_entries([], '.spr')[0]
            else:
                return

            if ioram_path == None:
                ioram_path = self.view_handler.open_file_dialog('file', 'Select the IORAM file', \
                    'IORAM (*.ioram *.pak *.zpak);;All files (*.*)')[0]
            if ioram_path:
                self.data['ioram_stpk'] = self.get_stpk_file(ioram_path)
                if self.data['ioram_stpk'] == None:
                    stream = open(ioram_path, "rb")
                    self.data['ioram'] = stream.read()
                    stream.close()
                else:
                    if cm.selected_game == 'dbrb':
                        # RB1 nested STPK
                        self.data['ioram_stpk'] = self.data['ioram_stpk'].entries[0]
                    self.data['ioram'] = self.data['ioram_stpk'].search_entries([], '.ioram')[0].data
            else:
                return
            
            vbuf_data = self.data['spr'].search_entries([], 'VBUF')
            if len(vbuf_data) > 0:
                ioram_stream = BytesIO(self.data['ioram'])

                for entry in vbuf_data:
                    entry.data.read_ioram(ioram_stream)
            else:
                raise Exception("No model info found in SPR !")

            if vram_path == None:
                vram_path = self.view_handler.open_file_dialog('file', 'Select the VRAM file', \
                    'VRAM (*.vram *.pak *.zpak);;All files (*.*)')[0]
            if vram_path:
                self.data['vram_stpk'] = self.get_stpk_file(vram_path)
                if self.data['vram_stpk'] == None:
                    stream = open(vram_path, "rb")
                    self.data['vram'] = stream.read()
                    stream.close()
                else:
                    if cm.selected_game == 'dbrb':
                        # RB1 nested STPK
                        self.data['vram_stpk'] = self.data['vram_stpk'].entries[0]
                    self.data['vram'] = self.data['vram_stpk'].search_entries([], '.vram')[0].data
            else:
                return

            tx2d_data = self.data['spr'].search_entries([], 'TX2D')
            if len(tx2d_data) > 0:
                vram_stream = BytesIO(self.data['vram'])

                for entry in tx2d_data:
                    entry.data.read_vram(vram_stream)
            else:
                raise Exception("No texture info found in SPR !")
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()
            self.view_handler.show_message_dialog("Error while loading files", 'critical')