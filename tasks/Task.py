import time
from PyQt5.QtCore import QObject, pyqtSignal

class Task(QObject):
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(str)
    finish_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.current_progress = 0

    def send_progress(self, end):
        i = self.current_progress
        while i <= end:
            self.progress_signal.emit(i)
            time.sleep(0.01)
            i += 1
        self.current_progress = end