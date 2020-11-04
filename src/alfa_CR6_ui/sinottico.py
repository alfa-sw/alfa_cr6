# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import logging
import asyncio

from PyQt5.QtCore import *
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import QWidget, QPushButton, QLabel, QApplication
from PyQt5.uic import loadUi
from alfa_CR6_ui.chrome_widget import ChromeWidget
from alfa_CR6_ui.keyboard import Keyboard
from alfa_CR6_ui.jar import Jar
from collections import namedtuple

Button = namedtuple('Button', 'label action target')
StatusItem = namedtuple('StatusItem', 'label path type flagno source current')


class Sinottico(QWidget):
    browser = False
    view = None
    visual = "none"
    defs = []
    first_update = True

    def __init__(self, parent=None):

        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/sinottico.ui", self)

        self.init_defs()
        self.home_btn.clicked.connect(self.onHomeBtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.main_view_stack.setCurrentWidget(self.image_sinottico)

        self.keyboard = Keyboard()
        self.keyboard_position.addWidget(self.keyboard)

    def move_mainview(self, view):
        self.main_view_stack.setCurrentWidget(view)

    def update_data(self, head_index, status):

        logging.debug("head_index:{}, status:{}".format(head_index, status))

        machine_status = status

        for update_obj in self.defs[head_index]:
            if self.first_update:
                self.first_update = False
                for button in update_obj['buttons']:
                    btn = QPushButton(button.label)
                    btn.setFont(QFont('Times', 35))
                    btn.setFixedHeight(50)
                    update_obj['view'].buttons.addWidget(btn)
                for n, statusItem in enumerate(update_obj['status']):
                    label = QLabel(statusItem.label)
                    label.setFixedHeight(25)
                    result = QLabel('')
                    if (statusItem.type == 'string'):
                        result = QLabel(machine_status[statusItem.path])
                        result.setFixedHeight(25)
                        statusItem.current.append(result)
                    elif (statusItem.type == 'flag'):
                        on = machine_status[statusItem.path] >> statusItem.flagno & 1
                        result = QLabel('')
                        pscaled = self.get_pscaled(on)
                        result.setPixmap(pscaled)
                        result.setFixedHeight(25)
                        statusItem.current.append(result)
                    update_obj['view'].status.addWidget(label, n, 0)
                    update_obj['view'].status.addWidget(result, n, 1)
            else:
                for statusItem in update_obj['status']:
                    if (statusItem.type == 'string'):
                        statusItem.current[0].setText(machine_status[statusItem.path])
                    elif (statusItem.type == 'flag'):
                        on = machine_status[statusItem.path] >> statusItem.flagno & 1
                        pscaled = self.get_pscaled(on)
                        statusItem.current[0].setPixmap(pscaled)

    def get_pscaled(self, on):
        p = "/grey.png"
        if (on):
            p = "/green.svg"
        pixmap = QPixmap(QApplication.instance().images_path + p)
        return pixmap.scaled(25, 25, Qt.KeepAspectRatio)

    def onHomeBtnClicked(self, other):
        self.main_view_stack.setCurrentWidget(self.image_sinottico)
        if self.browser:
            self.chrome_layout.removeWidget(self.view)
            self.browser = False

    def onChromeBtnClicked(self):
        if self.browser:
            self.browser = False
            self.main_view_stack.setCurrentWidget(self.image_sinottico)
            self.chrome_layout.removeWidget(self.view)
        else:
            self.browser = True
            self.view = ChromeWidget(self)
            self.chrome_layout.addWidget(self.view)
            self.main_view_stack.setCurrentWidget(self.chrome)

    def add_view(self, widget, clickarea):
        self.main_view_stack.addWidget(widget)
        clickarea.mousePressEvent = lambda event: self.move_mainview(widget)
        return widget

    def init_defs(self):
        self.defs = [  # head 1
            [
                {
                    # jar input
                    "view": self.add_view(Jar(), self.jar_input),
                    "buttons": [
                        Button('Start rulliera (MU_1)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 1"', 'start_s', 'm1'),
                        Button('Start "step 1 -step2"', 'start_s12', 'm1'),
                        Button('Lettura barcode', 'read', 'barcode'),
                    ],
                    "status":[
                        StatusItem('status', 'status_level', 'string', -1, 'm1', []),
                        StatusItem('photocell 1', 'photocells_status', 'flag', 0, 'm1', []),
                        StatusItem('photocell 2', 'photocells_status', 'flag', 1, 'm1', []),
                        StatusItem('photocell 3', 'photocells_status', 'flag', 2, 'm1', []),
                        StatusItem('photocell 4', 'photocells_status', 'flag', 3, 'm1', []),
                        StatusItem('photocell 5', 'photocells_status', 'flag', 4, 'm1', []),
                        StatusItem('photocell 6', 'photocells_status', 'flag', 5, 'm1', []),
                        StatusItem('photocell 7', 'photocells_status', 'flag', 6, 'm1', []),
                        StatusItem('photocell 8', 'photocells_status', 'flag', 7, 'm1', []),
                    ]
                }, ],
            [  # head 2
            ],
            [  # head 3
            ],
            [  # head 4
            ],
            [  # head 5
            ],
            [  # head 6
            ],
            [  # head 7
            ],
            [  # head 8
            ],
        ]
