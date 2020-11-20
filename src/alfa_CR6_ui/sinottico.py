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

Button = namedtuple('Button', 'label action')
StatusItem = namedtuple('StatusItem', 'label path type flagno source current')
StatusViewItem = namedtuple('StatusViewItem', 'path type source')
StatusFlag = namedtuple('StatusFlag', 'path_local other path_other')


class Sinottico(QWidget):
    browser = False
    view = None
    visual = "none"
    defs = []
    status_defs = []
    machine_head_dict = {}
    cr6_app = []
    keyboard = {}

    def __init__(self, parent=None):

        super().__init__(parent)
        self.cr6_app = QApplication.instance()
        loadUi(QApplication.instance().ui_path + "/sinottico.ui", self)
        self.machine_head_dict = QApplication.instance().machine_head_dict

        self.init_defs()
        self.add_data()
        self.home_btn.clicked.connect(self.onHomeBtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.main_view_stack.setCurrentWidget(self.image_sinottico)
        self.connect_status()

    def transferKeyboard(self, keyboard):
        self.keyboard = keyboard

    def move_mainview(self, view):
        self.main_view_stack.setCurrentWidget(view)

    def connect_status(self):
        service_page_urls = [ "http://{}:{}/service_page/".format(i[0], i[2]) for i in self.cr6_app.settings.MACHINE_HEAD_IPADD_PORTS_LIST]
        # TODO: rename the buttons to something meaningful
        self.view_status_HEAD_1_STEP_2.clicked.connect(lambda: self.openChrome(service_page_urls[0]))
        self.view_status_HEAD_2_STEP_9.clicked.connect(lambda: self.openChrome(service_page_urls[1]))
        self.view_status_HEAD_3_STEP_3.clicked.connect(lambda: self.openChrome(service_page_urls[2]))
        self.view_status_HEAD_4_STEP_8.clicked.connect(lambda: self.openChrome(service_page_urls[3]))
        self.view_status_HEAD_5_STEP_4.clicked.connect(lambda: self.openChrome(service_page_urls[4]))
        self.view_status_HEAD_6_STEP_7.clicked.connect(lambda: self.openChrome(service_page_urls[5]))

        self.out_btn_start.mousePressEvent = lambda event: self.jar_button(('single_move', 'A', {'Input_Roller': 2}))
        self.out_btn_out.mousePressEvent = lambda event: self.jar_button(('single_move', 'F', {'Output_Roller': 2}))

    def add_data(self):
        for head_index in range(len(self.defs)):
            for update_obj in self.defs[head_index]:
                for button in update_obj['buttons']:
                    btn = QPushButton(button.label)
                    btn.setFont(QFont('Times', 35))
                    btn.setFixedHeight(50)
                    btn.clicked.connect((lambda x: lambda: self.jar_button(x))(button.action))
                    update_obj['view'].buttons.addWidget(btn)
                existing = update_obj['view'].status.count() / 2
                for n, statusItem in enumerate(update_obj['status']):
                    label = QLabel(statusItem.label)
                    label.setFixedHeight(50)
                    label.setFont(QFont('Times', 35))
                    result = QLabel('')
                    if (statusItem.type == 'string'):
                        result = QLabel("")
                        result.setFixedHeight(50)
                        statusItem.current.append(result)
                    elif (statusItem.type == 'flag' or statusItem.type == 'bool'):
                        on = 0
                        result = QLabel('')
                        pscaled = self.get_pscaled(on)
                        result.setPixmap(pscaled)
                        result.setFixedHeight(50)
                        result.setFont(QFont('Times', 35))
                        statusItem.current.append(result)
                    update_obj['view'].status.addWidget(label, existing + n, 0)
                    update_obj['view'].status.addWidget(result, existing + n, 1)

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
            if status_obj.type == "jar":
                if machine_status['jar_photocells_status'] >> status_obj.source.path_local & 1:
                    pscaled = self.get_jar(0)
                else:
                    pscaled = self.get_jar(-1)
                status_obj.path.setPixmap(pscaled)

    def get_jar(self, n):
        dict_cans = ["/jar-green.png", "/jar-red.png", "/jat-blue.png"]
        p = ""
        if (n != -1):
            p = dict_cans[n]
            pixmap = QPixmap(QApplication.instance().images_path + p)
            return pixmap.scaled(75, 75, Qt.KeepAspectRatio)
        else:
            pixmap = QPixmap(QApplication.instance().images_path + dict_cans[0])
            return pixmap.scaled(0, 0, Qt.KeepAspectRatio)

    def get_pscaled(self, on):
        p = "/grey.png"
        if (on):
            p = "/green.svg"
        pixmap = QPixmap(QApplication.instance().images_path + p)
        return pixmap.scaled(25, 25, Qt.KeepAspectRatio)

    def onHomeBtnClicked(self, other):
        self.main_view_stack.setCurrentWidget(self.image_sinottico)
        self.keyboard.showMinimized()
        if self.browser:
            self.chrome_layout.removeWidget(self.view)
            self.browser = False

    def openChrome(self, target):

        logging.warning("target:{}".format(target))
        self.browser = True
        self.view = ChromeWidget(self, url=target)
        self.chrome_layout.addWidget(self.view)
        self.main_view_stack.setCurrentWidget(self.chrome)

    def onChromeBtnClicked(self):
        if self.browser:
            self.browser = False
            self.keyboard.showMinimized()
            self.main_view_stack.setCurrentWidget(self.image_sinottico)
            self.chrome_layout.removeWidget(self.view)
        else:
            self.keyboard.showNormal()
            self.openChrome("http://kccrefinish.co.kr")

    def add_view(self, widget, clickarea):
        self.main_view_stack.addWidget(widget)
        clickarea.mousePressEvent = lambda event: self.move_mainview(widget)
        return widget

    def jar_button(self, action):
        print(action)
        if (isinstance(action, str)):
            self.cr6_app.run_a_coroutine_helper(action)
        elif (isinstance(action, tuple)):
            self.cr6_app.run_a_coroutine_helper(*action)
        else:
            logging.error("{} is neither string nor tuple".format(type(action)))

    def init_defs(self):
        self.status_defs = [
            [  # head 1
                StatusViewItem(self.view_status_HEAD_1_STEP_2, "string", "status_level"),
                StatusViewItem(self.STEP_1, "jar", StatusFlag(0, 0, 0)),
                StatusViewItem(self.STEP_2, "jar", StatusFlag(8, 0, 0)),
            ],
            [  # head 2
                StatusViewItem(self.view_status_HEAD_2_STEP_9, "string", "status_level"),
                StatusViewItem(self.STEP_9, "jar", StatusFlag(8, 0, 0)),
                StatusViewItem(self.STEP_10, "jar", StatusFlag(7, 0, 5)),
                StatusViewItem(self.STEP_11, "jar", StatusFlag(7, 0, 6)),
                StatusViewItem(self.STEP_12, "jar", StatusFlag(2, 0, 0)),
            ],
            [  # head 3
                StatusViewItem(self.view_status_HEAD_3_STEP_3, "string", "status_level"),
                StatusViewItem(self.STEP_3, "jar", StatusFlag(8, 0, 0)),
            ],
            [  # head 4
                StatusViewItem(self.view_status_HEAD_4_STEP_8, "string", "status_level"),
                StatusViewItem(self.STEP_8, "jar", StatusFlag(8, 0, 0)),
            ],
            [  # head 5
                StatusViewItem(self.view_status_HEAD_5_STEP_4, "string", "status_level"),
                StatusViewItem(self.STEP_4, "jar", StatusFlag(8, 0, 0)),
                StatusViewItem(self.STEP_5, "jar", StatusFlag(1, 6, 4)),  # 1 6-4
                StatusViewItem(self.STEP_6, "jar", StatusFlag(1, 6, 4))  # 1 6-3
            ],
            [  # head 6
                StatusViewItem(self.view_status_HEAD_6_STEP_7, "string", "status_level"),
                StatusViewItem(self.STEP_7, "jar", StatusFlag(8, 0, 0)),
            ],
        ]
        jar_lifter_1 = self.add_view(Jar(), self.jar_lifter_1)
        self.defs = [  # head 1
            [
                {
                    # jar input
                    "view": self.add_view(Jar(), self.jar_input),
                    "buttons": [
                        Button('Start rulliera (MU_1)', ('single_move', 'A', {'Input_Roller': 1})),
                        Button('Stop rulliera', ('single_move', 'A', {'Input_Roller': 0})),
                        Button('Start "step 1"', ('single_move', 'A', {'Input_Roller': 2})),
                        Button('Start "step 1 -step2"', 'move_01_02'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_1', 'jar_photocells_status', 'flag', 0, 'm1', []),
                        StatusItem('Stato MS_5', 'jar_photocells_status', 'flag', 9, 'm1', []),
                        StatusItem('Stato MS_6', 'jar_photocells_status', 'flag', 10, 'm1', []),
                        StatusItem('Barcode', 'status_level', 'string', -1, 'm1', []),  # TODO read actual barcode
                    ]
                },
                {
                    # jar head 1
                    "view": self.add_view(Jar(), self.jar_t1),
                    "buttons": [
                        Button('Start rulliera (MU_2)', ('single_move', 'A', {'Dispensing_Roller': 1})),
                        Button('Stop rulliera', ('single_move', 'A', {'Dispensing_Roller': 0})),
                        Button('Start "step 2"', ('single_move', 'A', {'Dispensing_Roller': 2})),
                        Button('Start "step 2 -step3"', 'move_02_03'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_2', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_1', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },

            ],
            [  # head 2
                {
                    # jar head 2
                    "view": self.add_view(Jar(), self.jar_t2),
                    "buttons": [
                        Button('Start rulliera (MU_7)', ('single_move', 'F', {'Dispensing_Roller': 1})),
                        Button('Stop rulliera', ('single_move', 'F', {'Dispensing_Roller': 0})),
                        Button('Start "step 9"', ('single_move', 'F', {'Dispensing_Roller': 2})),
                        Button('Start "step 9 -step10"', 'move_09_10'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_8', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_2', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
                {
                    # jar lifter 2
                    "view": self.add_view(Jar(), self.jar_lifter_2),
                    "buttons": [
                        Button('Start rulliera (MU_8)', ('single_move', 'F', {'Lifter_Roller': 3})),
                        Button('Stop rulliera', ('single_move', 'F', {'Lifter_Roller': 0})),
                        #Button('Step rulliera', ('single_move', 'F', {'Lifter_Roller': 5})),
                        Button('Start "step 11 -step12"', 'move_11_12'),
                        Button('Start "sollevatore_up"', ('single_move', 'F', {'Lifter': 1})),
                        Button('Start "sollevatore_down"', ('single_move', 'F', {'Lifter': 2})),
                        Button('Stop sollevatore"', ('single_move', 'F', {'Lifter': 0})),
                        Button('Start "step 10 -step 11"', 'move_10_11'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_9', 'jar_photocells_status', 'flag', 7, 'm1', []),
                        StatusItem('Stato MS_4', 'jar_photocells_status', 'flag', 6, 'm1', []),
                        StatusItem('Stato MS_3', 'jar_photocells_status', 'flag', 5, 'm1', []),
                    ]
                },
                {
                    # jar output
                    "view": self.add_view(Jar(), self.jar_output),
                    "buttons": [
                        Button('Start rulliera (MU_9)', ('single_move', 'F', {'Output_Roller': 3})),
                        Button('Stop rulliera', ('single_move', 'F', {'Output_Roller': 0})),
                        Button('Start "step 12"', ('single_move', 'F', {'Output_Roller': 2})),
                    ],
                    "status": [
                        StatusItem('Stato FTC_10', 'jar_photocells_status', 'flag', 2, 'm1', []),
                    ]
                },
            ],
            [  # head 3
                {
                    # jar head 3
                    "view": self.add_view(Jar(), self.jar_t3),
                    "buttons": [
                        Button('Start rulliera (MU_3)', ('single_move', 'B', {'Dispenser_Roller': 1})),
                        Button('Stop rulliera', ('single_move', 'B', {'Dispenser_Roller': 0})),
                        Button('Start "step 3"', ('single_move', 'B', {'Dispenser_Roller': 2})),
                        Button('Start "step 3 -step4"', 'move_03_04'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_3', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_3', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
            [  # head 4
                {
                    # jar head 4
                    "view": self.add_view(Jar(), self.jar_t4),
                    "buttons": [
                        Button('Start rulliera (MU_6)', ('single_move', 'E', {'Dispenser_Roller': 1})),
                        Button('Stop rulliera', ('single_move', 'E', {'Dispenser_Roller': 0})),
                        Button('Start "step 8"', ('single_move', 'E', {'Dispenser_Roller': 2})),
                        Button('Start "step 8 -step9"', 'move_08_09'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_7', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_4', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
            ],
            [  # head 5
                {
                    # jar head 5
                    "view": self.add_view(Jar(), self.jar_t5),
                    "buttons": [
                        Button('Start rulliera (MU_4)', ('single_move', 'C', {'Dispenser_Roller': 1})),
                        Button('Stop rulliera', ('single_move', 'C', {'Dispenser_Roller': 0})),
                        Button('Start "step 4"', ('single_move', 'C', {'Dispenser_Roller': 2})),
                        Button('Start "step 4 -step5"', 'move_04_05'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_4', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_5', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
                {
                    # jar lifter 1 (1/2)
                    "view": jar_lifter_1,
                    "buttons": [
                        Button('Start rulliera direzione CW (MB_1)', ('single_move', 'C', {'Lifter_Roller': 2})),
                        Button('Start rulliera direzione CCW (MB_1)', ('single_move', 'C', {'Lifter_Roller': 3})),
                        Button('Stop rulliera', ('single_move', 'C', {'Lifter_Roller': 0})),
                        Button('Start "step 5"', 'move_04_05'),
                        Button('Start "step 5 -step6"', 'move_05_06'),
                        Button('Start "step 6 -step7"', 'move_06_07'),
                        Button('Start "sollevatore_up"', ('single_move', 'D', {'Lifter': 1})),
                        Button('Start "sollevatore_down"', ('single_move', 'D', {'Lifter': 2})),
                        Button('Stop sollevatore', ('single_move', 'D', {'Lifter': 0})),
                    ],
                    "status": [
                        StatusItem('Stato FTC_5', 'jar_photocells_status', 'flag', 1, 'm1', []),
                    ]
                },
            ],
            [  # head 6
                {
                    # jar head 6
                    "view": self.add_view(Jar(), self.jar_t6),
                    "buttons": [
                        Button('Start rulliera (MU_5)', ('single_move', 'D', {'Dispenser_Roller': 1})),
                        Button('Stop rulliera', ('single_move', 'D', {'Dispenser_Roller': 0})),
                        Button('Start "step 7"', ('single_move', 'D', {'Dispenser_Roller': 2})),
                        Button('Start "step 7 -step8"', 'move_07_08'),
                    ],
                    "status": [
                        StatusItem('Stato FTC_6', 'jar_photocells_status', 'flag', 8, 'm1', []),
                        StatusItem('Stato CP_6', 'container_presence', 'bool', -1, 'm1', []),
                    ]
                },
                {
                    # jar lifter 1 (2/2)
                    "view": jar_lifter_1,
                    "buttons": [
                    ],
                    "status":[
                        StatusItem('Stato MS_1', 'jar_photocells_status', 'flag', 4, 'm1', []),
                        StatusItem('Stato MS_2', 'jar_photocells_status', 'flag', 3, 'm1', []),
                    ]
                },
            ],
        ]
