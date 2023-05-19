import handlers.MainHandler as mh
import sys
from PyQt5 import QtWidgets
import core.common as cm

if __name__ == "__main__":
    cm.main_handler = mh.MainHandler()
    app = QtWidgets.QApplication([])
    cm.main_handler.init()
    sys.exit(app.exec_())