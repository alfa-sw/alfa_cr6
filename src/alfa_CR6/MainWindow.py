# This Python file uses the following encoding: utf-8
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QMainWindow
from PyQt5.uic import loadUi
from alfa_CR6.chromewidget import ChromeWidget


class MainWindow(QMainWindow):
    browser=False
    view=None
    path=None

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path=path
        loadUi(path+"/ui/mainwindow.ui", self)
        self.dialog_1_btn.clicked.connect(self.onDialog1BtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.bar1.mousePressEvent=self.onBar1Pressed
        self.tabs.setCurrentIndex(0)
        self.bottom_tab.setCurrentIndex(1)

    def onBar1Pressed(self, other):
        self.tabs.setCurrentIndex(2)
        self.bottom_tab.setCurrentIndex(0)
        if self.browser:
            self.mainlayout.removeWidget(self.view)
            self.browser=False


    def onDialog1BtnClicked(self, other):
        self.tabs.setCurrentIndex(0)
        self.bottom_tab.setCurrentIndex(1)
        if self.browser:
            self.mainlayout.removeWidget(self.view)
            self.browser=False


    def onChromeBtnClicked(self):
        if self.browser:
            self.browser=False
            self.tabs.setCurrentIndex(0)
            self.bottom_tab.setCurrentIndex(1)
            self.mainlayout.removeWidget(self.view)
        else:
            self.browser=True
            self.view = ChromeWidget(self.path)
            self.mainlayout.addWidget(self.view)
            self.tabs.setCurrentIndex(1)
            self.bottom_tab.setCurrentIndex(0)
