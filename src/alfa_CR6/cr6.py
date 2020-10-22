# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import sys
import os
import logging
import traceback
import asyncio
import subprocess
import json

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

import websockets                         # pylint: disable=import-error

from alfa_CR6.main_window import MainWindow
from alfa_CR6.sinottico import Sinottico

# ~ this dictionary keeps the url of the websocket servers 
# ~ to which the application connects its websocket clients,
# ~ if it is empty, no websocket client is started
WS_URL_DICT = {
    1: "ws://127.0.0.1:11000/device:machine:status",
}

# ~ this dictionary keeps the path to the files where 
# ~ the application looks for the mockup version of
# ~ the machine:status structures in json format,
# ~ if it is empty, no mockup file is searched for 
MOCKUP_FILE_PATH_DICT = {
    # ~ 1: '/opt/alfa_cr6/var/machine_status_0.json',
    # ~ 2: '/opt/alfa_cr6/var/machine_status_1.json',
}

LOG_LEVEL = logging.INFO
# ~ LOG_LEVEL = logging.WARNING


class CR6_application(QApplication):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.run_flag = True
        self.ui_path = os.path.dirname(os.path.abspath(__file__)) + '/ui'
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        self.init_widgets()

        self.head_status_dict = {}


    def init_widgets(self):
        self.main_window = MainWindow()
        self.sinottico = Sinottico()
        self.main_window.project_layout.addWidget(self.sinottico)


    def get_version(self):                                 # pylint: disable=no-self-use

        ver = None
        try:
            pth = os.path.abspath(os.path.dirname(sys.executable))
            cmd = '{}/pip show alfa_CR6'.format(pth)
            for line in subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode().split('\n'):
                if 'Version' in line:
                    ver = line.split(":")[1]
                    ver = ver.strip()
        except Exception as exc:  # pylint: disable=broad-except
            logging.error(exc)

        return ver

    def handle_head_status(self, head_index, status):     # pylint: disable=no-self-use
        old_status = self.head_status_dict.get(head_index, {})
        diff =  { k : v for k, v in status.items() if v != old_status.get(k) }
        logging.warning("head_index:{}".format(head_index))
        logging.warning("diff:{}".format(diff))

        self.head_status_dict[head_index] = status

    async def qt_loop_task(self):

        try:
            while self.run_flag:
                self.processEvents()
                await asyncio.sleep(0.02)
            asyncio.get_event_loop().stop()

        except asyncio.CancelledError:
            pass
        except Exception:       # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def ws_client_task(self, head_index, ws_url):

        try:
            async with websockets.connect(ws_url) as websocket:
                while self.run_flag:

                    msg = await websocket.recv()

                    msg_dict = dict(json.loads(msg))
                    if msg_dict.get('type') == 'time':
                        pass
                    elif msg_dict.get('type') == 'device:machine:status':
                        status = msg_dict.get('value')
                        status = dict(status)
                        self.handle_head_status(head_index, status)

        except asyncio.CancelledError:
            pass
        except Exception:       # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def mockup_task(self, head_index, status_file_name):

        try:
            while self.run_flag:
                try:
                    with open(status_file_name) as f:
                        status = json.load(f)
                        status = dict(status)
                        self.handle_head_status(head_index, status)
                except Exception as e:       # pylint: disable=broad-except
                    logging.debug(e)

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception:       # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def run_forever(self):

        self.main_window.show()

        _tasks = [asyncio.ensure_future(self.qt_loop_task()), ]

        for head_index, ws_url in WS_URL_DICT.items():
            _tasks += [asyncio.ensure_future(self.ws_client_task(head_index, ws_url)), ]

        for head_index, status_file_name in MOCKUP_FILE_PATH_DICT.items():
            _tasks += [asyncio.ensure_future(self.mockup_task(head_index, status_file_name)), ]

        try:
            asyncio.get_event_loop().run_forever()

        except KeyboardInterrupt:
            pass

        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())

        finally:

            for t in _tasks:
                try:
                    t.cancel()

                    async def _coro(_):
                        await _
                    asyncio.get_event_loop().run_until_complete(_coro(t))
                except asyncio.CancelledError:
                    logging.info(f"{ t } has been canceled now.")

            asyncio.get_event_loop().run_until_complete(asyncio.get_event_loop().shutdown_asyncgens())
            asyncio.get_event_loop().close()


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL, format=fmt_)

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
