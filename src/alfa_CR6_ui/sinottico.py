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
StatusViewItem = namedtuple('StatusViewItem', 'path type source')


class Sinottico(QWidget):
    browser = False
    view = None
    visual = "none"
    defs = []
    status_defs = []

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
            if update_obj['first_update']:
                update_obj['first_update'] = False
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
                    elif (statusItem.type == 'flag' or statusItem.type == 'bool'):
                        on = 0
                        if statusItem.type == 'flag':
                            on = machine_status[statusItem.path] >> statusItem.flagno & 1
                        else:
                            on = machine_status[statusItem.path]
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
                    elif (statusItem.type == 'flag' or statusItem.type == 'bool'):
                        on = 0
                        if statusItem.type == 'flag':
                            on = machine_status[statusItem.path] >> statusItem.flagno & 1
                        else:
                            on = machine_status[statusItem.path]
                        pscaled = self.get_pscaled(on)
                        statusItem.current[0].setPixmap(pscaled)

        for status_obj in self.status_defs[head_index]:
            if status_obj.type == "string":
                status_obj.path.setText(machine_status[status_obj.source])

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
        self.status_defs = [
            [  # head 1
                StatusViewItem(self.view_status_HEAD_1_STEP_2, "string", "status_level")
            ],
            [  # head 2
                StatusViewItem(self.view_status_HEAD_2_STEP_9, "string", "status_level")
            ],
            [  # head 3
                StatusViewItem(self.view_status_HEAD_3_STEP_3, "string", "status_level")
            ],
            [  # head 4
                StatusViewItem(self.view_status_HEAD_4_STEP_8, "string", "status_level")
            ],
            [  # head 5
                StatusViewItem(self.view_status_HEAD_5_STEP_4, "string", "status_level")
            ],
            [  # head 6
                StatusViewItem(self.view_status_HEAD_6_STEP_7, "string", "status_level")
            ],
        ]
        self.defs = [  # head 1
            [
                {
                    # jar input
                    "first_update": True,
                    "view": self.add_view(Jar(), self.jar_input),
                    "buttons": [
                        Button('Start rulliera (MU_1)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 1"', 'start_s', 'm1'),
                        Button('Start "step 1 -step2"', 'start_s12', 'm1'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_1', 'jar_photocells_status', 'flag', 0, 'm1', []),
                        StatusItem('Stato MS_5', 'jar_photocells_status', 'flag', 9, 'm1', []),
                        StatusItem('Stato MS_6', 'jar_photocells_status', 'flag', 10, 'm1', []),
                        StatusItem('Barcode', 'status_level', 'string', -1, 'm1', []),  # TODO read actual barcode
                    ]
                },
                {
                    # jar head 1
                    "first_update": True,
                    "view": self.add_view(Jar(), self.jar_t1),
                    "buttons": [
                        Button('Start rulliera (MU_2)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 2"', 'start_s', 'm1'),
                        Button('Start "step 2 -step3"', 'start_s23', 'm1'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_2', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_1', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },

            ],
            [  # head 2
                {
                    # jar head 2
                    "first_update": True,
                    "view": self.add_view(Jar(), self.jar_t2),
                    "buttons": [
                        Button('Start rulliera (MU_7)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 9"', 'start_s', 'm1'),
                        Button('Start "step 9 -step10"', 'start_s910', 'm1'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_8', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_2', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
            [  # head 3
                {
                    # jar head 3
                    "first_update": True,
                    "view": self.add_view(Jar(), self.jar_t3),
                    "buttons": [
                        Button('Start rulliera (MU_3)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 3"', 'start_s', 'm1'),
                        Button('Start "step 3 -step4"', 'start_s34', 'm1'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_3', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_3', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
            [  # head 4
                {
                    # jar head 4
                    "first_update": True,
                    "view": self.add_view(Jar(), self.jar_t4),
                    "buttons": [
                        Button('Start rulliera (MU_6)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 8"', 'start_s', 'm1'),
                        Button('Start "step 8 -step4"', 'start_s34', 'm1'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_7', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_4', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
            [  # head 5
                {
                    # jar head 5
                    "first_update": True,
                    "view": self.add_view(Jar(), self.jar_t5),
                    "buttons": [
                        Button('Start rulliera (MU_4)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 4"', 'start_s', 'm1'),
                        Button('Start "step 4 -step5"', 'start_s34', 'm1'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_4', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_5', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
            [  # head 6
                {
                    # jar head 6
                    "first_update": True,
                    "view": self.add_view(Jar(), self.jar_t6),
                    "buttons": [
                        Button('Start rulliera (MU_5)', 'start_r', 'm1'),
                        Button('Stop rulliera', 'stop_r', 'm1'),
                        Button('Start "step 7"', 'start_s', 'm1'),
                        Button('Start "step 7 -step8"', 'start_s34', 'm1'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_6', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_6', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
        ]
