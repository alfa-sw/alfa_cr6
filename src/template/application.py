# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import os
import time
import sys
import logging

from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMainWindow, QTableView, QAbstractItemView
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.Qt import QUrl

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5 import QtGui, QtCore

from alfa_CR6_backend.models import init_models, Order


class TableModel(QAbstractTableModel):

    def __init__(self, parent, session, *args):
        QAbstractTableModel.__init__(self, parent, *args)
        self.header = ['order_nr', 'status', 'json_properties']
        if session:
            # 5. fetch data
            # ~ self.results = connection.execute(db.select([demoTable])).fetchall()
            self.results = [[o.order_nr, o.status, o.json_properties] for o in session.query(Order).all()]
        else:
            self.results = [[], ]

    def rowCount(self, parent):
        return len(self.results)

    def columnCount(self, parent):
        return len(self.results[0])

    def data(self, index, role):
        # 5. populate data
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self.results[index.row()][index.column()]
        else:
            return QVariant()

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[col]
        return None


class MainWindow(QMainWindow):

    def __init__(self, parent=None):

        super().__init__(parent)
        loadUi("main_window.ui", self)

        self.webengine_view = QWebEngineView(self.browser_page)
        self.webengine_view.setGeometry(0, 28, self.stacked_widget.width(), self.stacked_widget.height() - 28)

        self.menu_btn_group.buttonClicked.connect(self.on_menu_btn_group_clicked)
        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)

        for b in self.service_btn_group.buttons():
            b.setAutoFillBackground(True)

        self.showFullScreen()

        self.db_session = init_models("sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite")

    def populate_table_view(self):

        self.order_model = TableModel(self, self.db_session)
        self.order_table.setModel(self.order_model)

    def on_service_btn_group_clicked(self, btn):

        logging.warning(f"btn.objectName():{btn.objectName()}")
        self.stacked_widget.setCurrentWidget(self.browser_page)
        # ~ self.webengine_view.setUrl(QUrl('http://127.0.0.1:8080/admin'))
        self.webengine_view.setUrl(QUrl('http://127.0.0.1:8080/service_page'))

    def on_menu_btn_group_clicked(self, btn):

        logging.warning(f"btn.objectName():{btn.objectName()}")
        btn_name = btn.objectName()
        if 'home' in btn_name:
            self.stacked_widget.setCurrentWidget(self.home_page)
        elif 'order' in btn_name:
            self.populate_table_view()
            self.stacked_widget.setCurrentWidget(self.order_page)
        elif 'browser' in btn_name:
            self.stacked_widget.setCurrentWidget(self.browser_page)
            # ~ self.webengine_view.setUrl(QUrl('http://google.com'))
            self.webengine_view.setUrl(QUrl('http://kccrefinish.co.kr'))
        elif 'keyboard' in btn_name:
            pass


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level='INFO', format=fmt_)

    app = QApplication(sys.argv)
    main_window = MainWindow()
    app.exec_()


if __name__ == "__main__":
    main()
