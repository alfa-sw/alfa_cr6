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
from functools import partial

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
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile

from alfa_CR6_backend.models import Order, Jar, decompile_barcode
from alfa_CR6_backend.dymo_printer import dymo_print
from alfa_CR6_backend.globals import (
    IMAGES_PATH, import_settings, get_res, tr_)

g_settings = import_settings()


class BaseTableModel(QAbstractTableModel):  # pylint:disable=too-many-instance-attributes

    def __init__(self, parent, *args):

        super().__init__(parent, *args)
        self.gray_icon = QPixmap(get_res("IMAGE", "gray.png"))
        self.green_icon = QPixmap(get_res("IMAGE", "green.png"))
        self.red_icon = QPixmap(get_res("IMAGE", "red.png"))
        self.yellow_icon = QPixmap(get_res("IMAGE", "yellow.png"))
        self.blue_icon = QPixmap(get_res("IMAGE", "blue.png"))
        self.add_icon = QPixmap(get_res("IMAGE", "add.png"))
        self.edit_icon = QPixmap(get_res("IMAGE", "edit.png"))
        self.barcode_C128_icon = QPixmap(get_res("IMAGE", "barcode_C128.png"))

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
            # ~ ret = self.parent().style().standardIcon(getattr(QStyle, "SP_FileDialogInfoView"))
            ret = self.barcode_C128_icon.scaled(80, 160, Qt.KeepAspectRatio)

        if role == Qt.DecorationRole and index.column() == 2:  # status
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


class BaseStackedPage(QFrame):

    ui_file_name = ''
    help_file_name = ''

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        loadUi(get_res("UI", self.ui_file_name), self)

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
            self.main_window.webengine_page.open_page(url_)

    def open_page(self):

        w = self.parent().currentWidget()
        if w != self:
            self.context_widget = w

        logging.warning(f"self.context_widget:{self.context_widget}")

        if hasattr(self.context_widget, 'help_file_name') and self.context_widget.help_file_name:
            help_file_name = self.context_widget.help_file_name
            with open(get_res("HELP", help_file_name)) as f:
                content = f.read()
                self.help_text_browser.setHtml(content)
            self.parent().setCurrentWidget(self)
        else:
            _msg = tr_("sorry, this help page is missing.")
            self.main_window.open_alert_dialog(_msg, title="ALERT")


class WebenginePage(BaseStackedPage):

    ui_file_name = "webengine_page.ui"
    help_file_name = 'webengine.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.webengine_view = QWebEngineView(self)
        self.webengine_view.setGeometry(8, 28, 1904, 960)
        self.start_page_url = QUrl.fromLocalFile((get_res("UI", "start_page.html")))
        self.webengine_view.setUrl(self.start_page_url)

        # ~ self.webengine_view.setStyleSheet("""
        # ~ QScrollBar:vertical {width: 40px;}
        # ~ ::-webkit-scrollbar {width: 80px}
        # ~ """)
        settings_ = self.webengine_view.settings()
        # ~ pdfviewerenabled = settings_.testAttribute(settings_.PdfViewerEnabled)
        pdfviewerenabled = settings_.setAttribute(30, True)
        pdfviewerenabled = settings_.testAttribute(30)
        logging.warning(f"pdfviewerenabled:{pdfviewerenabled}")
        # ~ QWebEngineSettings::setAttribute(QWebEngineSettings::WebAttribute attribute, bool on)

        self.webengine_view.loadStarted.connect(self.__on_load_start)
        self.webengine_view.loadProgress.connect(self.__on_load_progress)
        self.webengine_view.loadFinished.connect(self.__on_load_finish)

        QWebEngineProfile.defaultProfile().downloadRequested.connect(self.__on_downloadRequested)

        QWebEngineProfile.defaultProfile().setCachePath(g_settings.WEBENGINE_CACHE_PATH)
        QWebEngineProfile.defaultProfile().setPersistentStoragePath(g_settings.WEBENGINE_CACHE_PATH)

        self.__load_progress = 0
        self.start_load = tr_("start load:")
        self.loading = tr_("loading:")
        self.loaded = tr_("loaded:")

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

        q_url = QUrl(url)
        if q_url.toString() not in self.webengine_view.url().toString():
            logging.warning(f"q_url:{q_url}")
            self.webengine_view.setUrl(q_url)

        self.parent().setCurrentWidget(self)

    def __on_downloadRequested(self, download):

        logging.warning(f"download:{download}.")
        _msgs = {
            0: "Download has been requested, but has not been accepted yet.",
            1: "Download is in progress.",
            2: "Download completed successfully.",
            3: "Download has been cancelled.",
            4: "Download has been interrupted (by the server or because of lost connectivity).",
        }
        if not os.path.exists(g_settings.WEBENGINE_DOWNLOAD_PATH):
            os.makedirs(g_settings.WEBENGINE_DOWNLOAD_PATH)
        _name = time.strftime("%Y-%m-%d_%H:%M:%S") + ".json"
        full_name = os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, _name)
        download.setPath(full_name)
        download.accept()

        def _cb():
            _msg = "file name:{}\n\n ".format(_name) + tr_(_msgs[download.state()])
            self.main_window.open_alert_dialog(_msg, title="ALERT", callback=None, args=None)

        download.finished.connect(_cb)


class OrderPage(BaseStackedPage):

    ui_file_name = "order_page.ui"
    help_file_name = 'order.html'

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.jar_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.order_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.file_table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.order_table_view.clicked.connect(self.__on_order_table_clicked)
        self.jar_table_view.clicked.connect(self.__on_jar_table_clicked)
        self.file_table_view.clicked.connect(self.__on_file_table_clicked)

        self.new_order_btn.clicked.connect(self.__on_new_order_clicked)
        self.clone_order_btn.clicked.connect(self.__on_clone_order_clicked)

        self.search_order_line.textChanged.connect(self.populate_order_table)
        self.search_jar_line.textChanged.connect(self.populate_jar_table)
        self.search_file_line.textChanged.connect(self.populate_file_table)

        self.search_order_table_last_time = 0
        self.search_file_table_last_time = 0
        self.search_jar_table_last_time = 0

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

    def __on_order_table_clicked(self, index):

        datum = index.data()
        logging.warning(f"datum:{datum}")
        try:
            col = index.column()
            row = index.row()
            model = index.model()
            order_nr = model.results[row][3]

            logging.warning(f"row:{row}, col:{col}, order_nr:{order_nr}")
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
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"exception:{e}", title="ERROR", callback=None, args=None)

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
                order_nr, index = decompile_barcode(barcode)
                if order_nr and index >= 0:
                    order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).first()
                    if order:
                        query_ = QApplication.instance().db_session.query(Jar)
                        query_ = query_.filter(Jar.order == order)
                        query_ = query_.filter(Jar.index == index)
                        jar = query_.first()
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
                    ok_cb_args=[str(barcode), ])

            elif col == 2:  # status
                pass

            elif col == 3:  # barcode
                pass

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"exception:{e}", title="ERROR", callback=None, args=None)

    def __on_file_table_clicked(self, index):

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
                with open(os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)) as f:
                    content = f.read(3000)
                    try:
                        content = json.dumps(json.loads(content), indent=2)
                    except Exception:  # pylint: disable=broad-except
                        logging.error(traceback.format_exc())

                self.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxInformation",
                    message=tr_("file_name:{}").format(file_name),
                    content=content)

            elif col == 2:  # create order

                app = QApplication.instance()

                def cb():
                    n = int(self.main_window.input_dialog.content_container.toPlainText())
                    n = min(n, 20)
                    logging.warning(f"n:{n}")
                    order = app.create_order(
                        os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name),
                        json_schema_name="KCC",
                        n_of_jars=n)
                    barcodes = sorted([str(j.barcode) for j in order.jars])
                    logging.warning(f"file_name:{file_name}, barcodes:{barcodes}")

                    def cb_():
                        for b in barcodes:
                            response = dymo_print(str(b))
                            logging.warning(f"response:{response}")
                            time.sleep(.05)

                    msg_ = tr_("confirm printing {} barcodes?").format(len(barcodes))
                    self.main_window.open_input_dialog(message=msg_, content="{}".format(barcodes), ok_cb=cb_)

                    model.remove_file(file_name)
                    self.populate_file_table()
                    self.populate_order_table()
                    self.populate_jar_table()

                _msg = tr_("confirm creating order from file (file will be deleted):\n '{}'?\n").format(file_name)
                _msg += tr_('Please, insert below the number of jars.')
                self.main_window.open_input_dialog(message=_msg, content="<span align='center'>1</span>", ok_cb=cb)

            elif col == 3:  # file name
                pass

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"exception:{e}", title="ERROR", callback=None, args=None)

    def __on_new_order_clicked(self):

        try:
            new_order = QApplication.instance().create_order()
            msg = tr_("created order:{}.").format(new_order.order_nr)
            self.main_window.open_alert_dialog(msg, title="INFO")
            self.populate_order_table()
            self.populate_jar_table()

            # ~ s = self.order_table_view.model().index(row, 0)
            # ~ e = self.order_table_view.model().index(row, 3)
            # ~ self.formula_table.selectionModel().select(QItemSelection(s, e), QItemSelectionModel.ClearAndSelect)

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"exception:{e}", title="ERROR", callback=None, args=None)

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
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"exception:{e}", title="ERROR", callback=None, args=None)

    def open_page(self):

        self.search_order_line.setText("")
        self.search_jar_line  .setText("")
        self.search_file_line .setText("")

        self.populate_order_table()
        self.populate_jar_table()
        self.populate_file_table()
        self.parent().setCurrentWidget(self)


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

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.running_jars_lbl.setStyleSheet("font-size: 15px")

        for b in self.action_btn_group.buttons():
            b.setStyleSheet(
                """QPushButton { background-color: #00FFFFFF; border: 0px;}"""
            )

        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)
        self.action_btn_group.buttonClicked.connect(self.on_action_btn_group_clicked)

        self.reserve_movie = QMovie(get_res("IMAGE", "riserva.gif"))

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

            logging.warning(f"btn_name:{btn_name}, map_[btn]:{map_[btn]}, map_:{map_}")

            self.main_window.webengine_page.open_page(map_[btn])

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"btn_name:{btn_name} exception:{e}", title="ERROR")

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
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"btn_name:{btn_name} exception:{e}", title="ERROR")

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
            map_[head_index].setText(f"{status.get('status_level', 'empty')}")

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
                if "STANDBY" in status.get('status_level', '') and QApplication.instance().carousel_frozen:
                    map_[head_index].setPixmap(self.main_window.tank_icon_map['green'])
                else:
                    map_[head_index].setPixmap(self.main_window.tank_icon_map['gray'])

                map_[head_index].setText("")

    def update_jar_pixmaps(self):

        _ = [f"{k} ({j['jar'].position[0]})" for k, j in QApplication.instance().get_jar_runners().items()]
        self.running_jars_lbl.setText("\n".join(_))

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

    def __set_pixmap_by_photocells(self, lbl, head_letters_bit_names, position=None, icon=None):
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
                        text = ""
                        for j in QApplication.instance().get_jar_runners().values():
                            pos = j["jar"].position
                            if pos == position:
                                _bc = str(j["jar"].barcode)
                                text = _bc[-6:-3] + "\n" + _bc[-3:]
                                break

                        if text:
                            _img_url = get_res("IMAGE", "jar-green.png")
                        else:
                            _img_url = get_res("IMAGE", "jar-gray.png")

                        lbl.setStyleSheet(
                            'color:#000000; border-image:url("{0}"); font-size: 15px'.format(_img_url))
                        lbl.setText(text)
                else:
                    size = [0, 0] if false_condition else [32, 32]
                    pixmap = icon.scaled(*size, Qt.KeepAspectRatio)
                    lbl.setPixmap(pixmap)

                lbl.show()

            except Exception as e:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
                self.main_window.open_alert_dialog(f"exception:{e}", title="ERROR")

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

    reserve_3_label = None
    reserve_4_label = None

    service_3_btn = None
    service_4_btn = None

    container_presence_3_label = None
    container_presence_4_label = None
