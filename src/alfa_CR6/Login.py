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
from MainWindow import MainWindow

class Login(QMainWindow):
    switch_window = QtCore.pyqtSignal()
    path=None

    def __init__(self, path, parent=None):
        super().__init__(parent)
        loadUi(path+"/ui/login.ui", self)
        self.path=path
        self.login_btn.clicked.connect(self.onLoginBtnClicked)


    def onLoginBtnClicked(self):
        msg = QMessageBox()
        if self.user_edit.text() == '' and self.pass_edit.text() == '':
            self.user_edit.clear()
            self.pass_edit.clear()
            window = MainWindow(self.path)
            form = window
            window.show()
            self.switch_window.emit()

        else:
            msg.setText('Incorrect Password')
            msg.exec_()
