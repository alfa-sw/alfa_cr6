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


def handle_exception(e, ui_msg=None, db_event=None):

    # TODO: send alarm msg to Gui surface

    logging.error(traceback.format_exc())

    if db_event is None:
        db_event = settings.STORE_EXCEPTIONS_TO_DB_AS_DEFAULT

    if db_event:
        a = QApplication.instance()
        if a and a.db_session:
            try:
                evnt = Event(
                    name=e,
                    level='ERROR',
                    severity='',
                    source='CR6_application',
                    description=traceback.format_exc())
                a.db_session.add(evnt)
                a.db_session.commit()
            except BaseException:
                a.db_session.rollback()
                logging.error(traceback.format_exc())


class MachineHead(object):           # pylint: disable=too-many-instance-attributes

    def __init__(self, websocket=None, ip_add=None):

        self.websocket = websocket
        self.ip_add = ip_add
        self.aiohttp_clientsession = None
        self.status = {}
        self.photocells_status = {}
        self.jar_photocells_status = {}
        self.jar_size_detect = None
        self.pipe_list = []

    def on_cmd_answer(self, answer):

        logging.warning(f"self:{self}, answer:{answer}")

    async def update_pipes(self):

        ret = await self.call_api_rest('pipe', 'GET', {})
        self.pipe_list = ret.get('objects', [])

        # ~ logging.debug(f"{self.pipe_list}")

    def update_status(self, status):

        # ~ logging.warning("status:{}".format(status))

        # ~ see doc/machine_status_jsonschema.py

        self.status = status

        if status.get('photocells_status'):
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

        if status.get('jar_photocells_status'):
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

            self.jar_size_detect = (
                status['jar_photocells_status'] & 0x200 +
                status['jar_photocells_status'] & 0x400) >> 9

    async def call_api_rest(self, path: str, method: str, data: dict, timeout=5):

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

        # ~ logging.warning(f"{ r_json_as_dict }")
        # ~ logging.warning(f"{type(r_json_as_dict)}")
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
                t = self.websocket.send(json.dumps(msg))
                asyncio.ensure_future(t)

            except Exception as e:                           # pylint: disable=broad-except
                handle_exception(e)

    async def close(self):

        if self.aiohttp_clientsession:
            await self.aiohttp_clientsession.close()

    def can_movement(self, params=None):

        """ extracted from doc/Specifiche_Funzionamento_Car_Refinishing_REV12.pdf :
        (Please, verify current version of the doc)

        'Dispensing_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement, 2 = Start
        Movement till Photocell transition LIGHT - DARK ','propertyOrder': 1, 'type': 'number', 'fmt': 'B'},

        'Lifter_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement CW, 2 = Start
        Movement CW till Photocell transition LIGHT - DARK, 3 = Start Movement CCW, 4 = Start Movement CCW
        till Photocell transition DARK - LIGHT', 'propertyOrder': 2, 'type': 'number', 'fmt': 'B'},

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

    def dispense_position_busy(self):

        flag = self.jar_photocells_status.get('JAR_DISPENSING_POSITION_PHOTOCELL')
        return flag

    def dispense_position_available(self):

        flag = not self.jar_photocells_status.get('JAR_DISPENSING_POSITION_PHOTOCELL')
        flag = flag and not self.status.get('status_level') == 'JAR_POSITIONING'
        flag = flag and not self.status.get('container_presence')
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

    def __init_tasks(self):

        self.__tasks = [self.__inner_loop_task(), ]

        for dev_index, barcode_device_name in enumerate(settings.BARCODE_DEVICE_NAME_LIST):
            self.__tasks += [self.__barcode_read_task(dev_index, barcode_device_name), ]

        for head_index, ip_add in enumerate(settings.MACHINE_HEAD_IPADD_LIST):
            self.__tasks += [self.__ws_client_task(head_index, ip_add), ]

        for head_index, status_file_name in enumerate(settings.MOCKUP_FILE_PATH_LIST):
            self.__tasks += [self.__mockup_task(head_index, status_file_name), ]

        logging.debug(f"self.__tasks:{self.__tasks}")

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

                _last_feed_jar_in_input_time = self.__feed_jar_in_input(_last_feed_jar_in_input_time)

                await asyncio.sleep(self.__inner_loop_task_step)

            asyncio.get_event_loop().stop()

        except asyncio.CancelledError:
            pass
        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __ws_client_task(self, head_index, ip_add):

        ws_url = f"ws://{ ip_add }:11000/device:machine:status"

        try:
            self.machine_head_dict[head_index] = MachineHead(websocket=None, ip_add=ip_add)
            async with websockets.connect(ws_url) as websocket:
                self.machine_head_dict[head_index].websocket = websocket
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
        finally:
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
                            self.machine_head_dict[head_index] = MachineHead()

                        self.__on_head_status_changed(head_index, status)

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
                if not m.pipe_list:
                    await m.update_pipes()
        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __on_barcode_read(self, dev_index, barcode):     # pylint: disable=no-self-use

        await self.__update_machine_head_pipes()

        try:
            logging.debug("dev_index:{}, barcode:{}".format(dev_index, barcode))
            order_nr, index = decompile_barcode(barcode)
            logging.debug("order_nr:{}, index:{}".format(order_nr, index))

            q = self.db_session.query(Jar).filter(Jar.index == index)
            q = q.join(Order).filter((Order.order_nr == order_nr))
            jar = q.one()

            def condition():
                return self.machine_head_dict[0].jar_photocells_status['JAR_INPUT_ROLLER_PHOTOCELL']

            ret = await self.wait_for_condition(condition=condition, timeout=3)
            assert ret, "timeout waiting for JAR_INPUT_ROLLER_PHOTOCELL engagement"

            sz = self.machine_head_dict[0].jar_size_detect
            assert jar.size == sz, "{} != {}".format(jar.size, sz)

            # let's run a task that will manage the jar through the entire path inside the system
            t = self.__jar_task(jar)
            self.__jar_runners[barcode] = asyncio.ensure_future(t)

            logging.info("{} {} t:{}".format(len(self.__jar_runners), barcode, t))

        except Exception as e:                           # pylint: disable=broad-except
            handle_exception(e)

    async def __jar_task(self, jar):

        try:

            jar.status = 'PROGRESS'
            jar.position = 'step_1'

            # TODO: if available, move to step_2:
            # ~ while (step_2 not available): wait, if timeout: set jar.status = ERROR
            # ~ send roller_move comand
            # ~ while (not roller_status is moving): wait
            # ~ while (FTC_1): wait, if timeout: set jar.status = ERROR
            # ~ set jar.position = 'moving between 1 and 2'
            # ~ while (roller_status is moving): wait, if timeout: set jar.status = ERROR
            # ~ while (not FTC_2): wait, if timeout: set jar.status = ERROR
            # ~ set jar.position = 'FTC_2'

            r = await self.wait_for_condition(self.machine_head_dict[0].dispense_position_available, timeout=3 * 60)
            if not r:
                raise Exception("timeout waiting head 0 dispense_position_available")
            self.machine_head_dict[0].can_movement({'Input_Roller': 0})
            self.machine_head_dict[0].can_movement({'Input_Roller': 2})
            self.machine_head_dict[0].can_movement({'Dispensing_Roller': 2})
            jar.status = 'step_1,step_2'
            await self.wait_for_condition(self.machine_head_dict[0].dispense_position_busy, timeout=3 * 60)
            if not r:
                raise Exception("timeout waiting head 0 dispense_position_busy")

            # TODO: move through the sequence of positions till the end:
            # ~ for p in [f"FTC_{i}" for i in range(2,10)]:
            # ~ if due, do; then, if available, move on or set jar.status = ERROR
            # ~ if FTC_10 deliver and set jar.status = DONE

            import random
            await asyncio.sleep(2 + random.randint(1, 5))    # TODO: remove this

            jar.status = 'DONE'

        except asyncio.CancelledError:
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()

        except Exception as e:                           # pylint: disable=broad-except
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()
            handle_exception(e)

        logging.warning("jar:{}".format(jar))
        self.db_session.commit()

    def __feed_jar_in_input(self, last_time):

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

        # TODO: [for r in self.__jar_runners: check r.status]

        for k in [k_ for k_ in self.__jar_runners]:
            if self.__jar_runners[k].done():
                self.__jar_runners[k].cancel()
                del self.__jar_runners[k]

        # ~ logging.info("len(self.__jar_runners):{}".format(len(self.__jar_runners)))
        # ~ logging.debug(["{}.".format(r) for r in self.__jar_runners.values()])

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

    def __close(self, ):

        for m in self.machine_head_dict.values():
            try:
                asyncio.get_event_loop().run_until_complete(m.close())
            except Exception as e:                           # pylint: disable=broad-except
                handle_exception(e)

        for t in self.__runners[:] + [r for r in self.__jar_runners.values()]:
            try:
                t.cancel()

                async def _coro(_):
                    await _
                asyncio.get_event_loop().run_until_complete(_coro(t))
                # ~ asyncio.get_event_loop().run_until_complete(t.cancel())
            except asyncio.CancelledError:
                logging.info(f"{ t } has been canceled now.")

        self.__runners = []
        self.__jar_runners = []

        asyncio.get_event_loop().run_until_complete(asyncio.get_event_loop().shutdown_asyncgens())
        asyncio.get_event_loop().close()

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
            self.__close()

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

    async def wait_for_condition(self, condition, *args, timeout=5, timestep=.5):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if condition(*args):
                return True
            await asyncio.sleep(timestep)
            if self.suspend_all_timeouts:
                t0 += timestep

        return False


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=settings.LOG_LEVEL, format=fmt_)

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
