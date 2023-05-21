import handlers.MainHandler as mh
import sys
from PyQt5 import QtWidgets
from colorama import init as colorama_init
import core.common as cm

if __name__ == "__main__":
    colorama_init()
    cm.main_handler = mh.MainHandler()
    app = QtWidgets.QApplication([])
    cm.main_handler.init()
    sys.exit(app.exec_())