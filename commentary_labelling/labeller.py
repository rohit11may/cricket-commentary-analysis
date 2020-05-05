import re
import sys

from PyQt5 import QtWidgets, QtCore, uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem

from commentary_labelling.Logger import Logger
from commentary_labelling.dataloader import DataLoader
from commentary_labelling.runnable import ProcessRunnable

logger = None
bowlerPattern = "^(?P<bowler>[\w \-'?]+) to (?P<batsman>[\w \-']+),(?P<desc>.*)"


class ViewTree(QtWidgets.QTreeWidget):
    def __init__(self, value):
        super().__init__()

        def fill_item(item, value):
            def new_item(parent, text, val=None):
                child = QtWidgets.QTreeWidgetItem([text])
                fill_item(child, val)
                parent.addChild(child)
                child.setExpanded(True)

            if value is None:
                return
            elif isinstance(value, dict):
                for key, val in sorted(value.items()):
                    new_item(item, str(key), val)
            elif isinstance(value, (list, tuple)):
                for val in value:
                    text = (str(val) if not isinstance(val, (dict, list, tuple))
                            else '[%s]' % type(val).__name__)
                    new_item(item, text, val)
            else:
                new_item(item, str(value))

        fill_item(self.invisibleRootItem(), value)


class TableModel(QtCore.QAbstractTableModel):
    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.DisplayRole:
            # See below for the nested-list data structure.
            # .row() indexes into the outer list,
            # .column() indexes into the sub-list
            return self._data[index.row()][index.column()]

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        # The following takes the first sub-list, and returns
        # the length (only works if all rows are an equal length)
        return len(self._data[0])


class Ui(QtWidgets.QMainWindow):
    def __init__(self):
        super(Ui, self).__init__()  # Call the inherited classes __init__ method
        uic.loadUi('labeller.ui', self)  # Load the .ui file
        # self.bowler.setText("LEFT HAND BOWLER")
        # self.batsman.setText("LEFT HAND BOWLER")
        # self.batsman.setAlignment(Qt.AlignLeft)

        self.logArea = QtWidgets.QTextEdit()
        self.console.setWidget(self.logArea)

        self.overModel = None
        self.overView.setModel(self.overModel)
        self.overView.selectionModel().selectionChanged.connect(self.selectedBallChanged)

        self.detailModel = None
        self.match_details.setModel(self.detailModel)

        self.progress.valueChanged.connect(self.sliderValueChanged)
        self.forwardMatch.clicked.connect(self.nextMatch)
        self.backMatch.clicked.connect(self.previousMatch)
        self.forwardBall.clicked.connect(self.nextBall)
        self.backBall.clicked.connect(self.previousBall)

        self.players.setColumnCount(4)
        self.players.setHeaderLabels(['name', 'batting_hand', 'bowling_hand', 'role'])
        self.player = None

        global logger
        logger = Logger(self.logArea)

        self.searchPlayer.clicked.connect(self.search)
        self.clear.clicked.connect(self.logArea.clear)
        self.clearSelection.clicked.connect(self.clearChecked)

        saveCheckedRunner = ProcessRunnable(target=self.saveChecked, args=())
        self.pitchButtons.buttonClicked.connect(lambda: saveCheckedRunner.start())

        self.overs = []
        self.completed_balls = set()
        self.current_match = None
        self.current_ball = None

        self.show()  # Show the GUI

    def saveChecked(self):
        if not self.overs:
            return

        m_id, inn, balls = self.overs[self.current_match]
        line, length = self.getChecked()
        print(f"save_checked {line}, {length}")
        if line is not None:
            DataLoader.storePitch(line, length, m_id, inn, balls[self.current_ball])
            self.completed_balls.add((m_id, inn, balls[self.current_ball]))
            self.completed.setText(str(len(self.completed_balls)))
        else:
            DataLoader.clearPitch(m_id, inn, balls[self.current_ball])

        if len(self.completed_balls) % 10 == 0:
            filename = self.player['known_as']
            logger.log(f"committing to {filename}")
            DataLoader.commit(filename)

    def setChecked(self, line, length):
        if 'OFF' not in self.line1.text():
            line = 4 - line

        name = f'btn{length}{line}'
        for btn in self.pitchButtons.buttons():
            if btn.objectName() == name:
                btn.toggle()
                break

    def getChecked(self):
        for btn in self.pitchButtons.buttons():
            if btn.isChecked():
                name = btn.objectName()
                length, line = int(name[3]), int(name[4])
                if 'OFF' not in self.line1.text():
                    line = 4 - line
                return line, length

        return None, None

    def clearChecked(self):
        if self.overs:
            m_id, inn, balls = self.overs[self.current_match]
            DataLoader.clearPitch(m_id, inn, balls[self.current_ball])
            self.completed_balls.discard((m_id, inn, balls[self.current_ball]))
            self.completed.setText(str(len(self.completed_balls)))

        self.pitchButtons.setExclusive(False)
        for btn in self.pitchButtons.buttons():
            btn.setChecked(False)
        self.pitchButtons.setExclusive(True)

    def nextMatch(self):
        self.current_match = min(len(self.overs) - 1, self.current_match + 1)
        self.showMatch()

    def previousMatch(self):
        self.current_match = max(0, self.current_match - 1)
        self.showMatch()

    def nextBall(self):
        if self.overs:
            self.current_ball = min(len(self.overs[self.current_match][2]) - 1, self.current_ball + 1)
            self.overView.selectRow(self.current_ball)
            self.showSelectedBall()

    def previousBall(self):
        self.current_ball = max(0, self.current_ball - 1)
        self.overView.selectRow(self.current_ball)
        self.showSelectedBall()

    def selectedBallChanged(self):
        indexes = self.overView.selectionModel().selectedRows()
        self.current_ball = indexes[0].row()
        self.showSelectedBall()

    def showSelectedBall(self):
        m_id, inn, balls = self.overs[self.current_match]
        ball = DataLoader.getBall(m_id, inn, balls[self.current_ball])
        match = re.match(bowlerPattern, ball['desc'])
        batsman_name = ""
        if ball['batsman_id'] != "":
            batsman_name = DataLoader.players[ball['batsman_id']]['known_as']

        self.ballView.setText(f"{ball['number']},"
                              f" {ball['batsman'] if not batsman_name else batsman_name}")
        self.ballView.append(f"{match.group('desc')}")
        self.setHandedness(ball['batsman_id'], isBowler=False)
        if len(ball['pitch']) > 0:
            self.setChecked(ball['pitch']['line'], ball['pitch']['length'])
        else:
            self.clearChecked()

    def setLines(self, rightHanded=True):
        line0 = self.line0.text()
        line1 = self.line1.text()
        if rightHanded and 'OFF' not in line0 or (not rightHanded and 'OFF' in line0):
            self.line0.setText(self.line4.text())
            self.line1.setText(self.line3.text())
            self.line4.setText(line0)
            self.line3.setText(line1)

    def setHandedness(self, player_id, isBowler=False):
        label = self.bowler if isBowler else self.batsman
        hand = DataLoader.getHandedness(player_id, isBowler).upper()
        label.setText(hand)
        if 'RIGHT' in hand:
            label.setAlignment(Qt.AlignRight)
            if not isBowler: self.setLines(True)
        elif 'LEFT' in hand:
            label.setAlignment(Qt.AlignLeft)
            if not isBowler: self.setLines(False)
        else:
            label.setAlignment(Qt.AlignCenter)

    def sliderValueChanged(self):
        self.current_match = self.progress.value()
        self.current_ball = 0
        self.showMatch()
        self.showSelectedBall()

    def showMatch(self):
        self.showOverview()
        self.showMatchDetails()
        self.showPlayerTree()

    def showPlayerTree(self):
        match_id, inn, balls = self.overs[self.current_match]
        players = DataLoader.getPlayers(match_id)
        self.players.clear()
        team1 = QTreeWidgetItem(['team1'])
        team2 = QTreeWidgetItem(['team2'])
        items = [team1, team2]
        for i, item in enumerate(items):
            for p in players[f'team{i + 1}']:
                item.addChild(
                    QTreeWidgetItem([p['known_as'], p['batting_hand'], p['bowling_hand'], p['player_primary_role']]))
        self.players.addTopLevelItem(team1)
        self.players.addTopLevelItem(team2)
        self.players.expandAll()

    def showMatchDetails(self):
        match_id, inn, balls = self.overs[self.current_match]
        details = DataLoader.getMatchDetails(match_id)
        self.detailModel = TableModel(details)
        self.match_details.setModel(self.detailModel)
        self.oversLeft.setText(f"{self.current_match + 1}/{len(self.overs)}")
        return match_id

    def showOverview(self):
        match_id, inn, balls = self.overs[self.current_match]
        data = []
        for ball in balls:
            b = DataLoader.getBall(match_id, inn, ball)
            match = re.match(bowlerPattern, b['desc'])
            data.append([b['number'], b['outcome'], match.group('desc')])
        self.overModel = TableModel(data)
        self.overView.setModel(self.overModel)
        self.overView.resizeColumnsToContents()
        self.overView.selectionModel().selectionChanged.connect(self.selectedBallChanged)

    def search(self):
        query = self.searchBox.text()
        self.overs = DataLoader.getAllPlayerOvers(query, self.openPlayerFile.isChecked())
        logger.log(f"Fetched {len(self.overs)} innings for {query}")

        self.player = DataLoader.getPlayerProfile(query)[0]
        self.setHandedness(self.player['player_id'], isBowler=True)

        self.progress.setMaximum(len(self.overs) - 1)
        self.current_match = 0
        self.current_ball = 0

        for m_id, inn, balls in self.overs:
            for b_idx in balls:
                thisBall = (m_id, inn, b_idx)
                ball = DataLoader.getBall(*thisBall)
                if len(ball['pitch']) > 0:
                    self.completed_balls.add(thisBall)

        self.completed.setText(str(len(self.completed_balls)))
        self.totalBalls.setText(f"/{sum(list(map(len, [x[2] for x in self.overs])))}")
        self.showMatch()


app = QtWidgets.QApplication(sys.argv)
window = Ui()
app.exec_()
