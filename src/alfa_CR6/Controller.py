from PyQt5.QtWidgets import QApplication, QDialog, QMainWindow, QPushButton
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.Qt import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QMessageBox
from PyQt5 import QtGui
from PyQt5.QtGui import QPixmap
from MainWindow import MainWindow
from Login import Login

class Controller:
    path=None

    def __init__(self, path):
        self.path=path

    def show_login(self):
        self.login = Login(self.path)
        self.login.switch_window.connect(self.show_main)
        self.login.show()

    def show_main(self):
        self.window = MainWindow(self.path)
        self.window.show()
