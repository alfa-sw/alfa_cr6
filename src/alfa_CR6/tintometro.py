# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

from PyQt5.QtCore import *
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QApplication, QScrollArea, QVBoxLayout
from PyQt5.uic import loadUi
from alfa_CR6.chrome_widget import ChromeWidget
from alfa_CR6.definitions import BUTTONS
from alfa_CR6.machine_status_0 import FILE_JSON

class Tintometro(QWidget):
    browser=False
    view=None
    path=None

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/tintometro.ui", self)
        self.home_btn.clicked.connect(self.onHomeBtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.tabs.setCurrentIndex(0)
        self.bottom_tab.setCurrentIndex(1)

        self.STEP_2.mousePressEvent=lambda event:  self.onStepPressed(1)

    def onStepPressed(self, number):
        self.tabs.setCurrentIndex(2)
        self.bottom_tab.setCurrentIndex(0)

        self.widgetAction = QWidget()
        self.widgetStatus = QWidget()
        self.vboxStatus = QVBoxLayout()
        self.vboxAction = QVBoxLayout()
        self.vboxAction.setAlignment(Qt.AlignTop)

        for button in BUTTONS[number]['commands']:
                btn = QPushButton(button["nome"])
                self.vboxAction.addWidget(btn)

        # ~ TODO: 1. handle the machine:status of the six heads
        # ~ TODO: 2. this approach considers the status as a static thing, but 
        # ~          the status have to be dynamically refreshed, so we must 
        # ~          change it, e.g. having the 6 persistent viewboxes created at start time 
        # ~          and and always refreshing the view, for the ones that are are visible
        # ~ get the machine:status of the first head
        machine_status = QApplication.instance().head_status_dict.get(0, {})

        for key, value in machine_status.items():
                self.vboxStatus.addWidget(QLabel(key + ' : ' + str(value)))

        self.widgetAction.setLayout(self.vboxAction)
        self.scrollAreaAction.setWidgetResizable(True)
        self.scrollAreaAction.setWidget(self.widgetAction)

        self.widgetStatus.setLayout(self.vboxStatus)
        self.scrollAreaStatus.setWidgetResizable(True)
        self.scrollAreaStatus.setWidget(self.widgetStatus)

        if self.browser:
            self.mainlayout.removeWidget(self.view)
            self.browser=False


    def onHomeBtnClicked(self, other):
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
