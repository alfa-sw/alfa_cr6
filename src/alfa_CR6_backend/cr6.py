# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import sys
import os
import time
import logging
import traceback
import asyncio
import subprocess
import json
import types

from PyQt5.QtWidgets import QApplication    # pylint: disable=no-name-in-module

import evdev                                # pylint: disable=import-error
import websockets                           # pylint: disable=import-error


from alfa_CR6_ui.main_window import MainWindow
from alfa_CR6_backend.models import Order, Jar, decompile_barcode

RUNTIME_FILES_ROOT = '/opt/alfa_cr6'
HERE = os.path.dirname(os.path.abspath(__file__))


def _get_version():

    _ver = None

    try:
        pth = os.path.abspath(os.path.dirname(sys.executable))
        cmd = '{}/pip show alfa_CR6'.format(pth)
        for line in subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode().split('\n'):
            if 'Version' in line:
                _ver = line.split(":")[1]
                _ver = _ver.strip()
    except Exception as exc:  # pylint: disable=broad-except
        logging.error(exc)

    return _ver


settings = types.SimpleNamespace(
    LOG_LEVEL=logging.INFO,
    # ~ LOG_LEVEL = logging.WARNING,

    LOGS_PATH=os.path.join(RUNTIME_FILES_ROOT, 'log'),
    TMP_PATH=os.path.join(RUNTIME_FILES_ROOT, 'tmp'),
    CONF_PATH=os.path.join(RUNTIME_FILES_ROOT, 'conf'),

    UI_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'ui'),
    IMAGE_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'images'),

    # here is defined the path to the sqlite db used for persistent data,
    # if it is empty or None, no sqlite db is open
    # ~ SQLITE_CONNECT_STRING="sqlite:///" + \
    # ~ os.path.join(RUNTIME_FILES_ROOT, 'data', 'cr6.V' + _get_version().split('.')[1] + '.sqlite'),
    SQLITE_CONNECT_STRING=None,

    # this dictionary keeps the url of the websocket servers
    # to which the application connects its websocket clients,
    # if it is empty, no websocket client is started
    WS_URL_LIST=[
        # ~ "ws://127.0.0.1:11000/device:machine:status",
    ],

    # this dictionary keeps the path to the files where
    # the application looks for the mockup version of
    # the machine:status structures in json format,
    # if it is empty, no mockup file is searched for
    MOCKUP_FILE_PATH_LIST=[
        '/opt/alfa_cr6/var/machine_status_0.json',
        '/opt/alfa_cr6/var/machine_status_1.json',
        '/opt/alfa_cr6/var/machine_status_2.json',
        '/opt/alfa_cr6/var/machine_status_3.json',
        '/opt/alfa_cr6/var/machine_status_4.json',
        '/opt/alfa_cr6/var/machine_status_5.json',
    ],

    BARCODE_DEVICE_NAME_LIST=[
        # ~ '/dev/input/event7',
        # ~ '/dev/input/event8',
    ],
)


def handle_exception():
    # TODO: send alarm msg to the Gui surface
    logging.error(traceback.format_exc())


async def wait_for_condition(condition, timeout=5, timestep=.5, on_timeout=None):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if condition():
            return True
        await asyncio.sleep(timestep)
    if on_timeout:
        on_timeout()
    return False


class MachineHead(object):

    def __init__(self, websocket_client=None):

        self.websocket_client = websocket_client
        self.status = {}
        self.photocells_status = {}
        self.jar_photocells_status = {}
        self.jar_size_detect = None

    def on_cmd_answer(self, answer):

        logging.warning(f"self:{self}, answer:{answer}")

    def update_status(self, status):

        logging.debug("status:{}".format(status))

        self.status = status

        self.photocells_status = {
            'THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL': status['photocells_status'] & 0x001,
            'THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL': status['photocells_status'] & 0x002,
            'THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL': status['photocells_status'] & 0x004,
            'THOR TABLE_PHOTOCELL': status['photocells_status'] & 0x008,
            'THOR VALVE_OPEN_PHOTOCELL': status['photocells_status'] & 0x010,
            'THOR AUTOCAP_CLOSE_PHOTOCELL': status['photocells_status'] & 0x020,
            'THOR AUTOCAP_OPEN_PHOTOCELL': status['photocells_status'] & 0x040,
            'THOR BRUSH_PHOTOCELL': status['photocells_status'] & 0x080,
        }

        self.jar_photocells_status = {
            'JAR_INPUT_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x001,
            'JAR_LOAD_LIFTER_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x002,
            'JAR_OUTPUT_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x004,
            'LOAD_LIFTER_DOWN_PHOTOCELL': status['jar_photocells_status'] & 0x008,
            'LOAD_LIFTER_UP_PHOTOCELL': status['jar_photocells_status'] & 0x010,
            'UNLOAD_LIFTER_DOWN_PHOTOCELL': status['jar_photocells_status'] & 0x020,
            'UNLOAD_LIFTER_UP_PHOTOCELL': status['jar_photocells_status'] & 0x040,
            'JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x080,
            'JAR_DISPENSING_POSITION_PHOTOCELL': status['jar_photocells_status'] & 0x100,
            'JAR_DETECTION_MICROSWITCH_1': status['jar_photocells_status'] & 0x200,
            'JAR_DETECTION_MICROSWITCH_2': status['jar_photocells_status'] & 0x400,
        }

        self.jar_size_detect = (status['jar_photocells_status'] & 0x200 + status['jar_photocells_status'] & 0x400) >> 9

    def send_command(self, cmd_name: str, params: dict, type_='command', channel='machine'):
        """ param 'type_' can be 'command' or 'macro'

            examples:
                self.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
                self.send_command(cmd_name="PURGE", params={'items': [{'name': 'B01', 'qtity': 2.1}, {'name': 'C03', 'qtity': 1.1}, ]}, type_='macro')
        """
        if self.websocket_client:
            try:
                msg = {
                    'type': type_,
                    'channel': channel,
                    'msg_out_dict': {'command': cmd_name, 'params': params},
                }
                logging.warning(f"cmd_name:{cmd_name}, params:{params}, channel:{channel}")
                t = self.websocket_client.send(json.dumps(msg))
                asyncio.ensure_future(t)

            except Exception:                           # pylint: disable=broad-except
                handle_exception()


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

        logging.debug("settings:{}".format(settings))

        super().__init__(*args, **kwargs)

        self.run_flag = True
        self.ui_path = settings.UI_PATH
        self.images_path = settings.IMAGE_PATH
        self.db_session = None

        self.__inner_loop_task_step = 0.02 # secs

        self.machine_head_dict = {}

        self.__version = None
        self.__barcode_device = None
        self.__tasks = []
        self.__runners = []
        self.__jar_runners = {}

        for pth in [settings.LOGS_PATH, settings.TMP_PATH, settings.CONF_PATH]:
            if not os.path.exists(pth):
                os.makedirs(pth)

        if settings.SQLITE_CONNECT_STRING:

            from alfa_CR6_backend.models import init_models
            self.db_session = init_models(settings.SQLITE_CONNECT_STRING)

        self.__init_tasks()

        self.main_window = MainWindow()

    def __init_tasks(self):

        self.__tasks = [self.__inner_loop_task(), ]

        for dev_index, barcode_device_name in enumerate(settings.BARCODE_DEVICE_NAME_LIST):
            self.__tasks += [self.__barcode_read_task(dev_index, barcode_device_name), ]

        for head_index, ws_url in enumerate(settings.WS_URL_LIST):
            self.__tasks += [self.__ws_client_task(head_index, ws_url), ]

        for head_index, status_file_name in enumerate(settings.MOCKUP_FILE_PATH_LIST):
            self.__tasks += [self.__mockup_task(head_index, status_file_name), ]

        logging.debug(f"self.__tasks:{self.__tasks}")

    async def __barcode_read_task(self, dev_index, barcode_device_name):

        buffer = ''
        try:

            self.__barcode_device = evdev.InputDevice(barcode_device_name)
            self.__barcode_device.grab()   # become the sole recipient of all incoming input events from this device
            logging.warning(f"self.__barcode_device:{ self.__barcode_device }")

            async for event in self.__barcode_device.async_read_loop():
                keyEvent = evdev.categorize(event)
                type_key_event = evdev.ecodes.EV_KEY   # pylint:  disable=no-member
                if event.type == type_key_event and keyEvent.keystate == 0:  # key_up = 0
                    # ~ if event.type == evdev.ecodes.EV_KEY and event.value == 0: # key_up = 0
                    # ~ logging.warning("code:{} | {} | {}".format(event.code, chr(event.code), evdev.ecodes.KEY[event.code]))
                    # ~ logging.warning("code:{} | {} | {}".format(event.code,  keyEvent.keycode, evdev.ecodes.KEY[event.code]))
                    if keyEvent.keycode == 'KEY_ENTER':
                        await self.__on_barcode_read(dev_index, buffer)
                        buffer = ''
                    else:
                        buffer += self.BARCODE_DEVICE_KEY_CODE_MAP.get(keyEvent.keycode, '*')

        except asyncio.CancelledError:
            pass
        except Exception:                           # pylint: disable=broad-except
            handle_exception()

    async def __clock_tick(self):

        # TODO: check if machine_heads status is deprcated

        # TODO: [for r in self.__jar_runners: check r.status]

        for k in [k_ for k_ in self.__jar_runners]:
            if self.__jar_runners[k].done():
                self.__jar_runners[k].cancel()
                del self.__jar_runners[k]

        # ~ logging.info("len(self.__jar_runners):{}".format(len(self.__jar_runners)))
        # ~ logging.debug(["{}.".format(r) for r in self.__jar_runners.values()])

        pass

    async def __inner_loop_task(self):

        try:
            while self.run_flag:

                self.processEvents()  # gui events

                await self.__clock_tick()    # timer events

                await asyncio.sleep(self.__inner_loop_task_step)

            asyncio.get_event_loop().stop()

        except asyncio.CancelledError:
            pass
        except Exception:                           # pylint: disable=broad-except
            handle_exception()

    async def __ws_client_task(self, head_index, ws_url):

        try:
            async with websockets.connect(ws_url) as websocket:
                self.machine_head_dict[head_index] = MachineHead(websocket)
                while self.run_flag:

                    msg = await websocket.recv()

                    msg_dict = dict(json.loads(msg))
                    if msg_dict.get('type') == 'time':
                        pass
                    elif msg_dict.get('type') == 'device:machine:status':
                        status = msg_dict.get('value')
                        status = dict(status)
                        self.__on_head_status_changed(head_index, status)
                    elif msg_dict.get('type') == 'answer':
                        self.__on_head_answer_received(head_index, answer=msg_dict.get('value'))

        except asyncio.CancelledError:
            pass

    async def __mockup_task(self, head_index, status_file_name):

        try:
            while self.run_flag:
                try:
                    with open(status_file_name) as f:
                        status = json.load(f)
                        status = dict(status)

                        if not self.machine_head_dict.get(head_index):
                            self.machine_head_dict[head_index] = MachineHead()

                        self.__on_head_status_changed(head_index, status)

                except Exception:       # pylint: disable=broad-except
                    handle_exception()

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception:                           # pylint: disable=broad-except
            handle_exception()

    def __close(self, ):

        for t in self.__runners[:] + [r for r in  self.__jar_runners.values()]:
            try:
                t.cancel()

                async def _coro(_):
                    await _
                asyncio.get_event_loop().run_until_complete(_coro(t))
            except asyncio.CancelledError:
                logging.info(f"{ t } has been canceled now.")

        self.__runners = []
        self.__jar_runners = []

        asyncio.get_event_loop().run_until_complete(asyncio.get_event_loop().shutdown_asyncgens())
        asyncio.get_event_loop().close()

    async def __on_barcode_read(self, dev_index, barcode):     # pylint: disable=no-self-use

        try:
            logging.debug("dev_index:{}, barcode:{}".format(dev_index, barcode))
            order_nr, index = decompile_barcode(barcode)
            logging.debug("order_nr:{}, index:{}".format(order_nr, index))

            q = self.db_session.query(Jar).filter(Jar.index == index)
            q = q.join(Order).filter((Order.order_nr == order_nr))
            jar = q.one()

            def condition():
                return self.machine_head_dict[0].jar_photocells_status['JAR_INPUT_ROLLER_PHOTOCELL']

            def on_timeout():
                assert False, "timeout waiting for JAR_INPUT_ROLLER_PHOTOCELL engagement"

            await wait_for_condition(condition=condition, timeout=3, on_timeout=on_timeout)

            sz = self.machine_head_dict[0].jar_size_detect
            assert jar.size == sz, "{} != {}".format(jar.size, sz)

            # let's run a task that will manage the jar through the entire path inside the system
            t = self.__jar_task(jar)
            self.__jar_runners[barcode] = asyncio.ensure_future(t)

            logging.info("t:{}".format(t))

        except Exception:                           # pylint: disable=broad-except
            handle_exception()

    async def __jar_task(self, jar):

        logging.debug("jar:{}".format(jar))

        try:
            jar.status = 'PROGRESS'
            jar.position = 'FTC_1'

            # TODO: get order details (formula) and resolve it in terms of machine_heads and pipes
            # ~ save the stuff in jar.json_properties

            # TODO: if available, move to step_2:
            # ~ while (step_2 not available): wait, if timeout: set jar.status = ERROR
            # ~ send roller_move comand
            # ~ while (not roller_status is moving): wait
            # ~ while (FTC_1): wait, if timeout: set jar.status = ERROR
            # ~ set jar.position = 'moving between 1 and 2'
            # ~ while (roller_status is moving): wait, if timeout: set jar.status = ERROR
            # ~ while (not FTC_2): wait, if timeout: set jar.status = ERROR
            # ~ set jar.position = 'FTC_2'
            
            # TODO: move through the sequence of positions till the end:
            # ~ for p in [f"FTC_{i}" for i in range(2,12)]:
                # ~ if due, do; then, if available, move on or set jar.status = ERROR
            # ~ if FTC_12 deliver and set jar.status = DONE

            await asyncio.sleep(2)    # TODO: remove this

        except asyncio.CancelledError:
            jar.status = 'ERROR'

    def __on_head_answer_received(self, head_index, answer):

        self.machine_head_dict[head_index].on_cmd_answer(answer)

    def __on_head_status_changed(self, head_index, status):

        if self.machine_head_dict.get(head_index):
            old_status = self.machine_head_dict[head_index].status
            diff = {k: v for k, v in status.items() if v != old_status.get(k)}
            if diff:
                # ~ logging.warning("head_index:{}".format(head_index))
                # ~ logging.warning("diff:{}".format(diff))
                self.machine_head_dict[head_index].update_status(status)
                self.main_window.sinottico.update_data(head_index, status)

    def get_version(self):

        if not self.__version:
            self.__version = _get_version()
        return self.__version

    def run_forever(self):

        self.main_window.show()

        try:

            self.__runners = [asyncio.ensure_future(t) for t in self.__tasks]
            asyncio.get_event_loop().run_forever()

        except KeyboardInterrupt:
            pass

        except Exception:                           # pylint: disable=broad-except
            handle_exception()

        finally:
            self.__close()


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=settings.LOG_LEVEL, format=fmt_)

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
