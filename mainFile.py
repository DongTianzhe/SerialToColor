import sys

import UI
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTranslator
from PySide6.QtGui import QIcon
import configparser

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')
    language = config.get('General', 'language')

    app = QApplication(sys.argv)

    translator = QTranslator()
    translator.load(f'language/{language}.qm')
    app.installTranslator(translator)

    app.setWindowIcon(QIcon('img/icon.png'))

    window = UI.MainWindow()

    window.show()
    app.exec()
