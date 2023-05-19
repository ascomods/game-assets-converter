import os
from io import BytesIO
from PyQt5.QtCore import QThread
from natsort import natsorted
from tasks.ImportTask import *
from tasks.ExportTask import *
import core.utils as ut
import core.common as cm
import ui.handlers.ViewHandler as vh
from PyQt5.QtCore import QUrl

class MainHandler():
    def init(self, view_handler = None):
        self.paths = {}
        cm.data = {}

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
                'notify_import_action' : self.import_action,
                'notify_export_action' : self.export_action
            },
            'MessageWindowHandler': {
                'notify_yes_action' : self.yes_action,
                'notify_no_action' : self.close_action
            }
        })
        self.view_handler.load_window('MainWindowHandler')

    def run_task(self, task_class, args = (), error_message = 'Error while processing data'):
        try:
            self.thread = QThread()
            self.task = eval(task_class)(*args)
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
                self.run_task('ExportTask')
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

    def import_action(self, observed, args):
		# Saving last loaded input folder file into .ini
        last = cm.settings.value("LastInputFolder")
        cm.input_path = self.view_handler.open_file_dialog('folder', 
            'Select the input folder', '', False, last)
        if not cm.input_path:
            return
        cm.settings.setValue("LastInputFolder", QUrl(cm.input_path).toString())

		# Saving last loaded output folder file into .ini
        last = cm.settings.value("LastOutputFolder")
        cm.output_path = self.view_handler.open_file_dialog('folder', 
            'Select the output folder', '', False, last)
        if not cm.output_path:
            return
        cm.settings.setValue("LastOutputFolder", QUrl(cm.output_path).toString())

        self.view_handler.disable_elements()
        self.view_handler.load_window('ProgressWindowHandler')
        self.run_task('ImportTask')

    def add_files_action(self, observed = None, args = None):
        files = self.view_handler.open_file_dialog('file', 'Select files to add', '', True)[0]
        if not files:
            return
        
        for path in files:
            filename = os.path.basename(path)
            filename = re.sub('^\[\d+\]', '', filename)
            self.files[filename] = path
        self.view_handler.set_entries('file_list_model', self.files.keys())

    def export_action(self, observed, args):
        try:
            base_filter = ['ZPAK (*.zpak)', 'PAK (*.pak)', 'All files (*.*)']

            last = cm.settings.value("LastSprLoaded")
            filter = base_filter.copy()
            filter.insert(-1, 'SPR (*.spr)')
            cm.spr_path = self.view_handler.open_file_dialog('file', 'Select the SPR file',
                ';;'.join(filter), False, last)[0]

            cm.ioram_path = None
            cm.vram_path = None

            if cm.spr_path:
                cm.settings.setValue("LastSprLoaded", 
                    QUrl(cm.spr_path).adjusted(QUrl.RemoveFilename).toString())
                name, ext = os.path.splitext(cm.spr_path)
                ext = ext.replace('.', '').lower()
                base_filter = self.sort_filter(base_filter, ext)

                if (len(name) >= 2):
                    last_chars = name[-2:]
                    if (last_chars in ['_s', '_m']):
                        name = name[:-2]

                cm.ioram_path = name
                cm.vram_path = name
                if ('pak' in ext):
                    cm.ioram_path += '_i.' + ext
                    cm.vram_path += '_v.' + ext
                else:
                    cm.ioram_path += '.ioram'
                    cm.vram_path += '.vram'

                if ((cm.ioram_path) and (not os.path.exists(cm.ioram_path))):
                    cm.ioram_path = None
                if ((cm.vram_path) and (not os.path.exists(cm.vram_path))):
                    cm.vram_path = None
            else:
                return

            if (cm.selected_game == 'dbzb') and cm.spr_path.endswith("pak"):
                cm.ioram_path = cm.spr_path

            if cm.ioram_path == None:
                filter = base_filter.copy()
                filter.insert(-1,'IORAM (*.ioram)')
                cm.ioram_path = self.view_handler.open_file_dialog('file', 'Select the IORAM file',
                    ';;'.join(filter))[0]
            if cm.ioram_path == None:
                return

            if cm.vram_path == None:
                filter = base_filter.copy()
                filter.insert(-1,'VRAM (*.vram)')
                cm.vram_path = self.view_handler.open_file_dialog('file', 'Select the VRAM file',
                    ';;'.join(filter))[0]
            if cm.vram_path == None:
                return

            last = cm.settings.value("LastExportFolder")
            cm.output_path = self.view_handler \
                .open_file_dialog('folder', 'Select the destination folder', '', False, last)
            if not cm.output_path:
                return

            cm.settings.setValue("LastExportFolder", QUrl(cm.output_path).toString())

            if len(os.listdir(cm.output_path)) > 0:
                self.view_handler.show_message_dialog(
                    'Folder is not empty, data may be overwritten, Proceed ?', 'question', 'ExportTask'
                )
            else:
                self.view_handler.disable_elements()
                self.view_handler.load_window('ProgressWindowHandler')
                self.run_task('ExportTask')
        except Exception as e:
            print(e)
            import traceback
            traceback.print_exc()
            self.view_handler.show_message_dialog('Error while loading files', 'critical')