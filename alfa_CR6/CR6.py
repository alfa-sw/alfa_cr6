#!/usr/bin/python3
import sys
import os
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QDialog, QMainWindow, QPushButton
from PyQt5 import QtWidgets, uic
from PyQt5.Qt import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import QApplication, QPushButton

PATH=os.path.dirname(os.path.abspath(__file__))

class Window(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        loadUi(PATH+"/ui/mainwindow.ui", self)
        self.frame.setStyleSheet("background-image: url('"+PATH+"/ui/machine.jpg'); background-repeat: no-repeat; background-position: center;")
        self.dialog_1_Btn.clicked.connect(self.onDialog1BtnClicked)
        self.chrome_Btn.clicked.connect(self.onChromeBtnClicked)


    def onDialog1BtnClicked(self):
        dlg = Dialog1(self)
        dlg.exec()

    def onChromeBtnClicked(self):
        dlg = ChromeDialog(self)
        dlg.exec()


class Dialog1(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(PATH+"/ui/dialog.ui", self)

class ChromeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(PATH+"/ui/chrome.ui", self)
        view = QWebEngineView(self)
        view.setUrl(QUrl("http://www.google.com"))
        view.resize(1024, 650)
        view.show()

class Cr6():
#if __name__ == "__main__":
    def __init__(self, parent=None):
        app = QApplication(sys.argv)
        win = Window()
        win.show()

        sys.exit(app.exec())


