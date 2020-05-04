class Logger(object):
    instance = None
    widget = None

    def __init__(self, w):
        Logger.widget = w
        pass

    @staticmethod
    def getInstance():
        if not Logger.instance:
            Logger.instance = Logger(Logger.widget)

        return Logger.instance

    def log(self, msg):
        self.widget.append(str(msg))

