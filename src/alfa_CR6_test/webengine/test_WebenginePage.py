# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

"""
. /opt/alfa_cr6/venv/bin/activate
python /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/test_WebenginePage.py
"""

import sys
import logging
import traceback
import asyncio

from PyQt5.QtCore import QEventLoop  # pylint: disable=no-name-in-module
from PyQt5.QtWidgets import ( # pylint: disable=no-name-in-module
    QMainWindow,
    QApplication,
    QStackedWidget,
    QMessageBox)

from alfa_CR6_backend.globals import import_settings  # pylint: disable=import-error
from alfa_CR6_frontend.browser_page import BrowserPage

g_settings = import_settings()


class Application(QApplication):

    main_window = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.main_window = MainWindow(g_settings.WEBENGINE_CUSTOMER_URL)

    def processEvents(self, *args, **kwargs):
        if self.hasPendingEvents():
            # ~ logging.warning(f"args:{args}")
            r = super().processEvents(*args, **kwargs)
            if r:
                logging.warning(f"r :{r}")

    async def create_inner_loop_task(self):

        try:
            while 1:
                timeout_ms = 100
                try:
                    if self.hasPendingEvents():
                        self.processEvents(QEventLoop.AllEvents, timeout_ms)
                        dt = 0
                    else:
                        dt = 0.05
                    await asyncio.sleep(dt)
                except Exception as e:  # pylint: disable=broad-except
                    self.handle_exception(e)
        except asyncio.CancelledError:
            pass
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def handle_exception(self, e):  # pylint:  disable=no-self-use

        if "CancelledError" in traceback.format_exc():
            logging.warning(traceback.format_exc())
            raise e

        logging.error(traceback.format_exc())


class MainWindow(QMainWindow):

    def __init__(self, url_, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # ~ self.setGeometry(100, 20, 1800, 1200)
        self.setStyleSheet("""
                QWidget {font-size: 24px; font-family:Dejavu;}
                QPushButton {background-color: #F3F3F3F3; border: 1px solid #999999; border-radius: 4px;}
                QPushButton:pressed {background-color: #AAAAAA;}
                QScrollBar:vertical {width: 40px;}
            """)

        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)
        self.stacked_widget.setGeometry(100, 20, 1800, 1200)
        self.stacked_widget.show()

        self.browser_page = None
        self.start_url = url_

        self.browser_page = BrowserPage(parent=self)
        self.browser_page.setGeometry(100, 20, 1800, 1200)
        self.stacked_widget.setCurrentWidget(self.browser_page)
        self.browser_page.open_page(self.start_url)

        # ~ self.home = HomePage(parent=self)
        # ~ self.home = HomePageSixHeads(parent=self)
        # ~ self.stacked_widget.setCurrentWidget(self.home)

    def reset_browser(self):

        self.browser_page = BrowserPage(parent=self)
        self.browser_page.open_page(self.start_url)

    @staticmethod
    def open_alert_dialog(args_, title="ALERT"):

        logging.warning(f"args_:{args_}, title:{title}")
        msgBox = QMessageBox()
        msgBox.setText(f"{args_}")
        msgBox.exec()


def main():

    logging.basicConfig(
        stream=sys.stdout, level='INFO',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    g_settings.POPUP_WEB_ENGINE_PAGE = 1

    # ~ g_settings.WEBENGINE_CUSTOMER_URL = "http://kccrefinish.co.kr/" # kcc
    # ~ g_settings.WEBENGINE_CUSTOMER_URL = "https://cloud.e-mixing.eu/" # ludwig / mcm
    # ~ g_settings.WEBENGINE_CUSTOMER_URL = "https://capellasolutionsgroup.com/"
    # ~ g_settings.WEBENGINE_CUSTOMER_URL = "http://www.autorefinishes.co.kr/" # noroo
    g_settings.WEBENGINE_CUSTOMER_URL = "https://www.autorefinishes.co.kr/colorinformation/colormix_view.asp?MixCd=EM-4800-29&PaintTy=WQ"  # noroo

    # ~ here = os.path.dirname(os.path.abspath(__file__))
    # ~ g_settings.WEBENGINE_CUSTOMER_URL = QUrl.fromLocalFile(os.path.join(here, "test_WebenginePage.html"))
    # ~ g_settings.WEBENGINE_CUSTOMER_URL = QUrl("http://www.autorefinishes.co.kr/")
    # ~ g_settings.WEBENGINE_CUSTOMER_URL = QUrl("https://www.autorefinishes.co.kr/colorinformation/colormix_view_xmlForm.asp?MixCd=KS-071-2&PaintTy=WQ")
    # ~ g_settings.WEBENGINE_CUSTOMER_URL = QUrl("https://www.autorefinishes.co.kr/colorinformation/colormix_view_xmlForm.asp?MixCd=EM-4649&PaintTy=WQ")

    logging.warning(f"g_settings:{g_settings}")

    app = Application(sys.argv)

    app.main_window.showFullScreen()

    t = app.create_inner_loop_task()
    asyncio.ensure_future(t)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":

    main()
