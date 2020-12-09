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
from PyQt5.QtCore import Qt, QVariant, QAbstractTableModel
from PyQt5.QtWidgets import QApplication, QMainWindow, QHeaderView, QTableWidgetItem
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.Qt import QUrl
from PyQt5.QtGui import QIcon

from alfa_CR6_ui.keyboard import Keyboard                # pylint: disable=import-error
from alfa_CR6_backend.models import init_models, Order  # pylint: disable=import-error

DOWNLOAD_PATH = "/opt/alfa_cr6/data/kcc"
DB_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"

HERE = os.path.dirname(os.path.abspath(__file__))
KEYBOARD_PATH = os.path.join(HERE, '..', 'alfa_CR6_ui', 'keyboard')
IMAGES_PATH = os.path.join(HERE, '..', 'alfa_CR6_ui', 'images')


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
        self.header = ['icon', 'name', ]
        filter_text = parent.search_file_line.text()
        name_list_ = [p for p in os.listdir(path) if filter_text in p]
        icon_item = QTableWidgetItem()
        icon_item.setIcon(QIcon(os.path.join(IMAGES_PATH, 'green.png')))
        logging.warning(f"name_list_ :{name_list_ }")
        # ~ logging.warning(f"icon_ :{icon_ }")

        self.results = [[icon_item, p, ] for p in name_list_]


class OrderTableModel(Cr6TableModel):

    def __init__(self, parent, session, *args):
        super().__init__(parent, *args)
        self.header = ['order_nr', 'status', 'json_properties']
        filter_text = parent.search_order_line.text()
        if session:
            query_ = session.query(Order)
            query_ = query_.filter(Order.order_nr.contains(filter_text))
            query_ = query_.order_by(Order.order_nr.desc()).limit(100)
            self.results = [[o.order_nr, o.status, o.json_properties] for o in query_.all()]
        else:
            self.results = [[], ]


class MainWindow(QMainWindow):

    def __init__(self, parent=None):

        super().__init__(parent)
        loadUi("main_window.ui", self)

        self.webengine_view = QWebEngineView(self.browser_frame)
        self.webengine_view.setGeometry(0, 0, self.browser_frame.width(), self.browser_frame.height())
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

        self.keyboard = Keyboard(self, keyboard_path=KEYBOARD_PATH)
        self.keyboard.setGeometry(0, self.menu_frame.y() - self.keyboard.height(), self.menu_frame.width(), 256)

    def on_service_btn_group_clicked(self, btn):

        logging.warning(f"btn.objectName():{btn.objectName()}")
        self.stacked_widget.setCurrentWidget(self.browser_page)
        self.webengine_view.setUrl(QUrl('http://127.0.0.1:8080/service_page'))

    def on_menu_btn_group_clicked(self, btn):

        logging.warning(f"btn.objectName():{btn.objectName()}")
        btn_name = btn.objectName()
        if 'home' in btn_name:
            self.toggle_keyboard(on_off=False)
            self.stacked_widget.setCurrentWidget(self.home_page)
        elif 'order' in btn_name:
            self.toggle_keyboard(on_off=False)
            self.populate_order_table()
            self.populate_file_table()
            self.stacked_widget.setCurrentWidget(self.order_page)
        elif 'browser' in btn_name:
            self.toggle_keyboard(on_off=True)
            self.stacked_widget.setCurrentWidget(self.browser_page)
            self.webengine_view.setUrl(QUrl('http://kccrefinish.co.kr'))
        elif 'keyboard' in btn_name:
            self.toggle_keyboard()

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

    def toggle_keyboard(self, on_off=None):

        if on_off is None:
            on_off = not self.keyboard.isVisible()

        w = self.stacked_widget.currentWidget()
        if on_off and not self.keyboard.isVisible():
            self.keyboard.show()
            l = self.webengine_view
            l.resize(l.width(), l.height() - self.keyboard.height())
        elif not on_off and self.keyboard.isVisible():
            self.keyboard.hide()
            l = self.webengine_view
            l.resize(l.width(), l.height() + self.keyboard.height())


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level='INFO', format=fmt_)

    app = QApplication(sys.argv)
    _ = MainWindow()
    app.exec_()


if __name__ == "__main__":
    main()
