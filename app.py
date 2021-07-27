import handlers.MainHandler as mh
import core.utils as ut
import os, sys
from PyQt5 import QtWidgets

if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    mh.MainHandler()
    sys.exit(app.exec_())