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

Button = namedtuple('Button', 'label actions')
StatusItem = namedtuple('StatusItem', 'label path type flagno source current')
StatusViewItem = namedtuple('StatusViewItem', 'path type source')
Action = namedtuple('Action', 'target, key, param')


class Sinottico(QWidget):
    browser = False
    view = None
    visual = "none"
    defs = []
    status_defs = []
    machine_head_dict = {}

    def __init__(self, parent=None):

        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/sinottico.ui", self)
        self.machine_head_dict = QApplication.instance().machine_head_dict

        self.init_defs()
        self.add_data()
        self.home_btn.clicked.connect(self.onHomeBtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.main_view_stack.setCurrentWidget(self.image_sinottico)
        self.connect_status()

        self.keyboard = Keyboard()
        self.keyboard_position.addWidget(self.keyboard)

    def move_mainview(self, view):
        self.main_view_stack.setCurrentWidget(view)

    def connect_status(self):
        service_pages = {
            '192.168.15.156:8080/service_page/': self.view_status_HEAD_1_STEP_2,
            '192.168.15.19:8080/service_page/': self.view_status_HEAD_2_STEP_9,
            '192.168.15.60:8080/service_page/': self.view_status_HEAD_3_STEP_3,
            '192.168.15.61:8080/service_page/': self.view_status_HEAD_4_STEP_8,
            '192.168.15.62:8080/service_page/': self.view_status_HEAD_5_STEP_4,
            '192.168.15.170:8080/service_page/': self.view_status_HEAD_6_STEP_7
        }
        for key, value in service_pages.items():
            value.clicked.connect((lambda x: lambda: self.openChrome(x))(key))

            start_act = [Action(0, 'Input_Roller', 2)]
            stop_act = [Action(6, 'output_Roller', 2)]
            self.out_btn_start.clicked.connect(lambda: self.jar_button(start_act))
            self.out_btn_out.clicked.connect(lambda: self.jar_button(start_act))

    def add_data(self):
        for head_index in range(len(self.defs)):
            for update_obj in self.defs[head_index]:
                for button in update_obj['buttons']:
                    btn = QPushButton(button.label)
                    btn.setFont(QFont('Times', 35))
                    btn.setFixedHeight(50)
                    btn.clicked.connect((lambda x: lambda: self.jar_button(x))(button.actions))
                    update_obj['view'].buttons.addWidget(btn)
                for n, statusItem in enumerate(update_obj['status']):
                    label = QLabel(statusItem.label)
                    label.setFixedHeight(25)
                    result = QLabel('')
                    if (statusItem.type == 'string'):
                        result = QLabel("")
                        result.setFixedHeight(25)
                        statusItem.current.append(result)
                    elif (statusItem.type == 'flag' or statusItem.type == 'bool'):
                        on = 0
                        result = QLabel('')
                        pscaled = self.get_pscaled(on)
                        result.setPixmap(pscaled)
                        result.setFixedHeight(25)
                        statusItem.current.append(result)
                    update_obj['view'].status.addWidget(label, n, 0)
                    update_obj['view'].status.addWidget(result, n, 1)

    def update_data(self, head_index, status):

        logging.debug("head_index:{}, status:{}".format(head_index, status))

        machine_status = status

        for update_obj in self.defs[head_index]:
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

    def openChrome(self, target):
        self.browser = True
        self.view = ChromeWidget(self, url=target)
        self.chrome_layout.addWidget(self.view)
        self.main_view_stack.setCurrentWidget(self.chrome)

    def onChromeBtnClicked(self):
        if self.browser:
            self.browser = False
            self.main_view_stack.setCurrentWidget(self.image_sinottico)
            self.chrome_layout.removeWidget(self.view)
        else:
            self.openChrome("http://kccrefinish.co.kr")

    def add_view(self, widget, clickarea):
        self.main_view_stack.addWidget(widget)
        clickarea.mousePressEvent = lambda event: self.move_mainview(widget)
        return widget

    def jar_button(self, actions):
        for action in actions:
            self.machine_head_dict[action.target].can_movement({action.key: action.param})

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
                        Button('Start rulliera (MU_1)', [Action(0, 'Input_Roller', 1)]),
                        Button('Stop rulliera', [Action(0, 'Input_Roller', 0)]),
                        Button('Start "step 1"', [Action(0, 'Input_Roller', 2)]),
                        Button('Start "step 1 -step2"', [Action(0, 'Input_Roller', 2),
                                                         Action(0, 'Dispensing_Roller', 2)]),
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
                        Button('Start rulliera (MU_2)', 'start_r'),
                        Button('Stop rulliera', 'stop_r'),
                        Button('Start "step 2"', 'start_s'),
                        Button('Start "step 2 -step3"', 'start_s23'),
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
                        Button('Start rulliera (MU_7)', 'start_r'),
                        Button('Stop rulliera', 'stop_r'),
                        Button('Start "step 9"', 'start_s'),
                        Button('Start "step 9 -step10"', 'start_s910'),
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
                        Button('Start rulliera (MU_3)', 'start_r'),
                        Button('Stop rulliera', 'stop_r'),
                        Button('Start "step 3"', 'start_s'),
                        Button('Start "step 3 -step4"', 'start_s34'),
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
                        Button('Start rulliera (MU_6)', 'start_r'),
                        Button('Stop rulliera', 'stop_r'),
                        Button('Start "step 8"', 'start_s'),
                        Button('Start "step 8 -step4"', 'start_s34'),
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
                        Button('Start rulliera (MU_4)', 'start_r'),
                        Button('Stop rulliera', 'stop_r'),
                        Button('Start "step 4"', 'start_s'),
                        Button('Start "step 4 -step5"', 'start_s34'),
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
                        Button('Start rulliera (MU_5)', 'start_r'),
                        Button('Stop rulliera', 'stop_r'),
                        Button('Start "step 7"', 'start_s'),
                        Button('Start "step 7 -step8"', 'start_s34'),
                    ],
                    "status":[
                        StatusItem('Stato FTC_6', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_6', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
        ]
