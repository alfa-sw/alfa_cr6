# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import logging

from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMessageBox, QMainWindow  # pylint: disable=no-name-in-module
from PyQt5.QtGui import QFont

from alfa_CR6_ui.sinottico import Sinottico
from alfa_CR6_ui.keyboard import Keyboard
from alfa_CR6_ui.debug_status_view import DebugStatusView

from alfa_CR6_backend.dymo_printer import dymo_print


class MainWindow(QMainWindow):
    sinottico = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/main_window.ui", self)
        self.setFont(QFont('Times sans-serif', 28))
        self.login_btn.clicked.connect(self.login_clicked)
        self.main_window_stack.setCurrentWidget(self.login)

        ver = QApplication.instance().get_version()
        self.version_label.setText(f"ver:{ver}")

        self.sinottico = Sinottico(self)
        self.project_layout.addWidget(self.sinottico)
        self.showFullScreen()

        self.debug_status_view = DebugStatusView(self)
        self.main_window_stack.addWidget(self.debug_status_view.main_frame)

        def show_debug_view():
            self.main_window_stack.setCurrentWidget(self.debug_status_view.main_frame)
            self.debug_status_view.update_status()

        self.sinottico.status.mouseReleaseEvent = lambda event: show_debug_view()
        self.sinottico.barcode_btn.mouseReleaseEvent = lambda event: self.print_barcode()

        self.main_window_stack.setCurrentWidget(self.login)

        self.keyboard = Keyboard(self)
        self.keyboard.show()

    def print_barcode(self):

        txt = self.sinottico.bottom_text_edit.toPlainText()
        response = dymo_print(txt)
        QApplication.instance().show_alert_dialog(f" print_barcode() response: {response}")
        logging.warning(f"* txt:{txt}")

    def login_clicked(self):

        logging.warning("{ }")

        msg = QMessageBox()
        if self.user_edit.text() == '' and self.pass_edit.text() == '':
            self.user_edit.clear()
            self.pass_edit.clear()
            self.main_window_stack.setCurrentWidget(self.project)
            self.keyboard.hide()
            self.sinottico.transfer_keyboard(self.keyboard)

            logging.warning("{ }")

        else:
            msg.setText('Incorrect Password')
            msg.exec_()

    def get_stacked_widget(self):

        return self.main_window_stack

