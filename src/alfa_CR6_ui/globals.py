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
from PyQt5.QtCore import (  # ~ QItemSelectionModel, QItemSelection, QRect,
    Qt, QSize)

from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QStyle,
    QMessageBox,
    QFrame,
    QTableWidgetItem,
    QCompleter)

from alfa_CR6_backend.models import Order, Jar
from alfa_CR6_backend.dymo_printer import dymo_print

EPSILON = 0.00001

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


class ModalMessageBox(QMessageBox):  # pylint:disable=too-many-instance-attributes

    def __init__(self, msg="", title="", parent=None, ok_callback=None, ok_callback_args=None):   # pylint: disable=too-many-arguments
        super().__init__(parent=parent)

        self.ok_callback = ok_callback
        self.ok_callback_args = ok_callback_args

        self.setStyleSheet(
            """
                QMessageBox {
                    font-size: 20px;
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
        # ~ self.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)

        self.resize(800, 400)

        for i, b in enumerate(self.buttons()):
            if i == 0:
                b.setObjectName('esc')
                b.setText(tr_(' Cancel '))
                style_ = getattr(QStyle, "SP_MessageBoxCritical")
            elif i == 1:
                b.setObjectName('ok')
                b.setText(tr_('   OK   '))
                style_ = getattr(QStyle, "SP_DialogYesButton")

            b.setStyleSheet("""QWidget {font-size: 48px; font-family:Monospace;}""")
            b.setIcon(
                self.parent()
                .style()
                .standardIcon(style_))
            b.resize(300, 80)

        self.setWindowModality(0)
        self.setWindowFlags(
            self.windowFlags()
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.X11BypassWindowManagerHint
        )

        if self.ok_callback:
            def on_button_clicked(btn):
                logging.warning(f"btn:{btn}, btn.text():{btn.text()}")
                logging.warning(f"self.buttons().index(btn):{self.buttons().index(btn)}")

                # ~ if "ok" in btn.text().lower():
                if "ok" in btn.objectName().lower():
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
            QWidget {background:#CCBBBBBB; border: 1px solid #999999; border-radius: 4px;}
            QLabel {border: 0px;}
            QLineEdit {background:#FFFFAA; }
            QComboBox {background:#FFFFAA; }
            QPushButton { background-color: #F3F3F3F3;}
            QPushButton:pressed {background-color: #AAAAAA;}
            QSpinBox::up-button { height: 40px; width: 50px; }
            QSpinBox::down-button { height: 40px; width: 50px; }
            QCheckBox::indicator {width: 40px; height: 40px; color: #99FF99;}
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

        self.ok_button.clicked.connect(self.__save_changes)
        self.esc_button.clicked.connect(self.__discard_changes)
        self.set_item_btn.clicked.connect(self.__on_set_item_clicked)
        self.remove_item_btn.clicked.connect(self.__on_delete_item_clicked)

        self.formula_table.itemSelectionChanged.connect(self.__on_formula_table_itemSelectionChanged)

        self.pigment_combo.currentTextChanged.connect(self.__on_pigment_combo_currentTextChanged)
        
        self.n_of_jars_spinbox.valueChanged.connect(self.__on_n_of_jars_spinbox_valueChanged)

        self.pigment_combo.setEditable(True)
        self.pigment_combo.setInsertPolicy(self.pigment_combo.NoInsert)

        self.remove_item_btn.setIcon(QIcon(self.remove_icon))

        self.ok_button.setText(tr_("save changes"))
        self.esc_button.setText(tr_("discard changes"))
        self.remove_item_btn.setText(tr_("remove\nselected"))
        self.edit_item_group_box.setTitle(tr_("edit or add item:"))
        self.pigment_lbl.setText(tr_("pigment:"))
        self.quantity_lbl.setText(tr_("quantity (gr):"))
        self.jars_to_add_lbl.setText(tr_("n. of jars\nto add:"))
        self.print_check_box.setText(tr_("print\nbarcodes?"))

        self.order_nr = None
        self.available_pigments = {}

    def __on_n_of_jars_spinbox_valueChanged(self):

        if self.n_of_jars_spinbox.value() > 0:
            self.print_check_box.setEnabled(True)
            self.warning_lbl.setText(tr_('modified.'))
        else:
            self.print_check_box.setEnabled(False)
            self.print_check_box.setChecked(False)

    def __check_row(self, pigment_name):

        rows = self.formula_table.rowCount()
        ret = []
        for row in range(rows):
            if self.formula_table.item(row, 1) and pigment_name == self.formula_table.item(row, 1).data(Qt.DisplayRole):
                ret.append(row)

        if len(ret) > 1:
            self.warning_lbl.setText(
                tr_('<div style="color: red;">WARN: replicated entries {}.</div>'.format(pigment_name)))

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

            self.quantity_line_edit.setText('0.0')

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

    def __do_save_changes(self):  # pylint: disable=too-many-locals

        db_session = QApplication.instance().db_session

        try:
            order = db_session.query(Order).filter(Order.order_nr == self.order_nr).one()
            jar = db_session.query(Jar).filter(Jar.order == order).order_by(Jar.index.desc()).first()
            base_index = jar.index + 1 if jar else 1

            _meta = json.loads(self.meta_text_edit.toPlainText())
            _ingredients = []
            cols = self.formula_table.columnCount()
            rows = self.formula_table.rowCount()
            for row in range(rows):
                values_ = [self.formula_table.item(row, col).data(Qt.DisplayRole) for col in range(cols)]
                ingredient = {
                    'pigment_name': str(values_[1]),
                    'weight(g)': float(values_[2]),
                    'description': str(values_[3])}
                _ingredients.append(ingredient)

            _properties = json.loads(order.json_properties)
            _properties.update({'ingredients': _ingredients, 'meta': _meta})
            order.json_properties = json.dumps(_properties, indent=2)

            n_of_jars = self.n_of_jars_spinbox.value()
            barcodes = []
            for _indx in range(base_index, base_index + n_of_jars):
                jar = Jar(order=order, size=0, index=_indx)
                db_session.add(jar)
                barcodes.append(jar.barcode)

            db_session.commit()

            self.parent().order_page.populate_jar_table()

            logging.warning(f"self.print_check_box.isChecked() :{self.print_check_box.isChecked() }")
            logging.warning(f"barcodes:{barcodes}")
            if self.print_check_box.isChecked():
                for b in barcodes:
                    response = dymo_print(str(b))
                    logging.warning(f"response:{response}")
                    time.sleep(.05)

        except BaseException as e:  # pylint: disable=broad-except
            db_session.rollback()
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(
                f"exception:{e}", title="ERROR", callback=None, args=None)

        self.hide()

    def __save_changes(self):

        if self.warning_lbl.text():
            msg = tr_("confirm saving changes")
            n_of_jars = self.n_of_jars_spinbox.value()
            print_barcodes = self.print_check_box.isChecked()
            if n_of_jars:
                msg += tr_(",\ncreating {} jars").format(n_of_jars)
                if print_barcodes:
                    msg += tr_("\nand printing barcodes")
                else:
                    msg += tr_("\nwithout printing barcodes")
            msg += tr_(" ?")
            self.parent().open_alert_dialog(msg, title="ALERT", callback=self.__do_save_changes)
        else:
            self.hide()

    def __discard_changes(self):

        if self.warning_lbl.text():
            msg = tr_("confirm discarding changes?")
            self.parent().open_alert_dialog(msg, title="ALERT", callback=self.hide)
        else:
            self.hide()

    def show_dialog(self, order_nr):

        self.order_nr = order_nr
        order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).one()

        properties = json.loads(order.json_properties)
        # ~ logging.warning(f"properties:{properties}")

        ingredients = properties.get('ingredients', {})
        size = properties.get("size(cc)", "")
        meta = properties.get("meta", {})
        title = meta.get("basic information", {}).get("kcc code", tr_("order n.:"))
        meta_content = json.dumps(meta, indent=2)

        self.order_nr_lbl.setText(title)

        self.meta_text_edit.setText(meta_content)
        txt_ = "{}".format(order_nr)
        if size:
            txt_ += " <small>({}cc)</small>".format(size)
        self.order_nr_view_lbl.setText(txt_)

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

        self.move(360 + random.randint(-80, 80), 2)

        self.warning_lbl.setText("")
        self.quantity_line_edit.setText("")
        self.n_of_jars_spinbox.setValue(0)
        self.print_check_box.setEnabled(False)
        self.print_check_box.setChecked(False)

        for row, item_ in enumerate(ingredients):
            self.__set_row(row, item_['pigment_name'], item_['weight(g)'], item_['description'])

        self.show()


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
                try:
                    args_ = ok_cb_args if ok_cb_args is not None else []
                    ok_cb(*args_)
                except Exception as e:  # pylint: disable=broad-except
                    logging.error(traceback.format_exc())
                    self.parent().open_alert_dialog(
                        f"exception:{e}", title="ERROR", callback=None, args=None)
                    
            self.ok_button.clicked.connect(on_ok_button_clicked)

        self.show()
