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
from functools import partial

from sqlalchemy.sql import or_

from PyQt5.uic import loadUi
from PyQt5.QtCore import (Qt, QVariant, QAbstractTableModel)

from PyQt5.QtGui import QPixmap, QTextDocument
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
from alfa_CR6_flask.admin_views import _to_html_table

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
                    # ~ content += tr_("properties:{}\n").format(
                        # ~ json.dumps(json.loads(jar.json_properties), indent=2))
                    content += tr_("properties:\n") + _to_html_table(json.loads(jar.json_properties))

                    msg_ = tr_("do you want to print barcode:\n {} ?").format(barcode)

                    self.main_window.open_input_dialog(
                        icon_name="SP_MessageBoxInformation",
                        message=msg_,
                        content=content,
                        ok_cb=dymo_print_jar,
                        ok_cb_args=[jar, ], 
                        to_html=True,
                        wide=True)

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

                dialog_content_editable = False
                _msg = tr_("confirm creating order from file (file will be deleted):\n '{}'?\n").format(file_name)

                if not getattr(g_settings, 'FORCE_ORDER_JAR_TO_ONE', False):
                    _msg += tr_('Please, insert below the number of jars.')
                    dialog_content_editable = True

                self.main_window.open_input_dialog(
                    message=_msg,
                    content="<span align='center'>1</span>",
                    ok_cb=self.__create_order_cb,
                    ok_cb_args=[model, file_name],
                    content_editable=dialog_content_editable)

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
                jars = QApplication.instance().db_session.query(Jar).filter(Jar.order_id == order.id).all()
                jar_to_complete = None
                logging.warning(f"jars -> {jars}")
                for j in jars:
                    logging.warning(f"cloned jar: {j}")
                    if j.check_for_failure_refused_refill():
                        logging.warning("POPULATE CLONED ORDER USING not_dispensed_ingredients ")
                        jar_to_complete = j
                        break

                if order and jar_to_complete:
                    def clone_order_with_not_dispended_pgmts_callback(order_nr, not_dispensed_ingredients={}):
                        logging.warning(f"DO SPECIAL MAGICS HERE")
                        cloned_order = QApplication.instance().clone_order(order_nr, not_dispensed_pgmts=not_dispensed_ingredients)
                        logging.info(f"Order cloned: {cloned_order}")
                        self.populate_order_table()
                        self.populate_jar_table()
                    def clone_order_callback(order_nr):
                        cloned_order = QApplication.instance().clone_order(order_nr)
                        logging.info(f"Order cloned: {cloned_order}")
                        self.populate_order_table()
                        self.populate_jar_table()
                    msg = tr_(
                        "Do you want to create a new order with the not dispensed components from barcode {} ?\nIf YES press 'Recover Old'"
                    ).format(jar_to_complete.barcode)
                    self.main_window.open_alert_dialog(
                        msg,
                        title="INFO",
                        callback=clone_order_with_not_dispended_pgmts_callback,
                        cb_args=[order_nr, jar_to_complete.not_dispensed_ingredients],
                        cancel_callback=clone_order_callback,
                        cancel_cb_args=[order_nr],
                        btns_custom_text=["Clone New", "Recover Old"]
                    )

                if order and jar_to_complete is None:
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


