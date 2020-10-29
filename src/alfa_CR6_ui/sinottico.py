# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import logging
import asyncio 

from PyQt5.QtCore import *
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QApplication, QScrollArea, QVBoxLayout
from PyQt5.uic import loadUi
from alfa_CR6_ui.chrome_widget import ChromeWidget

class Sinottico(QWidget):
    browser=False
    view=None
    visual="none"

    def __init__(self, parent=None):

        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/sinottico.ui", self)

        self.home_btn.clicked.connect(self.onHomeBtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.main_view_stack.setCurrentWidget(self.image_sinottico)

        self.rulliera_input.mousePressEvent = lambda event: self.rullieraInputPressed()

    def rullieraInputPressed(self):
        self.main_view_stack.setCurrentWidget(self.modal_rulliera_input)

    def update_data(self, head_index, status):

        logging.info("head_index:{}, status:{}".format(head_index, status))

        for i in reversed(range(self.rulliera_input_data.count())):
            self.rulliera_input_data.itemAt(i).widget().setParent(None)

        if head_index == 0:
            for key, value in status.items():
                self.alabel=QLabel(key + ' : ' + str(value))
                self.rulliera_input_data.addWidget(self.alabel)

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

