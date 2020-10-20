# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QApplication
from PyQt5.uic import loadUi
from alfa_CR6.chrome_widget import ChromeWidget
from alfa_CR6.definitions import BUTTONS

class MainWindow(QWidget):
    browser=False
    view=None
    path=None

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/mainwindow.ui", self)
        self.dialog_1_btn.clicked.connect(self.onDialog1BtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.tabs.setCurrentIndex(0)
        self.bottom_tab.setCurrentIndex(1)

        self.bar1.mousePressEvent=lambda event:  self.onBarPressed(1)
        self.bar2.mousePressEvent=lambda event:  self.onBarPressed(2)



    def onBarPressed(self, number):
        self.tabs.setCurrentIndex(2)
        self.bottom_tab.setCurrentIndex(0)
        for button in BUTTONS[number]['commands']:
            self.modal_commands.addWidget(QPushButton(button["nome"]))
        for button in BUTTONS[number]['visual']:
            self.modal_visual.addWidget(QLabel("roba dal json"))
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
            self.view = ChromeWidget(self)
            self.mainlayout.addWidget(self.view)
            self.tabs.setCurrentIndex(1)
            self.bottom_tab.setCurrentIndex(0)
