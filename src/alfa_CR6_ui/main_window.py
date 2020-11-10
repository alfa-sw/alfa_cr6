# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow  # pylint: disable=no-name-in-module
from PyQt5 import QtCore

from alfa_CR6_ui.sinottico import Sinottico
from alfa_CR6_ui.keyboard import Keyboard


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
        self.keyboard = Keyboard()
        self.keyboard_position.addWidget(self.keyboard)

    def onLoginBtnClicked(self):
        msg = QMessageBox()
        if self.user_edit.text() == '' and self.pass_edit.text() == '':
            self.user_edit.clear()
            self.pass_edit.clear()
            self.main_window_stack.setCurrentWidget(self.project)
            self.sinottico.transferKeyboard(self.keyboard)

        else:
            msg.setText('Incorrect Password')
            msg.exec_()
