import sys
from PyQt5 import QtGui, QtWidgets
from PyQt5.QtWidgets import QFileDialog
from ui.handlers.MainWindowHandler import MainWindowHandler

class ViewHandler():
    def init(self, callback = None):
        self.app = QtWidgets.QApplication([])
        self.resetWindow()
        self.main_window = MainWindowHandler(self.window)
        self.initObservers()
        self.attachObservers()
        self.main_window.load()
        self.window.setWindowTitle("RB Character Editor - by Ascomods")
        if callback != None:
            eval(callback['name'])(callback['parameters'])
        self.window.show()
        sys.exit(self.app.exec_())

    def resetWindow(self):
        if hasattr(self, 'window'):
            self.window.close()
        self.window = QtWidgets.QMainWindow()
    
    def disableElements(self, elements):
        for elt in elements:
            eval(f"self.main_window.ui.{elt}").setEnabled(False)

    def enableElements(self, elements):
        for elt in elements:
            eval(f"self.main_window.ui.{elt}").setEnabled(True)

    def initObservers(self):
        if not hasattr(self, 'observers'):
            self.observers = {}
    
    def attachObservers(self):
        for key, val in self.observers.items():
            eval(f"self.{key}").add_observer(val, identify_observed=True)

    def addEntries(self, view, listModel, entries):
        for entry in entries:
            eval(f"self.{view}.{listModel}").appendRow(QtGui.QStandardItem(entry))
        self.main_window.ui.statusbar.showMessage(f"{len(entries)} entries found")
    
    def showMessageDialog(self, message, type = 'information', title = ''):
        """
        Possible types : 'information', 'warning', 'critical', 'question'
        """
        if title == '':
            title = type.title()
        res = eval(f"QtWidgets.QMessageBox.{type}")(None, title, message)
        if type == 'question':
            return res == QtWidgets.QMessageBox.Yes
        return False
    
    def setStatusBarMessage(self, message):
        self.main_window.ui.statusbar.showMessage(message)
    
    def openFileDialog(self, type = 'file', title = 'Open', filter = ''):
        if type == 'folder':
            method = "getExistingDirectory"
        elif type == 'save-file':
            method = "getSaveFileName"
        else:
            method = "getOpenFileName"
        if type != 'folder':
            return eval(f"QFileDialog.{method}")(self.window, title, filter=filter)
        else:
            return eval(f"QFileDialog.{method}")(self.window, title)