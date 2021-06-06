import core.utils as ut
import os, glob
from io import BytesIO
from core.STPK import STPK
import ui.handlers.ViewHandler as vh

class MainHandler():
    def __init__(self):
        self.paths = {}
        self.view_handler = vh.ViewHandler()
        self.view_handler.observers = {
            'main_window.notifyOpenAction' : self.openAction,
            'main_window.notifySaveAction' : self.saveAction,
            'main_window.notifySaveAsAction' : self.saveAction,
            'main_window.notifyDisableAction' : self.disableAction,
            'main_window.notifyImportAction' : self.importAction,
            'main_window.notifyExportAction' : self.exportAction
        }
        callback = {
            'name': 'self.disableElements',
            'parameters': ['saveBtn', 'saveAsBtn', 'disableBtn', 'importBtn', 'exportBtn']
        }
        self.view_handler.init(callback)

    def openAction(self, observed, args):
        try:
            self.view_handler.disableElements(
                ['saveBtn', 'saveAsBtn', 'disableBtn', 'importBtn', 'exportBtn']
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

            ioram_path = self.view_handler.openFileDialog('file', 'Select the IORAM file')[0]
            if ioram_path:
                self.paths['ioram'] = ioram_path
                stream = open(self.paths['ioram'], "rb")
                data_tag = stream.read(4)
            else:
                return
            
            self.ioram_stpk_object = eval(data_tag)()
            self.ioram_stpk_object.read(stream)

            res = self.spr_stpk_object.search_entries('VBUF')
            if len(res) > 0:
                ioram_stream = BytesIO(self.ioram_stpk_object.entries[0].data)

                for entry in res:
                    entry.data.read_ioram(ioram_stream)
                
                self.view_handler.addEntries('main_window', 'contentModel', 
                    [ut.b2s_name(x.name) for x in res])
                
                self.view_handler.enableElements(
                    ['saveBtn', 'saveAsBtn', 'disableBtn', 'importBtn', 'exportBtn']
                )
            else:
                raise Exception()
        except Exception as e:
            self.view_handler.showMessageDialog("Error while loading files", 'critical')
    
    def saveAction(self, observed, args):
        try:
            if 'spr' in self.paths and self.paths['spr'] and \
               'ioram' in self.paths and self.paths['ioram']:

                if observed.__name__ == 'notifySaveAsAction':
                    spr_path = self.view_handler.openFileDialog('save-file', 
                        'Save the SPR file', 'STPK (*.stpk)')[0]
                    if not spr_path:
                        return
                    self.paths['spr'] = spr_path

                    ioram_path = self.view_handler.openFileDialog('save-file', 
                        'Save the IORAM file', 'STPK (*.stpk)')[0]
                    if not ioram_path:
                        return
                    self.paths['ioram'] = ioram_path
                else:
                    res = self.view_handler.showMessageDialog(
                        "Loaded SPR and IORAM files will be overwritten, Proceed ?", 'question')
                    if not res:
                        return
                
                res = self.spr_stpk_object.search_entries('VBUF')
                if len(res) > 0:
                    # Build new ioram data
                    ioram_data = bytearray()

                    for entry in res:
                        vbuf = entry.data
                        data = vbuf.get_ioram()
                        padding = ut.add_padding(len(data))
                        ioram_data.extend(data)
                        ioram_data.extend(bytes(padding - len(data)))
                    
                    self.ioram_stpk_object.entries[0].data = ioram_data

                    spr_stpk_stream = open(self.paths['spr'], 'wb')
                    self.spr_stpk_object.write(spr_stpk_stream)

                    ioram_stpk_stream = open(self.paths['ioram'], 'wb')
                    self.ioram_stpk_object.write(ioram_stpk_stream)

                    self.view_handler.showMessageDialog("Files saved successfully !")
                else:
                    raise Exception()
            else:
                self.view_handler.showMessageDialog("Files are not loaded properly !", 'warning')
        except Exception as e:
            self.view_handler.showMessageDialog("Error while saving data", 'critical')
    
    def disableAction(self, observed, selectedItems):
        try:
            if len(selectedItems) > 0:
                res = self.view_handler.showMessageDialog(
                    "Selected model parts will be disabled, Proceed ?", 'question')
                if not res:
                    return
                
                res = self.spr_stpk_object.search_entries('VBUF')

                if len(res) > 0:
                    for entry in res:
                        name = ut.b2s_name(entry.name)
                        if name in selectedItems:
                            entry.data.ioram_data = bytes(entry.data.ioram_data_size)
                    self.view_handler.showMessageDialog(f"{len(selectedItems)} entries disabled")
                else:
                    raise Exception()     
            else:
                self.view_handler.showMessageDialog("No entries selected", 'warning')
        except Exception as e:
            self.view_handler.showMessageDialog("Error while disabling parts", 'critical')
    
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
                
                res = self.spr_stpk_object.search_entries('VBUF')

                if len(res) > 0:
                    os.chdir(input_path)

                    # Load entries
                    for entry in res:
                        name = ut.b2s_name(entry.name)
                        if name in selectedItems:
                            entry.load()

                    # Adding entries at the bottom of SPR
                    spr_object = self.spr_stpk_object.search_entries('SPRP')[0]
                    spr_data_offset = spr_object.info_offset + spr_object.data_info_size
                    last_spr_data_entry = spr_object.entries[-1].entries[-1]
                    spr_real_end_offset = \
                        ut.add_padding(last_spr_data_entry.offset + last_spr_data_entry.size)
                    
                    vbuf_entry_offset = spr_real_end_offset

                    for entry in res:
                        name = ut.b2s_name(entry.name)
                        if (name not in selectedItems) and (entry.offset < spr_real_end_offset):
                            offset = ut.add_padding(entry.offset + entry.data.get_size())
                        else:
                            offset = ut.add_padding(entry.offset)
                            if offset >= spr_real_end_offset:
                                vbuf_entry_offset = offset
                                break
                        vbuf_entry_offset = max(offset, vbuf_entry_offset)

                    # Update new VBUF offsets
                    for entry in res:
                        name = ut.b2s_name(entry.name)
                        if (name in selectedItems) or (entry.offset >= spr_real_end_offset):
                            entry.update_offsets(spr_data_offset, vbuf_entry_offset)
                            vbuf_entry_offset += entry.get_size()
                            spr_object.size += entry.get_size()

                    # Update ioram data chunk offset in VBUF parts
                    ioram_data_offset = 0
                    for entry in res:
                        vbuf = entry.data
                        vbuf.ioram_data_offset = ioram_data_offset
                        ioram_size = len(vbuf.get_ioram())
                        ioram_data_offset += ut.add_padding(ioram_size)
                    
                    self.view_handler.showMessageDialog(f"{len(selectedItems)} entries imported")
                else:
                    raise Exception()
            else:
                self.view_handler.showMessageDialog("No entries selected", 'warning')
        except Exception as e:
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
                
                res = self.spr_stpk_object.search_entries('VBUF')

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