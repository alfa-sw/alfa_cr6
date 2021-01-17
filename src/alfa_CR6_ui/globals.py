# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods

import os
import logging
import json
import time
import traceback
import random

from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, QVariant, QAbstractTableModel, QSize, QRect, QItemSelectionModel, QItemSelection
from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QStyle,
    QMessageBox,
    QFrame,
    QTableWidgetItem,
    QCompleter)

from alfa_CR6_backend.models import Order, Jar, decompile_barcode

HERE = os.path.dirname(os.path.abspath(__file__))
KEYBOARD_PATH = os.path.join(HERE, "keyboard")
IMAGES_PATH = os.path.join(HERE, "images")
UI_PATH = os.path.join(HERE, "ui")
HELP_PATH = os.path.join(HERE, "help")

WEBENGINE_DOWNLOAD_PATH = "/opt/alfa_cr6/data/kcc"
WEBENGINE_CUSTOMER_URL = "http://kccrefinish.co.kr/"
WEBENGINE_CACHE_PATH = "/opt/alfa_cr6/data/webengine"


def tr_(s):
    return s


class BaseTableModel(QAbstractTableModel):  # pylint:disable=too-many-instance-attributes
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
        
        order_nr = None
        sel_model = self.parent().order_table_view.selectionModel()
        sel_orders = sel_model.selectedRows()
        if sel_orders:
            row = sel_orders[0].row()
            model = sel_orders[0].model()
            order_nr = model.results[row][3]

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
            QComboBox {background:#FFFFAA; }
            QPushButton { background-color: #F3F3F3F3;}
            QPushButton:pressed {background-color: #AAAAAA;}
            """
        )
        self.move(440, 100)
        # ~ self.resize(1080, 575)

        self.green_icon = QPixmap(os.path.join(IMAGES_PATH, "green.png"))
        self.red_icon = QPixmap(os.path.join(IMAGES_PATH, "red.png"))
        self.yellow_icon = QPixmap(os.path.join(IMAGES_PATH, "yellow.png"))
        self.gray_icon = QPixmap(os.path.join(IMAGES_PATH, "gray.png"))
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
        self.set_item_btn.clicked.connect(self.__on_set_item_clicked)
        self.remove_item_btn.clicked.connect(self.__on_delete_item_clicked)

        self.formula_table.itemSelectionChanged.connect(self.__on_formula_table_itemSelectionChanged)

        self.pigment_combo.currentTextChanged.connect(self.__on_pigment_combo_currentTextChanged)

        self.pigment_combo.setEditable(True)
        self.pigment_combo.setInsertPolicy(self.pigment_combo.NoInsert)

        self.remove_item_btn.setIcon(QIcon(self.remove_icon))

        self.remove_item_btn.setText(tr_("remove\nselected"))
        self.order_nr_lbl.setText(tr_("order n.:"))
        self.pigment_lbl.setText(tr_("pigment:"))
        self.quantity_lbl.setText(tr_("quantity (gr):"))
        self.edit_item_group_box.setTitle(tr_("edit or add item:"))

        self.order_nr = None
        self.available_pigments = {}

    def __check_row(self, pigment_name):

        rows = self.formula_table.rowCount()
        ret = []
        for row in range(rows):
            if self.formula_table.item(row, 1) and pigment_name == self.formula_table.item(row, 1).data(Qt.DisplayRole):
                ret.append(row)

        if len(ret) > 1:
            self.warning_lbl.setText(tr_('<div style="color: red;">WARN: replicated entries {}.</div>'.format(pigment_name)))

        return ret

    def __set_row(self, row, pigment_name, quantity, descr=None):

        old_pigment_name = self.formula_table.item(row, 1) and self.formula_table.item(row, 1).data(Qt.DisplayRole)
        if old_pigment_name and pigment_name != old_pigment_name:
            logging.warning(f"pigment_name:{pigment_name}, old_pigment_name:{old_pigment_name}")

        bgcol = None
        if self.available_pigments.get(pigment_name):
            icon = QIcon(self.green_icon)
            pig = self.available_pigments[pigment_name]
            descr = descr or pig.get("description")
            bgcol = QColor(pig.get("rgb"))
        else:
            icon = QIcon(self.gray_icon)
        self.formula_table.setItem(row, 0, QTableWidgetItem(icon, ""))
        self.formula_table.setItem(row, 1, QTableWidgetItem(str(pigment_name)))
        self.formula_table.setItem(row, 2, QTableWidgetItem("{:.3f}".format(float(quantity))))
        self.formula_table.setItem(row, 3, QTableWidgetItem(str((descr or "-"))))

        # ~ s = self.formula_table.model().index(row, 0)
        # ~ e = self.formula_table.model().index(row, 3)
        # ~ self.formula_table.selectionModel().select(QItemSelection(s, e), QItemSelectionModel.ClearAndSelect)

        # ~ logging.warning(f"bgcol:{bgcol}")
        if bgcol:
            self.formula_table.item(row, 3).setBackground(bgcol)

    def __on_pigment_combo_currentTextChanged(self):

        pigment_name = self.pigment_combo.currentText()
        indexes = self.__check_row(pigment_name)
        logging.warning(f"indexes:{indexes}, pigment_name:{pigment_name}.")

        if not indexes:
            self.formula_table.clearSelection()

    def __on_delete_item_clicked(self):

        try:
            sel_items = self.formula_table.selectedItems()
            if sel_items:
                sel_item = sel_items[0]
                row = sel_item.row()
                self.formula_table.removeRow(row)
                # ~ self.formula_table.setRowCount(self.formula_table.rowCount() - 1)
                logging.warning(f"row:{row}/{self.formula_table.rowCount()}.")
                self.warning_lbl.setText(tr_('modified.'))

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None)

    def __on_set_item_clicked(self):

        try:
            pigment_name = self.pigment_combo.currentText()
            quantity = float(self.quantity_line_edit.text())
            sel_items = self.formula_table.selectedItems()
            indexes = self.__check_row(pigment_name)
            logging.warning(f"indexes:{indexes}, pigment_name:{pigment_name}.")
            description = None
            if sel_items:
                sel_item = sel_items[0]
                row = sel_item.row()
                description = self.formula_table.item(row, 3).data(Qt.DisplayRole)
            else:
                if indexes:
                    row = indexes[0]
                    description = self.formula_table.item(row, 3).data(Qt.DisplayRole)
                else:
                    row = self.formula_table.rowCount()
                    self.formula_table.setRowCount(row + 1)

                self.formula_table.scrollToBottom()

            self.__set_row(row, pigment_name, quantity, descr=description)
            self.warning_lbl.setText(tr_('modified.'))
            self.__check_row(pigment_name)

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None)

    def __on_formula_table_itemSelectionChanged(self):

        try:
            sel_items = self.formula_table.selectedItems()
            if sel_items:
                sel_item = sel_items[0]
                row = sel_item.row()
                values_ = [self.formula_table.item(row, col).data(Qt.DisplayRole) for col in range(3)]

                logging.warning(f"row:{row}, values_:{values_}")

                self.pigment_combo.setCurrentText(str(values_[1]))
                self.quantity_line_edit.setText(str(values_[2]))

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None)

    def show_dialog(self, order_nr):   # pylint: disable=too-many-arguments

        self.order_nr = order_nr
        order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).one()

        properties = json.loads(order.json_properties)
        # ~ logging.warning(f"properties:{properties}")

        ingredients = properties.get('ingredients')
        meta_content = json.dumps(properties.get("meta", {}), indent=2)

        self.meta_text_edit.setText(meta_content)
        self.order_nr_view_lbl.setText(str(order_nr))

        self.formula_table.clearContents()
        self.formula_table.setRowCount(len(ingredients))
        self.formula_table.setColumnCount(4)

        self.available_pigments = {}
        for m in QApplication.instance().machine_head_dict.values():
            for pig in m.pigment_list:
                self.available_pigments[pig["name"]] = pig

        # ~ logging.warning(f"self.available_pigments:{self.available_pigments}.")
        self.pigment_combo.clear()
        self.pigment_combo.addItems(self.available_pigments.keys())

        completer = QCompleter(self.available_pigments.keys())
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.popup().setFont(QFont('Times sans-serif', 18))
        self.pigment_combo.setCompleter(completer)

        self.move(360 + random.randint(-80, 80), 10)

        self.warning_lbl.setText("")

        for row, item_ in enumerate(ingredients):
            self.__set_row(row, item_['pigment_name'], item_['weight(g)'], item_['description'])

        self.show()

    def save(self):   # pylint: disable=too-many-arguments

        order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == self.order_nr).one()

        _meta = json.loads(self.meta_text_edit.toPlainText())
        _ingredients = []
        cols = self.formula_table.columnCount()
        rows = self.formula_table.rowCount()
        for row in range(rows):
            values_ = [self.formula_table.item(row, col).data(Qt.DisplayRole) for col in range(cols)]
            ingredient = {
                'pigment_name': str(values_[1]),
                'weight(g)': float(values_[2]),
                'description': str(values_[3]),
            }
            _ingredients.append(ingredient)

        _properties = json.loads(order.json_properties)
        _properties['ingredients'] = _ingredients
        _properties['meta'] = _meta

        order.json_properties = json.dumps(_properties, indent=2)

        QApplication.instance().db_session.commit()


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
