# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import logging
import asyncio 

from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QApplication
from PyQt5.uic import loadUi
from alfa_CR6_ui.chrome_widget import ChromeWidget
from collections import namedtuple

Button=namedtuple('Button', 'label action target')
StatusItem=namedtuple('StatusItem', 'label path type flagno source')



defs={
        'jar_input':{
            "buttons":[
                Button('Start rulliera (MU_1)', 'start_r', 'm1'),
                Button('Stop rulliera', 'stop_r', 'm1'),
                Button('Start "step 1"', 'start_s', 'm1'),
                Button('Start "step 1 -step2"', 'start_s12', 'm1'),
                Button('Lettura barcode', 'read', 'barcode'),
                ],
            "status":[
                StatusItem('status', 'status_level', 'string', -1, 'm1'),
                StatusItem('photocell 1', 'photocells_status', 'flag', 0, 'm1'),
                StatusItem('photocell 2', 'photocells_status', 'flag', 1, 'm1'),
                StatusItem('photocell 3', 'photocells_status', 'flag', 2, 'm1'),
                StatusItem('photocell 4', 'photocells_status', 'flag', 3, 'm1'),
                StatusItem('photocell 5', 'photocells_status', 'flag', 4, 'm1'),
                StatusItem('photocell 6', 'photocells_status', 'flag', 5, 'm1'),
                StatusItem('photocell 7', 'photocells_status', 'flag', 6, 'm1'),
                StatusItem('photocell 8', 'photocells_status', 'flag', 7, 'm1'),
                ]
            }
        }

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
        for i in reversed(range(self.jar_input_buttons.count())):
            self.jar_input_buttons.itemAt(i).widget().setParent(None)

        machine_status = status

        for button in defs['jar_input']['buttons']:
            btn=QPushButton(button.label)
            self.jar_input_buttons.addWidget(btn)

        for n, statusItem in enumerate(defs['jar_input']['status']):
            label=QLabel(statusItem.label)
            label.setFixedHeight(25)
            result=QLabel('')
            if (statusItem.type=='string'):
                result=QLabel(machine_status[statusItem.path])
                result.setFixedHeight(25)
            elif (statusItem.type=='flag'):
                on=machine_status[statusItem.path] >> statusItem.flagno & 1
                result=QLabel('')
                p= "/grey.png"
                if (on):
                    p= "/green.svg"
                pixmap=QPixmap(QApplication.instance().images_path + p)
                pscaled=pixmap.scaled(25, 25, Qt.KeepAspectRatio)
                result.setPixmap(pscaled)
                result.setFixedHeight(25)
            self.jar_input_data.addWidget(label, n, 0)
            self.jar_input_data.addWidget(result, n, 1)


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

