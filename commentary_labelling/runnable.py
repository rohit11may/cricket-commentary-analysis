from PyQt5.QtCore import QThread


class ProcessRunnable(QThread):
    def __init__(self, target, args):
        QThread.__init__(self)
        self.t = target
        self.args = args

    def run(self):
        self.t(*self.args)

