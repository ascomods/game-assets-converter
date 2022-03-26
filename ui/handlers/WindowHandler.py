from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget
from observed import observable_method

class WindowHandler():
    toggleable_elements = []

    def __init__(self, window, title = ''):
        super().__init__()
        self.window = window
        self.title = title
    
    def init_ui(self):
        if hasattr(self.ui, 'title_label') and self.title != '':
            self.ui.title_label.setText(self.title)

        # remove borders
        self.window.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        # make window moveable
        if hasattr(self.ui, 'title_frame'):
            self.ui.title_frame.mousePressEvent = self.mouse_press_event
            self.ui.title_frame.mouseMoveEvent = self.move_window
        
        # title buttons actions
        if hasattr(self.ui, 'title_btns_frame'):
            if hasattr(self.ui, 'minimize_btn'):
                self.ui.minimize_btn.clicked.connect(self.window.showMinimized)
            if hasattr(self.ui, 'exit_btn'):
                self.ui.exit_btn.clicked.connect(self.notify_exit_action)

    def disable_elements(self, elements = []):
        if elements == []:
            elements = self.toggleable_elements
        for elt in elements:
            eval(f"self.ui.{elt}").setEnabled(False)

    def enable_elements(self, elements = []):
        if elements == []:
            elements = self.toggleable_elements
        for elt in elements:
            eval(f"self.ui.{elt}").setEnabled(True)

    def move_window(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            self.window.move(self.window.pos() + event.globalPos() - self.window.drag_pos)
            self.window.drag_pos = event.globalPos()
            event.accept()
    
    def mouse_press_event(self, event):
        self.window.drag_pos = event.globalPos()
    
    @observable_method()
    def notify_exit_action(self, arg):
        pass