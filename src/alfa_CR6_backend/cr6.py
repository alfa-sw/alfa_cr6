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
from PyQt5.QtCore import pyqtSignal         # pylint: disable=no-name-in-module

try:
    import evdev                                # pylint: disable=import-error
    has_evdev = True
except BaseException:
    has_evdev = False
import websockets                           # pylint: disable=import-error
import aiohttp                              # pylint: disable=import-error
import async_timeout                        # pylint: disable=import-error


from alfa_CR6_ui.main_window import MainWindow
from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode

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
    # ~ LOG_LEVEL=logging.DEBUG,
    # ~ LOG_LEVEL=logging.INFO,
    LOG_LEVEL=logging.WARNING,

    LOGS_PATH=os.path.join(RUNTIME_FILES_ROOT, 'log'),
    TMP_PATH=os.path.join(RUNTIME_FILES_ROOT, 'tmp'),
    CONF_PATH=os.path.join(RUNTIME_FILES_ROOT, 'conf'),

    UI_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'ui'),
    IMAGE_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'images'),
    KEYBOARD_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'keyboard'),

    # here is defined the path to the sqlite db used for persistent data,
    # if it is empty or None, no sqlite db is open
    # ~ SQLITE_CONNECT_STRING="sqlite:///" + \
    # ~ os.path.join(RUNTIME_FILES_ROOT, 'data', 'cr6.V' + _get_version().split('.')[1] + '.sqlite'),
    SQLITE_CONNECT_STRING=None,

    # this dictionary keeps the url of the websocket servers
    # to which the application connects its websocket clients,
    # if it is empty, no websocket client is started
    MACHINE_HEAD_IPADD_LIST=[
        # ~ "127.0.0.1", 
        # ~ "127.0.0.1", "127.0.0.1", "127.0.0.1", "127.0.0.1", "127.0.0.1", "127.0.0.1", 
        # ~ "192.168.15.156", "192.168.15.19", "192.168.15.60", "192.168.15.61", "192.168.15.62", "192.168.15.170",
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

    STORE_EXCEPTIONS_TO_DB_AS_DEFAULT=False,
    DEFAULT_WAIT_FOR_TIMEOUT=90,
    DISABLE_FEED_JAR_IN_INPUT=True,
)


def parse_json_order(path_to_json_file, json_schema_name):

    # TODO implement parser(s)

    properties = {}
    with open(path_to_json_file) as f:

        properties = json.load(f)
        if json_schema_name == "KCC":
            sz = properties.get('total', '100')
            sz = '1000' if sz.lower() == '1l' else sz
        properties['size_cc'] = int(sz)

        return properties


def handle_exception(e, ui_msg=None, db_event=settings.STORE_EXCEPTIONS_TO_DB_AS_DEFAULT):

    # TODO: send alarm msg to Gui surface

    logging.error(traceback.format_exc())

    if db_event:
        a = QApplication.instance()
        if a and a.db_session:
            try:
                descr = "{} {}".format(ui_msg, traceback.format_exc())
                evnt = Event(
                    name=e,
                    level='ERROR',
                    severity='',
                    source='CR6_application',
                    description=descr)
                a.db_session.add(evnt)
                a.db_session.commit()
            except BaseException:
                a.db_session.rollback()
                logging.error(traceback.format_exc())


class MachineHead(object):           # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(self, index, websocket=None, ip_add=None):

        self.index = index
        self.name = QApplication.instance().MACHINE_HEAD_INDEX_TO_NAME_MAP[index]

        self.websocket = websocket
        self.ip_add = ip_add
        self.aiohttp_clientsession = None
        self.status = {}
        self.photocells_status = {}
        self.jar_photocells_status = {}
        self.jar_size_detect = None
        self.pipe_list = []

        self.refresh_status_event = asyncio.Event()

    async def wait_for_status(self, condition, *args,
                              timeout=settings.DEFAULT_WAIT_FOR_TIMEOUT,
                              timestep=.1,
                              msg=None):

        """ here we wait for a refresh_status_event be set and check the condition, till timeout """

        logging.info("{} condition:{}, args:{}".format(self.name, condition.__name__, args))

        t0 = time.time()
        ret = condition(*args)
        while not ret and time.time() - t0 < timeout:
            await self.refresh_status_event.wait()
            ret = condition(*args)
            logging.debug("ret:{}, {:.3f}/{}".format(ret, time.time() - t0, timeout))
            await asyncio.sleep(timestep)

        if not ret and msg:
            raise Exception("Timeout on waiting for: {}.".format(msg))
        logging.info("ret:{} msg:{}".format(ret, msg))
        return ret

    async def trigger_refresh_status_event(self):
        self.refresh_status_event.set()
        await asyncio.sleep(.1)  # let the waiters be notified
        self.refresh_status_event.clear()
        # ~ logging.warning("{} self.refresh_status_event:{}".format(self.name, self.refresh_status_event))

    def on_cmd_answer(self, answer):

        QApplication.instance().onCmdAnswer.emit(self.index, answer)
        logging.debug(f"self:{self}, answer:{answer}")

    async def do_dispense(self, jar):

        logging.warning("self:{}, index:{}, jar:{}".format(self, self.index, jar))
        # TODO: check jar order and dispense, if due
        return await asyncio.sleep(1)

    async def update_pipes(self):

        ret = await self.call_api_rest('pipe', 'GET', {})
        self.pipe_list = ret.get('objects', [])

        # ~ logging.debug(f"{self.pipe_list}")

    async def update_status(self, status):

        # ~ logging.warning("status:{}".format(status))

        # ~ see doc/machine_status_jsonschema.py

        self.status = status

        if status.get('photocells_status'):
            self.photocells_status = {
                'THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL': status['photocells_status'] & 0x001 and 1,
                'THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL': status['photocells_status'] & 0x002 and 1,
                'THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL': status['photocells_status'] & 0x004 and 1,
                'THOR TABLE_PHOTOCELL': status['photocells_status'] & 0x008 and 1,
                'THOR VALVE_OPEN_PHOTOCELL': status['photocells_status'] & 0x010 and 1,
                'THOR AUTOCAP_CLOSE_PHOTOCELL': status['photocells_status'] & 0x020 and 1,
                'THOR AUTOCAP_OPEN_PHOTOCELL': status['photocells_status'] & 0x040 and 1,
                'THOR BRUSH_PHOTOCELL': status['photocells_status'] & 0x080 and 1,
            }

        if status.get('jar_photocells_status'):
            self.jar_photocells_status = {
                'JAR_INPUT_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x001 and 1,
                'JAR_LOAD_LIFTER_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x002 and 1,
                'JAR_OUTPUT_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x004 and 1,
                'LOAD_LIFTER_DOWN_PHOTOCELL': status['jar_photocells_status'] & 0x008 and 1,
                'LOAD_LIFTER_UP_PHOTOCELL': status['jar_photocells_status'] & 0x010 and 1,
                'UNLOAD_LIFTER_DOWN_PHOTOCELL': status['jar_photocells_status'] & 0x020 and 1,
                'UNLOAD_LIFTER_UP_PHOTOCELL': status['jar_photocells_status'] & 0x040 and 1,
                'JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x080 and 1,
                'JAR_DISPENSING_POSITION_PHOTOCELL': status['jar_photocells_status'] & 0x100 and 1,
                'JAR_DETECTION_MICROSWITCH_1': status['jar_photocells_status'] & 0x200 and 1,
                'JAR_DETECTION_MICROSWITCH_2': status['jar_photocells_status'] & 0x400 and 1,
            }

            self.jar_size_detect = (
                status['jar_photocells_status'] & 0x200 +
                status['jar_photocells_status'] & 0x400) >> 9

        await self.trigger_refresh_status_event()

    async def call_api_rest(self, path: str, method: str, data: dict, timeout=5):

        r_json_as_dict = {}
        if self.ip_add:
            url = "http://{}:{}/{}/{}".format(self.ip_add, 8080, 'apiV1', path)
            if self.aiohttp_clientsession is None:
                self.aiohttp_clientsession = aiohttp.ClientSession()
            r_json_as_dict = {}
            try:
                with async_timeout.timeout(timeout):
                    if method.upper() == 'GET':
                        context_mngr = self.aiohttp_clientsession.get
                        args = [url]
                    elif method.upper() == 'POST':
                        context_mngr = self.aiohttp_clientsession.post
                        args = [url, data]

                    async with context_mngr(*args) as response:
                        r = response
                        r_json_as_dict = await r.json()

                    assert r.reason == 'OK', f"method:{method}, url:{url}, data:{data}, status:{r.status}, reason:{r.reason}"
            except Exception as e:                           # pylint: disable=broad-except
                handle_exception(e)
        return r_json_as_dict

    def send_command(self, cmd_name: str, params: dict, type_='command', channel='machine'):
        """ param 'type_' can be 'command' or 'macro'

            examples:
                self.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
                self.send_command(cmd_name="PURGE", params={'items': [{'name': 'B01', 'qtity': 2.1}, {'name': 'C03', 'qtity': 1.1}, ]}, type_='macro')
        """
        if self.websocket:
            try:
                msg = {
                    'type': type_,
                    'channel': channel,
                    'msg_out_dict': {'command': cmd_name, 'params': params},
                }
                logging.info(f"cmd_name:{cmd_name}, params:{params}, channel:{channel}")
                # ~ await self.websocket.send(json.dumps(msg))
                t = self.websocket.send(json.dumps(msg))
                asyncio.ensure_future(t)

            except Exception as e:                           # pylint: disable=broad-except
                handle_exception(e)

    async def close(self):

        if self.aiohttp_clientsession:
            await self.aiohttp_clientsession.close()

    async def can_movement(self, params=None):
        """ extracted from doc/Specifiche_Funzionamento_Car_Refinishing_REV12.pdf :
        (Please, verify current version of the doc)

        'Dispensing_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement, 2 = Start
        Movement till Photocell transition LIGHT - DARK ','propertyOrder': 1, 'type': 'number', 'fmt': 'B'},

        'Lifter_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement CW, 2 = Start
        Movement CW till Photocell transition LIGHT - DARK, 3 = Start Movement CCW, 4 = Start Movement CCW
        till Photocell transition DARK - LIGHT, 5 = Start Movement CCW till Photocell transition LIGHT- DARK', 'propertyOrder': 2, 'type': 'number', 'fmt': 'B'},

        'Input_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement, 2 = Start
        Movement till Photocell transition LIGHT - DARK', 'propertyOrder': 3, 'type': 'number', 'fmt': 'B'},

        'Lifter': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement Up till Photocell Up
        transition LIGHT – DARK, 2 = Start Movement Down till Photocell Down transition LIGHT – DARK',
        'propertyOrder': 4, 'type': 'number', 'fmt': 'B'},

        'Output_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement CCW till
        Photocell transition LIGHT – DARK, 2 = Start Movement CCW till Photocell transition DARK - LIGHT with a
        Delay', 3 = Start Movement', 'propertyOrder': 5, 'type': 'number', 'fmt': 'B'}}}},:

        """
        default = {'Dispensing_Roller': 0, 'Lifter_Roller': 0, 'Input_Roller': 0, 'Lifter': 0, 'Output_Roller': 0}
        if params:
            default.update(params)

        self.send_command('CAN_MOVEMENT', default)

        logging.warning("CAN_MOVEMENT index:{}, {}".format(self.index, default))

    def unload_lifter_up(self):
        flag = self.jar_photocells_status.get('UNLOAD_LIFTER_UP_PHOTOCELL')
        return flag

    def unload_lifter_down(self):
        flag = self.jar_photocells_status.get('UNLOAD_LIFTER_DOWN_PHOTOCELL')
        return flag

    def load_lifter_up(self):
        flag = self.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL')
        return flag

    def load_lifter_down(self):
        flag = self.jar_photocells_status.get('LOAD_LIFTER_DOWN_PHOTOCELL')
        return flag

    def unload_lifter_available(self):

        flag = not self.jar_photocells_status.get('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL')
        return flag

    def unload_lifter_busy(self):

        flag = self.jar_photocells_status.get('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL')
        return flag

    def load_lifter_available(self):

        flag = not self.jar_photocells_status.get('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL')
        return flag

    def load_lifter_busy(self):

        flag = self.jar_photocells_status.get('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL')
        return flag

    def dispense_position_busy(self):

        flag = self.jar_photocells_status.get('JAR_DISPENSING_POSITION_PHOTOCELL')
        return flag

    def dispense_position_available(self):

        flag = not self.jar_photocells_status.get('JAR_DISPENSING_POSITION_PHOTOCELL')
        # ~ flag = flag and not self.status.get('status_level') == 'JAR_POSITIONING'
        # ~ flag = flag and not self.status.get('container_presence')
        return flag

    def output_roller_busy(self):

        flag = self.jar_photocells_status.get('JAR_OUTPUT_ROLLER_PHOTOCELL')
        return flag

    def output_roller_available(self):

        flag = not self.jar_photocells_status.get('JAR_OUTPUT_ROLLER_PHOTOCELL')
        return flag

    def input_roller_busy(self):

        flag = self.jar_photocells_status.get('JAR_INPUT_ROLLER_PHOTOCELL')
        return flag

    def input_roller_available(self):

        flag = not self.jar_photocells_status.get('JAR_INPUT_ROLLER_PHOTOCELL')
        return flag


class CR6_application(QApplication):   # pylint:  disable=too-many-instance-attributes

    BARCODE_DEVICE_KEY_CODE_MAP = {
        'KEY_SPACE': ' ',
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

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {
        0: "A_TOP_LEFT",
        1: "F_BOTM_LEFT",
        2: "B_TOP_CENTER",
        3: "E_BOTM_CENTER",
        4: "C_TOP_RIGHT",
        5: "D_BOTM_RIGHT",
    }

    onHeadStatusChanged = pyqtSignal(int)
    onCmdAnswer = pyqtSignal(int, dict)

    def __init__(self, *args, **kwargs):

        logging.debug("settings:{}".format(settings))

        super().__init__(*args, **kwargs)

        self.run_flag = True
        self.ui_path = settings.UI_PATH
        self.images_path = settings.IMAGE_PATH
        self.keyboard_path = settings.KEYBOARD_PATH
        self.db_session = None

        self.__inner_loop_task_step = 0.02  # secs
        self.suspend_all_timeouts = False

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

        self.debug_status_view = None

    def __init_tasks(self):

        self.__tasks = [self.__inner_loop_task(), ]

        for dev_index, barcode_device_name in enumerate(settings.BARCODE_DEVICE_NAME_LIST):
            self.__tasks += [self.__barcode_read_task(dev_index, barcode_device_name), ]

        for head_index, ip_add in enumerate(settings.MACHINE_HEAD_IPADD_LIST):
            self.__tasks += [self.__ws_client_task(head_index, ip_add), ]

        for head_index, status_file_name in enumerate(settings.MOCKUP_FILE_PATH_LIST):
            self.__tasks += [self.__mockup_task(head_index, status_file_name), ]

        logging.debug(f"self.__tasks:{self.__tasks}")

    def __close_tasks(self, ):

        for m in self.machine_head_dict.values():
            try:
                asyncio.get_event_loop().run_until_complete(m.close())
            except Exception as e:                           # pylint: disable=broad-except
                handle_exception(e)

        for t in self.__runners[:] + [r['task'] for r in self.__jar_runners.values()]:
            try:
                t.cancel()

                async def _coro(_):
                    await _
                asyncio.get_event_loop().run_until_complete(_coro(t))
                # ~ asyncio.get_event_loop().run_until_complete(t.cancel())
            except asyncio.CancelledError:
                logging.info(f"{ t } has been canceled now.")

        self.__runners = []
        self.__jar_runners = {}

    async def __barcode_read_task(self, dev_index, barcode_device_name):

        buffer = ''
        if not has_evdev:
            return
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
        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __inner_loop_task(self):

        _last_feed_jar_in_input_time = 0

        try:
            while self.run_flag:

                self.processEvents()  # gui events

                self.__clock_tick()    # timer events

                if not settings.DISABLE_FEED_JAR_IN_INPUT:
                    _last_feed_jar_in_input_time = self.__feed_jar_in_input(_last_feed_jar_in_input_time)

                await asyncio.sleep(self.__inner_loop_task_step)

        except asyncio.CancelledError:
            pass
        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __ws_client_task(self, head_index, ip_add):

        ws_url = f"ws://{ ip_add }:11000/device:machine:status"

        try:
            self.machine_head_dict[head_index] = MachineHead(head_index, websocket=None, ip_add=ip_add)
            async with websockets.connect(ws_url) as websocket:
                # ~ websocket = await websockets.connect(ws_url)
                # ~ if websocket:
                self.machine_head_dict[head_index].websocket = websocket
                logging.warning("{} {}".format(head_index, self.machine_head_dict[head_index].name))
                while self.run_flag:

                    msg = await asyncio.wait_for(websocket.recv(), timeout=10)
                    if not msg:
                        msg = "{}"
                    msg_dict = dict(json.loads(msg))
                    if not msg or msg_dict.get('type') == 'time':
                        # let's refresh machine status anyway
                        await self.machine_head_dict[head_index].trigger_refresh_status_event()
                    elif msg_dict.get('type') == 'device:machine:status':
                        status = msg_dict.get('value')
                        status = dict(status)
                        await self.__on_head_status_changed(head_index, status)
                    elif msg_dict.get('type') == 'answer':
                        self.__on_head_answer_received(head_index, answer=msg_dict.get('value'))
        except asyncio.CancelledError:
            pass
        finally:
            # ~ if websocket:
                # ~ websocket.close()
            if self.machine_head_dict[head_index].aiohttp_clientsession:
                await self.machine_head_dict[head_index].aiohttp_clientsession.close()

    async def __mockup_task(self, head_index, status_file_name):

        try:
            while self.run_flag:
                try:
                    with open(status_file_name) as f:
                        status = json.load(f)
                        status = dict(status)

                        if not self.machine_head_dict.get(head_index):
                            self.machine_head_dict[head_index] = MachineHead(head_index)

                        await self.__on_head_status_changed(head_index, status)

                except Exception as e:                           # pylint: disable=broad-except
                    handle_exception(e)

                await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __update_machine_head_pipes(self):     # pylint: disable=no-self-use

        try:
            for m in self.machine_head_dict.values():

                # TODO: use cached vals, if present
                await m.update_pipes()
        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __on_barcode_read(self, dev_index, barcode,         # pylint: disable=no-self-use
                                skip_checks=False):     # debug only

        await self.__update_machine_head_pipes()

        try:
            logging.debug("dev_index:{}, barcode:{}".format(dev_index, barcode))
            order_nr, index = decompile_barcode(barcode)
            logging.debug("order_nr:{}, index:{}".format(order_nr, index))

            if skip_checks:
                q = self.db_session.query(Jar).filter(Jar.status == 'NEW')
                jar = q.first()
            else:
                q = self.db_session.query(Jar).filter(Jar.index == index)
                q = q.join(Order).filter((Order.order_nr == order_nr))
                jar = q.one()

                sz = self.machine_head_dict[0].jar_size_detect
                assert jar.size == sz, "{} != {}".format(jar.size, sz)

            if jar:
                # let's run a task that will manage the jar through the entire path inside the system
                t = self.__jar_task(jar)
                self.__jar_runners[barcode] = {'task': asyncio.ensure_future(t), 'jar': jar}

                logging.info("{} {} t:{}".format(len(self.__jar_runners), barcode, t))

        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __jar_task(self, jar):

        try:
            jar.status = 'PROGRESS'
            await self.move_01_02()
            jar.position = 'A'
            await self.get_machine_head_by_letter('A').do_dispense(jar)
            jar.position = 'A_B'
            await self.move_02_03()
            jar.position = 'B'
            await self.get_machine_head_by_letter('B').do_dispense(jar)
            jar.position = 'B_C'
            await self.move_03_04()
            jar.position = 'C'
            await self.get_machine_head_by_letter('C').do_dispense(jar)
            jar.position = 'C_UP'
            await self.move_04_05()
            jar.position = 'UP_LEFT'
            await self.move_05_06()
            jar.position = 'UP_DOWN_LEFT'
            await self.move_06_07()
            jar.position = 'D'
            await self.get_machine_head_by_letter('D').do_dispense(jar)
            jar.position = 'D_E'
            await self.move_07_08()
            jar.position = 'E'
            await self.get_machine_head_by_letter('E').do_dispense(jar)
            jar.position = 'E_F'
            await self.move_08_09()
            jar.position = 'F'
            await self.get_machine_head_by_letter('F').do_dispense(jar)
            jar.position = 'F_DOWN'
            await self.move_09_10()
            jar.position = 'DOWN_RIGHT'
            await self.move_10_11()
            jar.position = 'DOWN_UP_RIGHT'
            await self.move_11_12()
            jar.position = 'OUT'
            jar.status = 'DONE'

        except asyncio.CancelledError:
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()

        except Exception as e:                           # pylint: disable=broad-except
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()
            handle_exception(e)

        logging.warning("delivering jar:{}".format(jar))
        self.db_session.commit()

    def __feed_jar_in_input(self, last_time):

        last_time = None
        t = time.time()
        if t - last_time > 10:
            last_time = t
            if self.machine_head_dict.get(0):
                if not self.machine_head_dict[0].jar_photocells_status.get('JAR_INPUT_ROLLER_PHOTOCELL'):
                    self.machine_head_dict[0].can_movement({'Input_Roller': 0})
                    self.machine_head_dict[0].can_movement({'Input_Roller': 2})
        return last_time

    def __clock_tick(self):

        # TODO: check if machine_heads status is deprcated

        for k in [k_ for k_ in self.__jar_runners]:
            
            task = self.__jar_runners[k]['task']
            # ~ logging.warning("inspecting:{}".format(task))
            if task.done():
                task.cancel()
                logging.warning("deleting:{}".format(self.__jar_runners[k]))
                self.__jar_runners.pop(k)

    def __on_head_answer_received(self, head_index, answer):

        self.machine_head_dict[head_index].on_cmd_answer(answer)

    async def __on_head_status_changed(self, head_index, status):

        if self.machine_head_dict.get(head_index):
            # ~ old_status = self.machine_head_dict[head_index].status
            # ~ diff = {k: v for k, v in status.items() if v != old_status.get(k)}
            # ~ if diff:
                # ~ logging.warning("head_index:{}".format(head_index))
                # ~ logging.warning("diff:{}".format(diff))
            await self.machine_head_dict[head_index].update_status(status)
            self.main_window.sinottico.update_data(head_index, status)

            self.onHeadStatusChanged.emit(head_index)

    def get_machine_head_by_letter(self, letter):          # pylint: disable=inconsistent-return-statements

        for m in self.machine_head_dict.values():
            if m. name[0] == letter:
                return m

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

        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

        finally:

            self.__close_tasks()

        asyncio.get_event_loop().stop()
        asyncio.get_event_loop().run_until_complete(asyncio.get_event_loop().shutdown_asyncgens())
        asyncio.get_event_loop().close()

    def create_order(self, path_to_json_file, json_schema_name="KCC", n_of_jars=1):

        order = None
        if self.db_session:
            try:
                properties = parse_json_order(path_to_json_file, json_schema_name)
                order = Order(json_properties=json.dumps(properties))
                self.db_session.add(order)
                for j in range(n_of_jars):
                    jar = Jar(order=order, index=j, size=0)
                    self.db_session.add(jar)
                self.db_session.commit()
            except BaseException:
                logging.error(traceback.format_exc())
                order = None
                self.db_session.rollback()

        return order

    async def move_mu(self, l, roller='Dispensing_Roller', m=1):  # 'feed'
        A = self.get_machine_head_by_letter(l)
        await A.can_movement({roller: m})

    async def stop_mu(self, l, roller='Dispensing_Roller', m=0):  # 'feed'
        A = self.get_machine_head_by_letter(l)
        await A.can_movement({roller: m})

    async def move_step(self, l, roller='Dispensing_Roller', m=2):  # 'feed'
        A = self.get_machine_head_by_letter(l)
        await A.can_movement({roller: m})

    async def move_mu_01(self):  # 'feed'
        await self.move_mu('A', roller='Input_Roller')

    async def stop_mu_01(self):  # 'feed'
        await self.stop_mu('A', roller='Input_Roller')

    async def move_step_01(self):  # 'feed'
        await self.move_step('A', roller='Input_Roller')

    async def move_mu_02(self):  # 'feed'
        await self.move_mu('A')

    async def stop_mu_02(self):  # 'feed'
        await self.stop_mu('A')

    async def move_step_02(self):  # 'feed'
        await self.move_step('A')

    async def move_mu_03(self):  # 'feed'
        await self.move_mu('B')

    async def stop_mu_03(self):  # 'feed'
        await self.stop_mu('B')

    async def move_step_03(self):  # 'feed'
        await self.move_step('B')

    async def move_mu_04(self):  # 'feed'
        await self.move_mu('C')

    async def stop_mu_04(self):  # 'feed'
        await self.stop_mu('C')

    async def move_step_04(self):  # 'feed'
        await self.move_step('C')

    async def move_mu_05(self):  # 'feed'
        await self.move_mu('D')

    async def stop_mu_05(self):  # 'feed'
        await self.stop_mu('D')

    async def move_step_05(self):  # 'feed'
        await self.move_step('D')

    async def move_mu_07(self):  # 'feed'
        await self.move_mu('F')

    async def move_mu_06(self):  # 'feed'
        await self.move_mu('E')

    async def stop_mu_06(self):  # 'feed'
        await self.stop_mu('E')

    async def move_step_06(self):  # 'feed'
        await self.move_step('E')

    async def move_mu_07(self):  # 'feed'
        await self.move_mu('F')

    async def stop_mu_07(self):  # 'feed'
        await self.stop_mu('F')

    async def move_step_07(self):  # 'feed'
        await self.move_step('F')

    async def move_mu_08(self):  # 'feed'
        await self.move_mu('F', roller='Lifter_Roller', m=3)

    async def stop_mu_08(self):  # 'feed'
        await self.stop_mu('F', roller='Lifter_Roller')

    async def move_step_08(self):  # 'feed'
        await self.move_step('F', roller='Lifter_Roller', m=5)

    async def move_mu_09(self):  # 'feed'
        await self.move_mu('F', roller='Output_Roller', m=3)

    async def stop_mu_09(self):  # 'feed'
        await self.stop_mu('F', roller='Output_Roller')

    async def move_step_09(self):  # 'feed'
        await self.move_step('F', roller='Output_Roller', m=2)

    async def move_cw_mb_1(self):
        await self.move_mu('C', roller='Lifter_Roller', m=2)

    async def move_ccw_mb_1(self):
        await self.move_mu('C', roller='Lifter_Roller', m=3)

    async def stop_mb_1(self):
        await self.move_mu('C', roller='Lifter_Roller', m=0)

    async def lift_01_up(self):
        await self.move_mu('D', roller='Lifter', m=1)

    async def lift_01_down(self):
        await self.move_mu('D', roller='Lifter', m=2)

    async def lift_01_stop(self):
        await self.move_mu('D', roller='Lifter', m=0)

    async def lift_02_up(self):
        await self.move_mu('F', roller='Lifter', m=1)

    async def lift_02_down(self):
        await self.move_mu('F', roller='Lifter', m=2)

    async def lift_02_stop(self):
        await self.move_mu('F', roller='Lifter', m=0)

    async def move_00_01(self):  # 'feed'

        A = self.get_machine_head_by_letter('A')

        r = await A.wait_for_status(A.input_roller_busy, timeout=0.5)
        if not r:
            await A.wait_for_status(A.input_roller_available)
            await A.can_movement({'Input_Roller': 2})
            r = await A.wait_for_status(A.input_roller_busy, timeout=10)
            if not r:
                await A.can_movement()

    async def move_01_02(self):  # 'IN -> A'

        A = self.get_machine_head_by_letter('A')

        await A.can_movement({'Input_Roller': 1, 'Dispensing_Roller': 2})
        await A.wait_for_status(A.dispense_position_busy, timeout=10)

    async def move_02_03(self):  # 'A -> B'

        A = self.get_machine_head_by_letter('A')
        B = self.get_machine_head_by_letter('B')

        await B.wait_for_status(B.dispense_position_available)
        await A.can_movement({'Dispensing_Roller': 1})
        await B.can_movement({'Dispensing_Roller': 2})
        await B.wait_for_status(B.dispense_position_busy)
        await A.can_movement()

    async def move_03_04(self):  # 'B -> C'

        B = self.get_machine_head_by_letter('B')
        C = self.get_machine_head_by_letter('C')

        await C.wait_for_status(C.dispense_position_available)
        await B.can_movement({'Dispensing_Roller': 1})
        await C.can_movement({'Dispensing_Roller': 2})
        await C.wait_for_status(C.dispense_position_busy)
        await B.can_movement()

    async def move_04_05(self):  # 'C -> UP'

        C = self.get_machine_head_by_letter('C')
        D = self.get_machine_head_by_letter('D')

        await D.wait_for_status(D.load_lifter_up)
        await C.wait_for_status(C.load_lifter_available)
        await C.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 2})
        await C.wait_for_status(C.load_lifter_busy)

    async def move_05_06(self):  # 'UP -> DOWN'

        D = self.get_machine_head_by_letter('D')

        await D.can_movement({'Lifter': 2})
        await D.wait_for_status(D.load_lifter_down)

    async def move_06_07(self):  # 'DOWN -> D'

        C = self.get_machine_head_by_letter('C')
        D = self.get_machine_head_by_letter('D')

        await D.wait_for_status(D.dispense_position_available)
        await C.can_movement({'Lifter_Roller': 3})
        await D.can_movement({'Dispensing_Roller': 2})
        await D.wait_for_status(D.dispense_position_busy)
        await C.can_movement()
        await D.can_movement({'Lifter': 1})

    async def move_07_08(self):  # 'D -> E'

        D = self.get_machine_head_by_letter('D')
        E = self.get_machine_head_by_letter('E')

        await E.wait_for_status(E.dispense_position_available)
        r = await D.wait_for_status(D.load_lifter_up, timeout=1)
        if not r:
            await D.can_movement()
            await D.can_movement({'Lifter': 1, 'Dispensing_Roller': 1})
        else:
            await D.can_movement({'Dispensing_Roller': 1})
        await E.can_movement({'Dispensing_Roller': 2})
        await E.wait_for_status(E.dispense_position_busy)
        await D.can_movement()
        await D.can_movement({'Lifter': 1})

    async def move_08_09(self):  # 'E -> F'

        E = self.get_machine_head_by_letter('E')
        F = self.get_machine_head_by_letter('F')

        await F.wait_for_status(F.dispense_position_available)
        await E.can_movement({'Dispensing_Roller': 1})
        await F.can_movement({'Dispensing_Roller': 2})
        await F.wait_for_status(F.dispense_position_busy)
        await E.can_movement()

    async def move_09_10(self):  # 'F -> DOWN'

        F = self.get_machine_head_by_letter('F')

        await F.wait_for_status(F.unload_lifter_available)
        await F.wait_for_status(F.unload_lifter_down)
        await F.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 5})

    async def move_10_11(self):  # 'DOWN -> UP'

        F = self.get_machine_head_by_letter('F')

        await F.wait_for_status(F.unload_lifter_busy)
        await F.wait_for_status(F.unload_lifter_up)
        r = await F.wait_for_status(F.output_roller_available, timeout=1)
        if not r:
            await F.can_movement()
            await F.can_movement({'Output_Roller': 2})
            await F.wait_for_status(F.output_roller_available)
            await F.can_movement()
            await F.can_movement({'Lifter_Roller': 3, 'Output_Roller': 1})

    async def move_11_12(self):  # 'UP -> OUT'

        F = self.get_machine_head_by_letter('F')

        r = await F.wait_for_status(F.output_roller_available, timeout=5)
        if not r:
            await F.can_movement()
            raise Exception("Output_Roller Full")
        else:
            await F.wait_for_status(F.output_roller_busy)
            await F.can_movement()
            await F.can_movement({'Lifter': 2, 'Output_Roller': 3})
            await F.wait_for_status(F.output_roller_available)
            await F.wait_for_status(F.unload_lifter_down)
            await F.can_movement()

    async def stop_all(self):

        await self.get_machine_head_by_letter('A').can_movement()
        await self.get_machine_head_by_letter('B').can_movement()
        await self.get_machine_head_by_letter('C').can_movement()
        await self.get_machine_head_by_letter('D').can_movement()
        await self.get_machine_head_by_letter('E').can_movement()
        await self.get_machine_head_by_letter('F').can_movement()

    def run_a_coroutine_helper(self, coroutine_name):
        try:
            if hasattr(self, coroutine_name):
                _coroutine = getattr(self, coroutine_name)
                _future = _coroutine()
                asyncio.ensure_future(_future)
                logging.warning(f"coroutine_name:{coroutine_name}, _future:{_future}")
            else:
                logging.error(f"coroutine_name:{coroutine_name} not found!")
        except BaseException:
            logging.error(traceback.format_exc())


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=settings.LOG_LEVEL, format=fmt_)

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
