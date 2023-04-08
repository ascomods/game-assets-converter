from stat import filemode
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
from ui.handlers.ListWindowHandler import ListWindowHandler
from ui.handlers.MainWindowHandler import MainWindowHandler
from ui.handlers.ProgressWindowHandler import ProgressWindowHandler
from ui.handlers.MessageWindowHandler import MessageWindowHandler

class ViewHandler():
    observers = {}

    def init(self, callbacks = None):
        if callbacks != None:
            for function, params in callbacks.items():
                eval(function)(params)

    def close_window(self, return_to_parent = True):
        if hasattr(self, 'window'):
            self.window.close()
        if return_to_parent:
            if hasattr(self, 'parent_handler'):
                self.window_handler = self.parent_handler
                self.window = self.parent_handler.window
                self.enable_elements()
    
    def disable_elements(self, elements = []):
        self.window_handler.disable_elements(elements)

    def enable_elements(self, elements = []):
        self.window_handler.enable_elements(elements)

    def set_entries(self, list_model, entries):
        eval(f"self.window_handler.{list_model}").clear()
        for entry in entries:
            eval(f"self.window_handler.{list_model}") \
                .appendRow(QtGui.QStandardItem(entry))

    def add_observers(self, observers):
        self.observers = {**self.observers, **observers}

    def attach_observers(self):
        for window_class, functions in self.observers.items():
            for function, observer in functions.items():
                if self.window_handler.__class__.__name__ == window_class:
                    eval(f"self.window_handler.{function}").add_observer(observer, 
                        identify_observed=True)
                else:
                    for parent in self.window_handler.__class__.__bases__:
                        if parent.__name__ == window_class:
                            eval(f"self.window_handler.{function}").add_observer(observer, 
                                identify_observed=True)
                            break

    def load_window(self, handler_class, is_child = True, title = '', callbacks = None):
        if hasattr(self, 'window_handler'):
            self.parent_handler = self.window_handler
        if hasattr(self, 'window') and is_child:
            self.window = QtWidgets.QMainWindow(self.window)
        else:
            self.window = QtWidgets.QMainWindow()
        self.window_handler = eval(handler_class)(self.window, title)
        self.attach_observers()
        self.window_handler.load()
        if callbacks != None:
            for function, params in callbacks.items():
                eval(function)(params)
        self.window.show()
    
    def show_message_dialog(self, message, type = 'information', title = '', 
        callback = None, yes_no = False):
        """
        Possible types : 'information', 'warning', 'critical', 'question'
        """
        self.load_window('MessageWindowHandler')
        self.window_handler.set_message(type, title, message, yes_no)
        if callback != None:
            self.window_handler.set_callback(callback)
    
    def open_file_dialog(self, type = 'file', title = 'Open', filter = '', multiple = False, directory =''):
        if type == 'folder':
            method = "getExistingDirectory"
        elif type == 'save-file':
            method = "getSaveFileName"
        elif multiple:
            method = "getOpenFileNames"
        else:
            method = "getOpenFileName"
        if type != 'folder':
            return eval(f"QFileDialog.{method}")(self.window, title, filter=filter, directory=directory)
        else:
            return eval(f"QFileDialog.{method}")(self.window, title, directory=directory)