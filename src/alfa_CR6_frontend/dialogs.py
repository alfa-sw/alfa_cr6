# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import logging
import json
import time
import traceback
import copy
import random
import asyncio
from datetime import datetime
from functools import partial

from PyQt5.uic import loadUi
from PyQt5.QtCore import (  # ~ QItemSelectionModel, QItemSelection, QRect,
    Qt, QSize, QItemSelectionModel)

from PyQt5.QtGui import QFont, QPixmap, QIcon, QColor
from PyQt5.QtWidgets import (
    QApplication,
    QStyle,
    QMessageBox,
    QFrame,
    QTableWidgetItem,
    QCompleter)

from alfa_CR6_backend.models import Order, Jar
from alfa_CR6_backend.dymo_printer import dymo_print_jar

from alfa_CR6_backend.globals import get_res, tr_


class ModalMessageBox(QMessageBox):  # pylint:disable=too-many-instance-attributes

    def enable_buttons(self, flag_ok, flag_esc, flag_hp=True):
        for i, b in enumerate(self.buttons()):
            if i == 0:
                b.setEnabled(flag_esc)
            elif i == 1 and len(self.buttons()) == 3:
                b.setEnabled(flag_hp)
            else:
                b.setEnabled(flag_ok)

    def __init__(
            self, msg="", title="", parent=None, ok_callback=None,
            ok_callback_args=None, hp_callback=None
    ):   # pylint: disable=too-many-arguments
        super().__init__(parent=parent)

        self.ok_callback = ok_callback
        self.ok_callback_args = ok_callback_args
        self.hp_callback = hp_callback

        self.help_icon = QPixmap(get_res("IMAGE", "help.png"))

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

        self.setWindowModality(2)

        if self.hp_callback:
            self.setStandardButtons(QMessageBox.Cancel | QMessageBox.Help | QMessageBox.Ok)
        else:
            self.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
        # ~ self.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)

        self.resize(800, 400)

        for i, b in enumerate(self.buttons()):
            if i == 0:
                b.setObjectName('esc')
                b.setText(tr_(' Cancel '))
                icon_ = self.parent().style().standardIcon(getattr(QStyle, "SP_MessageBoxCritical"))
            elif i == 1 and len(self.buttons()) == 3:
                b.setObjectName('help')
                b.setText(tr_(' Info '))
                icon_ = QIcon(self.help_icon)
            else:
                b.setObjectName('ok')
                b.setText(tr_('   OK   '))
                icon_ = self.parent().style().standardIcon(getattr(QStyle, "SP_DialogYesButton"))

            b.setStyleSheet("""QWidget {font-size: 48px; font-family:Monospace;}""")
            b.setIcon(icon_)
            b.resize(300, 80)

        if self.ok_callback or self.hp_callback:
            def on_button_clicked(btn):

                btn_name = btn.objectName().lower()
                logging.warning(f"btn_name:{btn_name}, btn:{btn}, btn.text():{btn.text()}")
                # ~ logging.warning(f"self.buttons().index(btn):{self.buttons().index(btn)}")

                # ~ if "ok" in btn.text().lower():
                if self.ok_callback and "ok" in btn_name:
                    args_ = self.ok_callback_args if self.ok_callback_args is not None else []
                    self.ok_callback(*args_)

                if self.hp_callback and "help" in btn_name:
                    self.hp_callback()

            self.buttonClicked.connect(on_button_clicked)

        # ~ t = time.asctime()
        t = time.strftime("%Y-%m-%d %H:%M:%S (%Z)")
        msg = "[{}]: {}\n\n{}\n\n".format(t, title, msg)

        self.setIcon(QMessageBox.Information)
        self.setText(msg)
        self.setWindowTitle(title)
        self.show()


class BaseDialog(QFrame):

    ui_file_name = ""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        loadUi(get_res("UI", self.ui_file_name), self)

        self.setStyleSheet(
            """
            QWidget {background:#CCBBBBBB; border: 1px solid #999999; border-radius: 4px;}
            QLabel {border: 0px;}
            QLineEdit {background:#FFFFAA; }
            QComboBox {background:#CCCCCC; }
            QPushButton { background-color: #F3F3F3F3;}
            QPushButton:pressed {background-color: #AAAAAA;}
            QSpinBox::up-button { height: 40px; width: 50px; }
            QSpinBox::down-button { height: 40px; width: 50px; }
            QCheckBox::indicator {width: 40px; height: 40px; color: #99FF99;}
            """
        )
        self.move(440, 100)
        # ~ self.resize(1080, 575)

        self.green_icon = QPixmap(get_res("IMAGE", "green.png"))
        self.red_icon = QPixmap(get_res("IMAGE", "red.png"))
        self.yellow_icon = QPixmap(get_res("IMAGE", "yellow.png"))
        self.gray_icon = QPixmap(get_res("IMAGE", "gray.png"))
        self.remove_icon = QPixmap(get_res("IMAGE", "remove.png"))
        self.add_icon = QPixmap(get_res("IMAGE", "add.png"))

        self.ok_button.setText(tr_("OK"))
        self.ok_button.setIcon(QIcon(self.green_icon))
        self.ok_button.setAutoFillBackground(True)

        self.esc_button.setText(tr_("Cancel"))
        self.esc_button.setIcon(QIcon(self.red_icon))
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
                tr_('<div style="color: red;">WARN: replicated entries {} ({}).</div>'.format(pigment_name, len(ret))))

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
        sel_items = self.formula_table.selectedItems()
        if sel_items:
            sel_item = sel_items[0]
            row = sel_item.row()
            sel_pigment_name = self.formula_table.item(row, 1).data(Qt.DisplayRole)
            if pigment_name != sel_pigment_name:
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
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

    def __on_set_item_clicked(self):

        try:
            pigment_name = self.pigment_combo.currentText()
            quantity = float(self.quantity_line_edit.text())
            sel_items = self.formula_table.selectedItems()
            description = None

            indexes = self.__check_row(pigment_name)
            logging.warning(f"indexes:{indexes}, pigment_name:{pigment_name}.")

            if sel_items:
                sel_item = sel_items[0]
                row = sel_item.row()
                description = self.formula_table.item(row, 3).data(Qt.DisplayRole)
                # ~ sel_pigment_name = self.formula_table.item(row, 1).data(Qt.DisplayRole)
            else:
                if len(indexes) >= 1:
                    raise Exception(tr_(' Pigment {} is already present.'.format(pigment_name)))

                row = self.formula_table.rowCount()
                self.formula_table.setRowCount(row + 1)
                self.formula_table.scrollToBottom()

            self.__set_row(row, pigment_name, quantity, descr=description)
            self.warning_lbl.setText(tr_('modified.'))
            self.quantity_line_edit.setText('')

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

    def __on_formula_table_itemSelectionChanged(self):

        try:

            sel_items = self.formula_table.selectedItems()
            if sel_items:
                sel_item = sel_items[0]
                row = sel_item.row()
                values_ = [self.formula_table.item(row, col).data(Qt.DisplayRole) for col in range(3)]
                self.pigment_combo.setCurrentText(str(values_[1]))
                self.quantity_line_edit.setText(str(values_[2]))

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

    def __do_save_changes(self):  # pylint: disable=too-many-locals

        db_session = QApplication.instance().db_session

        try:
            order = db_session.query(Order).filter(Order.order_nr == self.order_nr).one()
            jar = db_session.query(Jar).filter(Jar.order == order).order_by(Jar.index.desc()).first()
            base_index = jar.index + 1 if jar else 1

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

            _meta = _properties.get("meta", {})
            _meta.update({"modified": datetime.now().isoformat(" ", timespec='seconds')})

            _properties.update({'ingredients': _ingredients})
            order.json_properties = json.dumps(_properties, indent=2)

            QApplication.instance().do_fill_unknown_pigment_list(order)

            # ~ logging.warning(f"order.json_properties:{order.json_properties}")

            n_of_jars = self.n_of_jars_spinbox.value()
            jars_to_print = []
            for _indx in range(base_index, base_index + n_of_jars):
                jar = Jar(order=order, size=0, index=_indx)
                db_session.add(jar)
                jars_to_print.append(jar)

            order.update_status()

            db_session.commit()

            self.parent().order_page.populate_jar_table()
            self.parent().order_page.populate_order_table()

            logging.warning(f"self.print_check_box.isChecked() :{self.print_check_box.isChecked() }")
            if self.print_check_box.isChecked():
                for j in jars_to_print:
                    # ~ b = str(j.barcode)
                    # ~ logging.warning(f"b, j.extra_lines_to_print:{b, j.extra_lines_to_print}")
                    # ~ response = dymo_print(b, *j.extra_lines_to_print)
                    response = dymo_print_jar(j)
                    logging.warning(f"response:{response}")
                    time.sleep(.05)

        except BaseException as e:  # pylint: disable=broad-except
            db_session.rollback()
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

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
            self.parent().open_alert_dialog((), fmt="confirm discarding changes?", title="ALERT", callback=self.hide)
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
        extra_lines_to_print = properties.get("extra_lines_to_print", {})

        meta_content = json.dumps(meta, indent=2, ensure_ascii=False)
        extra_lines_ = "\n".join(extra_lines_to_print)
        self.meta_text_edit.setText(f"{extra_lines_}\n{meta_content}")

        # ~ title = meta.get("basic information", {}).get("kcc code", tr_("order n.:"))
        try:
            title = meta["basic information"]["kcc code"]
        except Exception:  # pylint: disable=broad-except
            title = tr_("order n.:")

        self.order_nr_lbl.setText(title)

        txt_ = "{}".format(order_nr)
        if size:
            txt_ += " <small>({}cc)</small>".format(size)
        self.order_nr_view_lbl.setText(txt_)

        self.formula_table.clearContents()
        self.formula_table.setRowCount(len(ingredients))
        self.formula_table.setColumnCount(4)

        self.available_pigments = QApplication.instance().get_available_pigments()

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
            self.__set_row(row, item_['pigment_name'], item_['weight(g)'], item_.get('description', ''))

        self.show()


class InputDialog(BaseDialog):

    ui_file_name = "input_dialog.ui"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.content_container.textChanged.connect(self.on_text_cahnged)
        self.combo_box.currentIndexChanged.connect(self.on_combo_box_index_changed)

        self.__ok_cb = None
        self.__ok_cb_args = None
        self.ok_on_enter = None

        self.choices = []

        # ~ self.ok_button.clicked.connect(self.hide)

    def get_selected_choice(self):

        key = self.content_container.toPlainText()
        return self.choices.get(key)

    def get_content_text(self):

        return self.content_container.toPlainText()

    def on_combo_box_index_changed(self, index): # pylint: disable=unused-argument

        txt_ = self.combo_box.currentText()
        self.content_container.setText(txt_)

    def on_ok_button_clicked(self):

        try:
            if self.__ok_cb:
                tmp__args_ = self.__ok_cb_args if self.__ok_cb_args is not None else []
                tmp__ok_cb = self.__ok_cb
                self.__ok_cb = None
                # ~ tmp__ok_cb(*tmp__args_)
                asyncio.get_event_loop().call_later(.05, partial(tmp__ok_cb, *tmp__args_))
        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

    def on_text_cahnged(self):

        if self.ok_on_enter and self.on_ok_button_clicked:
            cnt_ = self.content_container.toPlainText()
            if "\n" in cnt_:
                self.on_ok_button_clicked()

    def show_dialog(self,    # pylint: disable=too-many-arguments
        icon_name=None,
        message=None,
        content=None,
        ok_cb=None,
        ok_cb_args=None,
        ok_on_enter=False,
        choices=None,
        bg_image=None,
        to_html=None,
        wide=None):

        """ 'SP_MessageBoxCritical', 'SP_MessageBoxInformation', 'SP_MessageBoxQuestion', 'SP_MessageBoxWarning' """

        self.ok_on_enter = ok_on_enter

        if icon_name is None:
            icon_ = self.style().standardIcon(getattr(QStyle, "SP_MessageBoxWarning"))
        else:
            icon_ = self.style().standardIcon(getattr(QStyle, icon_name))
        self.icon_label.setPixmap(icon_.pixmap(QSize(64, 64)))

        if message is None:
            self.message_label.setText("")
        else:
            self.message_label.setText(str(message))

        if choices is None:
            self.combo_box.hide()
            self.combo_box.clear()
            self.combo_box.resize(self.combo_box.width(), 0)
        else:
            self.choices = choices
            # ~ logging.warning(f"choices:{choices}")
            keys_ = list(choices.keys())
            keys_.sort()
            self.combo_box.clear()
            for choice in keys_:
                self.combo_box.addItem(choice)
            self.combo_box.show()
            self.combo_box.resize(self.combo_box.width(), 40)

        if content is None:
            self.content_container.setText("")
            self.content_container.resize(self.content_container.width(), 0)
            self.resize(self.width(), 275)    
        else:
            if to_html:
                self.content_container.setHtml(str(content).replace("\n", "<br/>"))
            else:
                self.content_container.setText(str(content))
            self.content_container.resize(self.content_container.width(), 400)
            self.content_container.setFocus()
            cursor = self.content_container.textCursor()
            # ~ cursor.setPosition(cursor.End)
            cursor.setPosition(cursor.position() + len(str(content)))
            if wide:
                self.content_container.resize(self.content_container.width(), 700)    
                self.resize(self.width(), 875)    
            else:
                self.content_container.resize(self.content_container.width(), 400)    
                self.resize(self.width(), 575)    

        self.__ok_cb = None
        self.__ok_cb_args = None
        if ok_cb is not None:
            self.__ok_cb = ok_cb
            self.__ok_cb_args = ok_cb_args

        if bg_image is None:
            css_ = 'background-image:;'
        else:
            css_ = f"background-image:url({bg_image});background-repeat:no-repeat;background-position:center;"
            self.content_container.resize(self.content_container.width(), 400)
        self.content_container.setStyleSheet(css_)
        logging.warning(f"css_:{css_}")

        self.show()


class AliasDialog(BaseDialog):

    ui_file_name = "alias_dialog.ui"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.title_lbl.setText(tr_("edit alias for pigment names"))

        self.warning_lbl.setText('')

        self.alias_txt_label.setText(
            tr_("Please, select a pigment on the left, then insert below a list of altermative names, a name for each line. ") +
            tr_("(Trailing whitespaces will be discarded)"))
        self.alias_txt_label.setWordWrap(True)

        self.ok_button.clicked.connect(self.__save_changes)
        self.esc_button.clicked.connect(self.__discard_changes)

        self.pigment_table.itemSelectionChanged.connect(self.__on_pigment_table_itemSelectionChanged)

        self.alias_file_path = None
        self.alias_dict = None
        self.old_sel_pigment_name = None

    def __save_changes(self):

        if self.warning_lbl.text():

            msg = tr_("confirm saving changes")
            msg += tr_(" ?")
            # ~ msg += f"\n{json.dumps(self.alias_dict)}"
            self.parent().open_alert_dialog(msg, title="ALERT", callback=self._do_save_changes)
        else:
            self.hide()

    def __discard_changes(self):

        if self.warning_lbl.text():
            self.parent().open_alert_dialog((), fmt="confirm discarding changes?", title="ALERT", callback=self.hide)
        else:
            self.hide()

    def _do_save_changes(self):

        indexes = self.pigment_table.selectionModel().selectedIndexes()
        if indexes:
            index = self.pigment_table.model().index(
                (indexes[0].row() + 1) %
                self.pigment_table.rowCount(), indexes[0].column())
            self.pigment_table.selectionModel().select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

        self._dump_to_file()

        self.hide()

    def _dump_to_file(self):

        # ~ logging.warning("")

        if self._validate_alias_dict(self.alias_dict):

            if not os.path.exists(self.alias_file_path):
                os.makedirs(self.alias_file_path)
            _alias_file = os.path.join(self.alias_file_path, "pigment_alias.json")

            try:
                with open(_alias_file, 'w', encoding='UTF-8') as f:
                    json.dump(self.alias_dict, f, indent=2)
            except Exception as e:  # pylint:disable=broad-except
                logging.error(f"e:{e}")

    def _validate_alias_dict(self, alias_dict=None):

        if alias_dict is None:
            alias_dict = self.alias_dict

        _total_list = []
        _duplicated_list = []
        for k, v in alias_dict.items():
            for i in v:
                if i not in _total_list:
                    _total_list.append(i)
                else:
                    _duplicated_list.append((i, k))

        # ~ logging.warning(f"_duplicated_list:{_duplicated_list}")

        if _duplicated_list:
            self.parent().open_alert_dialog(tr_("data not valid. duplicated alias:") + f" {_duplicated_list}", title="ERROR")
            return False

        return True

    def _load_from_file(self):

        self.alias_dict = {}

        if not os.path.exists(self.alias_file_path):
            os.makedirs(self.alias_file_path)
        _alias_file = os.path.join(self.alias_file_path, "pigment_alias.json")
        try:
            with open(_alias_file, encoding='UTF-8') as f:
                self.alias_dict = json.load(f)
        except Exception as e:  # pylint:disable=broad-except
            logging.error(f"e:{e}")

        if not self._validate_alias_dict(self.alias_dict):
            self.alias_dict = {}

    def __set_row(self, row, pig):

        bgcol = QColor(pig.get("rgb"))
        self.pigment_table.setItem(row, 0, QTableWidgetItem(str(pig['name'])))
        self.pigment_table.setItem(row, 1, QTableWidgetItem(str(pig['description'])))

        if bgcol:
            self.pigment_table.item(row, 1).setBackground(bgcol)

    def __on_pigment_table_itemSelectionChanged(self):

        try:

            sel_items = self.pigment_table.selectedItems()

            # ~ logging.warning(f"sel_items:{sel_items}")

            if sel_items:
                sel_item = sel_items[0]
                row = sel_item.row()
                name_ = self.pigment_table.item(row, 0).data(Qt.DisplayRole)
                # ~ logging.warning(f"name_:{name_}")
                txt_ = "\n".join(self.alias_dict.get(name_, []))

                _tmp_alias_dict = copy.deepcopy(self.alias_dict)

                if self.old_sel_pigment_name:
                    new_ = [l.strip() for l in self.alias_txt_edit.toPlainText().split('\n') if l.strip()]
                    if new_ != _tmp_alias_dict.get(self.old_sel_pigment_name):
                        _tmp_alias_dict[self.old_sel_pigment_name] = new_
                        self.warning_lbl.setText(tr_('modified.'))

                if self._validate_alias_dict(_tmp_alias_dict):
                    self.alias_dict = _tmp_alias_dict

                if self.alias_txt_edit.receivers(self.alias_txt_edit.textChanged):
                    self.alias_txt_edit.textChanged.disconnect()
                self.alias_txt_edit.setPlainText(txt_)
                self.alias_txt_edit.textChanged.connect(lambda: self.warning_lbl.setText(tr_('modified.')))
                self.old_sel_pigment_name = name_

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

    def show_dialog(self, alias_file_path):

        self.alias_file_path = alias_file_path

        self._load_from_file()

        _available_pigments = QApplication.instance().get_available_pigments()

        self.pigment_table.clearContents()
        self.pigment_table.setRowCount(len(_available_pigments))
        self.pigment_table.setColumnCount(2)

        for row, pig_ in enumerate(_available_pigments.values()):
            self.__set_row(row, pig_)

        self.alias_txt_edit.setPlainText('')
        self.warning_lbl.setText('')
        self.old_sel_pigment_name = None

        index = self.pigment_table.model().index(0, 0)
        self.pigment_table.selectionModel().select(index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)

        self.move(360 + random.randint(-80, 80), 2)

        self.show()
