from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget
import qtawesome as qta
from ui.handlers.WindowHandler import WindowHandler
from ui.views.MessageWindow import Ui_MessageWindow
from observed import observable_method

class MessageWindowHandler(WindowHandler, QWidget):
    callback = None

    def load(self):
        self.ui = Ui_MessageWindow()
        self.ui.setupUi(self.window)
        self.init_ui()
    
    def init_ui(self):
        super().init_ui()

        self.ui.yes_btn.clicked.connect(self.yes_action)
        self.ui.no_btn.clicked.connect(self.notify_no_action)

    def set_callback(self, callback):
        self.callback = callback

    def set_message(self, m_type, message, yes_no = False):
        if m_type == 'information':
            icon_pixmap = qta.icon('mdi.information', color='white') \
                .pixmap(QtCore.QSize(50, 50))
        elif m_type == 'warning':
            icon_pixmap = qta.icon('ph.warning-fill', color='yellow') \
                .pixmap(QtCore.QSize(50, 50))
        elif m_type == 'critical':
            icon_pixmap = qta.icon('msc.error', color='red') \
                .pixmap(QtCore.QSize(60, 60))
        elif m_type == 'question':
            icon_pixmap = qta.icon('ph.question-light', color='white') \
                .pixmap(QtCore.QSize(60, 60))
            yes_no = True
        if not yes_no:
            self.ui.no_btn.hide()
            spacer = self.ui.horizontalLayout_5.itemAt(2)
            self.ui.horizontalLayout_5.removeItem(spacer)
            self.ui.yes_btn.setText('OK')
        self.ui.message_icon.setPixmap(icon_pixmap)
        self.ui.message_label.setText(message)

    @QtCore.pyqtSlot()
    def yes_action(self):
        self.notify_yes_action(self.callback)

    @observable_method()
    def notify_yes_action(self, arg):
        pass        

    @observable_method()
    def notify_no_action(self, arg):
        pass