# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module

import os
import sys
import logging

from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QMainWindow, QHeaderView
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.Qt import QUrl

from PyQt5.QtCore import Qt, QVariant, QAbstractTableModel
# ~ from PyQt5.QtGui import *
# ~ from PyQt5 import QtGui, QtCore

from alfa_CR6_backend.models import init_models, Order  # pylint: disable=import-error

DOWNLOAD_PATH = "/opt/alfa_cr6/data/kcc"
DB_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"

class Cr6TableModel(QAbstractTableModel):

    def rowCount(self, parent):
        logging.debug(f"parent:{parent}")
        return len(self.results)

    def columnCount(self, parent):
        logging.debug(f"parent:{parent}")
        return len(self.results[0])

    def data(self, index, role):
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[col]
        return None

class FileTableModel(Cr6TableModel):

    def __init__(self, parent, path, *args):
        super().__init__(parent, *args)
        self.header = ['name', ]
        filter_text = parent.search_file_line.text()
        list_ = [p for p in os.listdir(path) if filter_text in p]
        logging.warning(f"list_:{list_}")
        self.results = [[p, ] for p in list_]

class OrderTableModel(Cr6TableModel):

    def __init__(self, parent, session, *args):
        super().__init__(parent, *args)
        self.header = ['order_nr', 'status', 'json_properties']
        filter_text = parent.search_order_line.text()
        if session:
            query_ = session.query(Order).filter(Order.order_nr.contains(filter_text)).order_by(Order.order_nr.desc()).limit(100)
            self.results = [[o.order_nr, o.status, o.json_properties] for o in query_.all()]
        else:
            self.results = [[], ]


class MainWindow(QMainWindow):

    def __init__(self, parent=None):

        super().__init__(parent)
        loadUi("main_window.ui", self)

        self.webengine_view = QWebEngineView(self.browser_page)
        self.webengine_view.setGeometry(0, 28, self.stacked_widget.width(), self.stacked_widget.height() - 28)

        self.order_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.menu_btn_group.buttonClicked.connect(self.on_menu_btn_group_clicked)
        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)

        self.order_table.clicked.connect(self.on_order_table_clicked)
        self.file_table.clicked.connect(self.on_file_table_clicked)

        self.search_order_btn.clicked.connect(self.populate_order_table)
        self.search_file_btn.clicked.connect(self.populate_file_table)

        for b in self.service_btn_group.buttons():
            b.setAutoFillBackground(True)

        self.showFullScreen()

        self.db_session = init_models(DB_STRING)

        self.stacked_widget.setCurrentWidget(self.order_page)

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
            self.populate_order_table()
            self.populate_file_table()
            self.stacked_widget.setCurrentWidget(self.order_page)
        elif 'browser' in btn_name:
            self.stacked_widget.setCurrentWidget(self.browser_page)
            self.webengine_view.setUrl(QUrl('http://kccrefinish.co.kr'))
        elif 'keyboard' in btn_name:
            pass

    def on_order_table_clicked(self, index):

        datum = index.data()
        logging.warning(f"datum:{datum}")

    def on_file_table_clicked(self, index):

        datum = index.data()
        logging.warning(f"datum:{datum}")

    def populate_order_table(self):

        order_model = OrderTableModel(self, self.db_session)
        self.order_table.setModel(order_model)

    def populate_file_table(self):

        file_model = FileTableModel(self, DOWNLOAD_PATH)
        self.file_table.setModel(file_model)

def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level='INFO', format=fmt_)

    app = QApplication(sys.argv)
    _ = MainWindow()
    app.exec_()


if __name__ == "__main__":
    main()
