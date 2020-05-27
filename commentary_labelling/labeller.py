import re
import sys

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTreeWidgetItem

from commentary_labelling.Logger import Logger
from commentary_labelling.classifier import Classifier
from commentary_labelling.dataloader import DataLoader
from commentary_labelling.runnable import ProcessRunnable
from commentary_labelling.ui_utils import TableModel

logger = None
bowlerPattern = "^(?P<bowler>[\w \-'?]+) to (?P<batsman>[\w \-']+),(?P<desc>.*)"


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
        self.threshold.valueChanged.connect(self.thresholdValueChanged)
        self.forwardMatch.clicked.connect(self.nextMatch)
        self.backMatch.clicked.connect(self.previousMatch)

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
        self.commit.clicked.connect(self.commitToFile)

        self.classifyAll.clicked.connect(self.classifyBalls)
        self.current_threshold = 0

        # [(match id, innings, list of ball indices from that innings)]
        self.all_overs = []
        self.completed_balls = set()
        self.current_match = None
        self.current_ball = None

        self.show()  # Show the GUI

    def commitToFile(self):
        filename = f"{self.player['known_as']}{len(self.completed_balls)}"
        if self.filename.text():
            filename = self.filename.text()

        logger.log(f"committing to {filename}")
        DataLoader.commit(filename)

    def classifyBalls(self):
        if not self.all_overs:
            return

        for i, (m_id, inn, balls) in enumerate(self.all_overs):
            if i % 10 == 0:
                print(f"Done {i} matches!")

            for b_idx in balls:
                thisBall = (m_id, inn, b_idx)
                ballData = DataLoader.getBall(*thisBall)
                if len(ballData['pitch']) == 0:
                    classification = Classifier.classify(ballData['desc'])
                    if not classification:
                        continue
                    (line, line_conf), (length, length_conf) = classification
                    DataLoader.storePitch(line, length, m_id, inn, b_idx,
                                          line_conf=line_conf, length_conf=length_conf)
                    self.completed_balls.add(thisBall)

        self.completed.setText(str(len(self.completed_balls)))

    def saveChecked(self):
        if not self.all_overs:
            return

        m_id, inn, balls = self.all_overs[self.current_match]
        line, length = self.getChecked()
        # print(f"save_checked {line}, {length}")
        if line is not None:
            DataLoader.storePitch(line, length, m_id, inn, balls[self.current_ball])
            self.completed_balls.add((m_id, inn, balls[self.current_ball]))
            self.completed.setText(str(len(self.completed_balls)))
        else:
            DataLoader.clearPitch(m_id, inn, balls[self.current_ball])

        # if len(self.completed_balls) % 10 == 0:
        #     self.commitToFile()

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
        if self.all_overs:
            m_id, inn, balls = self.all_overs[self.current_match]
            DataLoader.clearPitch(m_id, inn, balls[self.current_ball])
            self.completed_balls.discard((m_id, inn, balls[self.current_ball]))
            self.completed.setText(str(len(self.completed_balls)))

        self.pitchButtons.setExclusive(False)
        for btn in self.pitchButtons.buttons():
            btn.setChecked(False)
        self.pitchButtons.setExclusive(True)

    def nextMatch(self):
        self.current_match = min(len(self.all_overs) - 1, self.current_match + 1)
        self.showMatch()

    def previousMatch(self):
        self.current_match = max(0, self.current_match - 1)
        self.showMatch()

    def selectedBallChanged(self):
        indexes = self.overView.selectionModel().selectedRows()
        self.current_ball = indexes[0].row()
        self.showSelectedBall()

    def showSelectedBall(self):
        m_id, inn, balls = self.all_overs[self.current_match]
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
            self.ballView.append(f"\nLength confidence: {ball['pitch']['length_conf']*100:.1f}")
            self.ballView.append(f"Line confidence: {ball['pitch']['line_conf']*100:.1f}")
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

    def thresholdValueChanged(self):
        self.current_threshold = self.threshold.value()
        self.thresholdLabel.setText(f"{self.current_threshold}%")

    def showMatch(self):
        self.showOverview()
        self.showMatchDetails()
        self.showPlayerTree()

    def showPlayerTree(self):
        match_id, inn, balls = self.all_overs[self.current_match]
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
        match_id, inn, balls = self.all_overs[self.current_match]
        details = DataLoader.getMatchDetails(match_id)
        self.detailModel = TableModel(details)
        self.match_details.setModel(self.detailModel)
        self.oversLeft.setText(f"{self.current_match + 1}/{len(self.all_overs)}")
        return match_id

    def showOverview(self):
        match_id, inn, balls = self.all_overs[self.current_match]
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
        self.all_overs = DataLoader.getAllPlayerOvers(query, self.openPlayerFile.isChecked())
        logger.log(f"Fetched {len(self.all_overs)} innings for {query}")

        self.player = DataLoader.getPlayerProfile(query)[0]
        self.setHandedness(self.player['player_id'], isBowler=True)

        self.progress.setMaximum(len(self.all_overs) - 1)
        self.current_match = 0
        self.current_ball = 0

        for m_id, inn, balls in self.all_overs:
            for b_idx in balls:
                thisBall = (m_id, inn, b_idx)
                ball = DataLoader.getBall(*thisBall)
                if len(ball['pitch']) > 0:
                    self.completed_balls.add(thisBall)

        self.completed.setText(str(len(self.completed_balls)))
        self.totalBalls.setText(f"/{sum(list(map(len, [x[2] for x in self.all_overs])))}")
        self.showMatch()


app = QtWidgets.QApplication(sys.argv)
window = Ui()
app.exec_()
