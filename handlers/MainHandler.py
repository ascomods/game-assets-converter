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
from PyQt5.QtCore import QUrl

class MainHandler():
    def init(self, view_handler = None):
        self.paths = {}
        self.data = {}

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
            self.view_handler.load_window('ProgressWindowHandler')

            if callback == 'ExportTask':
                self.run_task('ExportTask', (self.output_path,))
            elif hasattr(self, f"{callback}"):
                eval(f"self.{callback}()")

    def close_action(self, observed = None, args = None):
        self.view_handler.close_window()

    def sort_filter(self, filter, ext):
        ext = ext.upper()
        new_filter = []
        for elt in filter:
            if ext in elt.rsplit(' ', 1)[0]:
                new_filter.insert(0, elt)
            else:
                new_filter.append(elt)
        
        return new_filter

    def select_input_action(self, observed, args):
		# Saving last loaded FBX file into .ini
        last = cm.settings.value("LastFolderLoaded")
        self.input_path = self.view_handler.open_file_dialog('folder', 
            'Select the input folder', '', False, last)
        if not self.input_path:
            return
        cm.settings.setValue("LastFolderLoaded", QUrl(self.input_path).toString())
        
        # Output files
        last = cm.settings.value("LastSprSaved")
        self.spr_path = self.view_handler.open_file_dialog('save-file', 
            'Save the SPR file', 'SPR (*.spr *.pak *.zpak);;All files (*.*)', False, last)[0]
        if not self.spr_path:
            return
        cm.settings.setValue("LastSprSaved", QUrl(self.spr_path).toString())

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
            self.view_handler.disable_elements()
            self.view_handler.load_window('ListWindowHandler', f"Files to include in {ext} file")
            
            self.files = {}
            for path in natsorted(glob.glob(os.path.join(self.input_path, "*"))):
                filename = os.path.basename(path)
                filename = re.sub('^\[\d+\]', '', filename)
                self.files[filename] = path
            self.view_handler.set_entries('file_list_model', self.files.keys())
            return
        self.import_action()

    def add_files_action(self, observed = None, args = None):
        files = self.view_handler.open_file_dialog('file', 'Select files to add', '', True)[0]
        if not files:
            return
        
        for path in files:
            filename = os.path.basename(path)
            filename = re.sub('^\[\d+\]', '', filename)
            self.files[filename] = path
        self.view_handler.set_entries('file_list_model', self.files.keys())
    
    def import_action(self, observed = None, args = []):
        if self.view_handler.window_handler.__class__.__name__ != 'MainWindowHandler':
            self.close_action()

        self.view_handler.disable_elements()
        self.view_handler.load_window('ProgressWindowHandler')

        files = []
        for filename in args:
            files.append(self.files[filename])
        self.run_task('ImportTask', (self.spr_path, self.ioram_path, 
            self.vram_path, files))

    def export_action(self, observed, args):
        try:
            ut.empty_temp_dir()
            self.open_action()

            if (('spr_stpk' in self.data.keys()) or ('spr' in self.data.keys())) and \
               (('ioram_stpk' in self.data.keys()) or ('ioram' in self.data.keys())) and \
               (('vram_stpk' in self.data.keys()) or ('vram' in self.data.keys())):
                last = cm.settings.value("LastExportFolder")
                self.output_path = self.view_handler \
                    .open_file_dialog('folder', 'Select the destination folder', '', False, last)
                if not self.output_path:
                    return
                cm.settings.setValue("LastExportFolder", QUrl(self.output_path).toString())

                if len(os.listdir(self.output_path)) > 0:
                    self.view_handler.show_message_dialog(
                        'Folder is not empty, data may be overwritten, Proceed ?', 'question', 'ExportTask'
                    )
                else:
                    self.view_handler.disable_elements()
                    self.view_handler.load_window('ProgressWindowHandler')
                    self.run_task('ExportTask', (self.output_path,))
        except Exception as e:
            self.view_handler.show_message_dialog('Error during convertion', 'critical')

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
            base_filter = ['ZPAK (*.zpak)', 'PAK (*.pak)', 'All files (*.*)']

            last = cm.settings.value("LastSprLoaded")
            filter = base_filter.copy()
            filter.insert(-1, 'SPR (*.spr)')
            spr_path = self.view_handler.open_file_dialog('file', 'Select the SPR file',
                ';;'.join(filter), False, last)[0]
            if spr_path :
                cm.settings.setValue("LastSprLoaded", QUrl(spr_path).adjusted(QUrl.RemoveFilename).toString())
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

                name, ext = os.path.splitext(spr_path.lower())
                ext = ext.replace('.', '')
                base_filter = self.sort_filter(base_filter, ext)
            else:
                return
                
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

            if ioram_path == None:
                filter = base_filter.copy()
                filter.insert(-1,'IORAM (*.ioram)')
                ioram_path = self.view_handler.open_file_dialog('file', 'Select the IORAM file',
                    ';;'.join(filter))[0]

            if ioram_path:
                self.data['ioram_stpk'] = self.get_stpk_file(ioram_path)
                if self.data['ioram_stpk'] == None:
                    stream = open(ioram_path, "rb")
                    self.data['ioram'] = stream.read()
                    stream.close()
            else:
                return

            if vram_path == None:
                filter = base_filter.copy()
                filter.insert(-1,'VRAM (*.vram)')
                vram_path = self.view_handler.open_file_dialog('file', 'Select the VRAM file',
                    ';;'.join(filter))[0]

            if vram_path:
                self.data['vram_stpk'] = self.get_stpk_file(vram_path)
                if self.data['vram_stpk'] == None:
                    stream = open(vram_path, "rb")
                    self.data['vram'] = stream.read()
                    stream.close()
            else:
                return
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()
            self.view_handler.show_message_dialog('Error while loading files', 'critical')