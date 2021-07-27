import core.utils as ut
import os, glob
from io import BytesIO
from core.STPK import STPK
import ui.handlers.ViewHandler as vh
import handlers.MainHandler as mh

class MaterialHandler():
    def __init__(self, view_handler = None):
        self.paths = {}
        if view_handler != None:
            self.view_handler = view_handler
        else:
            self.view_handler = vh.ViewHandler()
        self.view_handler.addObservers({
            'MaterialWindowHandler': {
                'notifyOpenAction' : self.openAction,
                'notifySaveAction' : self.saveAction,
                'notifySaveAsAction' : self.saveAction,
                'notifyImportAction' : self.importAction,
                'notifyExportAction' : self.exportAction,
                'notifyGoBackAction' : self.goBackAction
            }
        })
        callbacks = {
            'self.disableElements': ('saveBtn', 'saveAsBtn', 'importBtn', 'exportBtn')
        }
        self.view_handler.loadWindow('MaterialWindowHandler', callbacks)

    def openAction(self, observed, args):
        try:
            self.view_handler.disableElements(
                ['saveBtn', 'saveAsBtn', 'importBtn', 'exportBtn']
            )
            spr_path = self.view_handler.openFileDialog('file', 'Select the SPR file')[0]
            if spr_path:
                self.paths['spr'] = spr_path
                stream = open(self.paths['spr'], "rb")
                data_tag = stream.read(4)
            else:
                return
        
            self.spr_stpk_object = eval(data_tag)()
            self.spr_stpk_object.read(stream)

            res = self.spr_stpk_object.search_entries('MTRL')
            if len(res) > 0:
                self.view_handler.addEntries('contentModel', [ut.b2s_name(x.name) for x in res if x.name != b'DbzCharMtrl'])
                
                self.view_handler.enableElements(
                    ['saveBtn', 'saveAsBtn', 'importBtn', 'exportBtn']
                )
            else:
                raise Exception()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(e)
            self.view_handler.showMessageDialog("Error while loading files", 'critical')
    
    def saveAction(self, observed, args):
        try:
            if 'spr' in self.paths and self.paths['spr']:

                if observed.__name__ == 'notifySaveAsAction':
                    spr_path = self.view_handler.openFileDialog('save-file', 
                        'Save the SPR file', 'STPK (*.stpk)')[0]
                    if not spr_path:
                        return
                    self.paths['spr'] = spr_path
                else:
                    res = self.view_handler.showMessageDialog(
                        "Loaded SPR file will be overwritten, Proceed ?", 'question')
                    if not res:
                        return
                
                res = self.spr_stpk_object.search_entries('MTRL')
                if len(res) > 0:
                    spr_stpk_stream = open(self.paths['spr'], 'wb')
                    self.spr_stpk_object.write(spr_stpk_stream)

                    self.view_handler.showMessageDialog("File saved successfully !")
                else:
                    raise Exception()
            else:
                self.view_handler.showMessageDialog("File is not loaded properly !", 'warning')
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(e)
            self.view_handler.showMessageDialog("Error while saving data", 'critical')
    
    def importAction(self, observed, selectedItems):
        try:
            if len(selectedItems) > 0:
                input_path = self.view_handler.openFileDialog('folder', 'Select the source folder')

                if not input_path:
                    return
                
                folder_names = [os.path.basename(path) for path in glob.glob(f"{input_path}/*")]
                for item in selectedItems:
                    if item not in folder_names:
                        self.view_handler.showMessageDialog(
                            "Mismatch between folders and current selection !", 'critical')
                        return
                
                res = self.spr_stpk_object.search_entries('MTRL')

                if len(res) > 0:
                    os.chdir(input_path)

                    # Load entries
                    for entry in res:
                        name = ut.b2s_name(entry.name)
                        if name in selectedItems:
                            entry.load()
                    
                    spr_object = self.spr_stpk_object.search_entries('SPRP')[0]
                    self.view_handler.showMessageDialog(f"{len(selectedItems)} entries imported")
                else:
                    raise Exception()
            else:
                self.view_handler.showMessageDialog("No entries selected", 'warning')
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(e)
            self.view_handler.showMessageDialog("Error while importing data", 'critical')

    def exportAction(self, observed, selectedItems):
        try:
            if len(selectedItems) > 0:
                output_path = self.view_handler.openFileDialog('folder', 'Select the destination folder')

                if not output_path:
                    return
                
                if len(os.listdir(output_path)) > 0:
                    res = self.view_handler.showMessageDialog(
                        "Folder is not empty, data may be overwritten, Proceed ?", 'question')
                    if not res:
                        return
                
                res = self.spr_stpk_object.search_entries('MTRL')

                if len(res) > 0:
                    for entry in res:
                        name = ut.b2s_name(entry.name)
                        if name in selectedItems:
                            entry.save(output_path + '/', name)
                    self.view_handler.showMessageDialog(f"{len(selectedItems)} entries exported")
                else:
                    raise Exception()
            else:
                self.view_handler.showMessageDialog("No entries selected", 'warning')
        except Exception as e:
            print(e)
            self.view_handler.showMessageDialog("Error while exporting data", 'critical')
    
    def goBackAction(self, observed, args):
        self.view_handler.resetWindow()
        mh.MainHandler(self.view_handler)