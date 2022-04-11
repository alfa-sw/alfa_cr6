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
# ~ import webbrowser
from functools import partial
from types import SimpleNamespace

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

from PyQt5.Qt import QUrl
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView,
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings)

from alfa_CR6_backend.models import Order, Jar, decompile_barcode
from alfa_CR6_backend.dymo_printer import dymo_print
from alfa_CR6_backend.globals import (
    IMAGES_PATH, import_settings, get_res, get_encoding, tr_)

from alfa_CR6_frontend.debug_page import simulate_read_barcode

import magic       # pylint: disable=import-error

g_settings = import_settings()

single_popup_win = SimpleNamespace(
    child_view=None,
    child_page=None,
    cntr=0,
    profile=None,
    parent=None,
)


class PopUpWebEnginePage(QWebEnginePage):

    download_msgs = {
        0: tr_("Download has been requested, but has not been accepted yet."),
        1: tr_("Download is in progress."),
        2: tr_("Download completed successfully."),
        3: tr_("Download has been cancelled."),
        4: tr_("Download has been interrupted (by the server or because of lost connectivity)."),
    }

    def __init__(self, parent):

        super().__init__()
        single_popup_win.parent = parent

        if not os.path.exists(g_settings.WEBENGINE_DOWNLOAD_PATH):
            os.makedirs(g_settings.WEBENGINE_DOWNLOAD_PATH)

    def createWindow(self, _type):
        """ this is called when target == 'blank_' """

        if single_popup_win.child_page is None:
            single_popup_win.child_page = PopUpWebEnginePage(single_popup_win.parent)
            single_popup_win.child_view = QWebEngineView()
            single_popup_win.child_page.setView(single_popup_win.child_view)
            single_popup_win.profile = self.profile()
            single_popup_win.profile.setCachePath(g_settings.WEBENGINE_CACHE_PATH)
            single_popup_win.profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
            single_popup_win.profile.downloadRequested.connect(self.on_downloadRequested)
            single_popup_win.child_page.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
            single_popup_win.child_page.urlChanged.connect(self.change_url)

        logging.warning(
            f"_type:{_type}, _cntr:{single_popup_win.cntr}, _view:{single_popup_win.child_view}, _page:{single_popup_win.child_page}.")

        single_popup_win.cntr += 1

        if single_popup_win.child_view:
            single_popup_win.child_view.setGeometry((10 * single_popup_win.cntr) % 50, (20 * single_popup_win.cntr) % 100, 1000, 800)
            single_popup_win.child_view.show()

        return single_popup_win.child_page

    @staticmethod
    def change_url(url):

        logging.warning(f"url:{url}.")
        if 'colormix_toXml.asp' in f"{url}":
            logging.info(" ************* ")
        else:
            if single_popup_win.child_view:
                logging.info("")
                single_popup_win.child_view.setUrl(url)
                single_popup_win.child_view.show()

        return False

    def on_download_stateChanged(self, state):

        logging.warning(f"state:{self.download_msgs[state]}")
        if state > 0 and QApplication.instance().main_window.open_alert_dialog:
            args_ = f"state:{self.download_msgs[state]}"
            QApplication.instance().main_window.open_alert_dialog(args_, title="ALERT")

    def on_download_finished(self, download):

        try:
            pth = download.downloadDirectory()
            logging.warning(
                f"state:{self.download_msgs[download.state()]}, pth:{pth}, single_popup_win.child_view:{single_popup_win.child_view}.")

            if single_popup_win.child_view:
                if QApplication.instance().main_window.open_alert_dialog:
                    args_ = f"{download.downloadFileName()}\n{self.download_msgs[download.state()]}"
                    QApplication.instance().main_window.open_alert_dialog(args_, title="ALERT")

                single_popup_win.child_view.close()
                del single_popup_win.child_view
                single_popup_win.child_view = None

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def on_downloadRequested(self, download):

        download.setDownloadDirectory(g_settings.WEBENGINE_DOWNLOAD_PATH)
        download.finished.connect(partial(self.on_download_finished, download))
        download.stateChanged.connect(self.on_download_stateChanged)
        download.accept()

    @staticmethod
    def adjust_downloaded_file_name(full_name):

        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(full_name)
        logging.warning(f"full_name:{full_name}, mime_type:{mime_type}")

        if mime_type == 'application/json':
            try:
                with open(full_name, encoding='UTF-8') as f:
                    content = json.load(f)
                    color_code = content.get("color code")
                    if color_code:
                        head, _ = os.path.split(full_name)
                        os.rename(full_name, os.path.join(head, f"{color_code}.json"))
                    else:
                        os.rename(full_name, f"{full_name}.json")
            except Exception:   # pylint: disable=broad-except
                logging.error(traceback.format_exc())
        else:
            toks = mime_type.split("/")
            ext = toks[1:] and toks[1]
            if ext:
                os.rename(full_name, f"{full_name}.{ext}")

    @classmethod
    def javaScriptConsoleMessage(cls, *args):

        logging.warning(f"args:{args}.")
        # ~ for arg in args:
        # ~ logging.warning(f"arg:{arg}.")

        # ~ if "Uncaught TypeError: data.close is not a function" in args:
        # ~ pass


class BaseTableModel(QAbstractTableModel):  # pylint:disable=too-many-instance-attributes

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

    def __init__(self, parent, path, *args):
        super().__init__(parent, *args)
        self.header = [tr_("delete"), tr_("view"), tr_("create order"), tr_("file name")]
        filter_text = parent.search_file_line.text()
        name_list_ = [p for p in os.listdir(path) if filter_text in p][:101]
        if len(name_list_) >= 100:
            # ~ self.open_alert_dialog(
            # ~ tr_("Too many files saved and not used. Please delete unused files."),
            # ~ title="ERROR",
            # ~ )
            args, fmt = (), "Too many files saved and not used. Please delete unused files."
            self.main_window.open_alert_dialog(args, fmt=fmt, title="ERROR")

        name_list_.sort(reverse=True)
        self.results = [["", "", "", p] for p in name_list_]

    def remove_file(self, file_name):  # pylint: disable=no-self-use
        cmd_ = f'rm -f "{os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)}"'
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

    def __init__(self, parent, *args):
        super().__init__(parent, *args)
        self.session = QApplication.instance().db_session
        self.header = [tr_("delete"), tr_("edit"), tr_("status"), tr_("order nr."), tr_("file name")]
        filter_text = parent.search_order_line.text()

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

    def remove_order(self, order_nr):
        logging.warning(f"order_nr:{order_nr}, self.session:{self.session}")
        if self.session:
            order = self.session.query(Order).filter(Order.order_nr == order_nr).one()
            if not order.jars:
                j = Jar(order=order, index=1, size=0)
                j.position = 'DELETED'
                j.status = 'VIRTUAL'
                self.session.add(j)
            else:
                for j in order.jars:
                    QApplication.instance().delete_jar_runner(j.barcode)
                    j.position = 'DELETED'

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

    def __init__(self, parent, *args):

        super().__init__(parent, *args)
        self.session = QApplication.instance().db_session
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
            query_ = query_.filter(Jar.position != "DELETED")
            if filter_text:
                query_ = query_.filter(Jar.status.contains(filter_text))
            if order_nr is not None:
                order = self.session.query(Order).filter(Order.order_nr == order_nr).first()
                if order:
                    query_ = query_.filter(Jar.order == order)
            query_ = query_.order_by(Jar.index.desc()).limit(100)

            def _fmt_status(o):
                if o.unknown_pigments or o.insufficient_pigments:
                    r = [o.status, "!"]
                else:
                    r = [o.status, ""]
                return r
            self.results = [["", "", _fmt_status(o), o.barcode] for o in query_.all()]
            self.results.sort(key=lambda x: x[3], reverse=True)
        else:
            self.results = [[]]

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

    def remove_jar(self, barcode):

        QApplication.instance().delete_jar_runner(barcode)

        order_nr, index = decompile_barcode(barcode)
        if self.session and order_nr and index >= 0:
            order = self.session.query(Order).filter(Order.order_nr == order_nr).one()

            query_ = self.session.query(Jar)
            query_ = query_.filter(Jar.order == order)
            query_ = query_.filter(Jar.index == index)

            # ~ r = query_.delete()
            # ~ logging.warning(f"r:{r}")
            for j in query_.all():
                j.position = 'DELETED'

            self.session.commit()

    def data(self, index, role):
        if not index.isValid():
            return None
        ret = QVariant()
        if role == Qt.DecorationRole and index.column() == 0:
            ret = self.parent().style().standardIcon(getattr(QStyle, "SP_BrowserStop"))
        elif role == Qt.DecorationRole and index.column() == 1:  # view
            # ~ ret = self.parent().style().standardIcon(getattr(QStyle, "SP_FileDialogInfoView"))
            ret = self.barcode_C128_icon.scaled(80, 160, Qt.KeepAspectRatio)

        if role == Qt.DecorationRole and index.column() == 2:  # status
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

        elif role == Qt.DisplayRole and index.column() == 2:  # status
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


class BrowserPage(BaseStackedPage):

    ui_file_name = "browser_page.ui"
    help_file_name = 'webengine.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.webengine_view = QWebEngineView(self)
        self.popup_webengine_page = PopUpWebEnginePage(self)
        self.webengine_view.setPage(self.popup_webengine_page)

        logging.warning(f"_view:{self.webengine_view}, _page:{self.popup_webengine_page}.")

        self.url_lbl.mouseReleaseEvent = lambda event: self.__on_click_url_label()

        self.webengine_view.loadStarted.connect(self.__on_load_start)
        self.webengine_view.loadProgress.connect(self.__on_load_progress)
        self.webengine_view.loadFinished.connect(self.__on_load_finish)

        self.webengine_view.setGeometry(8, 28, 1904, 960)
        self.start_page_url = QUrl.fromLocalFile((get_res("UI", "start_page.html")))
        self.webengine_view.setUrl(self.start_page_url)

        self.__load_progress = 0
        self.start_load = tr_("start load:")
        self.loading = tr_("loading:")
        self.loaded = tr_("loaded:")

    def __on_click_url_label(self):
        logging.warning(f"self.webengine_view:{self.webengine_view}")

    def __on_load_start(self):
        self.__load_progress = 0
        url_ = self.webengine_view.url().toString()
        self.url_lbl.setText('<div style="font-size: 10pt; background-color: #EEEEFF;">{} {} ({})</div>'.format(
            self.start_load, url_, self.__load_progress))

    def __on_load_progress(self):
        self.__load_progress += 1
        url_ = self.webengine_view.url().toString()
        self.url_lbl.setText('<div style="font-size: 10pt; background-color: #DDEEFF;">{} {} ... ({})</div>'.format(
            self.loading, url_, "*" * (self.__load_progress % 10)))

    def __on_load_finish(self):
        url_ = self.webengine_view.url().toString()
        self.url_lbl.setText(
            '<div style="font-size: 10pt; background-color: #EEEEEE;">{} {}</div>'.format(self.loaded, url_))

    def open_page(self, url=g_settings.WEBENGINE_CUSTOMER_URL):

        logging.warning(f"url:{url}.")
        if url:
            q_url = QUrl(url)
            self.webengine_view.setUrl(q_url)
            self.parent().setCurrentWidget(self)


class OrderPage(BaseStackedPage):

    ui_file_name = "order_page.ui"
    help_file_name = 'order.html'

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setStyleSheet("font-size: 22px;")

        self.jar_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.order_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.file_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.order_table_view.clicked.connect(self.__on_order_table_clicked)
        self.jar_table_view.clicked.connect(self.__on_jar_table_clicked)
        self.file_table_view.clicked.connect(self.__on_file_table_clicked)

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

        self.edit_aliases_btn.clicked.connect(self.main_window.open_alias_dialog)

    def populate_order_table(self):

        t = time.time()
        if t - self.search_order_table_last_time > 0.1:
            self.search_order_table_last_time = t
            try:
                order_model = OrderTableModel(self)
                self.order_table_view.setModel(order_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

            self.search_order_box.setTitle(
                tr_("[{}] Orders: search by order nr.").format(
                    order_model.rowCount()))

    def populate_jar_table(self):

        t = time.time()
        if t - self.search_jar_table_last_time > 0.1:
            self.search_jar_table_last_time = t
            try:
                jar_model = JarTableModel(self)
                self.jar_table_view.setModel(jar_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
            self.search_jar_box.setTitle(tr_("[{}] Jars:   search by status").format(jar_model.rowCount()))

    def populate_file_table(self):

        t = time.time()
        if t - self.search_file_table_last_time > 0.1:
            self.search_file_table_last_time = t
            try:
                file_model = FileTableModel(self, g_settings.WEBENGINE_DOWNLOAD_PATH)
                self.file_table_view.setModel(file_model)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

            self.search_file_box.setTitle(tr_("[{}] Files:  search by file name").format(file_model.rowCount()))

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
            order_nr = model.results[row][3]

            logging.warning(f"datum:{datum}, row:{row}, col:{col}, order_nr:{order_nr}")
            if col == 0:  # delete

                def cb():
                    model.remove_order(order_nr)
                    self.populate_order_table()
                    self.populate_jar_table()

                msg_ = tr_("confirm deleting order '{}' and related jars?").format(order_nr)
                self.main_window.open_input_dialog(icon_name="SP_MessageBoxCritical", message=msg_, ok_cb=cb)
                self.populate_jar_table()

            elif col == 1:  # edit

                self.main_window.open_edit_dialog(order_nr)
                self.populate_jar_table()

            elif col == 2:  # status

                self.populate_jar_table()

            elif col == 3:  # order_nr

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
            barcode = model.results[row][3]
            logging.warning(f"row:{row}, col:{col}, barcode:{barcode}")
            if col == 0:  # delete

                def cb():
                    model.remove_jar(barcode)
                    self.populate_jar_table()

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxCritical",
                    message=tr_("confirm deleting jar\n '{}' ?").format(barcode),
                    ok_cb=cb,
                )

            elif col == 1:  # view
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
                        ok_cb=dymo_print,
                        ok_cb_args=[str(jar.barcode), ] + jar.extra_lines_to_print)

            elif col == 2:  # status
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

            elif col == 3:  # barcode
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
            file_name = model.results[row][3]
            logging.warning(f"row:{row}, col:{col}, file_name:{file_name}")
            if col == 0:  # delete

                def cb():
                    model.remove_file(file_name)
                    self.populate_file_table()

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxCritical",
                    message=tr_("confirm deleting file\n '{}' ?").format(file_name),
                    ok_cb=cb)

            elif col == 1:  # view

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

            elif col == 2:  # create order

                _msg = tr_("confirm creating order from file (file will be deleted):\n '{}'?\n").format(file_name)
                _msg += tr_('Please, insert below the number of jars.')
                self.main_window.open_input_dialog(
                    message=_msg,
                    content="<span align='center'>1</span>",
                    ok_cb=self.__create_order_cb,
                    ok_cb_args=[model, file_name])

            elif col == 3:  # file name
                pass

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def __on_new_order_clicked(self):

        try:
            new_order = QApplication.instance().create_order()
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

        n = int(self.main_window.input_dialog.content_container.toPlainText())
        n = min(n, 20)
        logging.warning(f"n:{n}")
        path_to_file = os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)
        order = app.create_order(path_to_file, n_of_jars=n)

        if order:
            properties = json.loads(order.json_properties)
            logging.warning(f"properties:{properties}")
            if properties.get('meta') and not properties['meta'].get('error'):
                args_to_print = sorted([[str(j.barcode), ] + j.extra_lines_to_print for j in order.jars])
                logging.warning(f"file_name:{file_name}, args_to_print:{args_to_print}")

                def cb_():
                    for a in args_to_print:
                        logging.warning(f"a:{a}")
                        response = dymo_print(*a)
                        logging.warning(f"response:{response}")
                        time.sleep(.05)

                msg_ = tr_("confirm printing {} barcodes?").format(len(args_to_print))
                self.main_window.open_input_dialog(message=msg_, content="{}".format(
                    [l[0] for l in args_to_print]), ok_cb=cb_)

                model.remove_file(file_name)

        self.populate_file_table()
        self.populate_order_table()
        self.populate_jar_table()

    def open_page(self):

        self.search_order_line.setText("")
        self.search_jar_line  .setText("")
        self.search_file_line .setText("")

        self.populate_order_table()
        self.populate_jar_table()
        self.populate_file_table()
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

            logging.debug(f"btn_name:{btn_name}, map_[btn]:{map_[btn]}, map_:{map_}")

            self.main_window.browser_page.open_page(map_[btn])

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
        if app.carousel_frozen:

            moving_heads = [m for m in app.machine_head_dict.values() if m and m.status.get('status_level')
                            not in ['STANDBY', 'DIAGNOSTIC']]

            if not moving_heads:

                try:
                    jar = None
                    for j in app.get_jar_runners().values():
                        if j and j['jar'] and j['jar'].position and (j['jar'].position == position):
                            logging.warning(f"j['jar']:{j['jar']}")
                            logging.warning(f"j['jar'].machine_head:{j['jar'].machine_head}")
                            jar = j['jar']
                            break
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
