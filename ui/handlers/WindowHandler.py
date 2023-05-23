import os
import core.common as cm
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QWidget, QDesktopWidget, QMainWindow
from observed import observable_method

class WindowHandler():
    toggleable_elements = []

    def __init__(self, window, title = ''):
        super().__init__()
        self.window = window
        self.title = title

    def init_ui(self):
        # set stylesheet
        self.window.setStyleSheet(cm.stylesheet)
        # remove borders and background
        self.window.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.window.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        if hasattr(self.ui, 'title_label') and self.title != '':
            self.ui.title_label.setText(self.title)

        # center window
        desktop_widget = QDesktopWidget()
        screen_number = desktop_widget.screenNumber(QtGui.QCursor.pos())
        desktop_rect = desktop_widget.screenGeometry(screen_number)
        x = (desktop_rect.width() - self.window.width()) / 2
        y = (desktop_rect.height() - self.window.height()) / 2
        self.window.move(x + desktop_rect.left(), y + desktop_rect.top())

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