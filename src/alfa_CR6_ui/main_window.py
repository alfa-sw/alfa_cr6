# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import logging

from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow  # pylint: disable=no-name-in-module

from alfa_CR6_ui.sinottico import Sinottico
from alfa_CR6_ui.keyboard import Keyboard
from alfa_CR6_ui.debug_status_view import DebugStatusView


class MainWindow(QMainWindow):
    keyboard = {}
    sinottico = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/main_window.ui", self)
        self.login_btn.clicked.connect(self.onLoginBtnClicked)
        self.main_window_stack.setCurrentWidget(self.login)

        self.sinottico = Sinottico(self)
        self.project_layout.addWidget(self.sinottico)
        self.showFullScreen()

        self.debug_status_view = DebugStatusView(self)
        self.main_window_stack.addWidget(self.debug_status_view.main_frame)

        self.sinottico.chrome_btn_2.clicked.connect(
            lambda: self.main_window_stack.setCurrentWidget(
                self.debug_status_view.main_frame))

        self.main_window_stack.setCurrentWidget(self.login)

        self.keyboard = Keyboard()

        self.keyboard_position.addWidget(self.keyboard)

        logging.warning("{ }")

    def onLoginBtnClicked(self):

        logging.warning("{ }")

        msg = QMessageBox()
        if self.user_edit.text() == '' and self.pass_edit.text() == '':
            self.user_edit.clear()
            self.pass_edit.clear()
            self.main_window_stack.setCurrentWidget(self.project)

            logging.warning("{ }")

            self.sinottico.transferKeyboard(self.keyboard)

        else:
            msg.setText('Incorrect Password')
            msg.exec_()
