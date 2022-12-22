# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=multiple-statements
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import logging
import json
import time
import traceback
import codecs
import subprocess
import asyncio
# ~ import webbrowser
from functools import partial
# ~ from itertools import islice

from sqlalchemy.sql import or_

from PyQt5.uic import loadUi
from PyQt5.QtCore import (Qt, QVariant, QAbstractTableModel)

from PyQt5.QtGui import QPixmap, QTextDocument, QMovie
from PyQt5.QtWidgets import (
    QApplication,
    QStyle,
    QFrame,
    QPushButton,
    QLabel,
    QHeaderView)


from alfa_CR6_backend.models import Order, Jar, decompile_barcode
from alfa_CR6_backend.dymo_printer import dymo_print_jar
from alfa_CR6_backend.globals import (
    IMAGES_PATH, import_settings, get_res, get_encoding, tr_)

from alfa_CR6_frontend.debug_page import simulate_read_barcode


g_settings = import_settings()

ORDER_PAGE_COLUMNS_ORDERS = {
    'file': ["delete", "view", "create order", "file name"],
    'order': ["delete", "edit", "status", "order nr.", "file name"],
    'can': ["delete", "view", "status", "barcode"],
}
if hasattr(g_settings, 'ORDER_PAGE_COLUMNS_ORDERS'):
    ORDER_PAGE_COLUMNS_ORDERS.update(g_settings.ORDER_PAGE_COLUMNS_ORDERS)


class BaseTableModel(QAbstractTableModel):  # pylint:disable=too-many-instance-attributes

    page_limit = 20

    def __init__(self, parent, *args):

        super().__init__(parent, *args)
        self.gray_icon = QPixmap(get_res("IMAGE", "gray.png"))
        self.green_icon = QPixmap(get_res("IMAGE", "green.png"))
        self.red_icon = QPixmap(get_res("IMAGE", "red.png"))
        self.yellow_icon = QPixmap(get_res("IMAGE", "yellow.png"))
        self.orange_icon = QPixmap(get_res("IMAGE", "orange.png"))
        self.blue_icon = QPixmap(get_res("IMAGE", "blue.png"))
        self.add_icon = QPixmap(get_res("IMAGE", "add.png"))
        self.edit_icon = QPixmap(get_res("IMAGE", "edit.png"))
        self.barcode_C128_icon = QPixmap(get_res("IMAGE", "barcode_C128.png"))

        # ~ self.item_font = QFont('Times sans-serif', 32)
        self.results = [[]]

        self.main_window = QApplication.instance().main_window

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

    page_limit = 50

    def __init__(self, parent, path, *args):
        super().__init__(parent, *args)
        # ~ self.header = [tr_("delete"), tr_("view"), tr_("create order"), tr_("file name")]
        self.header = [tr_(s) for s in ORDER_PAGE_COLUMNS_ORDERS['file']]
        filter_text = parent.search_file_line.text()

        # ~ name_list_ = [p for p in os.listdir(path) if filter_text.lower() in p.lower()][:101]
        # ~ if len(name_list_) >= 100:
            # ~ args, fmt = (), "Too many files saved and not used. Please delete unused files."
            # ~ self.main_window.open_alert_dialog(args, fmt=fmt, title="ERROR")

        name_list_ = []
        for n in os.listdir(path):
            if filter_text.lower() in n.lower():
                name_list_.append(n)
            if len(name_list_) >= self.page_limit:
                # ~ args, fmt = (), "Too many files saved and not used. Please delete unused files."
                # ~ self.main_window.open_alert_dialog(args, fmt=fmt, title="ERROR")
                break

        name_list_.sort(reverse=True)
        # ~ self.results = [["", "", "", p] for p in name_list_]
        self.results = []
        for p in name_list_:
            item = ["", "", "", ""]
            item[ORDER_PAGE_COLUMNS_ORDERS['file'].index("file name")] = p
            self.results.append(item)

    def remove_file(self, file_name):  # pylint: disable=no-self-use
        cmd_ = f'rm -f "{os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)}"'
        logging.warning(f"cmd_:{cmd_}")
        os.system(cmd_)

    def data(self, index, role):
        # ~ logging.warning(f"index, role:{index, role}")
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['file'].index('delete'):
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_BrowserStop"))
        elif role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['file'].index('view'):
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_FileDialogInfoView"))
        elif role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['file'].index('create order'):
            ret = (
                self.parent()
                .style()
                .standardIcon(getattr(QStyle, "SP_FileDialogDetailedView"))
            )
        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]
        return ret


class OrderTableModel(BaseTableModel):

    page_limit = 50

    def __original_load_results(self, filter_text):

        if self.session:
            query_ = self.session.query(Order)
            query_ = query_.filter(Order.order_nr.contains(filter_text))
            query_ = query_.order_by(Order.order_nr.desc())

            query_1 = query_.filter(~ Order.jars.any()).limit(100)

            N = query_1.count()

            query_2 = query_.join(Jar).filter(Jar.position != "DELETED").limit(100 - N)

            self.results = []
            for o in query_1.all() + query_2.all():
                try:
                    file_name = o.get_json_property('meta', {}).get("file name", '')
                except Exception:  # pylint: disable=broad-except
                    logging.warning(traceback.format_exc())
                    file_name = ''
                item = ["", "", o.status, o.order_nr, file_name]
                self.results.append(item)

            self.results.sort(key=lambda x: x[3], reverse=True)

        else:
            self.results = [[]]

    def __load_results(self, filter_text):

        t0 = time.time()

        if self.session:

            show_deleted = "DEL;" in filter_text
            filter_text = "".join(filter_text.split("DEL;"))
            # ~ logging.warning(f"show_deleted:{show_deleted}, filter_text:{filter_text}")

            query_ = self.session.query(Order)

            if not show_deleted:
                fltr = or_(Order.is_deleted == None, Order.is_deleted.notlike('%yes%')) # pylint: disable=singleton-comparison
                query_ = query_.filter(fltr)

            if filter_text:
                fltr = or_(Order.order_nr.ilike(f'%{filter_text}%'), Order.file_name.ilike(f'%{filter_text}%'))
                query_ = query_.filter(fltr)

            query_ = query_.order_by(Order.order_nr.desc())
            query_ = query_.limit(self.page_limit)

            list_ = query_.all()

            # ~ logging.info(f"dt:{time.time() - t0}, len(list_):{len(list_)}")

            self.results = []
            for o in list_:
                item = ["", "", "", "", ""]
                item[ORDER_PAGE_COLUMNS_ORDERS['order'].index("status")] = o.status
                item[ORDER_PAGE_COLUMNS_ORDERS['order'].index("order nr.")] = o.order_nr
                item[ORDER_PAGE_COLUMNS_ORDERS['order'].index("file name")] = o.file_name
                self.results.append(item)
        else:
            self.results = [["", "", "", "", ""]]

        logging.info(f"dt:{time.time() - t0}")

    def __init__(self, parent, *args):

        super().__init__(parent, *args)
        self.session = QApplication.instance().db_session
        # ~ self.header = [tr_("delete"), tr_("edit"), tr_("status"), tr_("order nr."), tr_("file name")]
        self.header = [tr_(s) for s in ORDER_PAGE_COLUMNS_ORDERS['order']]
        filter_text = parent.search_order_line.text()
        self.__load_results(filter_text)

    def delete_order(self, order_nr):
        logging.warning(f"order_nr:{order_nr}, self.session:{self.session}")
        if self.session:
            order = self.session.query(Order).filter(Order.order_nr == order_nr).one()
            for j in order.jars:
                QApplication.instance().delete_jar_runner(j.barcode)
                j.position = 'DELETED'

            order.is_deleted = 'yes'

            self.session.commit()

    def data(self, index, role):
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['order'].index("delete"):
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_BrowserStop"))
        elif role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['order'].index("edit"):
            ret = self.edit_icon.scaled(32, 32, Qt.KeepAspectRatio)
        if role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['order'].index("status"):
            # ~ datum = str(index.data()).upper()
            datum = self.results[index.row()][index.column()]
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
            ret = tr_(self.results[index.row()][index.column()])
        return ret


class JarTableModel(BaseTableModel):

    page_limit = 50

    def __load_results(self, filter_text):

        _order_model = self.parent().order_model

        sel_model = self.parent().order_table_view.selectionModel()
        sel_orders = sel_model.selectedRows()
        indx_ = ORDER_PAGE_COLUMNS_ORDERS['order'].index("order nr.")
        if sel_orders:
            row = sel_orders[0].row()
            order_nr = _order_model.results[row][indx_]
            sel_order_nrs = [order_nr, ]
        else:
            sel_order_nrs = [r[indx_] for r in _order_model.results]

        # ~ logging.warning(f"sel_order_nrs:{sel_order_nrs}")

        if self.session:

            show_deleted = "DEL;" in filter_text
            filter_text = "".join(filter_text.split("DEL;"))
            # ~ logging.warning(f"show_deleted:{show_deleted}, filter_text:{filter_text}, sel_order_nrs:{sel_order_nrs}.")

            query_ = self.session.query(Jar)

            if not show_deleted:
                query_ = query_.filter(or_(Jar.position == None, Jar.position.notlike("DELETED"))) # pylint: disable=singleton-comparison

            if filter_text:
                query_ = query_.filter(Jar.status.contains(filter_text))

            if sel_order_nrs:
                query_ = query_.join(Order).filter(Order.order_nr.in_(sel_order_nrs))

            query_ = query_.order_by(Jar.index.desc()).limit(self.page_limit)

            def _fmt_status(o):
                if o.unknown_pigments or o.insufficient_pigments:
                    r = [o.status, "!"]
                else:
                    r = [o.status, ""]
                return r

            self.results = [["", "", _fmt_status(o), o.barcode] for o in query_.all()]
            self.results = []
            for o in query_.all():
                item = ["", "", "", ""]
                item[ORDER_PAGE_COLUMNS_ORDERS['can'].index("status")] = _fmt_status(o)
                item[ORDER_PAGE_COLUMNS_ORDERS['can'].index("barcode")] = o.barcode
                self.results.append(item)

            self.results.sort(key=lambda x: x[3], reverse=True)

        else:
            self.results = [[]]

    def __init__(self, parent, *args):

        super().__init__(parent, *args)
        self.session = QApplication.instance().db_session
        # ~ self.header = [tr_("delete"), tr_("view"), tr_("status"), tr_("barcode")]
        self.header = [tr_(s) for s in ORDER_PAGE_COLUMNS_ORDERS['can']]
        filter_text = parent.search_jar_line.text()

        self.__load_results(filter_text)

    def get_jar(self, barcode):

        jar = None
        order_nr, index = decompile_barcode(barcode)
        if self.session and order_nr and index >= 0:
            order = self.session.query(Order).filter(Order.order_nr == order_nr).one()
            query_ = self.session.query(Jar)
            query_ = query_.filter(Jar.order == order)
            query_ = query_.filter(Jar.index == index)
            jar = query_.first()

        return jar

    def delete_jar(self, barcode):

        QApplication.instance().delete_jar_runner(barcode)

        order_nr, index = decompile_barcode(barcode)
        if self.session and order_nr and index >= 0:
            order = self.session.query(Order).filter(Order.order_nr == order_nr).one()

            query_ = self.session.query(Jar)
            query_ = query_.filter(Jar.order == order)
            query_ = query_.filter(Jar.index == index)

            for j in query_.all():
                j.position = 'DELETED'

            # ~ if not [j for j in order.jars if j.position != "DELETED"]:
                # ~ order.is_deleted = 'yes'

            self.session.commit()

    def data(self, index, role):
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['can'].index("delete"):
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_BrowserStop"))
        elif role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['can'].index("view"):
            # ~ ret = self.parent().style().standardIcon(getattr(QStyle, "SP_FileDialogInfoView"))
            ret = self.barcode_C128_icon.scaled(80, 160, Qt.KeepAspectRatio)

        if role == Qt.DecorationRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['order'].index("status"):
            # ~ datum = index.data()
            datum = self.results[index.row()][index.column()]

            logging.debug(f"datum:{datum}")

            if "DONE" in datum[0]:
                if "!" in datum[1]:
                    ret = self.orange_icon.scaled(32, 32, Qt.KeepAspectRatio)
                else:
                    ret = self.gray_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif "ERR" in datum[0]:
                ret = self.red_icon.scaled(32, 32, Qt.KeepAspectRatio)
            elif "PROGRESS" in datum[0]:
                ret = self.yellow_icon.scaled(32, 32, Qt.KeepAspectRatio)
            else:
                ret = self.green_icon.scaled(32, 32, Qt.KeepAspectRatio)

        elif role == Qt.DisplayRole and index.column() == ORDER_PAGE_COLUMNS_ORDERS['can'].index("status"):
            datum = self.results[index.row()][index.column()]
            ret = tr_(datum[0]) + datum[1]
        elif role == Qt.DisplayRole:
            ret = self.results[index.row()][index.column()]

        return ret


class BaseStackedPage(QFrame):

    ui_file_name = ''
    help_file_name = ''

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        try:
            loadUi(get_res("UI", self.ui_file_name), self)
        except Exception:   # pylint: disable=broad-except
            logging.error(traceback.format_exc())

        self.main_window = self.parent()
        self.main_window.stacked_widget.addWidget(self)


class HelpPage(BaseStackedPage):

    ui_file_name = "help_page.ui"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.help_text_browser.anchorClicked.connect(self.__on_anchor_clicked)

        self.context_widget = None

        self.help_text_browser.document().setMetaInformation(QTextDocument.DocumentUrl, "file:" + IMAGES_PATH + "/")

    def __on_anchor_clicked(self, link):

        logging.warning(f"link:{link}")
        link_s = link.toString()

        if '#exit' in link_s:
            if self.context_widget:
                self.parent().setCurrentWidget(self.context_widget)
                self.hide()
        elif link_s.startswith("#ext:"):
            url_ = link_s.split("#ext:")[1]
            logging.warning(f"url_:{url_}")
            self.main_window.browser_page.open_page(url_)

    def open_page(self):

        w = self.parent().currentWidget()
        if w != self:
            self.context_widget = w

        logging.warning(f"self.context_widget:{self.context_widget}")

        if hasattr(self.context_widget, 'help_file_name') and self.context_widget.help_file_name:
            help_file_name = self.context_widget.help_file_name
            with open(get_res("HELP", help_file_name), encoding='UTF-8') as f:
                content = f.read()
                self.help_text_browser.setHtml(content)
            self.parent().setCurrentWidget(self)
        else:
            _msg = tr_("sorry, this help page is missing.")
            self.main_window.open_alert_dialog(_msg, title="ALERT")


class OrderPage(BaseStackedPage):

    ui_file_name = "order_page.ui"
    help_file_name = 'order.html'

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setStyleSheet("QWidget {font-size: 22px}")

        self.jar_table_view.horizontalScrollBar().setStyleSheet("QScrollBar:horizontal { height: 36px; }")
        self.order_table_view.horizontalScrollBar().setStyleSheet("QScrollBar:horizontal { height: 36px; }")
        self.file_table_view.horizontalScrollBar().setStyleSheet("QScrollBar:horizontal { height: 36px; }")

        self.jar_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.order_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.file_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.order_table_view.clicked.connect(self.__on_order_table_clicked)
        self.jar_table_view.clicked.connect(self.__on_jar_table_clicked)
        self.file_table_view.clicked.connect(self.__on_file_table_clicked)

        self._view_mix_btn.clicked.connect (partial(self.__on_toggle_view_clicked, 'mix'))
        self._view_file_btn.clicked.connect(partial(self.__on_toggle_view_clicked, 'file'))
        self._view_jar_btn.clicked.connect (partial(self.__on_toggle_view_clicked, 'jar'))

        self._view_mix_btn.setText(tr_('all'))
        self._view_file_btn.setText(tr_('files'))
        self._view_jar_btn.setText(tr_('cans'))

        self.new_order_btn.clicked.connect(self.__on_new_order_clicked)
        self.clone_order_btn.clicked.connect(self.__on_clone_order_clicked)

        self.purge_all_btn.clicked.connect(self.__on_purge_all_clicked)

        self.new_order_btn.setText(tr_("new"))
        self.clone_order_btn.setText(tr_("copy"))

        self.edit_aliases_btn.setText(tr_("alias"))

        self.search_order_line.textChanged.connect(self.populate_order_table)
        self.search_jar_line.textChanged.connect(self.populate_jar_table)
        self.search_file_line.textChanged.connect(self.populate_file_table)

        self.search_order_table_last_time = 0
        self.search_file_table_last_time = 0
        self.search_jar_table_last_time = 0

        self.order_model = 0
        self.file_model = 0
        self.jar_model = 0

        self.edit_aliases_btn.clicked.connect(self.main_window.open_alias_dialog)

        self.last_view_mode = 'mix'

    def populate_order_table(self):

        t = time.time()
        if t - self.search_order_table_last_time > 0.1:
            self.search_order_table_last_time = t
            try:
                self.order_model = OrderTableModel(self)
                self.order_table_view.setModel(self.order_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

            self.search_order_box.setTitle(
                tr_("[{}] Orders: search by order nr.").format(
                    self.order_model.rowCount()))

        logging.info(f"dt:{time.time() - t}")

    def populate_jar_table(self):

        t = time.time()
        if t - self.search_jar_table_last_time > 0.1:
            self.search_jar_table_last_time = t
            try:
                self.jar_model = JarTableModel(self)
                self.jar_table_view.setModel(self.jar_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
            self.search_jar_box.setTitle(tr_("[{}] Jars:   search by status").format(self.jar_model.rowCount()))

        logging.info(f"dt:{time.time() - t}")

    def populate_file_table(self):

        t = time.time()
        if t - self.search_file_table_last_time > 0.1:
            self.search_file_table_last_time = t
            try:
                self.file_model = FileTableModel(self, g_settings.WEBENGINE_DOWNLOAD_PATH)
                self.file_table_view.setModel(self.file_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
            self.search_file_box.setTitle(tr_("[{}] Files:  search by file name").format(self.file_model.rowCount()))

        logging.info(f"dt:{time.time() - t}")

    def __hide_toggle_view_buttons(self):

        self._view_mix_btn. setGeometry(0,  2000, 0, 0)
        self._view_file_btn.setGeometry(0,  2000, 0, 0)
        self._view_jar_btn. setGeometry(0,  2000, 0, 0)

        self._view_mix_btn. setEnabled(False)
        self._view_file_btn.setEnabled(False)
        self._view_jar_btn. setEnabled(False)

        self.search_jar_box.setGeometry  (  4,  10, 624-80, 860)
        self.jar_table_view.setGeometry  (  4, 120, 624-80, 860)

        self.search_order_box.setGeometry( 644-80-12,  10, 664+60, 860)
        self.order_table_view.setGeometry( 644-80-12, 120, 664+60, 860)

        self.search_file_box.setGeometry (1318-20-18,  10, 584+40, 860)
        self.file_table_view.setGeometry (1318-20-18, 120, 584+40, 860)


    def __on_toggle_view_clicked(self, view_mode=None):

        self._view_mix_btn. setEnabled(True)
        self._view_file_btn.setEnabled(True)
        self._view_jar_btn. setEnabled(True)

        self._view_mix_btn. setGeometry(  10,  956, 624, 34)
        self._view_file_btn.setGeometry( 644,  956, 624, 34)
        self._view_jar_btn. setGeometry(1278,  956, 624, 34)

        if view_mode == "jar":

            self._view_jar_btn.setEnabled(False)

            self.search_order_box.setGeometry(  10,  10, 940+200, 830)
            self.order_table_view.setGeometry(  10, 120, 940+200, 836)

            self.search_jar_box.setGeometry  ( 970+200,  10, 940-200, 830)
            self.jar_table_view.setGeometry  ( 970+200, 120, 940-200, 830)

            self.search_file_box.setGeometry (1840,  10,   0, 830)
            self.file_table_view.setGeometry (1840, 120,   0, 830)

            self.populate_jar_table()

        elif view_mode == "file":

            self._view_file_btn.setEnabled(False)

            self.search_order_box.setGeometry(  10,  10, 940, 830)
            self.order_table_view.setGeometry(  10, 120, 940, 830)

            self.search_file_box.setGeometry ( 970,  10, 940, 830)
            self.file_table_view.setGeometry ( 970, 120, 940, 830)

            self.search_jar_box.setGeometry  (1840,  10,   0, 830)
            self.jar_table_view.setGeometry  (1840, 120,   0, 830)

            self.populate_file_table()

        elif view_mode == "mix":

            self._view_mix_btn.setEnabled(False)

            self.search_jar_box.setGeometry  (  10,  10, 624, 830)
            self.jar_table_view.setGeometry  (  10, 120, 624, 830)

            self.search_order_box.setGeometry( 644,  10, 624, 830)
            self.order_table_view.setGeometry( 644, 120, 624, 830)

            self.search_file_box.setGeometry (1278,  10, 624, 830)
            self.file_table_view.setGeometry (1278, 120, 624, 830)

            self.populate_jar_table()
            self.populate_file_table()

        self.last_view_mode = view_mode

    @staticmethod
    def __on_purge_all_clicked():

        QApplication.instance().create_purge_all_order()

    def __on_order_table_clicked(self, index):

        datum = index.data()
        # ~ logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            indx_ = ORDER_PAGE_COLUMNS_ORDERS['order'].index("order nr.")
            order_nr = model.results[row][indx_]

            logging.warning(f"datum:{datum}, row:{row}, col:{col}, order_nr:{order_nr}")
            if col == ORDER_PAGE_COLUMNS_ORDERS['order'].index("delete"):

                def cb():
                    model.delete_order(order_nr)
                    self.populate_order_table()
                    self.populate_jar_table()

                msg_ = tr_("confirm deleting order '{}' and related jars?").format(order_nr)
                self.main_window.open_input_dialog(icon_name="SP_MessageBoxCritical", message=msg_, ok_cb=cb)

            elif col == ORDER_PAGE_COLUMNS_ORDERS['order'].index("edit"):

                self.main_window.open_edit_dialog(order_nr)

            self.populate_jar_table()

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def __on_jar_table_clicked(self, index):  # pylint: disable=too-many-locals

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            indx_ = ORDER_PAGE_COLUMNS_ORDERS['can'].index("barcode")
            barcode = model.results[row][indx_]
            logging.warning(f"row:{row}, col:{col}, barcode:{barcode}")
            if col == ORDER_PAGE_COLUMNS_ORDERS['can'].index("delete"):

                def cb():
                    model.delete_jar(barcode)
                    self.populate_jar_table()

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxCritical",
                    message=tr_("confirm deleting jar\n '{}' ?").format(barcode),
                    ok_cb=cb,
                )

            elif col == ORDER_PAGE_COLUMNS_ORDERS['can'].index("view"):
                content = "{}"
                msg_ = ""
                jar = model.get_jar(barcode)
                if jar:
                    content = tr_("status:{}\n").format(jar.status)
                    if jar.position:
                        content += tr_("position:{}\n").format(jar.position)
                    if jar.machine_head:
                        content += tr_("machine_head:{}\n").format(jar.machine_head)
                    content += tr_("description:{}\n").format(jar.description)
                    content += tr_("date_created:{}\n").format(jar.date_created)
                    content += tr_("properties:{}\n").format(
                        json.dumps(json.loads(jar.json_properties), indent=2))

                    msg_ = tr_("do you want to print barcode:\n {} ?").format(barcode)

                    self.main_window.open_input_dialog(
                        icon_name="SP_MessageBoxInformation",
                        message=msg_,
                        content=content,
                        ok_cb=dymo_print_jar,
                        ok_cb_args=[jar, ])

            elif col == ORDER_PAGE_COLUMNS_ORDERS['can'].index("status"):
                content = "{}"
                msg_ = ""
                jar = model.get_jar(barcode)
                if jar:
                    if jar.insufficient_pigments or jar.unknown_pigments:
                        msg_ = tr_("pigments to be added for barcode:\n {}").format(barcode)

                        content = '<div style="text-align: center;">'

                        content += ''.join([f'<div>{k}: {round(float(v), 4)} gr</div>' for k,
                                            v in jar.unknown_pigments.items()])

                        content += '<hr></hr>'

                        content += ''.join([f'<div>{k}: {round(float(v), 4)} gr</div>' for k,
                                            v in jar.insufficient_pigments.items()])

                        content += '</div>'

                        self.main_window.open_input_dialog(
                            icon_name="SP_MessageBoxInformation",
                            message=msg_,
                            content=content)

            elif col == ORDER_PAGE_COLUMNS_ORDERS['can'].index("barcode"):
                pass

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def __on_file_table_clicked(self, index):   # pylint: disable=too-many-locals

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            indx_ = ORDER_PAGE_COLUMNS_ORDERS['file'].index("file name")
            file_name = model.results[row][indx_]
            logging.warning(f"row:{row}, col:{col}, file_name:{file_name}")
            if col == ORDER_PAGE_COLUMNS_ORDERS['file'].index("delete"):

                def cb():
                    model.remove_file(file_name)
                    self.populate_file_table()

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxCritical",
                    message=tr_("confirm deleting file\n '{}' ?").format(file_name),
                    ok_cb=cb)

            elif col == ORDER_PAGE_COLUMNS_ORDERS['file'].index("view"):

                content = "{}"
                split_ext = os.path.splitext(file_name)
                if split_ext[1:] and split_ext[1] == '.pdf':
                    pth_ = os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)
                    out_pth_ = f'{pth_}.txt'.replace(" ", "_")
                    cmd_ = 'pdftotext -raw "{}" "{}"'.format(pth_, out_pth_)
                    logging.warning(f"cmd_:{cmd_}")
                    # ~ process = await asyncio.create_subprocess_exec(
                    # ~ cmd_, stdout=asyncio.subprocess.PIPE, limit=10000)
                    os.system(cmd_)
                    # ~ stdout, stderr = await process.communicate()
                    with open(out_pth_, encoding='UTF-8') as f:
                        content = f.read().strip()
                    subprocess.run(["rm", "-f", out_pth_], check=False)
                else:
                    pth_ = os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)
                    e = get_encoding(pth_, key=None)
                    with codecs.open(pth_, encoding=e) as f:
                        content = f.read(100 * 1000)
                        split_ext = os.path.splitext(pth_)
                        if split_ext[1:] and split_ext[1] == '.json':
                            try:
                                content = json.dumps(json.loads(content), indent=2)
                            except Exception:  # pylint: disable=broad-except
                                logging.error(traceback.format_exc())

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxInformation",
                    message=tr_("file_name:{}").format(file_name),
                    content=content)

            elif col == ORDER_PAGE_COLUMNS_ORDERS['file'].index("create order"):

                _msg = tr_("confirm creating order from file (file will be deleted):\n '{}'?\n").format(file_name)
                _msg += tr_('Please, insert below the number of jars.')
                self.main_window.open_input_dialog(
                    message=_msg,
                    content="<span align='center'>1</span>",
                    ok_cb=self.__create_order_cb,
                    ok_cb_args=[model, file_name])

            elif col == ORDER_PAGE_COLUMNS_ORDERS['file'].index("file name"):
                pass

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def __on_new_order_clicked(self):

        try:
            # ~ new_order = QApplication.instance().create_order()
            new_order = QApplication.instance().create_new_order()
            if new_order:
                msg = tr_("created order:{}.").format(new_order.order_nr)
                self.main_window.open_alert_dialog(msg, title="INFO")
                self.populate_order_table()
                self.populate_jar_table()

            # ~ s = self.order_table_view.model().index(row, 0)
            # ~ e = self.order_table_view.model().index(row, 3)
            # ~ self.formula_table.selectionModel().select(QItemSelection(s, e), QItemSelectionModel.ClearAndSelect)

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def __on_clone_order_clicked(self):

        try:
            order_nr = None
            sel_model = self.order_table_view.selectionModel()
            sel_orders = sel_model.selectedRows()
            if sel_orders:
                row = sel_orders[0].row()
                model = sel_orders[0].model()
                order_nr = model.results[row][3]
                order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).first()
                if order:
                    cloned_order = QApplication.instance().clone_order(order_nr)
                    msg = tr_("cloned order:{} \n from:{}.").format(cloned_order.order_nr, order.order_nr)
                    self.main_window.open_alert_dialog(msg, title="INFO")
                    self.populate_order_table()
                    self.populate_jar_table()
            else:
                self.main_window.open_alert_dialog(tr_("no item selected. Please, select one to clone."))
        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def __create_order_cb(self, model, file_name):

        app = QApplication.instance()

        n = int(self.main_window.input_dialog.get_content_text())
        n = min(n, 20)
        logging.warning(f"n:{n}")
        path_to_file = os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)
        # ~ order = app.create_order(path_to_file, n_of_jars=n)
        orders = app.create_orders_from_file(path_to_file, n_of_jars=n)

        def print_label_cb_(jars_to_print):
            for a in jars_to_print:
                logging.warning(f"a:{a}")
                response = dymo_print_jar(a)
                logging.warning(f"response:{response}")
                time.sleep(.05)

        ok_flag = False
        jars_to_print = []
        for order in orders:
            if order:
                properties = json.loads(order.json_properties)
                logging.warning(f"properties:{properties}")
                if properties and properties.get('meta') and not properties['meta'].get('error'):

                    ok_flag = True

                    jars_ = list(order.jars)
                    jars_.sort(key=lambda j: str(j.barcode))
                    jars_to_print += jars_

        if ok_flag:
            model.remove_file(file_name)

            logging.warning(f"file_name:{file_name}, jars_to_print:{jars_to_print}")

            msg_ = tr_("confirm printing {} barcodes?").format(len(jars_to_print))
            self.main_window.open_input_dialog(message=msg_, content="{}".format(
                [str(j.barcode) for j in jars_to_print]), ok_cb=print_label_cb_, ok_cb_args=[jars_to_print, ])

        self.populate_file_table()
        self.populate_order_table()
        self.populate_jar_table()

    def open_page(self):

        self.search_order_line.setText("")
        self.search_jar_line  .setText("")
        self.search_file_line .setText("")

        self.populate_order_table()
        # ~ self.populate_jar_table()
        # ~ self.populate_file_table()

        self.__on_toggle_view_clicked(view_mode=self.last_view_mode)

        # ~ self.__hide_toggle_view_buttons()

        self.parent().setCurrentWidget(self)

        QApplication.instance().update_tintometer_data_on_all_heads()


class ActionPage(BaseStackedPage):

    ui_file_name = "action_frame.ui"

    def __do_action(self, args):
        logging.warning(f"args:{args}")
        if args[0] == 'open_home_page':
            self.parent().setCurrentWidget(self.main_window.home_page)
        else:
            try:
                QApplication.instance().run_a_coroutine_helper(args[0], *args[1:])
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

    def __do_show_val(self, w, head_letter, bit_name, text):
        logging.debug(f"self:{self}")
        try:
            m = QApplication.instance().get_machine_head_by_letter(head_letter)
            if bit_name.lower() == "container_presence":
                val_ = m.status.get("container_presence")
            else:
                val_ = m.jar_photocells_status.get(bit_name)

            pth_ = (
                get_res("IMAGE", "green.png")
                if val_ else get_res("IMAGE", "gray.png")
            )
            w.setText(
                f'<img widt="50" height="50" src="{pth_}" style="vertical-align:middle;">{tr_(text)}</img>'
            )
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def __init__(self, action_item, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setStyleSheet(
            """
            QFrame { border: 1px solid #999999; border-radius: 4px; background-color: #FEFEFE;}
            QWidget {font-size: 24px;}
            QLabel { border-width: 0px; background-color: #FFFFFF;}
            QPushButton { background-color: #EEEEEE; border: 1px solid #999999; border-radius: 4px;}
            QPushButton:pressed {background-color: #AAAAAA;}
            """
        )

        self.action_title_label.setText(tr_(action_item["title"]))

        for b in action_item["buttons"]:
            i = QPushButton(tr_(b["text"]), self)
            i.setFixedHeight(50)
            if b.get("action_args"):
                args_ = b.get("action_args")
                i.clicked.connect(partial(self.__do_action, args_))
            self.action_buttons_layout.addWidget(i)

        for l in action_item["labels_args"]:
            if l:
                i = QLabel(self)
                i.setTextFormat(Qt.RichText)
                args_ = [i, ] + list(l)
                setattr(i, "show_val", partial(self.__do_show_val, *args_))
                self.action_labels_layout.addWidget(i)


class HomePage(BaseStackedPage):

    def __init__(self, *args, **kwargs):  # pylint:disable=too-many-branches, too-many-statements

        super().__init__(*args, **kwargs)

        self.running_jars_lbl.setStyleSheet("font-size: 15px")

        for b in self.action_btn_group.buttons():
            b.setStyleSheet(
                """QPushButton { background-color: #00FFFFFF; border: 0px;}"""
            )

        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)
        self.action_btn_group.buttonClicked.connect(self.on_action_btn_group_clicked)

        self.reserve_movie = QMovie(get_res("IMAGE", "riserva.gif"))
        self.expiry_movie = QMovie(get_res("IMAGE", "expiry.gif"))

        if self.STEP_01_label:
            self.STEP_01_label.mouseReleaseEvent = lambda event: self.step_label_clicked("IN")
        if self.STEP_02_label:
            self.STEP_02_label.mouseReleaseEvent = lambda event: self.step_label_clicked("A")
        if self.STEP_03_label:
            self.STEP_03_label.mouseReleaseEvent = lambda event: self.step_label_clicked("B")
        if self.STEP_04_label:
            self.STEP_04_label.mouseReleaseEvent = lambda event: self.step_label_clicked("C")
        if self.STEP_05_label:
            self.STEP_05_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTR_UP")
        if self.STEP_06_label:
            self.STEP_06_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTR_DOWN")
        if self.STEP_07_label:
            self.STEP_07_label.mouseReleaseEvent = lambda event: self.step_label_clicked("D")
        if self.STEP_08_label:
            self.STEP_08_label.mouseReleaseEvent = lambda event: self.step_label_clicked("E")
        if self.STEP_09_label:
            self.STEP_09_label.mouseReleaseEvent = lambda event: self.step_label_clicked("F")
        if self.STEP_10_label:
            self.STEP_10_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTL_DOWN")
        if self.STEP_11_label:
            self.STEP_11_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTL_UP")
        if self.STEP_12_label:
            self.STEP_12_label.mouseReleaseEvent = lambda event: self.step_label_clicked("OUT")

        if self.reserve_1_label:
            self.reserve_1_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(0)
        if self.reserve_2_label:
            self.reserve_2_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(1)
        if self.reserve_3_label:
            self.reserve_3_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(2)
        if self.reserve_4_label:
            self.reserve_4_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(3)
        if self.reserve_5_label:
            self.reserve_5_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(4)
        if self.reserve_6_label:
            self.reserve_6_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(5)

        if self.expiry_1_label:
            self.expiry_1_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(0)
        if self.expiry_2_label:
            self.expiry_2_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(1)
        if self.expiry_3_label:
            self.expiry_3_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(2)
        if self.expiry_4_label:
            self.expiry_4_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(3)
        if self.expiry_5_label:
            self.expiry_5_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(4)
        if self.expiry_6_label:
            self.expiry_6_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(5)

        if self.refill_1_lbl: self.refill_1_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(0)
        if self.refill_2_lbl: self.refill_2_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(1)
        if self.refill_3_lbl: self.refill_3_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(2)
        if self.refill_4_lbl: self.refill_4_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(3)
        if self.refill_5_lbl: self.refill_5_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(4)
        if self.refill_6_lbl: self.refill_6_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(5)

    def open_page(self):

        self.parent().setCurrentWidget(self)

    def on_service_btn_group_clicked(self, btn):

        btn_name = btn.objectName()

        try:
            service_page_urls = ["http://127.0.0.1:8080/service_page/", ]
            for i in QApplication.instance().settings.MACHINE_HEAD_IPADD_PORTS_LIST:
                if i:
                    url = "http://{}:{}/service_page/".format(i[0], i[2])
                else:
                    url = None
                service_page_urls.append(url)

            service_btns = [
                self.service_0_btn,
                self.service_1_btn,
                self.service_2_btn,
                self.service_3_btn,
                self.service_4_btn,
                self.service_5_btn,
                self.service_6_btn,
            ]

            map_ = dict(zip(service_btns, service_page_urls))

            head_index = service_btns.index(btn) - 1
            logging.debug(f"btn_name:{btn_name}, map_[btn]:{map_[btn]}, map_:{map_}, head_index:{head_index}")
            self.main_window.browser_page.open_page(map_[btn], head_index=head_index)

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def on_action_btn_group_clicked(self, btn):

        btn_name = btn.objectName()
        try:
            if "feed" in btn_name:
                if hasattr(g_settings, 'SIMULATE_READ_BARCODE') and getattr(g_settings, 'SIMULATE_READ_BARCODE'):
                    allowed_jar_statuses = g_settings.SIMULATE_READ_BARCODE.get("allowed_jar_statuses", ("NEW", "DONE"))
                    simulate_read_barcode(allowed_jar_statuses)
                else:
                    QApplication.instance().run_a_coroutine_helper("move_00_01")

            elif "deliver" in btn_name:
                QApplication.instance().run_a_coroutine_helper("move_12_00")
            elif "freeze_carousel" in btn_name:
                msg_ = (
                    tr_("confirm unfreezing carousel?")
                    if QApplication.instance().carousel_frozen
                    else tr_("confirm freezing carousel?")
                )
                self.main_window.open_input_dialog(
                    icon_name=None,
                    message=msg_,
                    content=None,
                    ok_cb=QApplication.instance().toggle_freeze_carousel,
                )
            elif "action_" in btn_name:
                self.parent().setCurrentWidget(self.main_window.action_frame_map[btn])

            for i, m in QApplication.instance().machine_head_dict.items():
                if m:
                    self.main_window.update_status_data(i)

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def update_expired_products(self, head_index):

        map_ = [
            self.expiry_1_label,
            self.expiry_2_label,
            self.expiry_3_label,
            self.expiry_4_label,
            self.expiry_5_label,
            self.expiry_6_label,
        ]

        m = QApplication.instance().machine_head_dict.get(head_index)
        try:
            if m and map_[head_index]:

                # ~ logging.warning(f"head_index:{head_index}, m.expired_products:{m.expired_products}")

                if m.expired_products:
                    map_[head_index].setMovie(self.expiry_movie)
                    self.expiry_movie.start()
                    map_[head_index].show()
                else:
                    map_[head_index].setText("")
                    map_[head_index].hide()

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def update_service_btns__presences_and_lifters(self, head_index):

        status = QApplication.instance().machine_head_dict[head_index].status

        map_ = [
            self.service_1_btn,
            self.service_2_btn,
            self.service_3_btn,
            self.service_4_btn,
            self.service_5_btn,
            self.service_6_btn,
        ]
        if map_[head_index]:
            map_[head_index].setText(tr_(f"{status.get('status_level', 'NONE')}"))

        map_ = [
            self.container_presence_1_label,
            self.container_presence_2_label,
            self.container_presence_3_label,
            self.container_presence_4_label,
            self.container_presence_5_label,
            self.container_presence_6_label,
        ]

        if map_[head_index]:
            if status.get("container_presence"):
                map_[head_index].setPixmap(self.main_window.green_icon)
            else:
                map_[head_index].setPixmap(self.main_window.gray_icon)

            # ~ lifter positions
            self.__set_pixmap_by_photocells(self.load_lifter_up_label,
                                            (("D", "LOAD_LIFTER_UP_PHOTOCELL"),), icon=self.main_window.green_icon)
            self.__set_pixmap_by_photocells(self.load_lifter_down_label,
                                            (("D", "LOAD_LIFTER_DOWN_PHOTOCELL"),), icon=self.main_window.green_icon)
            self.__set_pixmap_by_photocells(self.unload_lifter_up_label,
                                            (("F", "UNLOAD_LIFTER_UP_PHOTOCELL"),), icon=self.main_window.green_icon)
            self.__set_pixmap_by_photocells(self.unload_lifter_down_label,
                                            (("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"),), icon=self.main_window.green_icon)

    def update_tank_pixmaps(self):
        map_ = [
            self.refill_1_lbl,
            self.refill_2_lbl,
            self.refill_3_lbl,
            self.refill_4_lbl,
            self.refill_5_lbl,
            self.refill_6_lbl,
        ]

        for head_index, m in QApplication.instance().machine_head_dict.items():
            if m and map_[head_index]:
                status = m.status
                crx_outputs_status = m.status.get('crx_outputs_status', 0x1)
                if (not crx_outputs_status and
                        status.get('status_level', '') in ("STANDBY", ) and
                        QApplication.instance().carousel_frozen):

                    map_[head_index].setPixmap(self.main_window.tank_icon_map['green'])
                else:
                    map_[head_index].setPixmap(self.main_window.tank_icon_map['gray'])

                map_[head_index].setText("")

    def update_jar_pixmaps(self):

        list_ = []
        for k, j in QApplication.instance().get_jar_runners().items():
            if j['jar'].position:
                if j['jar'].status == 'ERROR':
                    _color = "#990000"
                else:
                    _color = "#005500"
                _ = f"""<span style="color:{_color};background-color:#EEEEEE;">{k} ({j['jar'].position[0]})</span>"""
                list_.append(f"{_ : >4}")
        self.running_jars_lbl.setText("\n".join(list_))

        map_ = [
            (self.STEP_01_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),), "IN_A",),
            (self.STEP_02_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "A",),
            (self.STEP_03_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "B",),
            (self.STEP_04_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "C",),
            (self.STEP_05_label, (("D", "LOAD_LIFTER_UP_PHOTOCELL"), ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTR_UP",),
            (self.STEP_06_label, (("D", "LOAD_LIFTER_DOWN_PHOTOCELL"), ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTR_DOWN",),
            (self.STEP_07_label, (("D", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "D",),
            (self.STEP_08_label, (("E", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "E",),
            (self.STEP_09_label, (("F", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "F",),
            (self.STEP_10_label, (("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"), ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTL_DOWN",),
            (self.STEP_11_label, (("F", "UNLOAD_LIFTER_UP_PHOTOCELL"), ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTL_UP",),
            (self.STEP_12_label, (("F", "JAR_OUTPUT_ROLLER_PHOTOCELL"),), "OUT",),
        ]

        for lbl, head_letters_bit_names, position in map_:
            if lbl:
                self.__set_pixmap_by_photocells(lbl, head_letters_bit_names, position)

    @staticmethod
    def __set_pixmap_by_photocells(  # pylint: disable=too-many-locals
            lbl, head_letters_bit_names, position=None, icon=None):

        if lbl:
            def _get_bit(head_letter, bit_name):
                m = QApplication.instance().get_machine_head_by_letter(head_letter)
                ret = m.jar_photocells_status.get(bit_name) if m else None
                return ret

            try:

                false_condition = [
                    1 for h, b in head_letters_bit_names if not _get_bit(h, b)
                ]

                if icon is None:
                    if false_condition:
                        lbl.setStyleSheet("QLabel {{}}")
                        lbl.setText("")
                    else:
                        _text = ""
                        _status = ""
                        for j in QApplication.instance().get_jar_runners().values():
                            pos = j["jar"].position
                            if pos == position:
                                _status = j["jar"].status
                                _bc = str(j["jar"].barcode)
                                _text = _bc[-6:-3] + "\n" + _bc[-3:]
                                break

                        if _status == "ERROR":
                            _img_url = get_res("IMAGE", "jar-red.png")
                        else:
                            if _text:
                                _img_url = get_res("IMAGE", "jar-green.png")
                            else:
                                _img_url = get_res("IMAGE", "jar-gray.png")

                        lbl.setStyleSheet(
                            'color:#000000; border-image:url("{0}"); font-size: 15px'.format(_img_url))
                        lbl.setText(_text)
                else:
                    size = [0, 0] if false_condition else [32, 32]
                    pixmap = icon.scaled(*size, Qt.KeepAspectRatio)
                    lbl.setPixmap(pixmap)

                lbl.show()

            except Exception as e:  # pylint: disable=broad-except
                QApplication.instance().handle_exception(e)

    def show_reserve(self, head_index, flag=None):

        map_ = [
            self.reserve_1_label,
            self.reserve_2_label,
            self.reserve_3_label,
            self.reserve_4_label,
            self.reserve_5_label,
            self.reserve_6_label,
        ]

        if map_[head_index]:
            if flag is None:
                flag = not map_[head_index].isVisible()

            _label = map_[head_index]
            # ~ logging.warning(f"head_index:{head_index}, flag:{flag}, _label:{_label}.")

            if flag:
                _label.setMovie(self.reserve_movie)
                self.reserve_movie.start()
                _label.show()
            else:
                _label.setText("")
                _label.hide()

    def step_label_clicked(self, position):

        logging.warning(f"position:{position}")

        app = QApplication.instance()

        try:

            moving_heads = [m for m in app.machine_head_dict.values() if m and m.status.get('status_level')
                            not in ['STANDBY', 'DIAGNOSTIC']]

            logging.warning(f"moving_heads:{moving_heads}")

            jar = None
            for j in app.get_jar_runners().values():
                if j and j['jar'] and j['jar'].position and (j['jar'].position == position):
                    logging.warning(f"j['jar']:{j['jar']}")
                    logging.warning(f"j['jar'].machine_head:{j['jar'].machine_head}")
                    jar = j['jar']
                    break

            if jar:

                txt_ = f"{jar.barcode} " + ' '.join(jar.extra_lines_to_print)
                QApplication.instance().main_window.menu_line_edit.setText(txt_)

                if app.carousel_frozen and not moving_heads:
                    if jar:
                        def _remove_jar():
                            logging.warning(f"removing:{jar.barcode}")
                            try:
                                app.delete_jar_runner(jar.barcode)
                                self.update_jar_pixmaps()
                            except Exception:   # pylint: disable=broad-except
                                logging.error(traceback.format_exc())
                        msg_ = tr_("confirm removing {}?").format(jar.barcode)
                        self.main_window.open_input_dialog(message=msg_, content="", ok_cb=_remove_jar)

        except Exception:   # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    @staticmethod
    def reserve_label_clicked(head_index):

        logging.warning(f"head_index:{head_index}")

        m = QApplication.instance().machine_head_dict[head_index]
        if m.low_level_pipes:
            QApplication.instance().main_window.open_alert_dialog(
                tr_("{} Please, Check Pipe Levels: low_level_pipes:{}").format(m.name, m.low_level_pipes))

    @staticmethod
    def expiry_label_clicked(head_index):

        logging.warning(f"head_index:{head_index}")

        m = QApplication.instance().machine_head_dict[head_index]
        if m.expired_products:           # pylint: disable=too-many-nested-blocks

            try:
                # ~ txt_ = [{tr_(k): p['QR_code_info'].get(k) for k in keys_} for p in m.expired_products if p.get('QR_code_info')]

                # ~ keys_ = ('pipe_name', 'pigment_name', 'production_date', 'lot_number')
                keys_ = ('pipe_name', 'pigment_name')
                info_ = []
                for p in m.expired_products:
                    if p.get('QR_code_info'):
                        QR_code_info = p['QR_code_info']
                        item = []
                        for k in keys_:
                            try:
                                if QR_code_info and QR_code_info.get(k):
                                    # ~ item[tr_(k)] = QR_code_info[k]
                                    item.append(QR_code_info[k])
                            except Exception:   # pylint: disable=broad-except
                                logging.error(traceback.format_exc())
                        info_.append(item)

                QApplication.instance().main_window.open_alert_dialog((m.name, info_), fmt="{} expired produtcs:{}")

            except Exception as e:  # pylint: disable=broad-except
                QApplication.instance().handle_exception(e)

    def refill_lbl_clicked(self, head_index):  # pylint:disable=too-many-statements

        if head_index is not None and hasattr(g_settings, 'USE_PIGMENT_ID_AS_BARCODE') and g_settings.USE_PIGMENT_ID_AS_BARCODE:

            m = QApplication.instance().machine_head_dict[head_index]

            units_ = "CC"
            if m.machine_config:
                units_ = m.machine_config.get('UNITS', {}).get('service_page_unit')

            t = m.update_tintometer_data()
            asyncio.ensure_future(t)

            def __qtity_from_ml(val, pigment_name):

                _convert_factor = {
                    "CC": 1.,
                    "GR": m.get_specific_weight(pigment_name),
                }.get(units_, 1)
                logging.warning(f"_convert_factor({type(_convert_factor)}):{_convert_factor}.")
                return round(_convert_factor * float(val), 2)

            def __qtity_to_ml(val, pigment_name):

                _convert_factor = {
                    "CC": 1.,
                    "GR": 1. / m.get_specific_weight(pigment_name),
                }.get(units_, 1)
                logging.warning(f"_convert_factor({type(_convert_factor)}):{_convert_factor}.")
                return _convert_factor * float(val)

            async def __update_level_task(pigment_, pipe_, qtity_):

                m = QApplication.instance().machine_head_dict[head_index]
                data = {'action': 'adjust_pipe_levels', 'params': {pipe_['name']: qtity_}}
                ret = await m.call_api_rest("apiV1/ad_hoc", "POST", data, timeout=8)
                try:
                    msg_ = ""
                    for k, v in ret.items():
                        _ = " ".join([f"{_k}, {__qtity_from_ml(_v, pigment_['name'])} ({units_.lower()})" for _k, _v in v.items()])
                        msg_ += f"{tr_(k)}: {_}"
                        logging.warning(f"msg_:{msg_}.")
                        self.main_window.open_input_dialog(
                            icon_name="SP_MessageBoxInformation", message=msg_)
                except Exception:  # pylint: disable=broad-except
                    logging.error(traceback.format_exc())

                await m.update_tintometer_data()

                self.main_window.browser_page.reload_page()

            def __get_pipe_index_from_name(p_name):

                pipe_addresses = { "B%02d"%(i + 1): i for i in range(0, 8)}
                pipe_addresses.update( { "C%02d"%(i - 7): i for i in range(8, 32)} )
                return pipe_addresses[p_name]

            def _cb_confirm_quantity(pigment_, pipe_, qtity_):

                t = __update_level_task(pigment_, pipe_, qtity_)
                asyncio.ensure_future(t)

            def _cb_input_quantity(pigment_, pipe_):

                self.main_window.toggle_keyboard(on_off=False)

                qtity_ = self.main_window.input_dialog.get_content_text()
                qtity_ = round(float(qtity_), 2)
                msg_ = """please, confirm refilling pipe: {} <br>with {} ({}) of product: {}?."""
                msg_ = tr_(msg_).format(pipe_['name'], qtity_, units_.lower(), pigment_['name'])

                qtity_ = __qtity_to_ml(qtity_, pigment_['name'])

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxQuestion",
                    message=msg_,
                    content=None,
                    ok_cb=_cb_confirm_quantity,
                    ok_cb_args=(pigment_, pipe_, qtity_))

            def _cb_verify_barcode(pigment_, pipe_, _default_qtity, barcode_):

                barcode_check = self.main_window.input_dialog.get_content_text()
                barcode_check = barcode_check.strip()
                logging.warning(f"{m.name} barcode_check:{barcode_check}.")
                
                current_level_ = pipe_['current_level']
                current_level_ = __qtity_from_ml(current_level_, pigment_['name'])
                current_level_ = round(current_level_, 2)
                msg_ = """please, input quantity (in {}) of product: {}<br> for refilling pipe: {}<br> current level:{}, leave as is for total refill."""
                msg_ = tr_(msg_).format(units_.lower(), pigment_['name'], pipe_['name'], current_level_)

                if barcode_check == barcode_:
                    self.main_window.toggle_keyboard(on_off=True)
                    self.main_window.open_input_dialog(
                        icon_name="SP_MessageBoxQuestion",
                        message=msg_,
                        content=_default_qtity,
                        ok_cb=_cb_input_quantity,
                        ok_cb_args=(pigment_, pipe_))
                else:

                    self.main_window.open_input_dialog(
                        icon_name="SP_MessageBoxCritical",
                        message=tr_("barcode mismatch <br/>{} != {}").format(barcode_, barcode_check),
                        content=None)

            async def _roate_circuit_task(pigment_, pipe_, _default_qtity, barcode_):

                pipe_index = __get_pipe_index_from_name(pipe_['name'])
                m = QApplication.instance().machine_head_dict[head_index]
                pars_ = {'Id_color_circuit': pipe_index, 'Refilling_angle': 0, 'Direction': 0}

                await m.send_command(cmd_name='DIAG_ROTATING_TABLE_POSITIONING', params=pars_, type_='command', channel='machine')

                # ~ await asyncio.sleep(3)

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxQuestion",
                    message=tr_("please, verify barcode {} on canister.").format(barcode_),
                    content="",
                    ok_cb=_cb_verify_barcode,
                    ok_cb_args=(pigment_, pipe_, _default_qtity, barcode_),
                    ok_on_enter=True)

            def _cb_input_barcode():

                barcode_ = self.main_window.input_dialog.get_content_text()
                barcode_ = barcode_.strip()
                logging.warning(f"{m.name} barcode_:{barcode_}.")

                try:
                    # ~ logging.warning(f"{m.name}.pigment_list:\n\t{json.dumps(m.pigment_list, indent=2)}")
                    found_pigments = []
                    for p in m.pigment_list:
                        pigment_customer_id = p.get('customer_id')
                        if pigment_customer_id and barcode_ == pigment_customer_id:
                            found_pigments.append(p)

                    if found_pigments:

                        def _pipe_current_level(pigment):
                            return pigment['pipes'] and pigment['pipes'][0].get('current_level', 0)

                        found_pigments.sort(key=_pipe_current_level)

                        pigment_ = found_pigments[0]
                        pipe_ = pigment_['pipes'][0]
                        _default_qtity = pipe_['maximum_level'] - pipe_['current_level']
                        _default_qtity = __qtity_from_ml(_default_qtity, pigment_['name'])
                        _default_qtity = round(_default_qtity , 2)

                        t = _roate_circuit_task(pigment_, pipe_, _default_qtity, barcode_)
                        asyncio.ensure_future(t)

                    else:
                        QApplication.instance().main_window.open_alert_dialog(
                            tr_("barcode not known:{}").format(barcode_))

                except Exception as e:  # pylint: disable=broad-except
                    QApplication.instance().handle_exception(e)

            self.main_window.open_input_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=tr_("please, input barcode"),
                content="",
                ok_cb=_cb_input_barcode,
                ok_on_enter=True)

class HomePageSixHeads(HomePage):

    ui_file_name = "home_page_six_heads.ui"
    help_file_name = 'home_six_heads.html'


class HomePageFourHeads(HomePage):

    ui_file_name = "home_page_four_heads.ui"
    help_file_name = 'home_four_heads.html'

    action_03_btn = None
    action_07_btn = None

    STEP_03_label = None
    STEP_08_label = None

    refill_3_lbl = None
    refill_4_lbl = None

    expiry_3_label = None
    expiry_4_label = None

    reserve_3_label = None
    reserve_4_label = None

    service_3_btn = None
    service_4_btn = None

    container_presence_3_label = None
    container_presence_4_label = None
