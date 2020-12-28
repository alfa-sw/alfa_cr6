# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module

import os
import sys
import logging
import json
import time
import traceback

from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, QVariant, QAbstractTableModel, QSize
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.Qt import QUrl
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtWidgets import (QApplication,
                             QMainWindow,
                             QHeaderView,
                             # ~ QInputDialog,
                             QPushButton,
                             QLabel,
                             QStyle,
                             QMessageBox,
                             QFrame)

from alfa_CR6_ui.keyboard import Keyboard
from alfa_CR6_backend.models import Order, Jar

HERE = os.path.dirname(os.path.abspath(__file__))
KEYBOARD_PATH = os.path.join(HERE, 'keyboard')
IMAGES_PATH = os.path.join(HERE, 'images')
UI_PATH = os.path.join(HERE, 'ui')

DOWNLOAD_PATH = "/opt/alfa_cr6/data/kcc"
KCC_URL = "http://kccrefinish.co.kr"


def tr_(s):
    return s


class BaseTableModel(QAbstractTableModel):

    def __init__(self, parent, *args):
        super().__init__(parent, *args)
        self.gray_icon = QPixmap(os.path.join(IMAGES_PATH, 'gray.png'))
        self.green_icon = QPixmap(os.path.join(IMAGES_PATH, 'green.png'))
        self.red_icon = QPixmap(os.path.join(IMAGES_PATH, 'red.png'))
        # ~ self.item_font = QFont('Times sans-serif', 32)
        self.results = [[], ]

    def rowCount(self, parent):
        logging.debug(f"parent:{parent}")
        return len(self.results)

    def columnCount(self, parent):
        logging.debug(f"parent:{parent}")
        ret = 0
        if self.results:
            ret = len(self.results[0])
        return ret

    def data(self, index, role):
        # ~ logging.warning(f"index, role:{index, role}")
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == 0:
            # ~ ret = "#FF6633"
            ret = self.new_icon.scaled(48, 48, Qt.KeepAspectRatio)
        # ~ elif role == Qt.SizeHintRole:
            # ~ ret = 32
        # ~ elif role == Qt.FontRole:
            # ~ ret = self.item_font
        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[col]
        return None


class FileTableModel(BaseTableModel):

    def __init__(self, parent, path, *args):
        super().__init__(parent, *args)
        self.header = ['delete', 'create order', 'file name', ]
        filter_text = parent.search_file_line.text()
        name_list_ = sorted([p for p in os.listdir(path) if filter_text in p][:100])
        self.results = [['', '', p, ] for p in name_list_]

    def remove_file(self, file_name):
        cmd_ = f'rm -f "{os.path.join(DOWNLOAD_PATH, file_name)}"'
        logging.warning(f"cmd_:{cmd_}")
        os.system(cmd_)

    def data(self, index, role):
        # ~ logging.warning(f"index, role:{index, role}")
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == 0:
            ret = self.parent().style().standardIcon(getattr(QStyle, 'SP_BrowserStop'))
        elif role == Qt.DecorationRole and index.column() == 1:
            ret = self.parent().style().standardIcon(getattr(QStyle, 'SP_FileDialogDetailedView'))
        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret


class OrderTableModel(BaseTableModel):

    def __init__(self, parent, session, *args):
        super().__init__(parent, *args)
        self.session = session
        self.header = ['delete', 'status', 'order_nr', 'source']
        filter_text = parent.search_order_line.text()
        
        if self.session:
            query_ = self.session.query(Order)
            query_ = query_.filter(Order.order_nr.contains(filter_text))
            query_ = query_.order_by(Order.order_nr.desc()).limit(100)
            self.results = [['', o.status, o.order_nr, o.description] for o in query_.all()]
        else:
            self.results = [[], ]

    def remove_order(self, order_nr):
        logging.warning(f"order_nr:{order_nr}, self.session:{self.session}")
        if self.session:
            order = self.session.query(Order).filter(Order.order_nr==order_nr).one()
            r = self.session.query(Jar).filter(Jar.order==order).delete()
            logging.warning(f"r:{r}")
            self.session.delete(order)
            self.session.commit()
            
    def data(self, index, role):
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == 0:
            ret = self.parent().style().standardIcon(getattr(QStyle, 'SP_BrowserStop'))
        if role == Qt.DecorationRole and index.column() == 1:
            datum = str(index.data()).upper()
            if 'DONE' in datum:
                ret = self.gray_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif 'ERR' in datum:
                ret = self.red_icon.scaled(32, 32, Qt.KeepAspectRatio)
            else:
                ret = self.green_icon.scaled(32, 32, Qt.KeepAspectRatio)

        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret


class ModalMessageBox(QMessageBox):   # pylint:  disable=too-many-instance-attributes,too-few-public-methods

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setStyleSheet("""
                QMessageBox {
                    font-size: 20px;
                    font-family: monospace;
                    border: 2px solid #999999; border-radius: 4px; background-color: #FEFEFE;
                    }
                """)
        # ~ QFrame { border: 1px solid #999999; border-radius: 4px; background-color: #FFFFEE;}
        # ~ QWidget {font-size: 24px; font-family: Times sans-serif;}
        # ~ QLabel { border-width: 0px; background-color: #FFFFFF;}
        # ~ QPushButton { background-color: #FFFFEE; border: 1px solid #999999; border-radius: 4px;}

        # ~ Qt::NonModal	0	The window is not modal and does not block input to other windows.
        # ~ Qt::WindowModal	1	The window is modal to a single window hierarchy and blocks input to its parent window, all grandparent windows, and all siblings of its parent and grandparent windows.
        # ~ Qt::ApplicationModal	2	The window is modal to the application and blocks input to all windows.
        self.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
        self.resize(800, 400)
        for i, b in enumerate(self.buttons()):
            b.setStyleSheet("""
                    QWidget {
                        font-size: 48px;
                        font-family: monospace;
                        }
                    """)
            if i == 0:
                b.setIcon(self.parent().style().standardIcon(getattr(QStyle, 'SP_DialogYesButton')))
            if i == 1:
                b.setIcon(self.parent().style().standardIcon(getattr(QStyle, 'SP_MessageBoxCritical')))

        self.setWindowModality(0)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint |
                            Qt.WindowStaysOnTopHint | Qt.X11BypassWindowManagerHint)



class InputDialog(QFrame):   # pylint:  disable=too-few-public-methods

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        loadUi(os.path.join(UI_PATH, "input_dialog.ui"), self)
        # ~ self.input_dialog.setWindowFlags(Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QWidget {background:#CCBBBBBB; font-size: 24px; font-family: Times sans-serif; border: 1px solid #999999; border-radius: 4px;}
            QPushButton { background-color: #F3F3F3F3;}
            QPushButton:pressed {background-color: #AAAAAA;}""")
        self.move(400, 200)

        green_icon = QPixmap(os.path.join(IMAGES_PATH, 'green.png'))
        red_icon = QPixmap(os.path.join(IMAGES_PATH, 'red.png'))

        self.ok_button.setIcon(QIcon(green_icon))
        self.esc_button.setIcon(QIcon(red_icon))
        self.ok_button.setAutoFillBackground(True)
        self.esc_button.setAutoFillBackground(True)
        self.hide()


class MainWindow(QMainWindow):     # pylint:  disable=too-many-instance-attributes

    def __init__(self, parent=None):

        from alfa_CR6_ui.debug_status_view import DebugStatusView       # pylint: disable=import-outside-toplevel

        super().__init__(parent)
        r = loadUi(os.path.join(UI_PATH, "transition.ui"), self)

        logging.warning(f"r:{r}, QIcon.themeSearchPaths():{QIcon.themeSearchPaths()}")
        logging.warning(f"QApplication.instance().style():{QApplication.instance().style()}")

        self.setStyleSheet("""
            QWidget {font-size: 24px; font-family: Times sans-serif;}
            QPushButton {background-color: #F3F3F3F3; border: 1px solid #999999; border-radius: 4px;}
            QPushButton:pressed {background-color: #AAAAAA;}""")

        self.webengine_view = QWebEngineView(self.browser_frame)
        self.webengine_view.setGeometry(0, 0, self.browser_frame.width(), self.browser_frame.height())

        QWebEngineProfile.defaultProfile().downloadRequested.connect(self.on_downloadRequested)

        self.order_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.file_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.order_table_view.clicked.connect(self.on_order_table_clicked)
        self.file_table_view.clicked.connect(self.on_file_table_clicked)

        self.menu_btn_group.buttonClicked.connect(self.on_menu_btn_group_clicked)
        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)
        self.action_btn_group.buttonClicked.connect(self.on_action_btn_group_clicked)
        self.refill_btn_group.buttonClicked.connect(self.on_refill_btn_group_clicked)

        self.search_order_btn.clicked.connect(self.populate_order_table)
        self.search_file_btn.clicked.connect(self.populate_file_table)

        self.search_order_line.textChanged.connect(self.populate_order_table)
        self.search_file_line. textChanged.connect(self.populate_file_table)
        self.search_order_table_last_time = 0
        self.search_file_table_last_time = 0

        self.showFullScreen()

        self.keyboard = Keyboard(self, keyboard_path=KEYBOARD_PATH)
        self.keyboard.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.keyboard.setGeometry(0, self.menu_frame.y() - self.keyboard.height(), self.menu_frame.width(), 256)

        self.debug_status_view = DebugStatusView(self)
        self.stacked_widget.addWidget(self.debug_status_view.main_frame)

        self.reserve_movie = QMovie(os.path.join(IMAGES_PATH, 'riserva.gif'))

        self.action_frame_map = self.create_action_pages()

        self.gray_icon = QPixmap(os.path.join(IMAGES_PATH, 'gray.png'))
        self.green_icon = QPixmap(os.path.join(IMAGES_PATH, 'green.png'))
        self.red_icon = QPixmap(os.path.join(IMAGES_PATH, 'red.png'))

        self.jar_icon_map = {k: QPixmap(os.path.join(IMAGES_PATH, p)) for k, p in (
            ("no", ""), ("green", "jar-green.png"), ("red", "jar-red.png"), ("blue", "jat-blue.png"))}

        for b in self.action_btn_group.buttons():
            # ~ logging.warning(f"b.objectName():{b.objectName()}")
            b.setStyleSheet("""QPushButton { background-color: #00FFFFFF; border: 0px;}""")

        for b in self.refill_btn_group.buttons():
            # ~ logging.warning(f"b.objectName():{b.objectName()}")
            b.setStyleSheet("""QPushButton { background-color: #00FFFFFF; border: 0px;}""")

        self.input_dialog = InputDialog(self)

    def create_action_pages(self, ):
        from functools import partial           # pylint: disable=import-outside-toplevel

        def action_(args):
            logging.warning(f"args:{args}")
            try:
                QApplication.instance().run_a_coroutine_helper(args[0], *args[1:])
            except Exception:                     # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        def show_val_(head_letter, bit_name, text, w):
            # ~ logging.warning(f"head_letter:{head_letter}, bit_name:{bit_name}, text:{text}, w:{w}")
            try:
                m = QApplication.instance().get_machine_head_by_letter(head_letter)
                if bit_name.lower() == 'container_presence':
                    val_ = m.status.get('container_presence')
                else:
                    val_ = m.jar_photocells_status.get(bit_name)

                pth_ = os.path.join(IMAGES_PATH, 'green.png') if val_ else os.path.join(IMAGES_PATH, 'gray.png')
                w.setText(f'<img widt="50" height="50" src="{pth_}" style="vertical-align:middle;">{tr_(text)}</img>')
            except Exception:                     # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        map_ = {
            self.action_01_btn: {
                'title': 'action 01 (head 1 or A)',
                'buttons': [
                    {'text': "Start input roller", 'action': partial(action_, ("single_move", 'A', {'Input_Roller': 1}))},
                    {'text': "Stop  input roller", 'action': partial(action_, ("single_move", 'A', {'Input_Roller': 0}))},
                    {'text': "Start input roller to photocell", 'action': partial(action_, ("single_move", 'A', {'Input_Roller': 2}))},
                    {'text': "move 01 02 ('IN -> A')", 'action': partial(action_, ("move_01_02", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'A', 'JAR_INPUT_ROLLER_PHOTOCELL', 'INPUT ROLLER PHOTOCELL')},
                    {'show_val': partial(show_val_, 'A', 'JAR_DETECTION_MICROSWITCH_1', 'MICROSWITCH 1')},
                    {'show_val': partial(show_val_, 'A', 'JAR_DETECTION_MICROSWITCH_2', 'MICROSWITCH 2')},
                ],
            },
            self.action_02_btn: {
                'title': 'action 02 (head 1 or A)',
                'buttons': [
                    {'text': "Start dispensing roller", 'action': partial(action_, ("single_move", 'A', {'Dispensing_Roller': 1}))},
                    {'text': "Stop  dispensing roller", 'action': partial(action_, ("single_move", 'A', {'Dispensing_Roller': 0}))},
                    {'text': "Start dispensing roller to photocell", 'action': partial(action_, ("single_move", 'A', {'Dispensing_Roller': 2}))},
                    {'text': "move 02 03 ('A -> B')", 'action': partial(action_, ("move_02_03", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'A', 'JAR_DISPENSING_POSITION_PHOTOCELL', 'DISPENSING POSITION PHOTOCELL')},
                    {'show_val': partial(show_val_, 'A', 'container_presence', 'CONTAINER PRESENCE')},
                ],
            },
            self.action_03_btn: {
                'title': 'action 03 (head 3 or B)',
                'buttons': [
                    {'text': "Start dispensing roller", 'action': partial(action_, ("single_move", 'B', {'Dispensing_Roller': 1}))},
                    {'text': "Stop  dispensing roller", 'action': partial(action_, ("single_move", 'B', {'Dispensing_Roller': 0}))},
                    {'text': "Start dispensing roller to photocell", 'action': partial(action_, ("single_move", 'B', {'Dispensing_Roller': 2}))},
                    {'text': "move 03 04 ('B -> C')", 'action': partial(action_, ("move_03_04", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'B', 'JAR_DISPENSING_POSITION_PHOTOCELL', 'DISPENSING POSITION PHOTOCELL')},
                    {'show_val': partial(show_val_, 'B', 'container_presence', 'CONTAINER PRESENCE')},
                ],
            },
            self.action_04_btn: {
                'title': 'action 04 (head 5 or C)',
                'buttons': [
                    {'text': "Start dispensing roller", 'action': partial(action_, ("single_move", 'C', {'Dispensing_Roller': 1}))},
                    {'text': "Stop  dispensing roller", 'action': partial(action_, ("single_move", 'C', {'Dispensing_Roller': 0}))},
                    {'text': "Start dispensing roller to photocell", 'action': partial(action_, ("single_move", 'C', {'Dispensing_Roller': 2}))},
                    {'text': "move 04 05 ('C -> UP')", 'action': partial(action_, ("move_04_05", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'C', 'JAR_DISPENSING_POSITION_PHOTOCELL', 'DISPENSING POSITION PHOTOCELL')},
                    {'show_val': partial(show_val_, 'C', 'container_presence', 'CONTAINER PRESENCE')},
                ],
            },
            self.action_05_btn: {
                'title': 'action 05 (head 5, 6 or C, D)',
                'buttons': [
                    {'text': "Start lifter roller CW", 'action': partial(action_, ("single_move", 'C', {'Lifter_Roller': 2}))},
                    {'text': "Start lifter roller CCW", 'action': partial(action_, ("single_move", 'C', {'Lifter_Roller': 3}))},
                    {'text': "Stop  lifter roller", 'action': partial(action_, ("single_move", 'C', {'Lifter_Roller': 0}))},

                    {'text': "Start lifter up", 'action': partial(action_, ("single_move", 'D', {'Lifter': 1}))},
                    {'text': "Start lifter down", 'action': partial(action_, ("single_move", 'D', {'Lifter': 2}))},
                    {'text': "Stop  lifter", 'action': partial(action_, ("single_move", 'D', {'Lifter': 0}))},

                    {'text': "move 04 05 ('C -> UP')", 'action': partial(action_, ("move_04_05", ))},
                    {'text': "move 05 06 ('UP -> DOWN')", 'action': partial(action_, ("move_05_06", ))},
                    {'text': "move 06 07 ('DOWN -> D')", 'action': partial(action_, ("move_06_07", ))},

                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'C', 'JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', 'LIFTER ROLLER PHOTOCELL')},
                    {'show_val': partial(show_val_, 'D', 'LOAD_LIFTER_DOWN_PHOTOCELL', 'LIFTER DOWN PHOTOCELL')},
                    {'show_val': partial(show_val_, 'D', 'LOAD_LIFTER_UP_PHOTOCELL', 'LIFTER UP PHOTOCELL')},
                ],
            },
            self.action_06_btn: {
                'title': 'action 06 (head 6 or D)',
                'buttons': [
                    {'text': "Start dispensing roller", 'action': partial(action_, ("single_move", 'D', {'Dispensing_Roller': 1}))},
                    {'text': "Stop  dispensing roller", 'action': partial(action_, ("single_move", 'D', {'Dispensing_Roller': 0}))},
                    {'text': "Start dispensing roller to photocell", 'action': partial(action_, ("single_move", 'D', {'Dispensing_Roller': 2}))},
                    {'text': "move 07 08 ('D -> E')", 'action': partial(action_, ("move_07_08", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'D', 'JAR_DISPENSING_POSITION_PHOTOCELL', 'DISPENSING POSITION PHOTOCELL')},
                    {'show_val': partial(show_val_, 'D', 'container_presence', 'CONTAINER PRESENCE')},
                ],
            },
            self.action_07_btn: {
                'title': 'action 07 (head 4 or E)',
                'buttons': [
                    {'text': "Start dispensing roller", 'action': partial(action_, ("single_move", 'E', {'Dispensing_Roller': 1}))},
                    {'text': "Stop  dispensing roller", 'action': partial(action_, ("single_move", 'E', {'Dispensing_Roller': 0}))},
                    {'text': "Start dispensing roller to photocell", 'action': partial(action_, ("single_move", 'E', {'Dispensing_Roller': 2}))},
                    {'text': "move 08 09 ('E -> F')", 'action': partial(action_, ("move_08_09", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'E', 'JAR_DISPENSING_POSITION_PHOTOCELL', 'DISPENSING POSITION PHOTOCELL')},
                    {'show_val': partial(show_val_, 'E', 'container_presence', 'CONTAINER PRESENCE')},
                ],
            },
            self.action_08_btn: {
                'title': 'action 08 (head 2 or F)',
                'buttons': [
                    {'text': "Start dispensing roller", 'action': partial(action_, ("single_move", 'F', {'Dispensing_Roller': 1}))},
                    {'text': "Stop  dispensing roller", 'action': partial(action_, ("single_move", 'F', {'Dispensing_Roller': 0}))},
                    {'text': "Start dispensing roller to photocell", 'action': partial(action_, ("single_move", 'F', {'Dispensing_Roller': 2}))},
                    {'text': "move 09 10 ('F -> DOWN')", 'action': partial(action_, ("move_09_10", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'F', 'JAR_DISPENSING_POSITION_PHOTOCELL', 'DISPENSING POSITION PHOTOCELL')},
                    {'show_val': partial(show_val_, 'F', 'container_presence', 'CONTAINER PRESENCE')},
                ],
            },
            self.action_09_btn: {
                'title': 'action 09 (head 2 or F)',
                'buttons': [
                    {'text': "Start lifter roller CW", 'action': partial(action_, ("single_move", 'F', {'Lifter_Roller': 2}))},
                    {'text': "Start lifter roller CCW", 'action': partial(action_, ("single_move", 'F', {'Lifter_Roller': 3}))},
                    {'text': "Stop  lifter roller", 'action': partial(action_, ("single_move", 'F', {'Lifter_Roller': 0}))},

                    {'text': "Start lifter up", 'action': partial(action_, ("single_move", 'F', {'Lifter': 1}))},
                    {'text': "Start lifter down", 'action': partial(action_, ("single_move", 'F', {'Lifter': 2}))},
                    {'text': "Stop  lifter", 'action': partial(action_, ("single_move", 'F', {'Lifter': 0}))},

                    {'text': "move 09 10 ('F -> DOWN')", 'action': partial(action_, ("move_09_10", ))},
                    {'text': "move 10 11 ('DOWN -> UP -> OUT')", 'action': partial(action_, ("move_10_11", ))},

                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'F', 'JAR_OUTPUT_ROLLER_PHOTOCELL', 'LIFTER ROLLER PHOTOCELL')},
                    {'show_val': partial(show_val_, 'F', 'UNLOAD_LIFTER_DOWN_PHOTOCELL', 'LIFTER DOWN PHOTOCELL')},
                    {'show_val': partial(show_val_, 'F', 'UNLOAD_LIFTER_UP_PHOTOCELL', 'LIFTER UP PHOTOCELL')},
                ],
            },
            self.action_10_btn: {
                'title': 'action 10 (head 2 or F)',
                'buttons': [
                    {'text': "Start output roller", 'action': partial(action_, ("single_move", 'F', {'Output_Roller': 3}))},
                    {'text': "Stop  output roller", 'action': partial(action_, ("single_move", 'F', {'Output_Roller': 0}))},
                    {'text': "Start output roller to photocell dark", 'action': partial(action_, ("single_move", 'F', {'Output_Roller': 1}))},
                    {'text': "Start output roller to photocell light", 'action': partial(action_, ("single_move", 'F', {'Output_Roller': 2}))},
                    {'text': "move 11 12 ('UP -> OUT')", 'action': partial(action_, ("move_11_12", ))},
                    {'text': "Back to Home Page", 'action': partial(self.stacked_widget.setCurrentWidget, self.home_page)},
                ],
                'labels': [
                    {'show_val': partial(show_val_, 'F', 'JAR_OUTPUT_ROLLER_PHOTOCELL', 'OUTPUT ROLLER PHOTOCELL')},
                ],
            },
        }

        action_frame_map = {}
        for btn, val in map_.items():
            w = QFrame(self)
            loadUi(os.path.join(UI_PATH, "action_frame.ui"), w)
            w.setStyleSheet("""
                QFrame { border: 1px solid #999999; border-radius: 4px; background-color: #FEFEFE;}
                QWidget {font-size: 24px; font-family: Times sans-serif;}
                QLabel { border-width: 0px; background-color: #FFFFFF;}
                QPushButton { background-color: #EEEEEE; border: 1px solid #999999; border-radius: 4px;}
                QPushButton:pressed {background-color: #AAAAAA;}
                """)

            w.action_title_label.setText(tr_(val['title']))
            for b in val['buttons']:
                i = QPushButton(tr_(b['text']), w)
                i.setFixedHeight(50)
                if b.get('action'):
                    i.clicked.connect(b.get('action'))
                w.action_buttons_layout.addWidget(i)

            for l in val['labels']:

                i = QLabel(w)
                i.setTextFormat(Qt.RichText)
                if l.get('show_val'):
                    setattr(i, 'show_val', l.get('show_val'))
                w.action_labels_layout.addWidget(i)

            self.stacked_widget.addWidget(w)
            action_frame_map[btn] = w

        return action_frame_map

    def on_downloadRequested(self, download):        # pylint: disable=no-self-use

        logging.warning(f"download:{download}.")

        if not os.path.exists(DOWNLOAD_PATH):
            os.makedirs(DOWNLOAD_PATH)
        full_name = DOWNLOAD_PATH + '/' + time.asctime().replace(":", "_").replace(" ", "_") + '.json'
        download.setPath(full_name)
        download.accept()
        # ~ self.download_callback(full_name)

    def get_stacked_widget(self):
        return self.stacked_widget

    def on_service_btn_group_clicked(self, btn):

        btn_name = btn.objectName()

        try:
            service_page_urls = ["http://{}:{}/service_page/".format(i[0], i[2])
                                 for i in QApplication.instance().settings.MACHINE_HEAD_IPADD_PORTS_LIST]

            map_ = {
                self.service_1_btn: service_page_urls[0],
                self.service_2_btn: service_page_urls[1],
                self.service_3_btn: service_page_urls[2],
                self.service_4_btn: service_page_urls[3],
                self.service_5_btn: service_page_urls[4],
                self.service_6_btn: service_page_urls[5],
                self.service_0_btn: "http://127.0.0.1:8080/service_page/",
            }
            self.webengine_view.setUrl(QUrl(map_[btn]))
            self.stacked_widget.setCurrentWidget(self.browser_page)

        except Exception as e:                     # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.show_alert_dialog(
                f"btn_namel:{btn_name} exception:{e}", title="ERROR", callback=None, args=None)

    def on_menu_btn_group_clicked(self, btn):

        btn_name = btn.objectName()

        try:

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
                self.webengine_view.setUrl(QUrl(KCC_URL))
            elif 'keyboard' in btn_name:
                self.toggle_keyboard()
            elif 'global_status' in btn_name:
                self.stacked_widget.setCurrentWidget(self.debug_status_view.main_frame)

        except Exception as e:                      # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.show_alert_dialog(
                f"btn_namel:{btn_name} exception:{e}", title="ERROR", callback=None, args=None)

    def on_action_btn_group_clicked(self, btn):

        btn_name = btn.objectName()
        try:
            if 'feed' in btn_name:
                QApplication.instance().run_a_coroutine_helper('move_00_01')
            elif 'deliver' in btn_name:
                QApplication.instance().run_a_coroutine_helper('move_12_00')
            elif 'freeze_carousel' in btn_name:
                msg_ = "confirm unfreezing carousel?" if QApplication.instance().carousel_frozen else "confirm freezing carousel?"
                self.show_input_dialog(icon_name=None, message=msg_, content=None,
                                       ok_callback=QApplication.instance().toggle_freeze_carousel)
            elif 'action_' in btn_name:
                self.stacked_widget.setCurrentWidget(self.action_frame_map[btn])
            for i in QApplication.instance().machine_head_dict.keys():
                self.update_status_data(i)
        except Exception as e:                      # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.show_alert_dialog(
                f"btn_namel:{btn_name} exception:{e}", title="ERROR", callback=None, args=None)

    def on_refill_btn_group_clicked(self, btn):

        map_ = [
            self.refill_1_btn,
            self.refill_2_btn,
            self.refill_3_btn,
            self.refill_4_btn,
            self.refill_5_btn,
            self.refill_6_btn,
        ]
        try:
            self.show_reserve(map_.index(btn))
        except Exception as e:                      # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.show_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None)

    def on_order_table_clicked(self, index):            # pylint: disable=no-self-use

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            order_nr = model.results[row][2]
            logging.warning(f"row:{row}, col:{col}, order_nr:{order_nr}")
            if col == 0:  # delete
                def cb():
                    model.remove_order(order_nr)
                    self.populate_order_table()

                self.show_input_dialog(icon_name='SP_MessageBoxCritical',
                                       message=tr_("confirm deleting order and related jars?"),
                                       content=order_nr, ok_callback=cb)

        except Exception as e:                      # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.show_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None)

    def on_file_table_clicked(self, index):             # pylint: disable=no-self-use

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            file_name = model.results[row][2]
            logging.warning(f"row:{row}, col:{col}, file_name:{file_name}")
            if col == 0:  # delete
                def cb():
                    model.remove_file(file_name)
                    self.populate_file_table()

                self.show_input_dialog(icon_name='SP_MessageBoxCritical',
                                       message="confirm deleting file?",
                                       content=file_name, ok_callback=cb)

            elif col == 1:  # create order
                def cb():
                    n = int(self.input_dialog.content_container.toPlainText())
                    logging.warning(f"n:{n}")
                    QApplication.instance().create_order(os.path.join(DOWNLOAD_PATH, file_name), json_schema_name="KCC", n_of_jars=n)
                    self.populate_order_table()

                self.show_input_dialog(
                    message=f'confirm creating order from:\n "{file_name}"? \n Please, insert below the number of jars.',
                    content="<span align='center'>1</span>",
                    ok_callback=cb)

            elif col == 2:  # file name
                content = '{}'
                with open(os.path.join(DOWNLOAD_PATH, file_name)) as f:
                    content = f.read(3000)
                    try:
                        content = json.dumps(json.loads(content), indent=2)
                    except Exception:                     # pylint: disable=broad-except
                        logging.error(traceback.format_exc())

                self.show_input_dialog(icon_name='SP_MessageBoxInformation', message=file_name, content=content)
        except Exception as e:                      # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.show_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None)

    def populate_order_table(self):
        logging.warning("")
        t = time.time()
        if t - self.search_order_table_last_time > 0.1:
            self.search_order_table_last_time = t
            try:
                db_session = QApplication.instance().db_session
                order_model = OrderTableModel(self, db_session)
                self.order_table_view.setModel(order_model)
            except Exception:                     # pylint: disable=broad-except
                logging.error(traceback.format_exc())

    def populate_file_table(self):
        logging.warning("")
        t = time.time()
        if t - self.search_file_table_last_time > 0.1:
            self.search_file_table_last_time = t
            try:
                file_model = FileTableModel(self, DOWNLOAD_PATH)
                self.file_table_view.setModel(file_model)
            except Exception:                     # pylint: disable=broad-except
                logging.error(traceback.format_exc())

    def toggle_keyboard(self, on_off=None):

        if on_off is None:
            on_off = not self.keyboard.isVisible()

        if on_off and not self.keyboard.isVisible():
            self.keyboard.show()
            ls = [self.webengine_view, self.order_h_layout_widget]
            for l in ls:
                l.resize(l.width(), l.height() - self.keyboard.height())
        elif not on_off and self.keyboard.isVisible():
            self.keyboard.hide()
            ls = [self.webengine_view, self.order_h_layout_widget]
            for l in ls:
                l.resize(l.width(), l.height() + self.keyboard.height())

    def update_status_data(self, head_index, _=None):

        try:
            self.debug_status_view.update_status()

            status = QApplication.instance().machine_head_dict[head_index].status

            map_ = [
                self.service_1_btn,
                self.service_2_btn,
                self.service_3_btn,
                self.service_4_btn,
                self.service_5_btn,
                self.service_6_btn,
            ]
            map_[head_index].setText(status['status_level'])

            for action_frame in self.action_frame_map.values():
                for i in range(action_frame.action_labels_layout.count()):
                    lbl = action_frame.action_labels_layout.itemAt(i).widget()
                    if lbl.isVisible() and hasattr(lbl, 'show_val'):
                        getattr(lbl, 'show_val')(lbl)

            for action_frame in self.action_frame_map.values():
                def _get_status_level(head_letter):
                    return QApplication.instance().get_machine_head_by_letter(head_letter).status.get('status_level')
                if action_frame.isVisible():
                    action_frame.status_A_label.setText(tr_(f"{_get_status_level('A')}"))
                    action_frame.status_B_label.setText(tr_(f"{_get_status_level('B')}"))
                    action_frame.status_C_label.setText(tr_(f"{_get_status_level('C')}"))
                    action_frame.status_D_label.setText(tr_(f"{_get_status_level('D')}"))
                    action_frame.status_E_label.setText(tr_(f"{_get_status_level('E')}"))
                    action_frame.status_F_label.setText(tr_(f"{_get_status_level('F')}"))

            def set_pixmap_by_photocells(lbl, head_letter, bit_name):
                m = QApplication.instance().get_machine_head_by_letter(head_letter)
                f = m.jar_photocells_status.get(bit_name[0])
                pixmap = self.jar_icon_map['green'].scaled(
                    75, 75, Qt.KeepAspectRatio) if f else self.jar_icon_map['green'].scaled(0, 0)
                lbl.setPixmap(pixmap)
                lbl.show()

            set_pixmap_by_photocells(self.STEP_01_label, 'A', ('JAR_INPUT_ROLLER_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_02_label, 'A', ('JAR_DISPENSING_POSITION_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_03_label, 'B', ('JAR_DISPENSING_POSITION_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_04_label, 'C', ('JAR_DISPENSING_POSITION_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_05_label, 'D', ('LOAD_LIFTER_UP_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_06_label, 'D', ('LOAD_LIFTER_DOWN_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_07_label, 'D', ('JAR_DISPENSING_POSITION_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_08_label, 'E', ('JAR_DISPENSING_POSITION_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_09_label, 'F', ('JAR_DISPENSING_POSITION_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_10_label, 'F', ('UNLOAD_LIFTER_DOWN_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_11_label, 'F', ('UNLOAD_LIFTER_UP_PHOTOCELL',))
            set_pixmap_by_photocells(self.STEP_12_label, 'F', ('JAR_OUTPUT_ROLLER_PHOTOCELL',))

        except Exception:                     # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def show_reserve(self, head_index, flag=None):

        map_ = [
            self.reserve_1_label,
            self.reserve_2_label,
            self.reserve_3_label,
            self.reserve_4_label,
            self.reserve_5_label,
            self.reserve_6_label,
        ]

        if flag is None:
            flag = not map_[head_index].isVisible()

        l = map_[head_index]
        logging.warning(f"head_index:{head_index}, flag:{flag}, l:{l}.")

        if flag:
            l.setMovie(self.reserve_movie)
            self.reserve_movie.start()
            l.show()
        else:
            l.setText("")
            l.hide()

    def show_carousel_frozen(self, flag):
        if flag:
            self.freeze_carousel_btn.setText(tr_("Carousel Frozen"))
            self.freeze_carousel_btn.setIcon(QIcon(self.red_icon))
            self.freeze_carousel_btn.setStyleSheet("background-color: #00FFFFFF; color: #990000")
        else:
            self.freeze_carousel_btn.setText(tr_("Carousel OK"))
            self.freeze_carousel_btn.setIcon(QIcon(self.green_icon))
            self.freeze_carousel_btn.setStyleSheet("background-color: #00FFFFFF; color: #004400")

    def show_input_dialog(self, icon_name=None, message=None, content=None, ok_callback=None):

        # ~ 'SP_MessageBoxCritical',
        # ~ 'SP_MessageBoxInformation',
        # ~ 'SP_MessageBoxQuestion',
        # ~ 'SP_MessageBoxWarning',

        if icon_name is None:
            icon_ = self.style().standardIcon(getattr(QStyle, "SP_MessageBoxWarning"))
        else:
            icon_ = self.style().standardIcon(getattr(QStyle, icon_name))
        self.input_dialog.icon_label.setPixmap(icon_.pixmap(QSize(64, 64)))

        if message is None:
            self.input_dialog.message_label.setText('')
        else:
            self.input_dialog.message_label.setText(tr_(message))

        if content is None:
            self.input_dialog.content_container.setText('')
        else:
            self.input_dialog.content_container.setText(str(content))

        self.input_dialog.ok_button.clicked.disconnect()
        self.input_dialog.ok_button.clicked.connect(self.input_dialog.hide)
        if ok_callback is not None:
            self.input_dialog.ok_button.clicked.connect(ok_callback)

        self.input_dialog.show()

    def show_alert_dialog(self, msg, title="ALERT", callback=None, args=None):

        logging.warning(msg)

        ret = False

        t = time.asctime()
        msg = "[{}]\n\n{}\n\n".format(t, msg)

        _msgbox = ModalMessageBox(parent=self)

        def button_clicked(btn):
            logging.warning(f"btn:{btn}, btn.text():{btn.text()}")
            if "ok" in btn.text().lower() and callback:
                args_ = args if args is not None else []
                callback(*args_)

        _msgbox.buttonClicked.connect(button_clicked)

        _msgbox.setIcon(QMessageBox.Information)
        _msgbox.setText(msg)
        _msgbox.setWindowTitle(title)
        _msgbox.show()

        return ret

    def show_frozen_dialog(self, msg, title="ALERT"):

        logging.info(msg)

        msg = f'ALERT: carousel is frozen in {msg}! hit "OK" to unfreeze it'

        t = time.asctime()
        msg = "[{}] {}".format(t, msg)

        _msgbox = ModalMessageBox(parent=self)

        def button_clicked(btn):
            logging.warning(f"btn:{btn}, btn.text():{btn.text()}")
            if "ok" in btn.text().lower():
                QApplication.instance().freeze_carousel(False)

        _msgbox.buttonClicked.connect(button_clicked)

        _msgbox.setIcon(QMessageBox.Critical)
        _msgbox.setText(msg)
        _msgbox.setWindowTitle(title)
        _msgbox.show()


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level='INFO', format=fmt_)

    from alfa_CR6_backend.cr6 import CR6_application       # pylint: disable=import-outside-toplevel

    app = CR6_application(MainWindow, sys.argv)
    app.exec_()


if __name__ == "__main__":
    main()
