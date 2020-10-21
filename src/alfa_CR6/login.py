# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow  # pylint: disable=no-name-in-module
from PyQt5 import QtCore

from alfa_CR6.tintometro import Tintometro


class Login(QMainWindow):
    path = None

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/login.ui", self)
        self.login_btn.clicked.connect(self.onLoginBtnClicked)
        self.tab_login.setCurrentIndex(0)

    def onLoginBtnClicked(self):
        msg = QMessageBox()
        if self.user_edit.text() == '' and self.pass_edit.text() == '':
            self.user_edit.clear()
            self.pass_edit.clear()
            view_tintometro = Tintometro()
            self.mainwindowlayout.addWidget(view_tintometro)
            self.tab_login.setCurrentIndex(1)

        else:
            msg.setText('Incorrect Password')
            msg.exec_()
