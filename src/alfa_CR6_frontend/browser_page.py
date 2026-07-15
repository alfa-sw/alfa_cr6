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
import time
from types import SimpleNamespace

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer
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

SUSPEND_PAGE_WS_SCRIPT = """
    (function () {
        if (typeof window.alfaSuspendWS !== "function") { return false; }
        window.alfaSuspendWS();
        return true;
    })();
"""

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

    def clean(self):
        pass

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

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def on_downloadRequested(self, download):

        logging.warning(f"download:{download}.")

        try:
            self.current_download = download

            try:
                logging.warning(f"self.current_download.downloadFileName():{self.current_download.downloadFileName()}.")
            except Exception as e:  # pylint: disable=broad-except
                logging.warning(f"e:{e}.")

            # API changed in version 5.11 ?
            # 'QWebEngineDownloadItem' object has no attribute 'setDownloadDirectory'
            if hasattr(self.current_download, 'setDownloadDirectory'):
                self.current_download.setDownloadDirectory(g_settings.WEBENGINE_DOWNLOAD_PATH)
                logging.warning(f"self.current_download:{self.current_download}.")
            elif hasattr(self.current_download, 'setPath'):
                logging.warning(f"self.current_download.path():{self.current_download.path()}.")
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
        logging.debug("args:%s.", args)

    def acceptNavigationRequest(self, url, _type, isMainFrame):

        # ~ logging.warning(f"url:{url}, _type:{_type}, isMainFrame:{isMainFrame}.")
        logging.debug(f"self:{self}.")
        # ~ if g_settings.WEBENGINE_CUSTOMER_URL not in f"{url}":
        # ~ if QApplication.instance().main_window.open_alert_dialog:
        # ~ args_ = f"BEWARE:\n{g_settings.WEBENGINE_CUSTOMER_URL}\n not in \n{url}"
        # ~ QApplication.instance().main_window.open_alert_dialog(args_, title="ALERT")

        return super().acceptNavigationRequest(url, _type, isMainFrame)

    def chooseFiles(self, mode, oldFiles, acceptedMimeTypes):
        """
        QStringList QWebEnginePage::chooseFiles(QWebEnginePage::FileSelectionMode mode, const QStringList &oldFiles, const QStringList &acceptedMimeTypes)
        """
        logging.debug("%s %s %s %s", self, mode, oldFiles, acceptedMimeTypes)
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
            SINGLE_POPUP_WIN.child_view.setStyleSheet("""
                    QWidget {font-size: 24px; font-family:Dejavu;}
                    QPushButton {background-color: #F3F3F3F3; border: 1px solid #999999; border-radius: 4px;}
                    QPushButton:pressed {background-color: #AAAAAA;}
                    QScrollBar:vertical {width: 80px;}
                """)
            SINGLE_POPUP_WIN.child_view.setWindowFlags(
                SINGLE_POPUP_WIN.child_view.windowFlags() | Qt.WindowStaysOnTopHint)

            SINGLE_POPUP_WIN.child_page = PopUpWebEnginePage(SINGLE_POPUP_WIN.parent)
            SINGLE_POPUP_WIN.child_view.setPage(SINGLE_POPUP_WIN.child_page)
            SINGLE_POPUP_WIN.child_page.setView(SINGLE_POPUP_WIN.child_view)
            SINGLE_POPUP_WIN.child_page.settings().setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
            SINGLE_POPUP_WIN.child_page.urlChanged.connect(self.change_url)
            if SINGLE_POPUP_WIN.profile is None:
                SINGLE_POPUP_WIN.profile = self.profile()
                try:
                    SINGLE_POPUP_WIN.profile.downloadRequested.disconnect()
                except Exception:  # pylint: disable=broad-except
                    logging.warning("failed to disconnect previous downloadRequested handler", exc_info=True)

                SINGLE_POPUP_WIN.profile.downloadRequested.connect(self.on_downloadRequested)

            SINGLE_POPUP_WIN.child_view.setGeometry(*WEBENGINEVIEW_GEOMETRY)
            SINGLE_POPUP_WIN.child_view.show()

        except Exception:  # pylint: disable=broad-except
            logging.warning("failed to create popup window", exc_info=True)

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
                logging.info("SINGLE_POPUP_WIN:%s", SINGLE_POPUP_WIN)

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
                        logging.warning("failed to disconnect download stateChanged handler", exc_info=True)
                    self.current_download = None

                    # ~ SINGLE_POPUP_WIN.parent.reset_view()
                    QApplication.instance().main_window.browser_page.reset_view()

                else:
                    logging.error(f"SINGLE_POPUP_WIN.child_view:{SINGLE_POPUP_WIN.child_view}")
            else:
                logging.error(f"self.current_download:{self.current_download}, state:{self.download_msgs[state]}")

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def clean(self):
        pass

class BrowserPage(BaseStackedPage): # pylint: disable=too-many-instance-attributes

    ui_file_name = "browser_page.ui"
    help_file_name = 'webengine.html'

    def reload_page(self):

        logging.warning(f"QWebEnginePage.Reload:{QWebEnginePage.Reload}.")

        if self._webengine_page:
            self._webengine_page.triggerAction(QWebEnginePage.Reload)

    def reset_view(self):

        logging.debug(f"self.q_url:{self.q_url}.")

        self.webengine_view = QWebEngineView(self)

        self.webengine_view.setPage(self._webengine_page)
        self._webengine_page.setView(self.webengine_view)

        self.webengine_view.loadStarted.connect(self.__on_load_start)
        self.webengine_view.loadProgress.connect(self.__on_load_progress)
        self.webengine_view.loadFinished.connect(self.__on_load_finish)

        if self.splitter is None:
            self._setup_devtools_splitter()
        else:
            self.webengine_view.setParent(self.splitter)
            self.splitter.replaceWidget(0, self.webengine_view)

        if self.splitter is None:
            self.webengine_view.setGeometry(*WEBENGINEVIEW_GEOMETRY)

        self.webengine_view.show()

    def _setup_devtools_splitter(self):

        try:
            from PyQt5.QtWidgets import QSplitter
            from PyQt5.QtCore import Qt
            self.splitter = QSplitter(Qt.Horizontal, self)
            self.splitter.setContentsMargins(0, 0, 0, 0)

            # Posiziona lo splitter sotto la URL bar (come era la webengine_view)
            # URL bar è a (4, 2, 1900, 26), quindi splitter inizia da y=28
            self.splitter.setGeometry(8, 28, 1904, 960)

            self.webengine_view.setParent(self.splitter)
            self.splitter.addWidget(self.webengine_view)

            self.splitter.show()
            logging.info("DevTools splitter setup completed (DevTools will be created on demand)")

        except Exception as e:
            logging.error(f"Error setting up DevTools splitter: {e}")

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        _popup_web_engine_page = hasattr(
            g_settings, 'POPUP_WEB_ENGINE_PAGE') and getattr(
            g_settings, 'POPUP_WEB_ENGINE_PAGE')
        if _popup_web_engine_page:
            self._webengine_page = PopUpWebEnginePage(self)
        else:
            self._webengine_page = SingleWebEnginePage(self)

        # diagnostica: un crash del render process su embedded e' altrimenti silenzioso
        # (il recovery avviene comunque alla prossima setUrl di open_page)
        try:
            self._webengine_page.renderProcessTerminated.connect(
                self._on_render_process_terminated)
        except Exception:  # pylint: disable=broad-except
            logging.warning("cannot connect renderProcessTerminated", exc_info=True)

        self.url_lbl.mouseReleaseEvent = lambda event: self.__on_click_url_label()

        self.devtools_view = None
        self.devtools_page = None
        self.splitter = None

        devtools_btn = getattr(self, 'devtools_btn', None)
        if devtools_btn:
            devtools_btn.clicked.connect(self.toggleDevTools)

        self.__load_progress = 0
        self.start_load = tr_("start load:")
        self.loading = tr_("loading:")
        self.loaded = tr_("loaded:")

        # NOTE: vestigial loading splash. start_page.html (and images/hourglass.gif)
        # was meant as a "loading... please wait" placeholder, but it is never loaded:
        # self.q_url is overwritten by open_page() before any setUrl() in the normal
        # flow, and no setUrl(self.q_url) exists. Kept commented pending the decision
        # to remove the assets or restore the splash behavior.
        # url = QUrl.fromLocalFile((get_res("UI", "start_page.html")))
        # self.q_url = QUrl(url)
        self.q_url = QUrl()
        self.webengine_view = None
        self.__load_started_at = None
        self.__load_started_url = ""
        self.__load_requested_url = ""
        self.__open_requested_at = None

        self.current_head_index = None
        if self.refill_label:
            self.refill_label.mouseReleaseEvent = lambda event: self.main_window.home_page.refill_lbl_clicked(self.current_head_index)
        if self.print_label:
            self.print_label.mouseReleaseEvent = lambda event: self.main_window.home_page.print_label_clicked(self.current_head_index)

    def __on_click_url_label(self):
        if SINGLE_POPUP_WIN.child_view:
            SINGLE_POPUP_WIN.child_view.show()
        logging.warning(f"self.webengine_view:{self.webengine_view}")

    def __on_load_start(self):
        self.__load_progress = 0
        url_ = self.webengine_view.url().toString()
        self.__load_started_at = time.monotonic()
        self.__load_started_url = url_
        self.url_lbl.setText('<div style="font-size: 10pt; background-color: #EEEEFF;">{} {} ({})</div>'.format(
            self.start_load, url_, self.__load_progress))

    def __on_load_progress(self):
        self.__load_progress += 1
        url_ = self.webengine_view.url().toString()
        self.url_lbl.setText('<div style="font-size: 10pt; background-color: #DDEEFF;">{} {} ... ({})</div>'.format(
            self.loading, url_, "*" * (self.__load_progress % 10)))

    def __on_load_finish(self, ok=True):
        url_ = self.webengine_view.url().toString()
        now = time.monotonic()
        elapsed_ms = None
        if self.__load_started_at is not None:
            elapsed_ms = int((now - self.__load_started_at) * 1000)
        # Latenza percepita dal CLICK (non solo dalla pagina):
        #   click_to_loadstart  = click -> loadStarted  (attesa thread GUI + setUrl, invisibile al nav-timing)
        #   click_to_loadfinish = click -> loadFinished (tempo reale click -> DOM caricato)
        click_to_loadstart_ms = None
        click_to_loadfinish_ms = None
        # consuma il timestamp del click SOLO se questo loadFinished appartiene alla
        # navigazione richiesta: un load abortito (setUrl sopraggiunto mentre un'altra
        # pagina stava caricando) emette loadFinished per la pagina VECCHIA e
        # attribuirebbe il click all'URL sbagliato
        consume_click = (
            self.__open_requested_at is not None
            and self.__load_started_url == self.__load_requested_url)
        if consume_click:
            click_to_loadfinish_ms = int((now - self.__open_requested_at) * 1000)
            if self.__load_started_at is not None:
                click_to_loadstart_ms = int((self.__load_started_at - self.__open_requested_at) * 1000)
        # TODO - uncomment for debug
        # logging.warning(
        #     "webengine load finished ok:%s elapsed_ms:%s click_to_loadstart_ms:%s "
        #     "click_to_loadfinish_ms:%s requested:%s started:%s final:%s",
        #     ok, elapsed_ms, click_to_loadstart_ms, click_to_loadfinish_ms,
        #     self.__load_requested_url, self.__load_started_url, url_)
        if consume_click:
            self.__open_requested_at = None
        self.url_lbl.setText(
            '<div style="font-size: 10pt; background-color: #EEEEEE;">{} {}</div>'.format(self.loaded, url_))
        self.__log_page_performance(url_)
        # il load puo' completarsi quando l'operatore ha gia' lasciato la BrowserPage:
        # il documento appena nato apre il suo WS e visibilitychange non scatta
        # (pagina NATA nascosta) -> va risospeso qui, altrimenti il WS resta aperto
        # ad alimentare il fan-out a pagina invisibile
        if not self.isVisible():
            self._suspend_page_ws()

    def __log_page_performance(self, url_):
        # Strumentazione opzionale: di default OFF (zero costo, niente spam a WARNING
        # in produzione dove LOG_LEVEL=WARNING). Per profilare sulla macchina reale
        # impostare WEBENGINE_PERF_LOG = True nel conf attivo.
        if not getattr(g_settings, 'WEBENGINE_PERF_LOG', False):
            return
        if url_ == "about:blank" or self.webengine_view is None or self.webengine_view.page() is None:
            return

        script = """
            (function () {
                function roundMs(value) {
                    if (typeof value !== "number" || !isFinite(value)) {
                        return null;
                    }
                    return Math.round(value);
                }
                function delta(end, start) {
                    if (typeof end !== "number" || typeof start !== "number" ||
                            !isFinite(end) || !isFinite(start) || end <= 0 || start <= 0) {
                        return null;
                    }
                    return Math.max(0, Math.round(end - start));
                }

                var nav = null;
                if (performance.getEntriesByType) {
                    var navEntries = performance.getEntriesByType("navigation");
                    if (navEntries && navEntries.length) {
                        var n = navEntries[0];
                        nav = {
                            type: n.type || "",
                            duration: roundMs(n.duration),
                            responseEnd: roundMs(n.responseEnd),
                            domInteractive: roundMs(n.domInteractive),
                            domContentLoadedEventEnd: roundMs(n.domContentLoadedEventEnd),
                            loadEventEnd: roundMs(n.loadEventEnd),
                            transferSize: n.transferSize || 0,
                            encodedBodySize: n.encodedBodySize || 0,
                            decodedBodySize: n.decodedBodySize || 0
                        };
                    }
                }
                if (!nav && performance.timing) {
                    var t = performance.timing;
                    var s = t.navigationStart;
                    nav = {
                        type: "legacy",
                        duration: delta(t.loadEventEnd, s),
                        responseEnd: delta(t.responseEnd, s),
                        domInteractive: delta(t.domInteractive, s),
                        domContentLoadedEventEnd: delta(t.domContentLoadedEventEnd, s),
                        loadEventEnd: delta(t.loadEventEnd, s),
                        transferSize: 0,
                        encodedBodySize: 0,
                        decodedBodySize: 0
                    };
                }

                // Milestone di RENDER (mancavano): first-paint / first-contentful-paint.
                // E' qui che si vede il costo render-bound, non in domContentLoaded.
                var paint = {firstPaint: null, firstContentfulPaint: null};
                if (performance.getEntriesByType) {
                    performance.getEntriesByType("paint").forEach(function (p) {
                        if (p.name === "first-paint") {
                            paint.firstPaint = roundMs(p.startTime);
                        } else if (p.name === "first-contentful-paint") {
                            paint.firstContentfulPaint = roundMs(p.startTime);
                        }
                    });
                }

                var resources = [];
                if (performance.getEntriesByType) {
                    resources = performance.getEntriesByType("resource").map(function (r) {
                        return {
                            name: r.name || "",
                            type: r.initiatorType || "",
                            startTime: roundMs(r.startTime),
                            duration: roundMs(r.duration),
                            responseEnd: roundMs(r.responseEnd),
                            dns: roundMs(r.domainLookupEnd - r.domainLookupStart),
                            connect: roundMs(r.connectEnd - r.connectStart),
                            ttfb: roundMs(r.responseStart - r.requestStart),
                            download: roundMs(r.responseEnd - r.responseStart),
                            transferSize: r.transferSize || 0,
                            encodedBodySize: r.encodedBodySize || 0,
                            decodedBodySize: r.decodedBodySize || 0
                        };
                    });
                    resources.sort(function (a, b) {
                        return (b.duration || 0) - (a.duration || 0);
                    });
                }

                // Ritardo fino al primo frame compositato dopo il load: se alto, la
                // main thread e' ancora occupata da layout/paint -> render-bound.
                // requestAnimationFrame e' asincrono, il valore viene letto in 2a fase.
                window.__alfaPerfRafMs = null;
                if (window.requestAnimationFrame) {
                    var rafT0 = performance.now();
                    requestAnimationFrame(function () {
                        window.__alfaPerfRafMs = Math.max(0, Math.round(performance.now() - rafT0));
                    });
                }

                return JSON.stringify({
                    navigation: nav,
                    paint: paint,
                    scriptRunAt: roundMs(performance.now()),
                    resourceCount: resources.length,
                    slowResources: resources.slice(0, 8)
                });
            })();
        """

        def _on_performance_result(payload):
            try:
                data = json.loads(payload or "{}")
            except Exception as e:  # pylint: disable=broad-except
                logging.warning("webengine perf parse failed: %s payload:%s", e, payload)
                return

            nav = data.get("navigation") or {}
            paint = data.get("paint") or {}
            logging.warning(
                "webengine perf navigation final:%s duration_ms:%s response_end_ms:%s "
                "dom_interactive_ms:%s dom_content_loaded_ms:%s load_event_ms:%s "
                "first_paint_ms:%s first_contentful_paint_ms:%s script_run_at_ms:%s "
                "resources:%s transfer:%s encoded:%s decoded:%s",
                url_,
                nav.get("duration"),
                nav.get("responseEnd"),
                nav.get("domInteractive"),
                nav.get("domContentLoadedEventEnd"),
                nav.get("loadEventEnd"),
                paint.get("firstPaint"),
                paint.get("firstContentfulPaint"),
                data.get("scriptRunAt"),
                data.get("resourceCount"),
                nav.get("transferSize"),
                nav.get("encodedBodySize"),
                nav.get("decodedBodySize"))

            for resource in data.get("slowResources") or []:
                name = resource.get("name") or ""
                if len(name) > 140:
                    name = "{}...".format(name[:137])
                logging.warning(
                    "webengine perf resource duration_ms:%s type:%s start_ms:%s "
                    "response_end_ms:%s ttfb_ms:%s download_ms:%s transfer:%s "
                    "encoded:%s decoded:%s name:%s",
                    resource.get("duration"),
                    resource.get("type"),
                    resource.get("startTime"),
                    resource.get("responseEnd"),
                    resource.get("ttfb"),
                    resource.get("download"),
                    resource.get("transferSize"),
                    resource.get("encodedBodySize"),
                    resource.get("decodedBodySize"),
                    name)

            self.__log_raf_after_load(url_)

        try:
            self.webengine_view.page().runJavaScript(script, _on_performance_result)
        except Exception as e:  # pylint: disable=broad-except
            logging.warning("webengine perf runJavaScript failed: %s", e)

    def __log_raf_after_load(self, url_):
        # Seconda fase: rilegge il timestamp del primo frame dopo il load registrato
        # dallo script di __log_page_performance. requestAnimationFrame e' asincrono e
        # non e' disponibile nel return sincrono di runJavaScript, quindi serve un
        # secondo eval differito (la rAF e' gia' scattata entro ~1 frame).
        view = self.webengine_view
        if view is None or view.page() is None:
            return

        def _read_raf():
            if view.page() is None:
                return

            def _on_raf(value):
                logging.warning("webengine perf raf_next_frame_ms:%s final:%s", value, url_)

            try:
                view.page().runJavaScript("window.__alfaPerfRafMs", _on_raf)
            except Exception as e:  # pylint: disable=broad-except
                logging.warning("webengine perf raf read failed: %s", e)

        QTimer.singleShot(120, _read_raf)

    def toggleDevTools(self):

        try:
            if not self.splitter:
                logging.warning("Splitter not initialized yet - call ignored")
                return

            if self.devtools_view and self.devtools_page:
                logging.info("Destroying DevTools...")
                self._destroy_devtools()
                logging.info("DevTools destroyed and hidden")
            else:
                logging.info("Creating DevTools on demand...")
                self._create_devtools()
                logging.info("DevTools created and shown")

        except Exception as e:
            logging.error(f"Error toggling DevTools: {e}")
            if hasattr(self, 'main_window') and hasattr(self.main_window, 'open_alert_dialog'):
                self.main_window.open_alert_dialog(f"Error toggling DevTools:\n{e}", title="Error")

    def _create_devtools(self):
        """Create DevTools on demand"""
        try:
            self.devtools_view = QWebEngineView(self.splitter)
            self.devtools_page = QWebEnginePage(self.devtools_view)
            self.devtools_view.setPage(self.devtools_page)

            self.splitter.addWidget(self.devtools_view)

            if self.webengine_view and self.webengine_view.page():
                if hasattr(self.webengine_view.page(), 'setDevToolsPage'):
                    self.webengine_view.page().setDevToolsPage(self.devtools_page)
                    logging.info("DevTools relationship established using setDevToolsPage")
                elif hasattr(self.devtools_page, 'setInspectedPage'):
                    self.devtools_page.setInspectedPage(self.webengine_view.page())
                    logging.info("DevTools relationship established using setInspectedPage")

            self.devtools_view.show()
            self.splitter.setSizes([600, 400])  # 60% browser, 40% DevTools

        except Exception as e:
            logging.error(f"Error creating DevTools: {e}")
            raise

    def _destroy_devtools(self):

        try:

            if self.webengine_view and self.webengine_view.page():
                if hasattr(self.webengine_view.page(), 'setDevToolsPage'):
                    self.webengine_view.page().setDevToolsPage(None)
                elif self.devtools_page and hasattr(self.devtools_page, 'setInspectedPage'):
                    self.devtools_page.setInspectedPage(None)

            if self.devtools_view:
                self.devtools_view.setParent(None)
                self.devtools_view.deleteLater()
                self.devtools_view = None

            if self.devtools_page:
                self.devtools_page.deleteLater()
                self.devtools_page = None

        except Exception as e:
            logging.error(f"Error destroying DevTools: {e}")
            raise

    def clean(self):
        # Clean up DevTools if they exist
        if hasattr(self, 'devtools_view') and self.devtools_view:
            try:
                self._destroy_devtools()
                logging.info("DevTools cleaned up")
            except:
                pass

        if self._webengine_page:
            del self._webengine_page

    def _should_blank_without_ws_hook(self, view):
        """Return True for internal pages whose resources must not stay active."""
        try:
            host = view.url().host()
        except Exception:  # pylint: disable=broad-except
            return False
        if not host:
            return False

        head_hosts = {
            entry[0]
            for entry in (getattr(g_settings, "MACHINE_HEAD_IPADD_PORTS_LIST", []) or [])
            if entry
        }
        return host in ("127.0.0.1", "localhost", "::1") or host in head_hosts

    def _blank_internal_page_without_hook(self, view, expected_url):
        # runJavaScript e' asincrono: al ritorno si blanka solo se siamo ancora
        # sulla stessa pagina e questa e' effettivamente nascosta.
        if (view is not self.webengine_view or self.isVisible()
                or view.url().toString() != expected_url
                or not self._should_blank_without_ws_hook(view)):
            return
        blank = QUrl("about:blank")
        view.setUrl(blank)
        self.q_url = blank

    def blank_webengine_view(self, callback=None, timeout_ms=500):  # pylint: disable=unused-argument
        # Preferisce il contratto cooperativo alfaSuspendWS, che conserva DOM e
        # render. Se una pagina INTERNA non espone l'hook (versione devices meno
        # recente, admin/settings locali), torna ad about:blank per non lasciare
        # WebSocket o timer fantasma. Le pagine cliente esterne restano residenti.
        self._suspend_page_ws()
        if callback:
            QTimer.singleShot(0, callback)

    def _suspend_page_ws(self):
        # Chiude il WebSocket della pagina corrente tramite alfaSuspendWS. Il
        # risultato booleano consente il fallback per le pagine interne senza hook.
        view = self.webengine_view
        if view is None or view.page() is None:
            return

        expected_url = view.url().toString()

        def _on_suspend_result(hook_available):
            if not hook_available:
                self._blank_internal_page_without_hook(view, expected_url)

        try:
            view.page().runJavaScript(
                SUSPEND_PAGE_WS_SCRIPT,
                _on_suspend_result)
        except Exception:  # pylint: disable=broad-except
            logging.warning("failed to suspend page websocket", exc_info=True)
            self._blank_internal_page_without_hook(view, expected_url)

    def _resume_page_ws(self):
        view = self.webengine_view
        if view is not None and view.page() is not None:
            try:
                view.page().runJavaScript(
                    "if (window.alfaResumeWS) { window.alfaResumeWS(); }")
            except Exception:  # pylint: disable=broad-except
                logging.warning("failed to resume page websocket", exc_info=True)

    def release_local_ws(self):
        self.blank_webengine_view()

    def hideEvent(self, event):  # pylint: disable=invalid-name
        # View residente: niente blank, sospendi solo il WS della pagina.
        self._suspend_page_ws()
        super().hideEvent(event)

    def showEvent(self, event):  # pylint: disable=invalid-name
        # Copre i path di show che NON passano da open_page (es. ritorno dalla
        # help page via setCurrentWidget diretto): senza questo la pagina
        # ricomparirebbe con WS sospeso e dati congelati. Idempotente: lato JS
        # alfaResumeWS e' un no-op se non c'era stata una suspend.
        self._resume_page_ws()
        super().showEvent(event)

    def _on_render_process_terminated(self, termination_status, exit_code):
        logging.error(
            "webengine render process terminated status:%s exit_code:%s",
            termination_status, exit_code)

    def open_page(self, url=g_settings.WEBENGINE_CUSTOMER_URL, head_index=None, requested_at=None):

        _popup_web_engine_page = hasattr(
            g_settings, 'POPUP_WEB_ENGINE_PAGE') and getattr(
            g_settings, 'POPUP_WEB_ENGINE_PAGE')
        if _popup_web_engine_page or self.webengine_view is None:
            self.reset_view()
            time.sleep(.05)

        logging.debug(f"url:{url}.")
        if url:
            # requested_at: monotonic() catturato sul CLICK (home_page) per misurare
            # la latenza reale click -> pagina caricata, inclusa l'attesa sul thread
            # GUI che il Navigation Timing non vede. Armato SOLO se c'e' davvero una
            # navigazione da misurare: con url=None resterebbe stale e sporcherebbe
            # la misura del prossimo loadFinished.
            self.__open_requested_at = requested_at if requested_at is not None else time.monotonic()
            q_url = QUrl(url)
            self.q_url = q_url
            # Si ricarica SEMPRE l'URL richiesto, anche se identico a quello gia'
            # mostrato: la pagina e' renderizzata server-side con dati che cambiano
            # nel tempo (livelli pipe, pigmenti, config) e riusare la pagina
            # residente mostrerebbe dati stale. La view resta comunque residente
            # mentre e' nascosta (hideEvent non blanka, sospende solo il WS).
            self.__load_requested_url = q_url.toString()
            self.webengine_view.setUrl(q_url)
            self.parent().setCurrentWidget(self)

        self.current_head_index = head_index

        if self.main_window.home_page.refill_lbl_is_active(head_index):
            self.refill_label.show()
            self.refill_label.raise_()
        else:
            self.refill_label.hide()

        if 'service_page' in f"{url}":
            self.print_label.show()
            self.print_label.raise_()
        else:
            self.print_label.hide()
