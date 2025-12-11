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
import aiohttp
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
    QCompleter,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QHBoxLayout,
    QDialogButtonBox,
    QTextBrowser,
    QSizePolicy,
    QLayout,
)

from alfa_CR6_backend.models import Order, Jar
from alfa_CR6_backend.dymo_printer import dymo_print_jar, dymo_print_package_label

from alfa_CR6_backend.globals import get_res, tr_, import_settings


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

                if self.ok_callback and "ok" in btn_name:
                    if getattr(self, 'executing_callback', False):
                        return
                    self.executing_callback = True

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

    def _log_db_event(self, msg, localized_msg, source=None, level="INFO"):
        alert_infos = {'fmt': msg, 'args': {}, 'msg_': msg, 'msg': localized_msg}
        json_properties_ = json.dumps(
            alert_infos,
            indent=2,
            ensure_ascii=False
        )

        QApplication.instance().insert_db_event(
            name='UI_DIALOG',
            level=level,
            severity='',
            source=source,
            json_properties=json_properties_,
            description=msg
        )


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
            _app_settings = import_settings()
            force_order_jar_to_one = getattr(_app_settings, 'FORCE_ORDER_JAR_TO_ONE', False)

            order = db_session.query(Order).filter(Order.order_nr == self.order_nr).one()
            jar = db_session.query(Jar).filter(Jar.order == order).order_by(Jar.index.desc()).first()

            base_index = jar.index if force_order_jar_to_one and jar else (jar.index + 1 if jar else 1)
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

            if not force_order_jar_to_one:
                for _indx in range(base_index, base_index + n_of_jars):
                    jar = Jar(order=order, size=0, index=_indx)
                    db_session.add(jar)
                    jars_to_print.append(jar)

            else:
                if not jar:
                    jar = Jar(order=order, size=0, index=base_index)
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
            args = ()
            msg = ["confirm saving changes"]
            n_of_jars = self.n_of_jars_spinbox.value()
            print_barcodes = self.print_check_box.isChecked()
            if n_of_jars:
                args = str(n_of_jars)
                msg.append(",\ncreating {} jars")
                if print_barcodes:
                    msg.append("\nand printing barcodes")
                else:
                    msg.append("\nwithout printing barcodes")
            msg.append(" ?")
            self.parent().open_alert_dialog(args, fmt=msg, title="ALERT", callback=self.__do_save_changes)
        else:
            self.hide()

    def __discard_changes(self):

        if self.warning_lbl.text():
            self.parent().open_alert_dialog((), fmt="confirm discarding changes?", title="ALERT", callback=self.hide)
        else:
            self.hide()

    def __customer_personalization_on_show_dialog(self):
        _app_settings = import_settings()

        if getattr(_app_settings, 'FORCE_ORDER_JAR_TO_ONE', False):
            self.n_of_jars_spinbox.setValue(1)
            self.n_of_jars_spinbox.setReadOnly(True)

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

        self.__customer_personalization_on_show_dialog()

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
        self.use_combo_for_choice = False

        # ~ self.ok_button.clicked.connect(self.hide)
        self.esc_button.clicked.connect(self.close_actions)

    def get_selected_choice(self):

        if getattr(self, 'use_combo_for_choice', False):
            key = self.combo_box.currentText()
            return self.choices.get(key)

        key = self.content_container.toPlainText()
        return self.choices.get(key)

    def get_content_text(self):

        return self.content_container.toPlainText()

    def on_combo_box_index_changed(self, index): # pylint: disable=unused-argument

        if getattr(self, 'use_combo_for_choice', False):
            return
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
        wide=None,
        content_editable=True,
        use_combo_for_choice=False):

        """ 'SP_MessageBoxCritical', 'SP_MessageBoxInformation', 'SP_MessageBoxQuestion', 'SP_MessageBoxWarning' """

        self.ok_on_enter = ok_on_enter
        self.use_combo_for_choice = bool(use_combo_for_choice)

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
            # Ensure a default valid selection
            if self.combo_box.count() > 0:
                self.combo_box.setCurrentIndex(0)
            self.combo_box.show()

            # Increase font and size when using combo for choices
            if self.use_combo_for_choice:
                try:
                    self.combo_box.setMinimumHeight(60)
                    self.combo_box.resize(self.combo_box.width(), 60)
                    self.combo_box.setStyleSheet(
                        """
                        QComboBox { font-size: 34px; min-height: 60px; }
                        QComboBox QAbstractItemView { font-size: 30px; }
                        QAbstractItemView::item { min-height: 48px; }
                        """
                    )
                    self.resize(self.width(), max(self.height(), 625))
                except Exception:
                    logging.error(traceback.format_exc())
                    pass
            else:
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

        if hasattr(self.content_container, 'setReadOnly'):
            self.content_container.setReadOnly(not content_editable)
        elif hasattr(self.content_container, 'setEditable'):
            self.content_container.setEditable(content_editable)

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

    def hide_dialog(self):
        self.hide()

    def close_actions(self):
        try:
            self.parent().toggle_keyboard(on_off=False)
            QApplication.instance().barcode_read_blocked_on_refill = False

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")


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
            self.parent().open_alert_dialog(_duplicated_list, fmt="data not valid. duplicated alias: {}", title="ERROR")
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


class RecoveryInfoDialog(QDialog):
    def __init__(self, parent=None, recovery_items=[], lbl_text=None, app_frozen=False, bottom_lbl_text=[]):
        super(RecoveryInfoDialog, self).__init__(parent)
        self.setWindowTitle("Recovery Information")
        self.setModal(True)
        self.setMinimumWidth(520)

        self.parent = parent
        self.app_frozen = app_frozen
        self.recovery_items = recovery_items
        self.rows = []

        self.main_layout = QVBoxLayout(self)

        if lbl_text:
            self.top_label = QLabel(tr_(lbl_text))
            self.top_label.setWordWrap(True)
            self.top_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.top_label.adjustSize()
            self.main_layout.addWidget(self.top_label)

        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setAlignment(Qt.AlignTop)

        self.main_layout.addWidget(self.rows_container)
        db_text = ["[RecoveryInfoDialog] \n"]
        db_text.append(lbl_text)
        for item in self.recovery_items.copy():
            _lbl = f"{item[0]} - {item[1]}"
            _flag = item[2]
            self.add_recovery_row(_lbl, _flag)
            db_text.append(_lbl)

        if bottom_lbl_text:
            qlbl_bottom = "\n".join(tr_(t) for t in bottom_lbl_text)
            self.bottom_label = QLabel(qlbl_bottom)
            self.bottom_label.setWordWrap(True)
            self.bottom_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.bottom_label.adjustSize()
            self.main_layout.addWidget(self.bottom_label)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        self.button_box.accepted.connect(self.close_modal)
        self.main_layout.addWidget(self.button_box)

        db_text.extend(bottom_lbl_text)
        self.store_event(db_text)
        self._apply_content_sizing()
        self.show()

    def add_recovery_row(self, text, recover_ok=True):

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)

        label = QLabel(text)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        css_color = "#2B842B" if recover_ok else "#BA2D09"
        label.setStyleSheet(f"color: {css_color};")

        delete_button = QPushButton("Delete")
        delete_button.setFixedSize(90, 30)
        delete_button.setStyleSheet("QPushButton { color: red; font-weight: bold; }")

        row_layout.addWidget(label)
        row_layout.addStretch()
        row_layout.addWidget(delete_button)

        self.rows_layout.addWidget(row_widget)
        self.rows.append(row_widget)

        self._apply_content_sizing()

        delete_button.clicked.connect(lambda: self.remove_recovery_row(row_widget))

    def remove_recovery_row(self, row_widget):
        if not self.app_frozen and self.parent:
            msg_ = "\nAutomation paused is required!"
            self.parent.open_alert_dialog(msg_, title="ERROR")
            return

        try:
            index = self.rows.index(row_widget)
        except ValueError:
            return

        if 0 <= index < len(self.recovery_items):
            _removed_item = self.recovery_items.pop(index)

        self.rows_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        self.rows.remove(row_widget)

        self._apply_content_sizing()

        label = row_widget.findChild(QLabel)
        if label:
            label_text = label.text()
            tokens = label_text.split('-', maxsplit=1)
            if len(tokens) == 2:
                barcode = tokens[0].strip()
                jar_pos = tokens[1]
                QApplication.instance().recovery_mode_delete_jar_task(barcode, jar_pos)
                delete_infos = ["DELETED", label_text]
                self.store_event(delete_infos)

    def _apply_content_sizing(self):

        if not hasattr(self, 'button_box'):
            return

        self.layout().activate()

        margins = self.main_layout.contentsMargins()
        spacing = self.main_layout.spacing()

        total_h = margins.top() + margins.bottom()

        if hasattr(self, 'top_label') and self.top_label is not None:
            self.top_label.adjustSize()
            total_h += self.top_label.sizeHint().height()
            total_h += spacing

        rows_h = 0
        for i in range(self.rows_layout.count()):
            item = self.rows_layout.itemAt(i)
            if item and item.widget():
                item.widget().adjustSize()
                rows_h += item.widget().sizeHint().height()
                rows_h += self.rows_layout.spacing()
        total_h += rows_h

        if hasattr(self, 'bottom_label') and self.bottom_label is not None:
            self.bottom_label.adjustSize()
            total_h += self.bottom_label.sizeHint().height()
            total_h += spacing

        self.button_box.adjustSize()
        total_h += self.button_box.sizeHint().height()

        desktop = QApplication.instance().desktop().availableGeometry(self)
        max_h = int(desktop.height() * 0.9)
        self.setMaximumHeight(max_h)

        min_w = max(
            self.minimumWidth(),
            self.top_label.sizeHint().width() if hasattr(self, 'top_label') and self.top_label is not None else 0,
            self.bottom_label.sizeHint().width() if hasattr(self, 'bottom_label') and self.bottom_label is not None else 0,
            self.button_box.sizeHint().width(),
        )
        self.setMinimumWidth(min_w + margins.left() + margins.right() + 20)

        self.resize(self.minimumWidth(), min(total_h, max_h))

    def close_modal(self):
        self.store_event("[RecoveryInfoDialog] popup closed")
        self.close()
    
    def store_event(self, db_text):
        # msg  -> localized msg for UI
        # msg_ -> non localized msg (eng) for db event

        _msg = _l_msg = db_text
        if isinstance(db_text, list):
            _l_msg = "\n".join(tr_(text) for text in db_text)
            _msg = "\n".join(text for text in db_text)
        recovery_infos = {'fmt': (), 'args': (), 'msg_': _msg, 'msg': _l_msg}
        json_properties_ = json.dumps(
            recovery_infos,
            indent=2,
            ensure_ascii=False
        )
        QApplication.instance().insert_db_event(
            name='UI_DIALOG',
            level="INFO",
            severity='',
            source="RecoveryInfoDialog",
            json_properties=json_properties_,
            description=_msg
        )
        
class RefillDialog(BaseDialog):

    ui_file_name = "refill_dialog.ui"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.content_container.textChanged.connect(self.on_text_changed)
        self.esc_button.clicked.connect(self.close_actions)

        self.__ok_cb = None
        self.__ok_cb_args = None
        self.ok_on_enter = None

        self.choices = []

    def close_actions(self):
        try:
            self.parent().toggle_keyboard(on_off=False)
            QApplication.instance().barcode_read_blocked_on_refill = False

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

    def get_content_text(self):

        return self.content_container.toPlainText()

    def on_text_changed(self):

        if self.on_ok_button_clicked:
            self.content_container.toPlainText()

    def _update_content_container(self, qtity_value):
        logging.warning("pressed")
        logging.warning(f"setting {qtity_value}")
        self.content_container.setPlainText(qtity_value)

    def _update_choice_buttons(self):

        def _format_value(v):
            try:
                f = float(v)
                return int(f) if f.is_integer() else round(f, 2)
            except Exception:
                return v

        for i, choice in enumerate(self.choices, start=1):
            button = self.findChild(QPushButton, f'refill_choice_{i}')
            logging.warning(button)
            if button is not None:
                # Support both numeric values and dicts like {"label": "FILL UP", "value": 123.45}
                if isinstance(choice, dict):
                    value = float(choice.get('value', 0) or 0)
                    label = str(choice.get('label', '') or '')
                    disp_val = _format_value(value)
                    button.setEnabled(value > 0)
                    button.setText(f"{label}\n{disp_val}".strip())
                    logging.warning(f'btn value: {value} ({label})')
                    button.clicked.connect(lambda _, v=value: self._update_content_container(str(v)))
                else:
                    value = float(choice)
                    disp_val = _format_value(value)
                    button.setEnabled(value > 0)
                    button.setText(str(disp_val))
                    logging.warning(f'btn value: {value}')
                    button.clicked.connect(lambda _, v=value: self._update_content_container(str(v)))

    def on_ok_button_clicked(self):

        try:
            if self.__ok_cb:
                tmp__args_ = self.__ok_cb_args if self.__ok_cb_args is not None else []
                tmp__ok_cb = self.__ok_cb
                self.__ok_cb = None
                # ~ tmp__ok_cb(*tmp__args_)
                asyncio.get_event_loop().call_later(.05, partial(tmp__ok_cb, *tmp__args_))
    
            QApplication.instance().barcode_read_blocked_on_refill = False

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.parent().open_alert_dialog(f"exception:{e}", title="ERROR")

    def show_dialog(self,    # pylint: disable=too-many-arguments
            icon_name=None,
            message=None,
            ok_cb=None,
            ok_cb_args=None,
            ok_on_enter=False,
            choices=None,
            unit=None
    ):

        self.content_container.setText("")
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

        logging.debug("choices -> %s", choices)
        if choices:
            self.choices = choices
            self._update_choice_buttons()

        self.__ok_cb = None
        self.__ok_cb_args = None
        if ok_cb is not None:
            self.__ok_cb = ok_cb
            self.__ok_cb_args = ok_cb_args

        if unit:
            self.unit_label.setText(unit)

        self.show()


class PackageSizesDialog(BaseDialog):

    ui_file_name = "package_sizes_dialog.ui"

    def __init__(self, parent=None):
        super().__init__(parent)

        self.overlay = None

        self.package_table.setColumnCount(3)
        self.package_table.setHorizontalHeaderLabels([tr_("Nome"), tr_("Size"), tr_("Barcode")])

        self.package_table.horizontalHeader().setVisible(True)
        self.package_table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #E0E0E0;
                padding: 4px;
                border: 1px solid #999999;
                font-weight: bold;
                font-size: 24px;
            }
        """)

        # Set font size for table content
        self.package_table.setStyleSheet("""
            QTableWidget {
                background-color: #AAFFFFFF;
                font-size: 20px;
            }
            QTableWidget::item {
                padding: 4px;
                font-size: 20px;
            }
        """)

        self.title_lbl.setStyleSheet("""
            QLabel {
                font-size: 26px;
            }
        """)

        self.ok_button.hide()
        self.esc_button.clicked.connect(self.hide)

        self._load_package_data_sync()

    def __set_row(self, row, package):

        name = package.get("name", "N/A")
        size = package.get("size", "N/A")
        description = package.get("description", "N/A")

        self.package_table.setItem(row, 0, QTableWidgetItem(str(name)))
        self.package_table.setItem(row, 1, QTableWidgetItem(str(size)))

        barcode_widget = QWidget()
        barcode_layout = QHBoxLayout(barcode_widget)
        barcode_layout.setContentsMargins(5, 5, 5, 5)

        barcode_label = QLabel()
        barcode_pixmap = QPixmap(get_res("IMAGE", "barcode_C128.png"))
        scaled_pixmap = barcode_pixmap.scaled(80, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        barcode_label.setPixmap(scaled_pixmap)
        barcode_label.setAlignment(Qt.AlignCenter)

        barcode_label.mousePressEvent = lambda event: self._generate_barcode_label(package)

        barcode_layout.addWidget(barcode_label)
        self.package_table.setCellWidget(row, 2, barcode_widget)

    def _generate_barcode_label(self, package):

        try:

            result = dymo_print_package_label(package, fake=False)
            logging.warning(f"result :: {result}")

            if result.get('result') == 'OK':
                return

            error_msg = result.get('msg', "")
            logging.error(error_msg)
            QApplication.instance().main_window.open_alert_dialog(
                (),
                fmt=error_msg,
                show_cancel_btn=False
            )

        except Exception as e:
            error_msg = [
                "[PackageSizesDialog]",
                "An unexpected error has been occurred"
            ]
            logging.error(traceback.format_exc())
            QApplication.instance().main_window.open_alert_dialog(
                (),
                fmt=error_msg,
                traceback=result.get('msg', 'UNKNOWN ERROR'),
                show_cancel_btn=False
            )

    def __show_error_in_table(self, error_msg, font_size=18):

        self.package_table.setColumnCount(1)
        self.package_table.setRowCount(1)
        self.package_table.horizontalHeader().setVisible(False)

        localized_err_msg = tr_(error_msg)
        item = QTableWidgetItem(localized_err_msg)
        font = QFont()
        font.setPointSize(font_size)
        font.setBold(True)
        item.setFont(font)

        item.setTextAlignment(Qt.AlignCenter)
        self.package_table.setItem(0, 0, item)
        self.package_table.resizeRowsToContents()
        self._log_db_event(error_msg, localized_err_msg, source="PackageSizesDialog")

    def _load_package_data_sync(self):

        app = QApplication.instance()

        machine_head = None
        for head in app.machine_head_dict.values():
            if head:
                machine_head = head
                break

        asyncio.ensure_future(self._async_load_package_data(machine_head))

    async def _async_load_package_data(self, machine_head):

        try:

            ret = await machine_head.call_api_rest("apiV1/package", "GET", {}, 1.5)

            if not ret or ret.get("objects") is None:
                error_msg = "HEAD 1 (A): no response or invalid data"
                self.__show_error_in_table(error_msg)
                return

            packages = ret.get("objects")

            if not packages:
                error_msg = "HEAD 1 (A): no package data found"
                self.__show_error_in_table(error_msg)
                return

            self.package_table.setRowCount(len(packages))
            for row, package in enumerate(packages):
                self.__set_row(row, package)

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            error_msg = f"An unexpected error has been occurred. {str(e)}"
            self.__show_error_in_table(error_msg)

    def _create_overlay(self):

        if not hasattr(self, 'overlay'):
            self.overlay = None

        if self.parent():
            self.overlay = QWidget(self.parent())
            self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 50);")
            self.overlay.resize(self.parent().size())
            self.overlay.move(0, 0)
            self.overlay.show()
            self.overlay.raise_()

            # Make sure dialog is above overlay
            self.raise_()

    def _remove_overlay(self):
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None

    def show_dialog(self):
        self._create_overlay()
        self.show()
        self.raise_()  # Ensure dialog is on top
        return self

    def hide(self):
        self._remove_overlay()
        super().hide()
