# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

from PyQt5.QtCore import *
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QApplication, QScrollArea, QVBoxLayout
from PyQt5.uic import loadUi
from alfa_CR6_ui.chrome_widget import ChromeWidget
import asyncio 
from time import sleep

class Sinottico(QWidget):
    browser=False
    view=None
    visual="none"

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/sinottico.ui", self)
        self.update_data()
        self.home_btn.clicked.connect(self.onHomeBtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.main_view_stack.setCurrentWidget(self.image_sinottico)

        self.rulliera_input.mousePressEvent = lambda event: self.rullieraInputPressed()
        loop = asyncio.get_event_loop()
        self.update=QTimer()
        self.update.timeout.connect(self.update_data)
        self.update.start(1000)

        #self.STEP_2.mousePressEvent=lambda event:  self.onStep2Pressed()

    def rullieraInputPressed(self):
        self.main_view_stack.setCurrentWidget(self.modal_rulliera_input)

    def update_data(self):
        for i in reversed(range(self.rulliera_input_data.count())):
            self.rulliera_input_data.itemAt(i).widget().setParent(None)
        machine_status = QApplication.instance().head_status_dict.get(0, {})
        for key, value in machine_status.items():
            self.alabel=QLabel(key + ' : ' + str(value))
            self.rulliera_input_data.addWidget(self.alabel)

    def onStep2Pressed(self):
        self.main_view_stack.setCurrentWidget(self.modal_STEP_2_HEAD_1)

        self.v_layout_action.setAlignment(Qt.AlignTop)

        # ~ TODO: 1. handle the machine:status of the six heads
        # ~ TODO: 2. this approach considers the status as a static thing, but
        # ~          the status have to be dynamically refreshed, so we must
        # ~          change it, e.g. having the 6 persistent viewboxes created at start time
        # ~          and and always refreshing the view, for the ones that are are visible
        # ~ get the machine:status of the first head
        machine_status = QApplication.instance().head_status_dict.get(0, {})

        for key, value in machine_status.items():
                self.v_layout_status.addWidget(QLabel(key + ' : ' + str(value)))




    def onHomeBtnClicked(self, other):
        self.main_view_stack.setCurrentWidget(self.image_sinottico)
        if self.browser:
            self.chrome_layout.removeWidget(self.view)
            self.browser=False


    def onChromeBtnClicked(self):
        if self.browser:
            self.browser=False
            self.main_view_stack.setCurrentWidget(self.image_sinottico)
            self.chrome_layout.removeWidget(self.view)
        else:
            self.browser=True
            self.view = ChromeWidget(self)
            self.chrome_layout.addWidget(self.view)
            self.main_view_stack.setCurrentWidget(self.chrome)

