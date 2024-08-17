from PySide6.QtWidgets import (QMainWindow, QLabel, QWidget, QGridLayout,
                               QComboBox, QPushButton, QDialog, QLineEdit, QDialogButtonBox, QColorDialog, QToolBar,
                               QStatusBar, QTabWidget, QMessageBox)
from PySide6.QtCore import QSize, QTimer, Qt, QThread
from PySide6.QtGui import QFont, QIcon, QIntValidator, QColor, QPainter, QAction
from PySide6.QtCharts import QChart, QLineSeries, QChartView, QValueAxis

import serial.tools.list_ports
import configparser
import serial.tools.list_ports

config = configparser.ConfigParser()
config.read('config.ini')

# Global variable
numBlock = int(config.get('Display', 'numBlock'))
numBlockChanged = False
maxDataNum = int(config.get('Data', 'maxData'))
minDataNum = int(config.get('Data', 'minData'))
timeInterval = int(config.get('Data', 'timeinterval'))
timeIntervalChanged = False
xAxisLength = int(config.get('Graph', 'xAxisLength'))
xCount = 0
language = config.get('General', 'language')
firstRead = True
startReading = False
currentSerial = serial.Serial()
serialReadingThreadRunning = False

nameList = []
portList = []
colorData = [[255, 255, 255] for _ in range(numBlock)]
totalData = [(maxDataNum + minDataNum) // 2 for _ in range(numBlock)]
languageList = [['English', 'en'], ['简体中文', 'zh_CN']]
startColor = list(map(int, config.get('Color', 'startColor').split()))
endColor = list(map(int, config.get('Color', 'endColor').split()))
intervalColor = list(map(int, config.get('Color', 'intervalColor').split()))


def getPortList():
    global portList, nameList
    portList = list(serial.tools.list_ports.comports())
    nameList = []

    for i in range(len(portList)):
        nameList.append(str(portList[i]))
        portList[i] = str(portList[i]).split(' - ')[0]


def getColor(num):
    if num > maxDataNum:
        num = maxDataNum
    elif num < minDataNum:
        num = minDataNum

    middle = (maxDataNum + minDataNum) / 2
    if num < middle:
        interval = (num - minDataNum) / (middle - minDataNum)
        return interpolateColor(startColor, intervalColor, interval)
    elif num > middle:
        interval = (num - middle) / (maxDataNum - middle)
        return interpolateColor(intervalColor, endColor, interval)
    else:
        return intervalColor


def interpolateColor(start, end, interval):
    r = int(start[0] * (1 - interval) + end[0] * interval)
    g = int(start[1] * (1 - interval) + end[1] * interval)
    b = int(start[2] * (1 - interval) + end[2] * interval)
    return [r, g, b]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Variables
        self.currentSerialIndex = -1

        # Window
        self.setWindowTitle(self.tr('Show color'))
        self.resize(QSize(400, 450))

        # Thread
        self.serialReadingThread = SerialReadingThread(self)

        # Timer
        self.timer = QTimer()
        self.timer.setInterval(timeInterval)

        # Widgets
        self.labels = [ColorLabel(_) for _ in range(numBlock)]

        self.errorMessage = QMessageBox()

        # Toolbar
        self.toolbar = QToolBar()
        self.toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(self.toolbar)
        self.setStatusBar(QStatusBar(self))

        self.startButtonAction = QAction(QIcon('img/start.svg'), self.tr('Start'), self)
        self.startButtonAction.setStatusTip(self.tr('Start reading'))
        self.startButtonAction.triggered.connect(self.startButtonActionTriggered)
        self.toolbar.addAction(self.startButtonAction)

        self.toolbar.addSeparator()

        self.serialChooser = QComboBox()
        self.serialChooser.setStatusTip(self.tr('Choose serial'))
        self.toolbar.addWidget(self.serialChooser)

        self.toolbar.addSeparator()

        self.refreshButtonAction = QAction(QIcon('img/refresh.svg'), self.tr('Refresh'), self)
        self.refreshButtonAction.setStatusTip(self.tr('Refresh'))
        self.refreshButtonAction.triggered.connect(self.refresh)
        self.toolbar.addAction(self.refreshButtonAction)

        self.settingButtonAction = QAction(QIcon('img/setting.svg'), self.tr('Setting'), self)
        self.settingButtonAction.setStatusTip(self.tr('Setting'))
        self.settingButtonAction.triggered.connect(self.settingButtonClicked)
        self.toolbar.addAction(self.settingButtonAction)

        # Layouts
        self.labelLayout = QGridLayout()
        self.totalLayout = QGridLayout()

        for _ in range(numBlock):
            self.labels[_].setText('255')
            self.labels[_].setFont(QFont("Arial", 10))
            self.labels[_].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.labels[_].setStyleSheet(
                f"background-color: rgb({colorData[_][0]}, {colorData[_][1]}, {colorData[_][2]});")
            self.labelLayout.addWidget(self.labels[_], _ // int(numBlock ** 0.5), _ % int(numBlock ** 0.5))

        self.totalLayout.addLayout(self.labelLayout, 0, 0)

        centralWidget = QWidget()
        centralWidget.setLayout(self.totalLayout)
        self.setCentralWidget(centralWidget)

        self.timer.timeout.connect(self.changeColor)
        self.timer.start()
        self.setNameList()

    def getCurrentSerialIndex(self):
        return self.currentSerialIndex

    def setNameList(self):
        global nameList
        getPortList()
        self.serialChooser.clear()
        self.serialChooser.addItems(nameList)
        self.serialChooser.adjustSize()
        self.serialChooser.setCurrentIndex(-1)
        self.serialChooser.currentIndexChanged.connect(self.serialIndexChanged)

    def settingButtonClicked(self):
        global numBlockChanged, timeIntervalChanged
        settingDialog = SettingDialog(self)
        settingDialog.exec()
        if numBlockChanged:
            self.updateLabels()
            numBlockChanged = False
        if timeIntervalChanged:
            self.timer.setInterval(timeInterval)
            timeIntervalChanged = False

    def startButtonActionTriggered(self):
        global startReading, firstRead
        try:
            if not startReading:
                self.startRunning()
            else:
                self.stopRunning()
        except BaseException as e:
            self.stopRunning()
            self.refresh()
            self.errorMessage.warning(self, self.tr('Error'), f'startButtonActionTriggered:\n{str(e)}')

    def refresh(self):
        self.serialChooser.currentIndexChanged.disconnect(self.serialIndexChanged)
        self.setNameList()

    def serialIndexChanged(self, index):
        global currentSerial
        try:
            if currentSerial:
                currentSerial.close()
                print(f'{nameList[self.currentSerialIndex]} is closed.')
            self.currentSerialIndex = index
            if self.currentSerialIndex != -1:
                currentSerial = serial.Serial(portList[self.currentSerialIndex], 115200)
                print(f'{nameList[self.currentSerialIndex]} is opened.')
                currentSerial.close()
        except BaseException as e:
            self.stopRunning()
            self.refresh()
            self.errorMessage.warning(self, self.tr('Error'), f'serialIndexChanged:\n{str(e)}')

    def startRunning(self):
        global startReading, currentSerial
        startReading = True
        self.startButtonAction.setIcon(QIcon('img/stop.svg'))
        self.startButtonAction.setStatusTip(self.tr('Stop reading'))
        self.startButtonAction.setText(self.tr('Stop'))
        if currentSerial is not None:
            if not currentSerial.is_open:
                currentSerial.open()

    def stopRunning(self):
        global startReading, firstRead, currentSerial, serialReadingThreadRunning
        startReading = False
        serialReadingThreadRunning = False
        self.serialReadingThread.wait()
        self.startButtonAction.setIcon(QIcon('img/start.svg'))
        self.startButtonAction.setStatusTip(self.tr('Start reading'))
        self.startButtonAction.setText(self.tr('Start'))
        if currentSerial:
            if currentSerial.is_open:
                currentSerial.close()
                firstRead = True

    def updateLabels(self):
        global colorData, totalData
        for _ in range(len(self.labels)):
            self.labels[_].deleteLater()
        self.labels = [ColorLabel(_) for _ in range(numBlock)]
        colorData = [[255, 255, 255] for _ in range(numBlock)]
        totalData = [(maxDataNum + minDataNum) // 2 for _ in range(numBlock)]
        self.labelLayout = QGridLayout()

        for _ in range(numBlock):
            self.labels[_].setText('255')
            self.labels[_].setFont(QFont("Arial", 10))
            self.labels[_].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.labels[_].setStyleSheet(
                f"background-color: rgb({colorData[_][0]}, {colorData[_][1]}, {colorData[_][2]});")
            self.labelLayout.addWidget(self.labels[_], _ // int(numBlock ** 0.5), _ % int(numBlock ** 0.5))

        self.totalLayout.removeItem(self.labelLayout)
        self.totalLayout.addLayout(self.labelLayout, 0, 0)

    def showErrorMessage(self, message):
        self.errorMessage.warning(self, self.tr('Error'), message)

    def changeColor(self):
        # if self.currentSerial:
        #     # print(self.currentSerial.is_open)
        #     if self.currentSerial.is_open:
        #         currentData = self.currentSerial.readline()
        #         if currentData:
        #             currentArr = currentData.decode('utf-8').split()
        #             for _ in range(numBlock):
        #                 currentNum = float(currentArr[_ * 2 + 1])
        #                 self.labels[_].setText(str(currentNum))
        #                 data[_] = getColor(currentNum)
        #                 self.labels[_].setStyleSheet(
        #                     f"background-color: rgb({data[_][0]}, {data[_][1]}, {data[_][2]});")
        global firstRead, startReading, currentSerial, serialReadingThreadRunning
        if startReading:
            try:
                if currentSerial is not None:
                    if currentSerial.is_open:
                        if not serialReadingThreadRunning:
                            self.serialReadingThread.start()
                        # while firstRead:
                        #     currentData = currentSerial.readline()
                        #     if currentData == b'----------------------------------------------------------\n':
                        #         firstRead = False
                        # totalData = []
                        # for _ in range(int(numBlock ** 0.5) + 1):
                        #     currentData = currentSerial.readline()
                        #     while currentData == b'\n':
                        #         currentData = currentSerial.readline()
                        #     if _ < int(numBlock ** 0.5):
                        #         currentArr = currentData.decode('utf-8').split()
                        #         for i in currentArr:
                        #             totalData.append(float(i))

                            for _ in range(numBlock):
                                currentNum = totalData[_]
                                self.labels[_].setText(str(currentNum))
                                colorData[_] = getColor(currentNum)
                                self.labels[_].setStyleSheet(
                                    f"background-color: rgb({colorData[_][0]}, {colorData[_][1]}, {colorData[_][2]});")
            except BaseException as e:
                self.stopRunning()
                self.refresh()
                self.errorMessage.warning(self, self.tr('Error'), f'changeColor:\n{str(e)}')

    def closeEvent(self, event):
        global currentSerial
        config.set('Data', 'maxData', str(maxDataNum))
        config.set('Data', 'minData', str(minDataNum))
        config.set('Data', 'timeinterval', str(timeInterval))
        config.set('Display', 'numBlock', str(numBlock))
        config.set('Color', 'startColor', ' '.join([str(i) for i in startColor]))
        config.set('Color', 'endColor', ' '.join([str(i) for i in endColor]))
        config.set('Color', 'intervalColor', ' '.join([str(i) for i in intervalColor]))
        config.set('Graph', 'xAxisLength', str(xAxisLength))
        config.set('General', 'language', language)

        with open('config.ini', 'w') as f:
            config.write(f)

        self.serialReadingThread.wait()

        if currentSerial:
            currentSerial.close()
            print(f'{nameList[self.currentSerialIndex]} is closed.')
        event.accept()


class SerialReadingThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        global firstRead, startReading, currentSerial, totalData, serialReadingThreadRunning
        try:
            serialReadingThreadRunning = True
            while firstRead:
                currentData = currentSerial.readline()
                if currentData == b'----------------------------------------------------------\n':
                    firstRead = False
            currentTotalData = []
            for _ in range(int(numBlock ** 0.5) + 1):
                currentData = currentSerial.readline()
                while currentData == b'\n' or currentData == b'':
                    currentData = currentSerial.readline()
                if _ < int(numBlock ** 0.5):
                    currentArr = currentData.decode('utf-8').split()
                    for i in currentArr:
                        currentTotalData.append(float(i))
            totalData = currentTotalData
            serialReadingThreadRunning = False
        except BaseException as e:
            self.parent().stopRunning()
            # self.parent().refresh()
            print(f'SerialReadingThread error:\n{str(e)}')





class ColorLabel(QLabel):
    def __init__(self, index):
        super().__init__()
        self.index = index
        self.lineChart = LineChart(self.index)
        self.chartView = QChartView(self.lineChart)
        self.chartView.setRenderHint(QPainter.RenderHint.Antialiasing)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # print('left', self.index)
            self.lineChart.reset()
            self.chartView.show()

    def setText(self, arg__1):
        super().setText(arg__1)
        if self.lineChart.isActive():
            self.lineChart.dataUpdate(arg__1)


class SettingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.resize(QSize(350, 200))
        self.currentStartColor = startColor
        self.currentEndColor = endColor
        self.currentIntervalColor = intervalColor
        self.currentLanguage = language
        self.currentLanguageIndex = -1

        self.setWindowTitle(self.tr('Setting'))

        self.currentPage = 0

        self.buttonLayout = QGridLayout()
        self.totalLayout = QGridLayout()

        # Tab widget
        self.tabWidget = QTabWidget()
        self.totalLayout.addWidget(self.tabWidget, 0, 0)

        # From
        self.dataFrom = QWidget()
        self.dataFormLayout = QGridLayout(self.dataFrom)

        self.thresholdLabel = QLabel(self.tr('Set data threshold'))
        self.thresholdLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.maxNumLabel = QLabel(self.tr('Max:'))
        self.maxNumLineEdit = QLineEdit(str(maxDataNum))
        self.maxNumLineEdit.setValidator(QIntValidator())

        self.minNumLabel = QLabel(self.tr('Min:'))
        self.minNumLineEdit = QLineEdit(str(minDataNum))
        self.minNumLineEdit.setValidator(QIntValidator())

        self.timeIntervalLabel = QLabel(self.tr('Time interval(ms):'))
        self.timeIntervalLineEdit = QLineEdit(str(timeInterval))
        self.timeIntervalLineEdit.setValidator(QIntValidator())

        self.dataFormLayout.addWidget(self.thresholdLabel, 0, 0, 1, 2)
        self.dataFormLayout.addWidget(self.maxNumLabel, 1, 0)
        self.dataFormLayout.addWidget(self.maxNumLineEdit, 1, 1)
        self.dataFormLayout.addWidget(self.minNumLabel, 2, 0)
        self.dataFormLayout.addWidget(self.minNumLineEdit, 2, 1)
        self.dataFormLayout.addWidget(self.timeIntervalLabel, 3, 0)
        self.dataFormLayout.addWidget(self.timeIntervalLineEdit, 3, 1)
        self.tabWidget.addTab(self.dataFrom, self.tr('Data'))

        self.displayForm = QWidget()
        self.displayFormLayout = QGridLayout(self.displayForm)
        self.setNumberOfBlocksLabel = QLabel(self.tr('Number of blocks:'))
        self.setNumberOfBlocksLineEdit = QLineEdit(str(numBlock))
        self.setNumberOfBlocksLineEdit.setValidator(QIntValidator())

        self.displayFormLayout.addWidget(self.setNumberOfBlocksLabel, 0, 0)
        self.displayFormLayout.addWidget(self.setNumberOfBlocksLineEdit, 0, 1)
        self.tabWidget.addTab(self.displayForm, self.tr('Display'))

        self.colorForm = QWidget()
        self.colorFormLayout = QGridLayout(self.colorForm)

        self.colorChangeLabel = QLabel(self.tr('Color change'))
        self.colorChangeLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.startColorLabel = QLabel(self.tr('Start color'))
        self.endColorLabel = QLabel(self.tr('End color'))
        self.intervalColorLabel = QLabel(self.tr('Interval color'))

        self.startColorChangeButton = QPushButton(self.tr('Change'))
        self.startColorChangeButton.clicked.connect(self.startColorDialog)
        self.endColorChangeButton = QPushButton(self.tr('Change'))
        self.endColorChangeButton.clicked.connect(self.endColorDialog)
        self.intervalColorChangeButton = QPushButton(self.tr('Change'))
        self.intervalColorChangeButton.clicked.connect(self.intervalColorDialog)

        self.startColorDemonstration = QLabel()
        self.startColorDemonstration.setStyleSheet(
            f"background-color: rgb({startColor[0]}, {startColor[1]}, {startColor[2]});")
        self.endColorDemonstration = QLabel()
        self.endColorDemonstration.setStyleSheet(
            f"background-color: rgb({endColor[0]}, {endColor[1]}, {endColor[2]});")
        self.intervalColorDemonstration = QLabel()
        self.intervalColorDemonstration.setStyleSheet(
            f"background-color: rgb({intervalColor[0]}, {intervalColor[1]}, {intervalColor[2]});")

        self.colorDialog = QColorDialog()

        self.colorFormLayout.addWidget(self.colorChangeLabel, 0, 0, 1, 3)
        self.colorFormLayout.addWidget(self.startColorLabel, 1, 0)
        self.colorFormLayout.addWidget(self.startColorDemonstration, 1, 1)
        self.colorFormLayout.addWidget(self.startColorChangeButton, 1, 2)
        self.colorFormLayout.addWidget(self.endColorLabel, 2, 0)
        self.colorFormLayout.addWidget(self.endColorDemonstration, 2, 1)
        self.colorFormLayout.addWidget(self.endColorChangeButton, 2, 2)
        self.colorFormLayout.addWidget(self.intervalColorLabel, 3, 0)
        self.colorFormLayout.addWidget(self.intervalColorDemonstration, 3, 1)
        self.colorFormLayout.addWidget(self.intervalColorChangeButton, 3, 2)
        self.tabWidget.addTab(self.colorForm, self.tr('Color'))

        self.graphForm = QWidget()
        self.graphFormLayout = QGridLayout(self.graphForm)

        self.xAxisLengthLabel = QLabel(self.tr('Maximum X-axis length:'))
        self.setXAxisLengthLineEdit = QLineEdit(str(xAxisLength))
        self.setXAxisLengthLineEdit.setValidator(QIntValidator())

        self.graphFormLayout.addWidget(self.xAxisLengthLabel, 0, 0)
        self.graphFormLayout.addWidget(self.setXAxisLengthLineEdit, 0, 1)
        self.tabWidget.addTab(self.graphForm, self.tr('Graph'))

        self.generalForm = QWidget()
        self.generalFormLayout = QGridLayout(self.generalForm)

        self.languageLabel = QLabel(self.tr('Language'))
        self.languageComboBox = QComboBox()
        for _ in range(len(languageList)):
            self.languageComboBox.addItem(languageList[_][0], languageList[_][1])
            if language == languageList[_][1]:
                self.currentLanguageIndex = _
        self.languageComboBox.setCurrentIndex(self.currentLanguageIndex)
        self.languageComboBox.currentIndexChanged.connect(self.changeLanguage)

        self.generalFormLayout.addWidget(self.languageLabel, 0, 0)
        self.generalFormLayout.addWidget(self.languageComboBox, 0, 1)
        self.generalFormLayout.addWidget(QLabel(self.tr('Restart to change language')), 1, 0)
        self.tabWidget.addTab(self.generalForm, self.tr('General'))

        self.checkButtonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                               QDialogButtonBox.StandardButton.Cancel)
        self.checkButtonBox.accepted.connect(self.saveValues)
        self.checkButtonBox.accepted.connect(self.accept)
        self.checkButtonBox.rejected.connect(self.reject)

        self.totalLayout.addWidget(self.checkButtonBox, 1, 0)

        self.setLayout(self.totalLayout)

    def changeLanguage(self):
        self.currentLanguage = self.languageComboBox.currentData()

    def saveValues(self):
        global maxDataNum, minDataNum, startColor, endColor, intervalColor, xAxisLength, numBlock, numBlockChanged, \
            timeInterval, timeIntervalChanged, language
        maxDataNum = int(self.maxNumLineEdit.text())
        minDataNum = int(self.minNumLineEdit.text())
        xAxisLength = int(self.setXAxisLengthLineEdit.text())
        startColor = self.currentStartColor
        endColor = self.currentEndColor
        intervalColor = self.currentIntervalColor
        numBlock = int(self.setNumberOfBlocksLineEdit.text())
        numBlockChanged = True
        timeInterval = int(self.timeIntervalLineEdit.text())
        timeIntervalChanged = True
        language = self.currentLanguage
        print(f'Values saved.\nMax: {maxDataNum}, Min: {minDataNum}\n'
              f'Start color: {startColor}, End color: {endColor}, Interval color: {intervalColor}\n'
              f'Maximum x-axis length: {xAxisLength}\n'
              f'Number of blocks: {numBlock}\n'
              f'Time interval: {timeInterval}\n'
              f'Language: {language}')

    def startColorDialog(self):
        global startColor
        currentColor = self.colorDialog.getColor(QColor(startColor[0], startColor[1], startColor[2]))
        if currentColor.isValid():
            self.currentStartColor = [currentColor.red(), currentColor.green(), currentColor.blue()]
            self.startColorDemonstration.setStyleSheet(
                f"background-color: "
                f"rgb({self.currentStartColor[0]}, {self.currentStartColor[1]}, {self.currentStartColor[2]});")

    def endColorDialog(self):
        global endColor
        currentColor = self.colorDialog.getColor(QColor(endColor[0], endColor[1], endColor[2]))
        if currentColor.isValid():
            self.currentEndColor = [currentColor.red(), currentColor.green(), currentColor.blue()]
            self.endColorDemonstration.setStyleSheet(
                f"background-color: "
                f"rgb({self.currentEndColor[0]}, {self.currentEndColor[1]}, {self.currentEndColor[2]});")

    def intervalColorDialog(self):
        global intervalColor
        currentColor = self.colorDialog.getColor(QColor(intervalColor[0], intervalColor[1], intervalColor[2]))
        if currentColor.isValid():
            self.currentIntervalColor = [currentColor.red(), currentColor.green(), currentColor.blue()]
            self.intervalColorDemonstration.setStyleSheet(
                f"background-color: "
                f"rgb({self.currentIntervalColor[0]}, {self.currentIntervalColor[1]}, {self.currentIntervalColor[2]});")


class LineChart(QChart):
    def __init__(self, index):
        super().__init__()

        global xCount

        xCount = 0
        self.totalData = []
        self.currentMinAxisX = 0

        self.resize(QSize(600, 400))
        self.legend().hide()
        self.setTitle(self.tr(
            f'Label row {str(index // int(numBlock ** 0.5), )} column {str(index % int(numBlock ** 0.5))}'))

        self.series = QLineSeries()
        self.addSeries(self.series)

        self.axisX = QValueAxis()
        self.axisX.setMin(self.currentMinAxisX)
        self.axisX.setMax(1)

        self.axisY = QValueAxis()
        self.axisY.setMin(0)
        self.axisY.setMax(0)

        self.addAxis(self.axisX, Qt.AlignmentFlag.AlignBottom)
        self.addAxis(self.axisY, Qt.AlignmentFlag.AlignLeft)

        self.series.attachAxis(self.axisX)
        self.series.attachAxis(self.axisY)

    def dataUpdate(self, num):
        global xAxisLength, xCount
        if len(self.totalData) > xAxisLength:
            self.totalData.pop(0)
            self.series.remove(0)
            self.currentMinAxisX += 1
            self.axisX.setMin(self.currentMinAxisX)
        self.totalData.append(float(num))
        self.series.append(float(xCount), float(num))
        minY = min(self.totalData)
        maxY = max(self.totalData)
        self.axisY.setMin(minY - 1)
        self.axisY.setMax(maxY + 1)
        self.axisX.setMax(xCount)
        xCount += 1

    def reset(self):
        global xCount
        xCount = 0
        self.totalData.clear()
        self.series.clear()
        self.axisX.setMax(1)
        self.axisY.setMin(0)
        self.axisY.setMax(0)
