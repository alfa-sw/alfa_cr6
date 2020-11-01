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

        logging.debug("head_index:{}, status:{}".format(head_index, status))

        for i in reversed(range(self.jar_input_data.count())):
            self.jar_input_data.itemAt(i).widget().setParent(None)

        machine_status = status

        self.label_FTC_1=QLabel('Stato FTC_1')
        self.label_FTC_1.setAlignment(Qt.AlignCenter)
        self.led_FTC_1=QLabel('')
        self.label_MS_5=QLabel('Stato MS_5')
        self.label_MS_5.setAlignment(Qt.AlignCenter)
        self.led_MS_5=QLabel('')
        self.label_MS_6=QLabel('Stato MS_6')
        self.label_MS_6.setAlignment(Qt.AlignCenter)
        self.led_MS_6=QLabel('')
#         self.label_barcode=QLabel('BAR CODE')
#         self.label_barcode.setAlignment(Qt.AlignCenter)

        self.jar_input_data.addWidget(self.label_FTC_1)
        self.jar_input_data.addWidget(self.led_FTC_1)
        self.jar_input_data.addWidget(self.label_MS_5)
        self.jar_input_data.addWidget(self.led_MS_5)
        self.jar_input_data.addWidget(self.label_MS_6)
        self.jar_input_data.addWidget(self.led_MS_6)
#         self.jar_input_data.addWidget(self.label_barcode)

        for key, value in machine_status.items():
            if key == 'jar_photocells_status':
                self.led_FTC_1.setText('jar_photocells_status: ' + str(value))
                self.led_FTC_1.setAlignment(Qt.AlignCenter)

            if key == 'bases_carriage':
                if value == True:
                    self.led_MS_6.setStyleSheet("background-image : url(" + QApplication.instance().images_path + "/green.svg); background-repeat:no-repeat; background-position:center;")
                else:
                    self.led_MS_6.setStyleSheet("background-image : url(" + QApplication.instance().images_path + "/grey.png); background-repeat:no-repeat; background-position:center;")

            if key == 'water_level':
                if value == True:
                    self.led_MS_5.setStyleSheet("background-image : url(" + QApplication.instance().images_path + "/green.svg); background-repeat:no-repeat; background-position:center;")
                else:
                    self.led_MS_5.setStyleSheet("background-image : url(" + QApplication.instance().images_path + "/grey.png); background-repeat:no-repeat; background-position:center;")


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

