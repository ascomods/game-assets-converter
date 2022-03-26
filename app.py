import handlers.MainHandler as mh
import sys
from PyQt5 import QtWidgets

if __name__ == "__main__":
    main_handler = mh.MainHandler()
    app = QtWidgets.QApplication([])
    main_handler.init()
    sys.exit(app.exec_())