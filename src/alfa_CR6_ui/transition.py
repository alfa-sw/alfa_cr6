# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods

import os
import sys
import logging
import json
import time
import traceback
from functools import partial

from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, QVariant, QAbstractTableModel, QSize
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile
from PyQt5.Qt import QUrl
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QHeaderView,
    # ~ QInputDialog,
    QPushButton,
    QLabel,
    QStyle,
    QMessageBox,
    QFrame,
    QTableWidgetItem,
    QComboBox,
)

from alfa_CR6_ui.keyboard import Keyboard
from alfa_CR6_backend.models import Order, Jar, decompile_barcode
from alfa_CR6_backend.dymo_printer import dymo_print

HERE = os.path.dirname(os.path.abspath(__file__))
KEYBOARD_PATH = os.path.join(HERE, "keyboard")
IMAGES_PATH = os.path.join(HERE, "images")
UI_PATH = os.path.join(HERE, "ui")

WEBENGINE_DOWNLOAD_PATH = "/opt/alfa_cr6/data/kcc"
WEBENGINE_CUSTOMER_URL = "http://kccrefinish.co.kr/"
WEBENGINE_CACHE_PATH = "/opt/alfa_cr6/data/webengine"


def tr_(s):
    return s


class BaseTableModel(QAbstractTableModel):
    def __init__(self, parent, *args):

        super().__init__(parent, *args)
        self.gray_icon = QPixmap(os.path.join(IMAGES_PATH, "gray.png"))
        self.green_icon = QPixmap(os.path.join(IMAGES_PATH, "green.png"))
        self.red_icon = QPixmap(os.path.join(IMAGES_PATH, "red.png"))
        self.yellow_icon = QPixmap(os.path.join(IMAGES_PATH, "yellow.png"))
        self.blue_icon = QPixmap(os.path.join(IMAGES_PATH, "blue.png"))

        self.add_icon = QPixmap(os.path.join(IMAGES_PATH, "add.png"))
        self.edit_icon = QPixmap(os.path.join(IMAGES_PATH, "edit.png"))

        # ~ self.item_font = QFont('Times sans-serif', 32)
        self.results = [[]]

    def rowCount(self, parent=None):
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
        self.header = [tr_("delete"), tr_("view"), tr_("create order"), tr_("file name")]
        filter_text = parent.search_file_line.text()
        name_list_ = [p for p in os.listdir(path) if filter_text in p][:101]
        if len(name_list_) >= 100:
            self.open_alert_dialog(
                tr_("Too many files saved and not used. Please delete unused files."),
                title="ERROR",
            )
        name_list_.sort(reverse=True)
        self.results = [["", "", "", p] for p in name_list_]

    def remove_file(self, file_name):  # pylint: disable=no-self-use
        cmd_ = f'rm -f "{os.path.join(WEBENGINE_DOWNLOAD_PATH, file_name)}"'
        logging.warning(f"cmd_:{cmd_}")
        os.system(cmd_)

    def data(self, index, role):
        # ~ logging.warning(f"index, role:{index, role}")
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == 0:
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_BrowserStop"))
        elif role == Qt.DecorationRole and index.column() == 1:  # view
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_FileDialogInfoView"))
        elif role == Qt.DecorationRole and index.column() == 2:  # create order
            ret = (
                self.parent()
                .style()
                .standardIcon(getattr(QStyle, "SP_FileDialogDetailedView"))
            )
        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret


class OrderTableModel(BaseTableModel):

    def __init__(self, parent, session, *args):
        super().__init__(parent, *args)
        self.session = session
        self.header = [tr_("delete"), tr_("edit"), tr_("status"), tr_("order nr.")]
        filter_text = parent.search_order_line.text()

        if self.session:
            query_ = self.session.query(Order)
            query_ = query_.filter(Order.order_nr.contains(filter_text))
            # ~ query_ = query_.order_by(Order.order_nr.desc())
            query_ = query_.limit(100)
            self.results = [
                ["", "", o.status, o.order_nr] for o in query_.all()
            ]
            self.results.sort()

        else:
            self.results = [[]]

    def remove_order(self, order_nr):
        logging.warning(f"order_nr:{order_nr}, self.session:{self.session}")
        if self.session:
            order = self.session.query(Order).filter(Order.order_nr == order_nr).one()

            for j in self.session.query(Jar).filter(Jar.order == order).all():
                self.session.delete(j)
                QApplication.instance().delete_jar_runner(j.barcode)

            self.session.delete(order)
            self.session.commit()

    def data(self, index, role):
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == 0:
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_BrowserStop"))
        elif role == Qt.DecorationRole and index.column() == 1:  # edit
            ret = self.edit_icon.scaled(32, 32, Qt.KeepAspectRatio)
        if role == Qt.DecorationRole and index.column() == 2:  # status
            datum = str(index.data()).upper()
            if "DONE" in datum:
                ret = self.gray_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif "ERR" in datum:
                ret = self.red_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif "PARTIAL" in datum:
                ret = self.blue_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif "PROGRESS" in datum:
                ret = self.yellow_icon.scaled(32, 32, Qt.KeepAspectRatio)
            else:
                ret = self.green_icon.scaled(32, 32, Qt.KeepAspectRatio)

        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret


class JarTableModel(BaseTableModel):

    def __init__(self, parent, session, *args):

        super().__init__(parent, *args)
        self.session = session
        self.header = [tr_("delete"), tr_("view"), tr_("status"), tr_("barcode")]
        filter_text = parent.search_jar_line.text()
        order_nr = parent.order_table_selected_order_nr

        if self.session:
            query_ = self.session.query(Jar)
            if filter_text:
                query_ = query_.filter(Jar.status.contains(filter_text))
            if order_nr is not None:
                order = self.session.query(Order).filter(Order.order_nr == order_nr).first()
                if order:
                    query_ = query_.filter(Jar.order == order)
            query_ = query_.order_by(Jar.index.desc()).limit(100)
            self.results = [
                ["", "", o.status, o.barcode] for o in query_.all()
            ]
        else:
            self.results = [[]]

    def remove_jar(self, barcode):
        order_nr, index = decompile_barcode(barcode)
        if self.session and order_nr and index >= 0:
            order = self.session.query(Order).filter(Order.order_nr == order_nr).one()

            query_ = self.session.query(Jar)
            query_ = query_.filter(Jar.order == order)
            query_ = query_.filter(Jar.index == index)
            r = query_.delete()
            logging.warning(f"r:{r}")
            self.session.commit()

            QApplication.instance().delete_jar_runner(barcode)

    def data(self, index, role):
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == 0:
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_BrowserStop"))
        elif role == Qt.DecorationRole and index.column() == 1:  # view
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_FileDialogInfoView"))
        if role == Qt.DecorationRole and index.column() == 2:  # barcode
            datum = str(index.data()).upper()
            if "DONE" in datum:
                ret = self.gray_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif "ERR" in datum:
                ret = self.red_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif "PROGRESS" in datum:
                ret = self.yellow_icon.scaled(32, 32, Qt.KeepAspectRatio)
            else:
                ret = self.green_icon.scaled(32, 32, Qt.KeepAspectRatio)

        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret


class ModalMessageBox(QMessageBox):  # pylint:disable=too-many-instance-attributes

    def __init__(self, msg="", title="", parent=None, ok_callback=None, ok_callback_args=None):   # pylint: disable=too-many-arguments
        super().__init__(parent=parent)

        self.ok_callback = ok_callback
        self.ok_callback_args = ok_callback_args

        self.setStyleSheet(
            """
                QMessageBox {
                    font-size: 20px;
                    font-family: monospace;
                    border: 2px solid #999999; border-radius: 4px; background-color: #FEFEFE;
                    }
                """
        )
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
            b.setStyleSheet(
                """
                    QWidget {
                        font-size: 48px;
                        font-family: monospace;
                        }
                    """
            )
            if i == 0:
                b.setIcon(
                    self.parent()
                    .style()
                    .standardIcon(getattr(QStyle, "SP_DialogYesButton"))
                )
            if i == 1:
                b.setIcon(
                    self.parent()
                    .style()
                    .standardIcon(getattr(QStyle, "SP_MessageBoxCritical"))
                )

        self.setWindowModality(0)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.X11BypassWindowManagerHint
        )

        if self.ok_callback:
            def on_button_clicked(btn):
                # ~ logging.warning(f"btn.objectName():{btn.objectName()}")
                # ~ if "ok" in btn.objectName().lower():
                logging.warning(f"btn:{btn}, btn.text():{btn.text()}")
                if "ok" in btn.text().lower():
                    args_ = self.ok_callback_args if self.ok_callback_args is not None else []
                    self.ok_callback(*args_)

            self.buttonClicked.connect(on_button_clicked)

        logging.warning(msg)

        t = time.asctime()
        msg = "[{}]\n\n{}\n\n".format(t, msg)

        self.setIcon(QMessageBox.Information)
        self.setText(msg)
        self.setWindowTitle(title)
        self.show()


class BaseDialog(QFrame):

    ui_file_name = ""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        loadUi(os.path.join(UI_PATH, self.ui_file_name), self)

        self.setStyleSheet(
            """
            QWidget {background:#CCBBBBBB; font-size: 24px; font-family: Times sans-serif; border: 1px solid #999999; border-radius: 4px;}
            QLabel {border: 0px;}
            QLineEdit {background:#FFFFAA; }
            QPushButton { background-color: #F3F3F3F3;}
            QPushButton:pressed {background-color: #AAAAAA;}"""
        )
        self.move(440, 100)
        # ~ self.resize(1080, 575)

        self.green_icon = QPixmap(os.path.join(IMAGES_PATH, "green.png"))
        self.red_icon = QPixmap(os.path.join(IMAGES_PATH, "red.png"))
        self.remove_icon = QPixmap(os.path.join(IMAGES_PATH, "remove.png"))
        self.add_icon = QPixmap(os.path.join(IMAGES_PATH, "add.png"))

        self.ok_button.setIcon(QIcon(self.green_icon))
        self.esc_button.setIcon(QIcon(self.red_icon))
        self.ok_button.setAutoFillBackground(True)
        self.esc_button.setAutoFillBackground(True)
        self.hide()


class EditDialog(BaseDialog):

    ui_file_name = "edit_dialog.ui"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.ok_button.clicked.connect(self.hide)
        self.ok_button.clicked.connect(self.save)
        self.set_item_btn.clicked.connect(self.on_set_item_clicked)
        self.add_item_btn.clicked.connect(self.on_add_item_clicked)
        self.formula_table.clicked.connect(self.on_formula_table_clicked)

        self.remove_item_btn.setIcon(QIcon(self.remove_icon))
        self.add_item_btn.setIcon(QIcon(self.add_icon))

        self.remove_item_btn.setText(tr_("remove\nselected"))
        self.add_item_btn.setText(tr_("add a\nnew one"))
        self.order_nr_lbl.setText(tr_("order n.:"))
        self.size_lbl.setText(tr_("size:"))
        self.pigment_lbl.setText(tr_("pigment:"))
        self.quantity_lbl.setText(tr_("quantity (gr):"))
        self.edit_item_group_box.setTitle(tr_("edit selected item:"))

        pigment_names = [
            'KB10',
            'KM702',
            'KA69F',
            'KM816',
            'KM814',
            'KM200',
            'KM302',
            'KM605',
            'KM900',
            'KM101',
            'KM600',
        ]
        self.pigment_combo.addItems(pigment_names)

    def on_set_item_clicked(self):

        try:
            pigment_name = self.pigment_line_edit.text()
            quantity = float(self.quantity_line_edit.text())
            logging.warning(f"pigment_name:{pigment_name}, quantity:{quantity}.")

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None
            )

    def on_add_item_clicked(self):

        try:
            pigment_name = self.pigment_line_edit.text()
            quantity = float(self.quantity_line_edit.text())
            logging.warning(f"pigment_name:{pigment_name}, quantity:{quantity}.")

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None
            )

    def on_formula_table_clicked(self, index):

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            row = index.row()
            values_ = [self.formula_table.item(row, col).data(Qt.DisplayRole) for col in range(3)]
            logging.warning(f"row:{row}, values_:{values_}")

            self.pigment_line_edit.setText(str(values_[0]))
            self.quantity_line_edit.setText(str(values_[1]))
            # ~ self.pigment_combo.

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None
            )

    def show_dialog(self, order_nr):   # pylint: disable=too-many-arguments

        order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).one()

        properties = json.loads(order.json_properties)
        logging.warning(f"properties:{properties}")

        size = properties.get('size(cc)')
        ingredients = properties.get('ingredients')
        content = "\n".join([f"{k}:{v}" for k, v in properties.get("meta", {}).items()])

        self.size_line_edit.setText(str(size))
        self.meta_text_edit.setText(content)
        self.order_nr_view_lbl.setText(str(order_nr))

        self.formula_table.clearContents()
        self.formula_table.setRowCount(len(ingredients))
        self.formula_table.setColumnCount(3)

        for row, item_ in enumerate(ingredients):
            self.formula_table.setItem(row, 0, QTableWidgetItem(str(item_['pigment_name'])))
            self.formula_table.setItem(row, 1, QTableWidgetItem(str(item_['weight(g)'])))
            self.formula_table.setItem(row, 2, QTableWidgetItem(str(item_['description'])))

        self.move(440, 10)

        self.show()

    def save(self):   # pylint: disable=too-many-arguments

        logging.warning(f"self:{self}")


class InputDialog(BaseDialog):

    ui_file_name = "input_dialog.ui"

    def show_dialog(self, icon_name=None, message=None, content=None, ok_cb=None, ok_cb_args=None):   # pylint: disable=too-many-arguments

        # ~ 'SP_MessageBoxCritical',
        # ~ 'SP_MessageBoxInformation',
        # ~ 'SP_MessageBoxQuestion',
        # ~ 'SP_MessageBoxWarning',

        if icon_name is None:
            icon_ = self.style().standardIcon(getattr(QStyle, "SP_MessageBoxWarning"))
        else:
            icon_ = self.style().standardIcon(getattr(QStyle, icon_name))
        self.icon_label.setPixmap(icon_.pixmap(QSize(64, 64)))

        if message is None:
            self.message_label.setText("")
        else:
            self.message_label.setText(str(message))

        if content is None:
            self.content_container.setText("")
            self.content_container.resize(self.content_container.width(), 0)
        else:
            self.content_container.setText(str(content))
            self.content_container.resize(self.content_container.width(), 400)

        self.ok_button.clicked.disconnect()
        self.ok_button.clicked.connect(self.hide)
        if ok_cb is not None:
            def on_ok_button_clicked():
                args_ = ok_cb_args if ok_cb_args is not None else []
                ok_cb(*args_)

            self.ok_button.clicked.connect(on_ok_button_clicked)

        self.show()


class MainWindow(QMainWindow):  # pylint:  disable=too-many-instance-attributes
    def __init__(self, parent=None):

        from alfa_CR6_ui.debug_status_view import DebugStatusView  # pylint: disable=import-outside-toplevel

        super().__init__(parent)
        loadUi(os.path.join(UI_PATH, "transition.ui"), self)

        self.setStyleSheet("""
                QWidget {font-size: 24px; font-family: Times sans-serif;}
                QPushButton {background-color: #F3F3F3F3; border: 1px solid #999999; border-radius: 4px;}
                QPushButton:pressed {background-color: #AAAAAA;}
                QScrollBar:vertical {width: 40px;}
            """)
        self.running_jars_lbl.setStyleSheet("font-size: 15px")

        self.menu_btn_group.buttonClicked.connect(self.on_menu_btn_group_clicked)

        self.search_order_table_last_time = 0
        self.search_file_table_last_time = 0
        self.search_jar_table_last_time = 0

        self.order_table_selected_order_nr = None

        self.keyboard = Keyboard(self, keyboard_path=KEYBOARD_PATH)
        self.keyboard.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.keyboard.setGeometry(
            0,
            self.menu_frame.y() - self.keyboard.height(),
            self.menu_frame.width(),
            256,
        )
        self.keyboard.hide()

        self.debug_status_view = DebugStatusView(self)
        self.stacked_widget.addWidget(self.debug_status_view.main_frame)

        self.__init_action_pages()
        self.__init_home_page()
        self.__init_order_page()
        self.__init_browser_page()
        self.__init_dialogs()
        self.__init_icons()

        self.showFullScreen()

        # ~ self.refill_1_lbl.mouseReleaseEvent = lambda event: self.show_reserve(0)
        # ~ self.refill_2_lbl.mouseReleaseEvent = lambda event: self.show_reserve(1)
        # ~ self.refill_3_lbl.mouseReleaseEvent = lambda event: self.show_reserve(2)
        # ~ self.refill_4_lbl.mouseReleaseEvent = lambda event: self.show_reserve(3)
        # ~ self.refill_5_lbl.mouseReleaseEvent = lambda event: self.show_reserve(4)
        self.refill_6_lbl.mouseReleaseEvent = lambda event: self.show_reserve(5)

    def __init_icons(self):

        self.reserve_movie = QMovie(os.path.join(IMAGES_PATH, "riserva.gif"))

        self.gray_icon = QPixmap(os.path.join(IMAGES_PATH, "gray.png"))
        self.green_icon = QPixmap(os.path.join(IMAGES_PATH, "green.png"))
        self.red_icon = QPixmap(os.path.join(IMAGES_PATH, "red.png"))

        self.jar_icon_map = {
            k: QPixmap(os.path.join(IMAGES_PATH, p))
            for k, p in (
                ("no", ""),
                ("green", "jar-green.png"),
                ("red", "jar-red.png"),
                ("blue", "jat-blue.png"),
            )
        }
        self.tank_icon_map = {
            k: QPixmap(os.path.join(IMAGES_PATH, p))
            for k, p in (
                ("green", "tank_green.png"),
                ("gray", "tank_gray.png"),
            )
        }

    def __init_home_page(self):

        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)
        self.action_btn_group.buttonClicked.connect(self.on_action_btn_group_clicked)

        for b in self.action_btn_group.buttons():
            b.setStyleSheet(
                """QPushButton { background-color: #00FFFFFF; border: 0px;}"""
            )

    def __init_order_page(self):

        self.jar_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.order_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.file_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.order_table_view.clicked.connect(self.on_order_table_clicked)
        self.jar_table_view.clicked.connect(self.on_jar_table_clicked)
        self.file_table_view.clicked.connect(self.on_file_table_clicked)

        self.search_order_btn.clicked.connect(self.populate_order_table)
        self.search_file_btn.clicked.connect(self.populate_file_table)

        self.search_order_line.textChanged.connect(self.populate_order_table)
        self.search_jar_line.textChanged.connect(self.populate_jar_table)
        self.search_file_line.textChanged.connect(self.populate_file_table)

    def __init_browser_page(self):

        self.webengine_view = QWebEngineView(self.browser_frame)
        self.webengine_view.setGeometry(0, 0, self.browser_frame.width(), self.browser_frame.height())
        self.start_page_url = QUrl.fromLocalFile((os.path.join(UI_PATH, "start_page.html")))
        self.webengine_view.setUrl(self.start_page_url)

        QWebEngineProfile.defaultProfile().downloadRequested.connect(self.on_downloadRequested)
        QWebEngineProfile.defaultProfile().setCachePath(WEBENGINE_CACHE_PATH)
        QWebEngineProfile.defaultProfile().setPersistentStoragePath(WEBENGINE_CACHE_PATH)

        logging.warning(
            f"QWebEngineProfile.defaultProfile().storageName():{QWebEngineProfile.defaultProfile().storageName()}")

    def __init_dialogs(self):

        self.input_dialog = InputDialog(self)
        self.edit_dialog = EditDialog(self)

    def __init_action_pages(self,):

        def action_(args):
            logging.warning(f"args:{args}")
            try:
                QApplication.instance().run_a_coroutine_helper(args[0], *args[1:])
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        def show_val_(head_letter, bit_name, text, w):
            # ~ logging.warning(f"head_letter:{head_letter}, bit_name:{bit_name}, text:{text}, w:{w}")
            try:
                m = QApplication.instance().get_machine_head_by_letter(head_letter)
                if bit_name.lower() == "container_presence":
                    val_ = m.status.get("container_presence")
                else:
                    val_ = m.jar_photocells_status.get(bit_name)

                pth_ = (
                    os.path.join(IMAGES_PATH, "green.png")
                    if val_
                    else os.path.join(IMAGES_PATH, "gray.png")
                )
                w.setText(
                    f'<img widt="50" height="50" src="{pth_}" style="vertical-align:middle;">{tr_(text)}</img>'
                )
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        map_ = {
            self.action_01_btn: {
                "title": "action 01 (head 1 or A)",
                "buttons": [
                    {
                        "text": "Start input roller",
                        "action": partial(action_, ("single_move", "A", {"Input_Roller": 1})),
                    },
                    {
                        "text": "Stop  input roller",
                        "action": partial(action_, ("single_move", "A", {"Input_Roller": 0})),
                    },
                    {
                        "text": "Start input roller to photocell",
                        "action": partial(action_, ("single_move", "A", {"Input_Roller": 2})),
                    },
                    {
                        "text": "move 01 02 ('IN -> A')",
                        "action": partial(action_, ("move_01_02",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "A",
                            "JAR_INPUT_ROLLER_PHOTOCELL",
                            "INPUT ROLLER PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_,
                            "A",
                            "JAR_DETECTION_MICROSWITCH_1",
                            "MICROSWITCH 1",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_,
                            "A",
                            "JAR_DETECTION_MICROSWITCH_2",
                            "MICROSWITCH 2",
                        )
                    },
                ],
            },
            self.action_02_btn: {
                "title": "action 02 (head 1 or A)",
                "buttons": [
                    {
                        "text": "Start dispensing roller",
                        "action": partial(action_, ("single_move", "A", {"Dispensing_Roller": 1})),
                    },
                    {
                        "text": "Stop  dispensing roller",
                        "action": partial(action_, ("single_move", "A", {"Dispensing_Roller": 0})),
                    },
                    {
                        "text": "Start dispensing roller to photocell",
                        "action": partial(action_, ("single_move", "A", {"Dispensing_Roller": 2})),
                    },
                    {
                        "text": "move 02 03 ('A -> B')",
                        "action": partial(action_, ("move_02_03",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "A",
                            "JAR_DISPENSING_POSITION_PHOTOCELL",
                            "DISPENSING POSITION PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_, "A", "container_presence", "CONTAINER PRESENCE"
                        )
                    },
                ],
            },
            self.action_03_btn: {
                "title": "action 03 (head 3 or B)",
                "buttons": [
                    {
                        "text": "Start dispensing roller",
                        "action": partial(action_, ("single_move", "B", {"Dispensing_Roller": 1})),
                    },
                    {
                        "text": "Stop  dispensing roller",
                        "action": partial(action_, ("single_move", "B", {"Dispensing_Roller": 0})),
                    },
                    {
                        "text": "Start dispensing roller to photocell",
                        "action": partial(action_, ("single_move", "B", {"Dispensing_Roller": 2})),
                    },
                    {
                        "text": "move 03 04 ('B -> C')",
                        "action": partial(action_, ("move_03_04",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "B",
                            "JAR_DISPENSING_POSITION_PHOTOCELL",
                            "DISPENSING POSITION PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_, "B", "container_presence", "CONTAINER PRESENCE"
                        )
                    },
                ],
            },
            self.action_04_btn: {
                "title": "action 04 (head 5 or C)",
                "buttons": [
                    {
                        "text": "Start dispensing roller",
                        "action": partial(action_, ("single_move", "C", {"Dispensing_Roller": 1})),
                    },
                    {
                        "text": "Stop  dispensing roller",
                        "action": partial(action_, ("single_move", "C", {"Dispensing_Roller": 0})),
                    },
                    {
                        "text": "Start dispensing roller to photocell",
                        "action": partial(action_, ("single_move", "C", {"Dispensing_Roller": 2})),
                    },
                    {
                        "text": "move 04 05 ('C -> UP')",
                        "action": partial(action_, ("move_04_05",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "C",
                            "JAR_DISPENSING_POSITION_PHOTOCELL",
                            "DISPENSING POSITION PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_, "C", "container_presence", "CONTAINER PRESENCE"
                        )
                    },
                ],
            },
            self.action_05_btn: {
                "title": "action 05 (head 5, 6 or C, D)",
                "buttons": [
                    {
                        "text": "Start lifter roller CW",
                        "action": partial(action_, ("single_move", "C", {"Lifter_Roller": 2})),
                    },
                    {
                        "text": "Start lifter roller CCW",
                        "action": partial(action_, ("single_move", "C", {"Lifter_Roller": 3})),
                    },
                    {
                        "text": "Stop  lifter roller",
                        "action": partial(action_, ("single_move", "C", {"Lifter_Roller": 0})),
                    },
                    {
                        "text": "Start lifter up",
                        "action": partial(action_, ("single_move", "D", {"Lifter": 1})),
                    },
                    {
                        "text": "Start lifter down",
                        "action": partial(action_, ("single_move", "D", {"Lifter": 2})),
                    },
                    {
                        "text": "Stop  lifter",
                        "action": partial(action_, ("single_move", "D", {"Lifter": 0})),
                    },
                    {
                        "text": "move 04 05 ('C -> UP')",
                        "action": partial(action_, ("move_04_05",)),
                    },
                    {
                        "text": "move 05 06 ('UP -> DOWN')",
                        "action": partial(action_, ("move_05_06",)),
                    },
                    {
                        "text": "move 06 07 ('DOWN -> D')",
                        "action": partial(action_, ("move_06_07",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "C",
                            "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL",
                            "LIFTER ROLLER PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_,
                            "D",
                            "LOAD_LIFTER_UP_PHOTOCELL",
                            "LIFTER UP PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_,
                            "D",
                            "LOAD_LIFTER_DOWN_PHOTOCELL",
                            "LIFTER DOWN PHOTOCELL",
                        )
                    },
                ],
            },
            self.action_06_btn: {
                "title": "action 06 (head 6 or D)",
                "buttons": [
                    {
                        "text": "Start dispensing roller",
                        "action": partial(action_, ("single_move", "D", {"Dispensing_Roller": 1})),
                    },
                    {
                        "text": "Stop  dispensing roller",
                        "action": partial(action_, ("single_move", "D", {"Dispensing_Roller": 0})),
                    },
                    {
                        "text": "Start dispensing roller to photocell",
                        "action": partial(action_, ("single_move", "D", {"Dispensing_Roller": 2})),
                    },
                    {
                        "text": "move 07 08 ('D -> E')",
                        "action": partial(action_, ("move_07_08",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "D",
                            "JAR_DISPENSING_POSITION_PHOTOCELL",
                            "DISPENSING POSITION PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_, "D", "container_presence", "CONTAINER PRESENCE"
                        )
                    },
                ],
            },
            self.action_07_btn: {
                "title": "action 07 (head 4 or E)",
                "buttons": [
                    {
                        "text": "Start dispensing roller",
                        "action": partial(action_, ("single_move", "E", {"Dispensing_Roller": 1})),
                    },
                    {
                        "text": "Stop  dispensing roller",
                        "action": partial(action_, ("single_move", "E", {"Dispensing_Roller": 0})),
                    },
                    {
                        "text": "Start dispensing roller to photocell",
                        "action": partial(action_, ("single_move", "E", {"Dispensing_Roller": 2})),
                    },
                    {
                        "text": "move 08 09 ('E -> F')",
                        "action": partial(action_, ("move_08_09",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "E",
                            "JAR_DISPENSING_POSITION_PHOTOCELL",
                            "DISPENSING POSITION PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_, "E", "container_presence", "CONTAINER PRESENCE"
                        )
                    },
                ],
            },
            self.action_08_btn: {
                "title": "action 08 (head 2 or F)",
                "buttons": [
                    {
                        "text": "Start dispensing roller",
                        "action": partial(action_, ("single_move", "F", {"Dispensing_Roller": 1})),
                    },
                    {
                        "text": "Stop  dispensing roller",
                        "action": partial(action_, ("single_move", "F", {"Dispensing_Roller": 0})),
                    },
                    {
                        "text": "Start dispensing roller to photocell",
                        "action": partial(action_, ("single_move", "F", {"Dispensing_Roller": 2})),
                    },
                    {
                        "text": "move 09 10 ('F -> DOWN')",
                        "action": partial(action_, ("move_09_10",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "F",
                            "JAR_DISPENSING_POSITION_PHOTOCELL",
                            "DISPENSING POSITION PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_, "F", "container_presence", "CONTAINER PRESENCE"
                        )
                    },
                ],
            },
            self.action_09_btn: {
                "title": "action 09 (head 2 or F)",
                "buttons": [
                    {
                        "text": "Start lifter roller CW",
                        "action": partial(action_, ("single_move", "F", {"Lifter_Roller": 2})),
                    },
                    {
                        "text": "Start lifter roller CCW",
                        "action": partial(action_, ("single_move", "F", {"Lifter_Roller": 3})),
                    },
                    {
                        "text": "Stop  lifter roller",
                        "action": partial(action_, ("single_move", "F", {"Lifter_Roller": 0})),
                    },
                    {
                        "text": "Start lifter up",
                        "action": partial(action_, ("single_move", "F", {"Lifter": 1})),
                    },
                    {
                        "text": "Start lifter down",
                        "action": partial(action_, ("single_move", "F", {"Lifter": 2})),
                    },
                    {
                        "text": "Stop  lifter",
                        "action": partial(action_, ("single_move", "F", {"Lifter": 0})),
                    },
                    {
                        "text": "move 09 10 ('F -> DOWN')",
                        "action": partial(action_, ("move_09_10",)),
                    },
                    {
                        "text": "move 10 11 ('DOWN -> UP -> OUT')",
                        "action": partial(action_, ("move_10_11",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "F",
                            "JAR_OUTPUT_ROLLER_PHOTOCELL",
                            "LIFTER ROLLER PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_,
                            "F",
                            "UNLOAD_LIFTER_UP_PHOTOCELL",
                            "LIFTER UP PHOTOCELL",
                        )
                    },
                    {
                        "show_val": partial(
                            show_val_,
                            "F",
                            "UNLOAD_LIFTER_DOWN_PHOTOCELL",
                            "LIFTER DOWN PHOTOCELL",
                        )
                    },
                ],
            },
            self.action_10_btn: {
                "title": "action 10 (head 2 or F)",
                "buttons": [
                    {
                        "text": "Start output roller",
                        "action": partial(action_, ("single_move", "F", {"Output_Roller": 3})),
                    },
                    {
                        "text": "Stop  output roller",
                        "action": partial(action_, ("single_move", "F", {"Output_Roller": 0})),
                    },
                    {
                        "text": "Start output roller to photocell dark",
                        "action": partial(action_, ("single_move", "F", {"Output_Roller": 1})),
                    },
                    {
                        "text": "Start output roller to photocell light",
                        "action": partial(action_, ("single_move", "F", {"Output_Roller": 2})),
                    },
                    {
                        "text": "move 11 12 ('UP -> OUT')",
                        "action": partial(action_, ("move_11_12",)),
                    },
                    {
                        "text": "Back to Home Page",
                        "action": partial(
                            self.stacked_widget.setCurrentWidget, self.home_page
                        ),
                    },
                ],
                "labels": [
                    {
                        "show_val": partial(
                            show_val_,
                            "F",
                            "JAR_OUTPUT_ROLLER_PHOTOCELL",
                            "OUTPUT ROLLER PHOTOCELL",
                        )
                    }
                ],
            },
        }

        action_frame_map = {}
        for btn, val in map_.items():
            w = QFrame(self)
            loadUi(os.path.join(UI_PATH, "action_frame.ui"), w)
            w.setStyleSheet(
                """
                QFrame { border: 1px solid #999999; border-radius: 4px; background-color: #FEFEFE;}
                QWidget {font-size: 24px; font-family: Times sans-serif;}
                QLabel { border-width: 0px; background-color: #FFFFFF;}
                QPushButton { background-color: #EEEEEE; border: 1px solid #999999; border-radius: 4px;}
                QPushButton:pressed {background-color: #AAAAAA;}
                """
            )

            w.action_title_label.setText(tr_(val["title"]))
            for b in val["buttons"]:
                i = QPushButton(tr_(b["text"]), w)
                i.setFixedHeight(50)
                if b.get("action"):
                    i.clicked.connect(b.get("action"))
                w.action_buttons_layout.addWidget(i)

            for l in val["labels"]:

                i = QLabel(w)
                i.setTextFormat(Qt.RichText)
                if l.get("show_val"):
                    setattr(i, "show_val", l.get("show_val"))
                w.action_labels_layout.addWidget(i)

            self.stacked_widget.addWidget(w)
            action_frame_map[btn] = w

        self.action_frame_map = action_frame_map

    def on_downloadRequested(self, download):  # pylint: disable=no-self-use

        logging.warning(f"download:{download}.")
        _msgs = {
            0: "Download has been requested, but has not been accepted yet.",
            1: "Download is in progress.",
            2: "Download completed successfully.",
            3: "Download has been cancelled.",
            4: "Download has been interrupted (by the server or because of lost connectivity).",
        }
        if not os.path.exists(WEBENGINE_DOWNLOAD_PATH):
            os.makedirs(WEBENGINE_DOWNLOAD_PATH)
        _name = time.strftime("%Y-%m-%d_%H:%M:%S") + ".json"
        full_name = os.path.join(WEBENGINE_DOWNLOAD_PATH, _name)
        download.setPath(full_name)
        download.accept()

        def _cb():
            _msg = "file name:{}\n\n ".format(_name) + tr_(_msgs[download.state()])
            self.open_alert_dialog(_msg, title="ALERT", callback=None, args=None)

        download.finished.connect(_cb)

    def get_stacked_widget(self):
        return self.stacked_widget

    def on_service_btn_group_clicked(self, btn):

        btn_name = btn.objectName()

        try:
            service_page_urls = [
                "http://{}:{}/service_page/".format(i[0], i[2])
                for i in QApplication.instance().settings.MACHINE_HEAD_IPADD_PORTS_LIST
            ]

            map_ = {
                self.service_1_btn: service_page_urls[0],
                self.service_2_btn: service_page_urls[1],
                self.service_3_btn: service_page_urls[2],
                self.service_4_btn: service_page_urls[3],
                self.service_5_btn: service_page_urls[4],
                self.service_6_btn: service_page_urls[5],
                self.service_0_btn: "http://127.0.0.1:8080/service_page/",
            }
            self.webengine_view.setUrl(self.start_page_url)
            self.stacked_widget.setCurrentWidget(self.browser_page)
            self.webengine_view.setUrl(QUrl(map_[btn]))

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.open_alert_dialog(
                f"btn_namel:{btn_name} exception:{e}",
                title="ERROR",
                callback=None,
                args=None,
            )

    def on_menu_btn_group_clicked(self, btn):

        btn_name = btn.objectName()

        try:

            if "keyboard" in btn_name:
                self.toggle_keyboard()

            elif "home" in btn_name:
                self.toggle_keyboard(on_off=False)
                self.stacked_widget.setCurrentWidget(self.home_page)

            elif "order" in btn_name:
                self.order_table_selected_order_nr = None
                self.toggle_keyboard(on_off=False)
                self.populate_order_table()
                self.populate_jar_table()
                self.populate_file_table()
                self.stacked_widget.setCurrentWidget(self.order_page)

            elif "browser" in btn_name:
                self.stacked_widget.setCurrentWidget(self.browser_page)
                self.toggle_keyboard(on_off=True)
                if QUrl(WEBENGINE_CUSTOMER_URL).toString() not in self.webengine_view.url().toString():
                    self.webengine_view.setUrl(QUrl(WEBENGINE_CUSTOMER_URL))

            elif "global_status" in btn_name:
                self.stacked_widget.setCurrentWidget(self.debug_status_view.main_frame)

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.open_alert_dialog(
                f"btn_namel:{btn_name} exception:{e}",
                title="ERROR",
                callback=None,
                args=None,
            )

    def on_action_btn_group_clicked(self, btn):

        btn_name = btn.objectName()
        try:
            if "feed" in btn_name:
                QApplication.instance().run_a_coroutine_helper("move_00_01")
            elif "deliver" in btn_name:
                QApplication.instance().run_a_coroutine_helper("move_12_00")
            elif "freeze_carousel" in btn_name:
                msg_ = (
                    tr_("confirm unfreezing carousel?")
                    if QApplication.instance().carousel_frozen
                    else tr_("confirm freezing carousel?")
                )
                self.open_input_dialog(
                    icon_name=None,
                    message=msg_,
                    content=None,
                    ok_cb=QApplication.instance().toggle_freeze_carousel,
                )
            elif "action_" in btn_name:
                self.stacked_widget.setCurrentWidget(self.action_frame_map[btn])
            for i in QApplication.instance().machine_head_dict.keys():
                self.update_status_data(i)
        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.open_alert_dialog(
                f"btn_namel:{btn_name} exception:{e}",
                title="ERROR",
                callback=None,
                args=None,
            )

    def on_order_table_clicked(self, index):  # pylint: disable=no-self-use

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            order_nr = model.results[row][3]

            self.order_table_selected_order_nr = order_nr

            logging.warning(f"row:{row}, col:{col}, order_nr:{order_nr}")
            if col == 0:  # delete

                def cb():
                    model.remove_order(order_nr)
                    self.populate_order_table()
                    self.populate_jar_table()

                msg_ = tr_("confirm deleting order '{}' and related jars?").format(order_nr)
                self.open_input_dialog(icon_name="SP_MessageBoxCritical", message=msg_, ok_cb=cb)

            elif col == 1:  # edit

                self.open_edit_dialog(order_nr)

                # ~ content = "{}"
                # ~ query_ = QApplication.instance().db_session.query(Order)
                # ~ query_ = query_.filter(Order.order_nr == order_nr)
                # ~ order = query_.first()
                # ~ if order:
                # ~ _props = json.loads(order.json_properties)
                # ~ content = json.dumps(_props, indent=2)
                # ~ msg_ = tr_("order nr.:{}\n description:{}\n date_created:{}").format(
                # ~ order_nr, order.description, order.date_created)

                # ~ self.open_input_dialog(
                # ~ icon_name="SP_MessageBoxInformation",
                # ~ message=msg_,
                # ~ content=content,
                # ~ )

                self.populate_jar_table()

            elif col == 2:  # status

                self.populate_jar_table()

            elif col == 3:  # order_nr

                self.populate_jar_table()

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None
            )

    def on_jar_table_clicked(self, index):  # pylint: disable=no-self-use, too-many-locals

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            barcode = model.results[row][3]
            logging.warning(f"row:{row}, col:{col}, barcode:{barcode}")
            if col == 0:  # delete

                def cb():
                    model.remove_jar(barcode)
                    self.populate_jar_table()

                self.open_input_dialog(
                    icon_name="SP_MessageBoxCritical",
                    message=tr_("confirm deleting jar\n '{}' ?").format(barcode),
                    ok_cb=cb,
                )

            elif col == 1:  # view
                content = "{}"
                order_nr, index = decompile_barcode(barcode)
                if order_nr and index >= 0:
                    order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).first()
                    if order:
                        query_ = QApplication.instance().db_session.query(Jar)
                        query_ = query_.filter(Jar.order == order)
                        query_ = query_.filter(Jar.index == index)
                        jar = query_.first()
                        if jar:
                            _props = json.loads(jar.json_properties)
                            content = json.dumps(_props, indent=2)
                            msg_ = tr_("barcode:{}\n description:{}\n date_created:{}").format(
                                barcode, jar.description, jar.date_created)

                self.open_input_dialog(
                    icon_name="SP_MessageBoxInformation",
                    message=msg_,
                    content=content,
                )

            elif col == 2:  # status
                pass

            elif col == 3:  # barcode
                pass

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None
            )

    def on_file_table_clicked(self, index):  # pylint: disable=no-self-use

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            file_name = model.results[row][3]
            logging.warning(f"row:{row}, col:{col}, file_name:{file_name}")
            if col == 0:  # delete

                def cb():
                    model.remove_file(file_name)
                    self.populate_file_table()

                self.open_input_dialog(
                    icon_name="SP_MessageBoxCritical",
                    message=tr_("confirm deleting file\n '{}' ?").format(file_name),
                    ok_cb=cb,
                )

            elif col == 1:  # view
                content = "{}"
                with open(os.path.join(WEBENGINE_DOWNLOAD_PATH, file_name)) as f:
                    content = f.read(3000)
                    try:
                        content = json.dumps(json.loads(content), indent=2)
                    except Exception:  # pylint: disable=broad-except
                        logging.error(traceback.format_exc())

                self.open_input_dialog(
                    icon_name="SP_MessageBoxInformation",
                    message=tr_("file_name:{}").format(file_name),
                    content=content,
                )

            elif col == 2:  # create order

                app = QApplication.instance()

                def cb():
                    n = int(self.input_dialog.content_container.toPlainText())
                    n = min(n, 20)
                    logging.warning(f"n:{n}")
                    order = app.create_order(
                        os.path.join(WEBENGINE_DOWNLOAD_PATH, file_name),
                        json_schema_name="KCC",
                        n_of_jars=n,
                    )
                    barcodes = sorted([str(j.barcode) for j in order.jars])
                    logging.warning(f"file_name:{file_name}, barcodes:{barcodes}")

                    def cb_():
                        for b in barcodes:
                            response = dymo_print(str(b))
                            logging.warning(f"response:{response}")
                            time.sleep(.05)

                    msg_ = tr_("confirm printing {} barcodes?").format(len(barcodes))
                    self.open_input_dialog(message=msg_, content="{}".format(barcodes), ok_cb=cb_)

                    self.order_table_selected_order_nr = None

                    model.remove_file(file_name)
                    self.populate_file_table()
                    self.populate_order_table()
                    self.populate_jar_table()

                _msg = tr_("confirm creating order from file (file will be deleted):\n '{}'?\n").format(file_name)
                _msg += tr_('Please, insert below the number of jars.')
                self.open_input_dialog(message=_msg, content="<span align='center'>1</span>", ok_cb=cb)

            elif col == 3:  # file name
                pass

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None
            )

    def populate_order_table(self):

        t = time.time()
        if t - self.search_order_table_last_time > 0.1:
            self.search_order_table_last_time = t
            try:
                db_session = QApplication.instance().db_session
                order_model = OrderTableModel(self, db_session)
                self.order_table_view.setModel(order_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

            self.search_order_box.setTitle(tr_("[{}] Orders: search by order nr.").format(order_model.rowCount()))

    def populate_jar_table(self):

        t = time.time()
        if t - self.search_jar_table_last_time > 0.1:
            self.search_jar_table_last_time = t
            try:
                db_session = QApplication.instance().db_session
                jar_model = JarTableModel(self, db_session)
                self.jar_table_view.setModel(jar_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

            self.search_jar_box.setTitle(tr_("[{}] Jars:   search by status").format(jar_model.rowCount()))
        else:
            logging.warning(" ################ ")
            logging.warning(" ################ ")
            logging.warning(" ################ ")
            logging.warning(" ################ ")
            logging.warning(" ################ ")

    def populate_file_table(self):

        t = time.time()
        if t - self.search_file_table_last_time > 0.1:
            self.search_file_table_last_time = t
            try:
                file_model = FileTableModel(self, WEBENGINE_DOWNLOAD_PATH)
                self.file_table_view.setModel(file_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

            self.search_file_box.setTitle(tr_("[{}] Files:  search by file name").format(file_model.rowCount()))

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
            self.__update_service_btns_and_container_presences(head_index)
            self.__update_action_pages()
            self.__update_jar_pixmaps()
            self.__update_tank_pixmaps()
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def __update_service_btns_and_container_presences(self, head_index):
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
        map_[head_index].setText(f"{status['status_level']}")

        map_ = [
            self.container_presence_1_label,
            self.container_presence_2_label,
            self.container_presence_3_label,
            self.container_presence_4_label,
            self.container_presence_5_label,
            self.container_presence_6_label,
        ]
        if status["container_presence"]:
            map_[head_index].setPixmap(self.green_icon)
        else:
            map_[head_index].setPixmap(self.gray_icon)

    def __update_tank_pixmaps(self):
        map_ = [
            self.refill_1_lbl,
            self.refill_2_lbl,
            self.refill_3_lbl,
            self.refill_4_lbl,
            self.refill_5_lbl,
            self.refill_6_lbl,
        ]

        for head_index, m in QApplication.instance().machine_head_dict.items():
            status = m.status
            if "STANDBY" in status.get('status_level', '') and QApplication.instance().carousel_frozen:
                map_[head_index].setPixmap(self.tank_icon_map['green'])
            else:
                map_[head_index].setPixmap(self.tank_icon_map['gray'])

            map_[head_index].setText("")

    def __update_action_pages(self):

        for action_frame in self.action_frame_map.values():
            if action_frame.isVisible():
                for i in range(action_frame.action_labels_layout.count()):
                    lbl = action_frame.action_labels_layout.itemAt(i).widget()
                    if hasattr(lbl, "show_val"):
                        getattr(lbl, "show_val")(lbl)

        def _get_status_level(head_letter):
            return (
                QApplication.instance()
                .get_machine_head_by_letter(head_letter)
                .status.get("status_level")
            )

        for action_frame in self.action_frame_map.values():
            if action_frame.isVisible():
                action_frame.status_A_label.setText(tr_(f"{_get_status_level('A')}"))
                action_frame.status_B_label.setText(tr_(f"{_get_status_level('B')}"))
                action_frame.status_C_label.setText(tr_(f"{_get_status_level('C')}"))
                action_frame.status_D_label.setText(tr_(f"{_get_status_level('D')}"))
                action_frame.status_E_label.setText(tr_(f"{_get_status_level('E')}"))
                action_frame.status_F_label.setText(tr_(f"{_get_status_level('F')}"))

    def __update_jar_pixmaps(self):

        _ = [f"{k}" for k, j in QApplication.instance().get_jar_runners().items()]
        self.running_jars_lbl.setText("\n".join(_))

        _label_to_position_map = {
            self.STEP_01_label: "IN_A",
            self.STEP_02_label: "A",
            self.STEP_03_label: "B",
            self.STEP_04_label: "C",
            self.STEP_05_label: "LIFTR_UP",
            self.STEP_06_label: "LIFTR_DOWN",
            self.STEP_07_label: "D",
            self.STEP_08_label: "E",
            self.STEP_09_label: "F",
            self.STEP_10_label: "LIFTL_DOWN",
            self.STEP_11_label: "LIFTL_UP",
            self.STEP_12_label: "OUT",
        }

        def _get_bit(head_letter, bit_name):
            m = QApplication.instance().get_machine_head_by_letter(head_letter)
            return m.jar_photocells_status.get(bit_name)

        def _set_pixmap_by_photocells(lbl, head_letters_bit_names, icon=None):

            false_condition = [
                1 for h, b in head_letters_bit_names if not _get_bit(h, b)
            ]

            if icon is None:  # jar position
                if false_condition:
                    lbl.setStyleSheet("QLabel {{}}")
                    lbl.setText("")
                else:
                    text = ""
                    for j in QApplication.instance().get_jar_runners().values():
                        pos = j["jar"].position
                        # ~ logging.warning(f"_label_to_position_map.get(lbl):{_label_to_position_map.get(lbl)}, pos:{pos}")
                        if _label_to_position_map.get(lbl) == pos:
                            _bc = str(j["jar"].barcode)
                            text = _bc[-6:-3] + "\n" + _bc[-3:]
                            break

                    if text:
                        _img_url = os.path.join(IMAGES_PATH, "jar-green.png")
                    else:
                        _img_url = os.path.join(IMAGES_PATH, "jar-gray.png")

                    lbl.setStyleSheet(
                        'color:#000000; border-image:url("{0}"); font-size: 15px'.format(_img_url)
                    )
                    lbl.setText(text)
                    # ~ logging.warning(f"text:{text}")

            else:  # lifter position
                size = [0, 0] if false_condition else [32, 32]
                pixmap = icon.scaled(*size, Qt.KeepAspectRatio)
                lbl.setPixmap(pixmap)

            lbl.show()

        _set_pixmap_by_photocells(
            self.STEP_01_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),)
        )
        _set_pixmap_by_photocells(
            self.STEP_02_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),)
        )
        _set_pixmap_by_photocells(
            self.STEP_03_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"),)
        )
        _set_pixmap_by_photocells(
            self.STEP_04_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),)
        )
        _set_pixmap_by_photocells(
            self.STEP_05_label,
            (
                ("D", "LOAD_LIFTER_UP_PHOTOCELL"),
                ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),
            ),
        )
        _set_pixmap_by_photocells(
            self.STEP_06_label,
            (
                ("D", "LOAD_LIFTER_DOWN_PHOTOCELL"),
                ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),
            ),
        )
        _set_pixmap_by_photocells(
            self.STEP_07_label, (("D", "JAR_DISPENSING_POSITION_PHOTOCELL"),)
        )
        _set_pixmap_by_photocells(
            self.STEP_08_label, (("E", "JAR_DISPENSING_POSITION_PHOTOCELL"),)
        )
        _set_pixmap_by_photocells(
            self.STEP_09_label, (("F", "JAR_DISPENSING_POSITION_PHOTOCELL"),)
        )
        _set_pixmap_by_photocells(
            self.STEP_10_label,
            (
                ("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"),
                ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),
            ),
        )
        _set_pixmap_by_photocells(
            self.STEP_11_label,
            (
                ("F", "UNLOAD_LIFTER_UP_PHOTOCELL"),
                ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),
            ),
        )
        _set_pixmap_by_photocells(
            self.STEP_12_label, (("F", "JAR_OUTPUT_ROLLER_PHOTOCELL"),)
        )

        _set_pixmap_by_photocells(
            self.load_lifter_up_label,
            (("D", "LOAD_LIFTER_UP_PHOTOCELL"),),
            icon=self.green_icon,
        )
        _set_pixmap_by_photocells(
            self.load_lifter_down_label,
            (("D", "LOAD_LIFTER_DOWN_PHOTOCELL"),),
            icon=self.green_icon,
        )
        _set_pixmap_by_photocells(
            self.unload_lifter_up_label,
            (("F", "UNLOAD_LIFTER_UP_PHOTOCELL"),),
            icon=self.green_icon,
        )
        _set_pixmap_by_photocells(
            self.unload_lifter_down_label,
            (("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"),),
            icon=self.green_icon,
        )

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
        # ~ logging.warning(f"head_index:{head_index}, flag:{flag}, l:{l}.")

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
            self.freeze_carousel_btn.setStyleSheet(
                "background-color: #00FFFFFF; color: #990000"
            )
        else:
            self.freeze_carousel_btn.setText(tr_("Carousel OK"))
            self.freeze_carousel_btn.setIcon(QIcon(self.green_icon))
            self.freeze_carousel_btn.setStyleSheet(
                "background-color: #00FFFFFF; color: #004400"
            )

        try:
            self.__update_action_pages()
            self.__update_jar_pixmaps()
            self.__update_tank_pixmaps()
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def open_edit_dialog(self, order_nr):

        self.edit_dialog.show_dialog(order_nr)
        self.toggle_keyboard(on_off=True)

    def open_input_dialog(self, icon_name=None, message=None, content=None, ok_cb=None, ok_cb_args=None):   # pylint: disable=too-many-arguments

        self.input_dialog.show_dialog(
            icon_name=icon_name,
            message=message,
            content=content,
            ok_cb=ok_cb,
            ok_cb_args=ok_cb_args)

    def open_alert_dialog(self, msg, title="ALERT", callback=None, args=None):

        _msgbox = ModalMessageBox(parent=self, msg=msg, title=title, ok_callback=callback, ok_callback_args=args)

    def open_frozen_dialog(self, msg, title="ALERT"):

        callback = QApplication.instance().freeze_carousel
        args = [False, ]
        logging.info(msg)
        msg_ = tr_("carousel is frozen.")
        msg_ += f'\n------------------------------\n"{msg}"\n------------------------------\n'
        msg_ += tr_("hit 'OK' to unfreeze it")
        self.open_alert_dialog(msg_, title=title, callback=callback, args=args)

    def show_barcode(self, barcode, is_ok=False):

        css = "color: #000000" if is_ok else "color: #990000"
        self.menu_line_edit.setStyleSheet(css)
        self.menu_line_edit.setText(f"{barcode}")


def main():

    fmt_ = (
        "[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s"
    )
    logging.basicConfig(stream=sys.stdout, level="INFO", format=fmt_)

    from alfa_CR6_backend.cr6 import CR6_application  # pylint: disable=import-outside-toplevel

    app = CR6_application(MainWindow, sys.argv)
    app.exec_()


if __name__ == "__main__":
    main()
