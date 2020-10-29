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

        self.jar_input.mousePressEvent = lambda event: self.jarInputPressed()

    def jarInputPressed(self):
        self.main_view_stack.setCurrentWidget(self.modal_jar_input)

    def update_data(self, head_index, status):

        logging.info("head_index:{}, status:{}".format(head_index, status))

        for i in reversed(range(self.jar_input_data.count())):
            self.jar_input_data.itemAt(i).widget().setParent(None)

        if head_index == 0:
            for key, value in status.items():
            
                if key == 'status_level':
                  self.alabel=QLabel('Stato FTC_1')
                  self.alabel3=QLabel('Stato MS_5')
                  self.alabel4=QLabel('Stato MS_6')
                  self.alabel5=QLabel('BAR CODE')

                  self.jar_input_data.addWidget(self.alabel)
                  self.jar_input_data.addWidget(self.alabel3)
                  self.jar_input_data.addWidget(self.alabel4)
                  self.jar_input_data.addWidget(self.alabel5)

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

