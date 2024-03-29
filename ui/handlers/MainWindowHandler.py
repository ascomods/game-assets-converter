from PyQt5 import QtCore
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QWidget
from ui.handlers.WindowHandler import WindowHandler
from ui.views.MainWindow import Ui_MainWindow
from observed import observable_method
import core.common as cm

class MainWindowHandler(WindowHandler, QWidget):
    toggleable_elements = [
        'minimize_btn',
        'exit_btn',
        'game_cmb_box',
        'platform_cmb_box',
        'import_btn',
        'export_btn'
    ]

    def load(self):
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self.window)
        self.init_ui()

        self.ui.game_cmb_box.currentIndexChanged.connect(self.game_select_action)
        self.ui.platform_cmb_box.currentIndexChanged.connect(self.platform_select_action)

        self.ui.import_btn.clicked.connect(self.notify_import_action)
        self.ui.export_btn.clicked.connect(self.notify_export_action)

        self.ui.blender_chk_box.clicked.connect(self.set_use_blender)
        self.ui.debug_chk_box.clicked.connect(self.set_use_debug_mode)
    
    def init_ui(self):
        super().init_ui()

        # game combo box
        for key, val in cm.games.items():
            self.ui.game_cmb_box.addItem(val)
        game_idx = list(cm.games.keys()).index(cm.selected_game)
        self.ui.game_cmb_box.setCurrentIndex(game_idx)

        # platform combo box
        for key, val in cm.platforms.items():
            self.ui.platform_cmb_box.addItem(val)
        platform_idx = list(cm.platforms.keys()).index(cm.selected_platform)
        self.ui.platform_cmb_box.setCurrentIndex(platform_idx)

        # checkboxes
        self.ui.blender_chk_box.setChecked(cm.use_blender)
        self.ui.debug_chk_box.setChecked(cm.use_debug_mode)
    
    @QtCore.pyqtSlot()
    def game_select_action(self):
        cm.selected_game = list(cm.games.keys())[self.ui.game_cmb_box.currentIndex()]
        cm.settings.setValue("Game", QUrl(cm.selected_game).toString())

    @QtCore.pyqtSlot()
    def platform_select_action(self):
        cm.selected_platform = list(cm.platforms.keys())[self.ui.platform_cmb_box.currentIndex()]
        cm.settings.setValue("Platform", QUrl(cm.selected_platform).toString())

    @observable_method()
    def notify_import_action(self, arg):
        pass

    @observable_method()
    def notify_export_action(self, arg):
        pass

    @QtCore.pyqtSlot()
    def set_use_blender(self):
        if cm.use_blender != None:
            cm.use_blender = not cm.use_blender
        else:
            cm.use_blender = False
        cm.settings.setValue("Blender", cm.use_blender)

    @QtCore.pyqtSlot()
    def set_use_debug_mode(self):
        if cm.use_debug_mode != None:
            cm.use_debug_mode = not cm.use_debug_mode
        else:
            cm.use_debug_mode = False
        cm.settings.setValue("Debug", cm.use_debug_mode)