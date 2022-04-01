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

import os
import sys
import logging
import traceback
import asyncio

from functools import partial

from PyQt5.QtCore import QEventLoop, QUrl # pylint: disable=no-name-in-module
from PyQt5.QtWidgets import QMainWindow, QApplication, QStackedWidget # pylint: disable=no-name-in-module

from alfa_CR6_frontend.pages import BrowserPage # pylint: disable=import-error
from alfa_CR6_backend.globals import import_settings # pylint: disable=import-error

g_settings = import_settings()


class Application(QApplication):

    main_window = None

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
            raise  # pylint:  disable=misplaced-bare-raise

        logging.error(traceback.format_exc())

class MainWindow(QMainWindow):

    def __init__(self, url_, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.stacked_widget = QStackedWidget(self)
        self.setGeometry(100, 200, 1200, 600)
        self.setCentralWidget(self.stacked_widget)
        self.browser = BrowserPage(parent=self)
        self.browser.open_page(url_)

    def open_alert_dialog(self, args_, title="ALERT"):

        logging.warning(f"args_:{args_}, title:{title}")

def main():

    logging.basicConfig(
        stream=sys.stdout, level='INFO',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")
    logging.warning(f"g_settings:{g_settings}")
    app = Application(sys.argv)

    here = os.path.dirname(os.path.abspath(__file__))
    # ~ url_ = QUrl.fromLocalFile(os.path.join(here, "test_WebenginePage.html"))
    url_ = QUrl("http://www.autorefinishes.co.kr/")
    # ~ url_ = QUrl("https://www.autorefinishes.co.kr/colorinformation/colormix_view_xmlForm.asp?MixCd=KS-071-2&PaintTy=WQ")
    # ~ url_ = QUrl("https://www.autorefinishes.co.kr/colorinformation/colormix_view_xmlForm.asp?MixCd=EM-4649&PaintTy=WQ")
    window = MainWindow(url_)
    app.main_window = window
    window.show()

    t = app.create_inner_loop_task()
    asyncio.ensure_future(t)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":

    main()
