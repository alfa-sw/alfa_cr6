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

from PyQt5.QtGui import QPixmap
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
from alfa_CR6_ui.globals import (
    WEBENGINE_DOWNLOAD_PATH,
    WEBENGINE_CUSTOMER_URL,
    WEBENGINE_CACHE_PATH,
    IMAGES_PATH,
    UI_PATH,
    HELP_PATH,
    tr_)


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
        self.barcode_C128_icon = QPixmap(os.path.join(IMAGES_PATH, "barcode_C128.png"))

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
            ret = self.barcode_C128_icon.scaled(48, 64, Qt.KeepAspectRatio)

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

    ui_file_name = ""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        loadUi(os.path.join(UI_PATH, self.ui_file_name), self)

        self.main_window = self.parent()
        self.main_window.stacked_widget.addWidget(self)


class HelpPage(BaseStackedPage):

    ui_file_name = "help_page.ui"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exit_help_btn.clicked.connect(self.__on_exit)
        self.context_widget = None

    def __on_exit(self):
        if self.context_widget:
            self.parent().setCurrentWidget(self.context_widget)
            self.hide()

    def open_page(self):

        w = self.parent().currentWidget()
        if w != self:
            self.context_widget = w

        logging.warning(f"self.context_widget:{self.context_widget}")

        help_file_name = 'html5_example.html'

        with open(os.path.join(HELP_PATH, help_file_name)) as f:
            content = f.read()
            self.help_text_browser.setHtml(content)
        self.parent().setCurrentWidget(self)


class WebenginePage(BaseStackedPage):

    ui_file_name = "webengine_page.ui"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.webengine_view = QWebEngineView(self)
        self.webengine_view.setGeometry(8, 28, 1904, 960)
        self.start_page_url = QUrl.fromLocalFile((os.path.join(UI_PATH, "start_page.html")))
        self.webengine_view.setUrl(self.start_page_url)

        # ~ self.webengine_view.setStyleSheet("""
        # ~ QScrollBar:vertical {width: 40px;}
        # ~ ::-webkit-scrollbar {width: 80px}
        # ~ """)

        self.webengine_view.loadStarted.connect(self.__on_load_start)
        self.webengine_view.loadProgress.connect(self.__on_load_progress)
        self.webengine_view.loadFinished.connect(self.__on_load_finish)

        QWebEngineProfile.defaultProfile().downloadRequested.connect(self.__on_downloadRequested)

        QWebEngineProfile.defaultProfile().setCachePath(WEBENGINE_CACHE_PATH)
        QWebEngineProfile.defaultProfile().setPersistentStoragePath(WEBENGINE_CACHE_PATH)

        self.__load_progress = 0
        self.start_load = tr_("start load:")
        self.loading = tr_("loading:")
        self.loaded = tr_("loaded:")

    def __on_load_start(self):
        self.__load_progress = 0
        url_ = self.webengine_view.url().toString()
        self.url_lbl.setText('<div style="font-size: 10pt;">{} {} ({})</div>'.format(
            self.start_load, url_, self.__load_progress))

    def __on_load_progress(self):
        self.__load_progress += 1
        url_ = self.webengine_view.url().toString()
        self.url_lbl.setText('<div style="font-size: 10pt;">{} {} ... ({})</div>'.format(
            self.loading, url_, "*" * self.__load_progress))

    def __on_load_finish(self):
        url_ = self.webengine_view.url().toString()
        self.url_lbl.setText('<div style="font-size: 10pt;">{} {}</div>'.format(self.loaded, url_))

    def open_page(self, url=WEBENGINE_CUSTOMER_URL):

        q_url = QUrl(url)
        if q_url.toString() not in self.webengine_view.url().toString():
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
        if not os.path.exists(WEBENGINE_DOWNLOAD_PATH):
            os.makedirs(WEBENGINE_DOWNLOAD_PATH)
        _name = time.strftime("%Y-%m-%d_%H:%M:%S") + ".json"
        full_name = os.path.join(WEBENGINE_DOWNLOAD_PATH, _name)
        download.setPath(full_name)
        download.accept()

        def _cb():
            _msg = "file name:{}\n\n ".format(_name) + tr_(_msgs[download.state()])
            self.main_window.open_alert_dialog(_msg, title="ALERT", callback=None, args=None)

        download.finished.connect(_cb)


class OrderPage(BaseStackedPage):

    ui_file_name = "order_page.ui"

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
                file_model = FileTableModel(self, WEBENGINE_DOWNLOAD_PATH)
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
                            content = tr_("status:{}").format(jar.status)
                            content += tr_("\ndescription:{}").format(jar.description)
                            content += tr_("\ndate_created:{}\n").format(jar.date_created)
                            content += tr_("\nproperties:{}\n").format(json.loads(jar.json_properties))

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
                with open(os.path.join(WEBENGINE_DOWNLOAD_PATH, file_name)) as f:
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
                        os.path.join(WEBENGINE_DOWNLOAD_PATH, file_name),
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


class HomePage(BaseStackedPage):

    ui_file_name = "home_page.ui"

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.service_btn_group.buttonClicked.connect(self.__on_service_btn_group_clicked)
        self.action_btn_group.buttonClicked.connect(self.__on_action_btn_group_clicked)

        self.running_jars_lbl.setStyleSheet("font-size: 15px")

        for b in self.action_btn_group.buttons():
            b.setStyleSheet(
                """QPushButton { background-color: #00FFFFFF; border: 0px;}"""
            )

        self.action_frame_map = {}

        self.__init_action_pages()

    def __init_action_pages(self):

        def action_back_home_():
            self.parent().setCurrentWidget(self.main_window.home_page_c)

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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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
                        "action": action_back_home_,
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

            self.parent().addWidget(w)
            action_frame_map[btn] = w

        self.action_frame_map = action_frame_map

    def __on_service_btn_group_clicked(self, btn):

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
            self.main_window.webengine_page.open_page(map_[btn])

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"btn_namel:{btn_name} exception:{e}", title="ERROR")

    def __on_action_btn_group_clicked(self, btn):

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
                self.parent().setCurrentWidget(self.action_frame_map[btn])
            for i in QApplication.instance().machine_head_dict.keys():
                self.main_window.update_status_data(i)
        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.main_window.open_alert_dialog(f"btn_namel:{btn_name} exception:{e}", title="ERROR")

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
        map_[head_index].setText(f"{status.get('status_level', 'empty')}")

        map_ = [
            self.container_presence_1_label,
            self.container_presence_2_label,
            self.container_presence_3_label,
            self.container_presence_4_label,
            self.container_presence_5_label,
            self.container_presence_6_label,
        ]
        if status["container_presence"]:
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
            status = m.status
            if "STANDBY" in status.get('status_level', '') and QApplication.instance().carousel_frozen:
                map_[head_index].setPixmap(self.main_window.tank_icon_map['green'])
            else:
                map_[head_index].setPixmap(self.main_window.tank_icon_map['gray'])

            map_[head_index].setText("")

    def update_jar_pixmaps(self):

        _ = [f"{k} ({j['jar'].position[0]})" for k, j in QApplication.instance().get_jar_runners().items()]
        self.running_jars_lbl.setText("\n".join(_))

        self.__set_pixmap_by_photocells(
            self.STEP_01_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),), position="IN_A")
        self.__set_pixmap_by_photocells(
            self.STEP_02_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),), position="A")
        self.__set_pixmap_by_photocells(
            self.STEP_03_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"),), position="B")
        self.__set_pixmap_by_photocells(
            self.STEP_04_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),), position="C")
        self.__set_pixmap_by_photocells(
            self.STEP_05_label, (("D", "LOAD_LIFTER_UP_PHOTOCELL"),
                                 ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), position="LIFTR_UP")
        self.__set_pixmap_by_photocells(
            self.STEP_06_label, (("D", "LOAD_LIFTER_DOWN_PHOTOCELL"),
                                 ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), position="LIFTR_DOWN")
        self.__set_pixmap_by_photocells(
            self.STEP_07_label, (("D", "JAR_DISPENSING_POSITION_PHOTOCELL"),), position="D")
        self.__set_pixmap_by_photocells(
            self.STEP_08_label, (("E", "JAR_DISPENSING_POSITION_PHOTOCELL"),), position="E")
        self.__set_pixmap_by_photocells(
            self.STEP_09_label, (("F", "JAR_DISPENSING_POSITION_PHOTOCELL"),), position="F")
        self.__set_pixmap_by_photocells(
            self.STEP_10_label, (("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"),
                                 ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), position="LIFTL_DOWN")
        self.__set_pixmap_by_photocells(
            self.STEP_11_label, (("F", "UNLOAD_LIFTER_UP_PHOTOCELL"),
                                 ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), position="LIFTL_UP")
        self.__set_pixmap_by_photocells(
            self.STEP_12_label, (("F", "JAR_OUTPUT_ROLLER_PHOTOCELL"),), position="OUT")

    def __set_pixmap_by_photocells(self, lbl, head_letters_bit_names, position=None, icon=None):

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
                        _img_url = os.path.join(IMAGES_PATH, "jar-green.png")
                    else:
                        _img_url = os.path.join(IMAGES_PATH, "jar-gray.png")

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

    def update_action_pages(self):

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
                .status.get("status_level"))

        for action_frame in self.action_frame_map.values():
            if action_frame.isVisible():
                action_frame.status_A_label.setText(tr_(f"{_get_status_level('A')}"))
                action_frame.status_B_label.setText(tr_(f"{_get_status_level('B')}"))
                action_frame.status_C_label.setText(tr_(f"{_get_status_level('C')}"))
                action_frame.status_D_label.setText(tr_(f"{_get_status_level('D')}"))
                action_frame.status_E_label.setText(tr_(f"{_get_status_level('E')}"))
                action_frame.status_F_label.setText(tr_(f"{_get_status_level('F')}"))

    def open_page(self):
        self.parent().setCurrentWidget(self)
