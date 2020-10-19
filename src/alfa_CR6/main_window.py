# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMainWindow   # pylint: disable=no-name-in-module
from PyQt5 import QtCore

from alfa_CR6.chrome_widget import ChromeWidget


class MainWindow(QMainWindow):
    switch_window = QtCore.pyqtSignal(str)
    browser = False

    def __init__(self):
        super().__init__(None)
        loadUi(QApplication.instance().ui_path + "/mainwindow.ui", self)
        self.dialog_1_btn.clicked.connect(self.onDialog1BtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.bar1.mousePressEvent = self.onDialog1BtnClicked
        self.tabs.setCurrentIndex(0)

    def onDialog1BtnClicked(self, other):
        dlg = Dialog1(self)
        dlg.exec()

    def onChromeBtnClicked(self):
        if self.browser:
            self.browser = False
            self.tabs.setCurrentIndex(0)
            self.mainlayout.removeWidget(self.view)
        else:
            self.browser = True
            self.view = ChromeWidget(self)
            self.mainlayout.addWidget(self.view)
            self.tabs.setCurrentIndex(1)
