import sys

import UI
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator
from PySide6.QtGui import QIcon
import configparser

if __name__ == '__main__':
    # portList = list(serial.tools.list_ports.comports())
    # nameList = []
    #
    # for i in range(len(portList)):
    #     nameList.append(str(portList[i]))
    #     portList[i] = str(portList[i]).split(' - ')[0]
    #
    # UI.portList = portList
    config = configparser.ConfigParser()
    config.read('config.ini')
    language = config.get('General', 'language')

    UI.data = [[255, 255, 255] for _ in range(UI.numBlock)]

    app = QApplication(sys.argv)

    translator = QTranslator()
    translator.load(f'language/{language}.qm')
    app.installTranslator(translator)

    app.setWindowIcon(QIcon('img/icon.png'))

    window = UI.MainWindow()

    # window.setNameList(nameList)

    window.show()
    app.exec()
