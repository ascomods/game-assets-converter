from PyQt5.QtWidgets import QWidget
from ui.handlers.WindowHandler import WindowHandler
from ui.views.ProgressWindow import Ui_ProgressWindow

class ProgressWindowHandler(WindowHandler, QWidget):   
    def load(self):
        self.ui = Ui_ProgressWindow()
        self.ui.setupUi(self.window)
        self.init_ui()
    
    def init_ui(self):
        super().init_ui()

    def set_progress(self, val):
        self.ui.progress_bar.setValue(val)