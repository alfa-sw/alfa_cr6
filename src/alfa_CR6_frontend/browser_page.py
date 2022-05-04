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
import traceback
from types import SimpleNamespace

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.Qt import QUrl
from PyQt5.QtWebEngineWidgets import (
    QWebEngineView,
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings)

from alfa_CR6_backend.globals import (import_settings, get_res, tr_)

from alfa_CR6_frontend.pages import BaseStackedPage

import magic       # pylint: disable=import-error

g_settings = import_settings()

WEBENGINEVIEW_GEOMETRY = (8, 28, 1904, 960)

SINGLE_POPUP_WIN = SimpleNamespace(
    child_view=None,
    child_page=None,
    profile=None,
    parent=None,
)


class SingleWebEnginePage(QWebEnginePage):

    download_msgs = {
        0: tr_("Download has been requested, but has not been accepted yet."),
        1: tr_("Download is in progress."),
        2: tr_("Download completed successfully."),
        3: tr_("Download has been cancelled."),
        4: tr_("Download has been interrupted (by the server or because of lost connectivity)."),
    }

    def __init__(self, parent):

        super().__init__(parent)

        webengine_download_path = os.path.normpath(g_settings.WEBENGINE_DOWNLOAD_PATH)
        webengine_cache_path = os.path.normpath(g_settings.WEBENGINE_CACHE_PATH)

        if not os.path.exists(webengine_download_path):
            os.makedirs(webengine_download_path)

        profile = self.profile()
        profile.setCachePath(webengine_cache_path)
        profile.setPersistentStoragePath(webengine_cache_path)
        profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

        self.current_download = None

        profile.downloadRequested.connect(self.on_downloadRequested)

    def on_download_stateChanged(self, state):

        logging.warning(f"state:{self.download_msgs[state]}")

        try:
            if state > 1 and QApplication.instance().main_window.open_alert_dialog:

                if QApplication.instance().main_window.open_alert_dialog:
                    try:
                        args_ = f"{self.current_download.downloadFileName()}\n{self.download_msgs[self.current_download.state()]}"
                    except Exception:  # pylint: disable=broad-except
                        args_ = f"{self.download_msgs[self.current_download.state()]}"
                    QApplication.instance().main_window.open_alert_dialog(args_, title="ALERT")

                self.adjust_downloaded_file_name()

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def on_downloadRequested(self, download):

        logging.warning(f"download:{download}.")

        try:
            self.current_download = download

            # API changed in version 5.11 ?
            # 'QWebEngineDownloadItem' object has no attribute 'setDownloadDirectory'
            if hasattr(self.current_download, 'setDownloadDirectory'):
                self.current_download.setDownloadDirectory(g_settings.WEBENGINE_DOWNLOAD_PATH)
            elif hasattr(self.current_download, 'setPath'):
                _, file_name = os.path.split(self.current_download.path())
                pth = os.path.join(g_settings.WEBENGINE_DOWNLOAD_PATH, file_name)
                self.current_download.setPath(pth)

            self.current_download.stateChanged.connect(self.on_download_stateChanged)
            self.current_download.accept()

        except Exception:   # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def adjust_downloaded_file_name(self):

        logging.warning(f"self:{self}")

        if hasattr(self.current_download, 'downloadDirectory') and hasattr(self.current_download, 'downloadFileName'):
            full_name = os.path.join(
                self.current_download.downloadDirectory(), self.current_download.downloadFileName())
        elif hasattr(self.current_download, 'setPath'):
            full_name = self.current_download.path()

        logging.warning(f"full_name:{full_name}")
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(full_name)
        logging.warning(f"mime_type:{mime_type}")

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
        # ~ else:
            # ~ toks = mime_type.split("/")
            # ~ ext = toks[1:] and toks[1]
            # ~ if ext:
                # ~ os.rename(full_name, f"{full_name}.{ext}")

    @classmethod
    def javaScriptConsoleMessage(cls, *args):
        logging.debug(f"args:{args}.")

    def acceptNavigationRequest(self, url, _type, isMainFrame):

        logging.warning(f"url:{url}, type:{_type}, isMainFrame:{isMainFrame}.")
        # ~ if g_settings.WEBENGINE_CUSTOMER_URL not in f"{url}":
        # ~ if QApplication.instance().main_window.open_alert_dialog:
        # ~ args_ = f"BEWARE:\n{g_settings.WEBENGINE_CUSTOMER_URL}\n not in \n{url}"
        # ~ QApplication.instance().main_window.open_alert_dialog(args_, title="ALERT")

        return super().acceptNavigationRequest(url, _type, isMainFrame)

    def chooseFiles(self, mode, oldFiles, acceptedMimeTypes):
        """
        QStringList QWebEnginePage::chooseFiles(QWebEnginePage::FileSelectionMode mode, const QStringList &oldFiles, const QStringList &acceptedMimeTypes)
        """
        logging.debug(f"{self} {mode} {oldFiles} {acceptedMimeTypes}")
        logging.warning("chooseFiles Disabled.")
        return []


class PopUpWebEnginePage(SingleWebEnginePage):

    def __init__(self, parent):

        super().__init__(None)

        if SINGLE_POPUP_WIN.parent is None:
            SINGLE_POPUP_WIN.parent = parent
        elif SINGLE_POPUP_WIN.parent != parent:
            logging.error(f"SINGLE_POPUP_WIN.parent:{SINGLE_POPUP_WIN.parent}, parent:{parent}.")

        logging.warning(f"self:{self}, parent:{parent}.")

    def createWindow(self, _type):
        """ this is called when target == 'blank_' """

        try:

            SINGLE_POPUP_WIN.child_view = QWebEngineView(SINGLE_POPUP_WIN.parent)
            _w = SINGLE_POPUP_WIN.child_view
            _w.setStyleSheet("""
                    QWidget {font-size: 24px; font-family:Dejavu;}
                    QPushButton {background-color: #F3F3F3F3; border: 1px solid #999999; border-radius: 4px;}
                    QPushButton:pressed {background-color: #AAAAAA;}
                    QScrollBar:vertical {width: 40px;}
                """)
            _w.setWindowFlags(_w.windowFlags() | Qt.WindowStaysOnTopHint)

            SINGLE_POPUP_WIN.child_page = PopUpWebEnginePage(SINGLE_POPUP_WIN.parent)
            SINGLE_POPUP_WIN.child_page.setView(SINGLE_POPUP_WIN.child_view)

            SINGLE_POPUP_WIN.child_page.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
            SINGLE_POPUP_WIN.child_page.urlChanged.connect(self.change_url)

            if SINGLE_POPUP_WIN.profile is None:
                SINGLE_POPUP_WIN.profile = self.profile()

                try:
                    SINGLE_POPUP_WIN.profile.downloadRequested.disconnect()
                except Exception:  # pylint: disable=broad-except
                    logging.warning(traceback.format_exc())

                SINGLE_POPUP_WIN.profile.downloadRequested.connect(self.on_downloadRequested)

        except Exception:  # pylint: disable=broad-except
            logging.warning(traceback.format_exc())

        if SINGLE_POPUP_WIN.child_view:
            SINGLE_POPUP_WIN.child_view.setGeometry(*WEBENGINEVIEW_GEOMETRY)

            SINGLE_POPUP_WIN.child_view.show()

        logging.warning(
            f"_type:{_type}, _view:{SINGLE_POPUP_WIN.child_view}, _page:{SINGLE_POPUP_WIN.child_page}.")

        return SINGLE_POPUP_WIN.child_page

    @staticmethod
    def change_url(url):

        logging.warning(f"url:{url}.")
        if 'colormix_toXml.asp' in f"{url}" or f"{url}" in (
                "PyQt5.QtCore.QUrl('')", "PyQt5.QtCore.QUrl('about:blank')"):
            logging.info(" ************* ")
        else:
            if SINGLE_POPUP_WIN.child_view:
                logging.info("")
                SINGLE_POPUP_WIN.child_view.setUrl(url)
                SINGLE_POPUP_WIN.child_view.show()
            else:
                logging.info(f"SINGLE_POPUP_WIN:{SINGLE_POPUP_WIN}")

        return False

    def on_download_stateChanged(self, state):

        logging.warning(f"state:{self.download_msgs[state]}")

        try:
            if state > 1 and self.current_download:
                try:
                    args_ = f"{self.current_download.downloadFileName()}\n{self.download_msgs[self.current_download.state()]}"
                except Exception:  # pylint: disable=broad-except
                    args_ = f"{self.download_msgs[self.current_download.state()]}"
                QApplication.instance().main_window.open_alert_dialog(args_, title="ALERT")

                if SINGLE_POPUP_WIN.child_view:
                    try:
                        self.current_download.stateChanged.disconnect()
                    except Exception:  # pylint: disable=broad-except
                        logging.warning(traceback.format_exc())
                    self.current_download = None
                    SINGLE_POPUP_WIN.child_view.close()

                    SINGLE_POPUP_WIN.child_view = None
                    SINGLE_POPUP_WIN.child_page = None
                    SINGLE_POPUP_WIN.profile = None
                    SINGLE_POPUP_WIN.parent = None

                    QApplication.instance().main_window.reset_browser()

                else:
                    logging.error(f"SINGLE_POPUP_WIN.child_view:{SINGLE_POPUP_WIN.child_view}")
            else:
                logging.error(f"self.current_download:{self.current_download}, state:{self.download_msgs[state]}")

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)


class BrowserPage(BaseStackedPage):

    ui_file_name = "browser_page.ui"
    help_file_name = 'webengine.html'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.webengine_view = QWebEngineView(self)

        _popup_web_engine_page = hasattr(
            g_settings, 'POPUP_WEB_ENGINE_PAGE') and getattr(
            g_settings, 'POPUP_WEB_ENGINE_PAGE')
        if _popup_web_engine_page:
            self._webengine_page = PopUpWebEnginePage(self)
        else:
            self._webengine_page = SingleWebEnginePage(self)
        self.webengine_view.setPage(self._webengine_page)

        logging.warning(
            f"_popup_web_engine_page:{_popup_web_engine_page}, _view:{self.webengine_view}, _page:{self._webengine_page}.")

        self.url_lbl.mouseReleaseEvent = lambda event: self.__on_click_url_label()

        self.webengine_view.loadStarted.connect(self.__on_load_start)
        self.webengine_view.loadProgress.connect(self.__on_load_progress)
        self.webengine_view.loadFinished.connect(self.__on_load_finish)

        self.webengine_view.setGeometry(*WEBENGINEVIEW_GEOMETRY)
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
