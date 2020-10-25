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

LOG_LEVEL = logging.INFO
# ~ LOG_LEVEL = logging.WARNING

# ~ this dictionary keeps the url of the websocket servers
# ~ to which the application connects its websocket clients,
# ~ if it is empty, no websocket client is started
WS_URL_DICT = {
    # ~ 1: "ws://127.0.0.1:11000/device:machine:status",
}

# ~ this dictionary keeps the path to the files where
# ~ the application looks for the mockup version of
# ~ the machine:status structures in json format,
# ~ if it is empty, no mockup file is searched for
MOCKUP_FILE_PATH_DICT = {
    1: '/opt/alfa_cr6/var/machine_status_0.json',
    # ~ 2: '/opt/alfa_cr6/var/machine_status_1.json',
}

BARCODE_DEVICE_NAME_LIST = [
    # ~ '/dev/input/event7',
    # ~ '/dev/input/event8',
]


class Jar(object):

    def __init__(self, barcode):
        self.barcode = barcode

        self.machine_head = None
        self.status = None
        self.position = None

    def update(self):
        pass

    def move(self):
        pass


class CR6_application(QApplication):   # pylint:  disable=too-many-instance-attributes

    BARCODE_DEVICE_KEY_CODE_MAP = {
        'KEY_SPACE': ' ',
        'KEY_Q': 'Q',
        'KEY_W': 'W',
        'KEY_E': 'E',
        'KEY_R': 'R',
        'KEY_T': 'T',
        'KEY_Y': 'Y',
        'KEY_U': 'U',
        'KEY_I': 'I',
        'KEY_O': 'O',
        'KEY_P': 'P',
        'KEY_A': 'A',
        'KEY_S': 'S',
        'KEY_D': 'D',
        'KEY_F': 'F',
        'KEY_G': 'G',
        'KEY_H': 'H',
        'KEY_J': 'J',
        'KEY_K': 'K',
        'KEY_L': 'L',
        'KEY_Z': 'Z',
        'KEY_X': 'X',
        'KEY_C': 'C',
        'KEY_V': 'V',
        'KEY_B': 'B',
        'KEY_N': 'N',
        'KEY_M': 'M',
        'KEY_1': '1',
        'KEY_2': '2',
        'KEY_3': '3',
        'KEY_4': '4',
        'KEY_5': '5',
        'KEY_6': '6',
        'KEY_7': '7',
        'KEY_8': '8',
        'KEY_9': '9',
        'KEY_0': '0',
    }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.run_flag = True
        self.ui_path = os.path.dirname(os.path.abspath(__file__)) + '/ui'

        self.head_status_dict = {}
        self.jar_dict = {}

        self.__version = None
        self.__barcode_device = None
        self.__tasks = []
        self.__runners = []

        self.__init_tasks()

        self.main_window = MainWindow()

    def __init_tasks(self):

        self.__tasks = [self.__qt_loop_task(), ]

        for barcode_device_name in BARCODE_DEVICE_NAME_LIST:
            self.__tasks += [self.__barcode_read_task(barcode_device_name), ]

        for head_index, ws_url in WS_URL_DICT.items():
            self.__tasks += [self.__ws_client_task(head_index, ws_url), ]

        for head_index, status_file_name in MOCKUP_FILE_PATH_DICT.items():
            self.__tasks += [self.__mockup_task(head_index, status_file_name), ]


    def __on_barcode_read(self, barcode):     # pylint: disable=no-self-use

        logging.warning("barcode:{}".format(barcode))
        self.jar_dict[barcode] = Jar(barcode)

    def __on_head_status_changed(self, head_index, status):     # pylint: disable=no-self-use

        old_status = self.head_status_dict.get(head_index, {})
        diff = {k: v for k, v in status.items() if v != old_status.get(k)}
        logging.warning("head_index:{}".format(head_index))
        logging.warning("diff:{}".format(diff))

        self.head_status_dict[head_index] = status

    async def __barcode_read_task(self, barcode_device_name):

        buffer = ''
        try:

            import evdev     # pylint: disable=import-error

            self.__barcode_device = evdev.InputDevice(barcode_device_name)
            self.__barcode_device.grab()   # become the sole recipient of all incoming input events from this device
            logging.warning(f"self.__barcode_device:{ self.__barcode_device }")

            async for event in self.__barcode_device.async_read_loop():
                keyEvent = evdev.categorize(event)

                if event.type == evdev.ecodes.EV_KEY and keyEvent.keystate == 0:  # key_up = 0
                    # ~ if event.type == evdev.ecodes.EV_KEY and event.value == 0: # key_up = 0
                    logging.warning("code:{} | {} | {}".format(event.code, chr(event.code), evdev.ecodes.KEY[event.code]))
                    # ~ logging.warning("code:{} | {} | {}".format(event.code,  keyEvent.keycode, evdev.ecodes.KEY[event.code]))
                    if keyEvent.keycode == 'KEY_ENTER':
                        self.__on_barcode_read(buffer)
                        buffer = ''
                    else:
                        buffer += self.BARCODE_DEVICE_KEY_CODE_MAP.get(keyEvent.keycode, '*')

        except asyncio.CancelledError:
            pass
        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def __qt_loop_task(self):

        try:
            while self.run_flag:
                self.processEvents()
                await asyncio.sleep(0.02)
            asyncio.get_event_loop().stop()

        except asyncio.CancelledError:
            pass
        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def __ws_client_task(self, head_index, ws_url):

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
                        self._on_head_status_changed(head_index, status)

        except asyncio.CancelledError:
            pass

    async def __mockup_task(self, head_index, status_file_name):

        try:
            while self.run_flag:
                try:
                    with open(status_file_name) as f:
                        status = json.load(f)
                        status = dict(status)
                        self._on_head_status_changed(head_index, status)
                except Exception as e:       # pylint: disable=broad-except
                    logging.debug(e)

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def __close(self, ):

        for t in self.__runners:
            try:
                t.cancel()
                async def _coro(_):
                    await _
                asyncio.get_event_loop().run_until_complete(_coro(t))
            except asyncio.CancelledError:
                logging.info(f"{ t } has been canceled now.")

        asyncio.get_event_loop().run_until_complete(asyncio.get_event_loop().shutdown_asyncgens())
        asyncio.get_event_loop().close()

    def get_version(self):                                 # pylint: disable=no-self-use

        if not self.__version:
            try:
                pth = os.path.abspath(os.path.dirname(sys.executable))
                cmd = '{}/pip show alfa_CR6'.format(pth)
                for line in subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode().split('\n'):
                    if 'Version' in line:
                        ver = line.split(":")[1]
                        self.__version = ver.strip()
            except Exception as exc:  # pylint: disable=broad-except
                logging.error(exc)

        return self.__version

    def run_forever(self):

        self.main_window.show()

        try:

            self.__runners = [asyncio.ensure_future(t) for t in self.__tasks]
            asyncio.get_event_loop().run_forever()

        except KeyboardInterrupt:
            pass

        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())

        finally:
            self.__close()


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL, format=fmt_)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
