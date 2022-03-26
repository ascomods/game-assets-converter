from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QWidget
import qtawesome as qta
from ui.handlers.WindowHandler import WindowHandler
from ui.views.ListWindow import Ui_ListWindow
from observed import observable_method

class ListWindowHandler(WindowHandler, QWidget):
    def load(self):
        self.ui = Ui_ListWindow()
        self.ui.setupUi(self.window)
        self.init_ui()
        self.ui.add_btn.clicked.connect(self.notify_add_action)
        self.ui.remove_btn.clicked.connect(self.remove_action)
        self.ui.done_btn.clicked.connect(self.done_action)
    
    def init_ui(self):
        super().init_ui()

        # content list
        self.file_list_model = QtGui.QStandardItemModel()
        self.ui.file_list_view.setModel(self.file_list_model)

    @observable_method()
    def notify_add_action(self, arg):
        pass

    @QtCore.pyqtSlot()
    def remove_action(self):
        model_indexes = self.ui.file_list_view.selectedIndexes()
        for m_idx in model_indexes[::-1]:
            self.file_list_model.removeRow(m_idx.row())

    @QtCore.pyqtSlot()
    def done_action(self):
        items = []
        for i in range(self.file_list_model.rowCount()):
            items.append(self.file_list_model.item(i).text())
        self.notify_done_action(items)

    @observable_method()
    def notify_done_action(self, items):
        pass