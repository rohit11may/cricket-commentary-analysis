from PyQt5 import QtWidgets, uic
from PyQt5 import QtGui
from PyQt5.QtCore import *
import sys
import json

team_map = {'U.A.E.': 'UAE',
            'Namibia': 'NAM',
            'Australia': 'AUS',
            'Zimbabwe': 'ZIM',
            'New Zealand': 'NZ',
            'Kenya': 'KENYA',
            'Scotland': 'SCOT',
            'Canada': 'CAN',
            'Nepal': 'NEPAL',
            'West Indies': 'WI',
            'Bangladesh': 'BDESH',
            'Bermuda': 'BMUDA',
            'Pakistan': 'PAK',
            'Hong Kong': 'HKG',
            'Afghanistan': 'AFG',
            'England': 'ENG',
            'P.N.G.': 'PNG',
            'South Africa': 'SA',
            'U.S.A.': 'USA',
            'India': 'INDIA',
            'Sri Lanka': 'SL',
            'Ireland': 'IRE',
            'Netherlands': 'NL'}


class DataLoader(object):
    def __init__(self):
        with open('../matches.json', 'r') as f:
            self.matches = json.load(f)

        with open('../player_table.json', 'r') as f:
            self.players = json.load(f)

    def getPlayerOvers(self):
        pass


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('labeller.ui', self)  # Load the .ui file
        # self.bowler.setText("LEFT HAND BOWLER")
        # self.batsman.setText("LEFT HAND BOWLER")
        # self.batsman.setAlignment(Qt.AlignLeft)

        self.logArea = QtWidgets.QTextEdit()
        self.console.setWidget(self.logArea)
        self.data = DataLoader()
        self.log(list(self.data.matches.keys())[0])
        self.submit.clicked.connect(self.save)
        self.show()  # Show the GUI

    def log(self, msg):
        self.logArea.append(msg)

    def save(self):
        pass

    def getChecked(self):
        for btn in self.pitchButtons.buttons():
            if btn.isChecked():
                return btn.objectName()


app = QtWidgets.QApplication(sys.argv)
window = Ui()
app.exec_()
