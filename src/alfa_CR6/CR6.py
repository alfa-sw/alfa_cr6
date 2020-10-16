import sys
import os
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QDialog, QMainWindow, QPushButton
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.Qt import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QMessageBox
from PyQt5 import QtGui
from PyQt5.QtGui import QPixmap
from Controller import Controller
from Login import Login


PATH=os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = Controller(PATH)
    controller.show_login()
    sys.exit(app.exec_())
