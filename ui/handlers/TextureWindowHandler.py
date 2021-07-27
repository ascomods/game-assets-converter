from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QWidget
import qtawesome as qta
from ui.views.TextureWindow import Ui_TextureWindow
from observed import observable_method
import core.common as cm

class TextureWindowHandler(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def load(self):
        self.ui = Ui_TextureWindow()
        self.ui.setupUi(self.window)
        self.initUi()
        self.ui.gameCmbBox.currentIndexChanged.connect(self.gameSelectAction)
        self.ui.platformCmbBox.currentIndexChanged.connect(self.platformSelectAction)
        self.ui.contentListView.selectionModel().selectionChanged.connect(self.contentListSelectAction)
        self.ui.openBtn.clicked.connect(self.notifyOpenAction)
        self.ui.saveBtn.clicked.connect(self.notifySaveAction)
        self.ui.saveAsBtn.clicked.connect(self.notifySaveAsAction)
        self.ui.importBtn.clicked.connect(self.importAction)
        self.ui.exportBtn.clicked.connect(self.exportAction)
        self.ui.goBackBtn.clicked.connect(self.notifyGoBackAction)
    
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
        self.ui.importBtn.setIcon(qta.icon('fa5s.file-import', color='white'))
        self.ui.importBtn.setToolTip("Import")
        self.ui.exportBtn.setIcon(qta.icon('fa5s.file-export', color='white'))
        self.ui.exportBtn.setToolTip("Export")
        self.ui.goBackBtn.setIcon(qta.icon('fa.mail-reply', color='white'))
        self.ui.goBackBtn.setToolTip("Main Menu")

    @QtCore.pyqtSlot()
    def gameSelectAction(self):
        cm.selected_game = list(cm.games.keys())[self.ui.gameCmbBox.currentIndex()]

    @QtCore.pyqtSlot()
    def platformSelectAction(self):
        cm.selected_platform = list(cm.platforms.keys())[self.ui.platformCmbBox.currentIndex()]
    
    @observable_method()
    @QtCore.pyqtSlot()
    def notifyOpenAction(self, arg):
        self.contentModel.clear()

    @observable_method()
    @QtCore.pyqtSlot()
    def notifySaveAction(self, arg):
        pass

    @observable_method()
    @QtCore.pyqtSlot()
    def notifySaveAsAction(self, arg):
        pass

    @QtCore.pyqtSlot()
    def disableAction(self):
        selectedIndexes = self.ui.contentListView.selectedIndexes()
        self.notifyDisableAction([x.data() for x in selectedIndexes])

    @observable_method()
    def notifyDisableAction(self, selectedItems):
        pass

    @QtCore.pyqtSlot()
    def importAction(self):
        selectedIndexes = self.ui.contentListView.selectedIndexes()
        self.notifyImportAction([x.data() for x in selectedIndexes])

    @observable_method()
    def notifyImportAction(self, selectedItems):
        pass

    @QtCore.pyqtSlot()
    def contentListSelectAction(self):
        self.ui.statusbar.showMessage(f"{len(self.ui.contentListView.selectedIndexes())} entries selected")
    
    @QtCore.pyqtSlot()
    def exportAction(self):
        selectedIndexes = self.ui.contentListView.selectedIndexes()
        self.notifyExportAction([x.data() for x in selectedIndexes])
    
    @observable_method()
    def notifyExportAction(self, selectedItems):
        pass

    @observable_method()
    def notifyGoBackAction(self, arg):
        pass