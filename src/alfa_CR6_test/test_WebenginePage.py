# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except

"""
. /opt/alfa_cr6/venv/bin/activate
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/test_WebenginePage.py
"""

import sys
import time
import logging
import traceback
import asyncio


from PyQt5.QtCore import QEventLoop, QUrl
from PyQt5.QtWidgets import QMainWindow, QApplication, QStackedWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage


from alfa_CR6_frontend.pages import WebenginePage
from alfa_CR6_backend.globals import import_settings

g_settings = import_settings()

class CustomWebEnginePage(QWebEnginePage):
    """ Custom WebEnginePage to customize how we handle link navigation """
    external_windows = []
    def acceptNavigationRequest(self, url,  _type, isMainFrame):
        logging.warning(f" ######################### url,  _type, isMainFrame:{(url,  _type, isMainFrame)}")
        if "BACK HOME -------" in str(url):
            url_ = QUrl.fromLocalFile("/opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/test_WebenginePage.html")
        else:
            return super().acceptNavigationRequest(url,  _type, isMainFrame)


class Application(QApplication):
    # ~ pass

    def processEvents(self, *args, **kwargs):
        if self.hasPendingEvents():
            # ~ logging.warning(f"args:{args}")
            r = super().processEvents(*args, **kwargs)
            if r:
                logging.warning(f"r :{r}")

class MainWindow(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.stacked_widget = QStackedWidget(self)
        self.setGeometry(100, 200, 1800, 600)
        self.setCentralWidget(self.stacked_widget)
        self.webengine_page = WebenginePage(parent=self)

        self.customwebenginepage = CustomWebEnginePage()

        self.webengine_page.webengine_view.setPage(self.customwebenginepage)

        url_ = QUrl.fromLocalFile("/opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/test_WebenginePage.html")
        self.webengine_page.open_page(url=url_)

    def open_alert_dialog(self, _msg, title="ALERT", callback=None, args=None):
        logging.warning(f"""
************************* 
*************************
_msg:{_msg}
*************************
************************* """)

async def create_inner_loop_task(app):

    try:
        cntr = 0
        while 1:

            timeout_ms = 100
            app.processEvents(QEventLoop.AllEvents, timeout_ms)
            if app.hasPendingEvents():
                dt = 0
            else:
                dt = 0.01

            await asyncio.sleep(dt)

    except asyncio.CancelledError:
        pass
    except Exception as e:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())

def main():

    logging.basicConfig(
        stream=sys.stdout, level='INFO',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")
    logging.warning(f"g_settings:{g_settings}")
    app = Application(sys.argv)
    window = MainWindow()
    window.show()
    t = create_inner_loop_task(app)
    asyncio.ensure_future(t)
    asyncio.get_event_loop().run_forever()
    # ~ app.exec_()





main()
