from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QWidget
import qtawesome as qta
from ui.views.MainWindow import Ui_MainWindow
from observed import observable_method
import core.common as cm

class MainWindowHandler(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def load(self):
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self.window)
        self.ui.modelBtn.clicked.connect(self.notifyModelEditAction)
        self.ui.textureBtn.clicked.connect(self.notifyTextureEditAction)
        self.ui.materialBtn.clicked.connect(self.notifyMaterialEditAction)
    
    def initUi(self):
        # game combo box
        for key, val in cm.games.items():
            self.ui.gameCmbBox.addItem(val)
        gameIdx = list(cm.games.keys()).index(cm.selected_game)
        self.ui.gameCmbBox.setCurrentIndex(gameIdx)

        # platform combo box
        for key, val in cm.platforms.items():
            self.ui.platformCmbBox.addItem(val)
        platformIdx = list(cm.platforms.keys()).index(cm.selected_platform)
        self.ui.platformCmbBox.setCurrentIndex(platformIdx)

        # content list
        self.contentModel = QtGui.QStandardItemModel()
        self.ui.contentListView.setModel(self.contentModel)

        # actions buttons
        self.ui.openBtn.setIcon(qta.icon('fa5s.folder-open', color='white'))
        self.ui.openBtn.setToolTip("Open")
        self.ui.saveBtn.setIcon(qta.icon('fa.save', color='white'))
        self.ui.saveBtn.setToolTip("Save")
        self.ui.saveAsBtn.setIcon(qta.icon('mdi.content-save-all', color='white'))
        self.ui.saveAsBtn.setToolTip("Save As")
        self.ui.disableBtn.setIcon(qta.icon('ei.ban-circle', color='white'))
        self.ui.disableBtn.setToolTip("Disable Parts")
        self.ui.importBtn.setIcon(qta.icon('fa5s.file-import', color='white'))
        self.ui.importBtn.setToolTip("Import")
        self.ui.exportBtn.setIcon(qta.icon('fa5s.file-export', color='white'))
        self.ui.exportBtn.setToolTip("Export")

    @observable_method()
    @QtCore.pyqtSlot()
    def notifyModelEditAction(self, arg):
        pass

    @observable_method()
    @QtCore.pyqtSlot()
    def notifyTextureEditAction(self, arg):
        pass

    @observable_method()
    @QtCore.pyqtSlot()
    def notifyMaterialEditAction(self, arg):
        pass