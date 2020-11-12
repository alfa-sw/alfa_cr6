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

from alfa_CR6_ui.main_window import MainWindow
from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode
from alfa_CR6_backend.machine_head import MachineHead
from alfa_CR6_test.machine_proto import Machine

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
    MACHINE_HEAD_IPADD_PORTS_LIST=[
        ('127.0.0.1', 11000, 8080)
        # ~ ("192.168.15.156", 11000, 8080)
        # ~ ("192.168.15.19",  11000, 8080)
        # ~ ("192.168.15.60",  11000, 8080)
        # ~ ("192.168.15.61",  11000, 8080)
        # ~ ("192.168.15.62",  11000, 8080)
        # ~ ("192.168.15.170", 11000, 8080)
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


class BarCodeReader:   # pylint:  disable=too-many-instance-attributes,too-few-public-methods

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

    def __init__(self, dev_index, barcode_device_name, barcode_handler):

        self.barcode_device_name = barcode_device_name
        self.barcode_handler = barcode_handler
        self.dev_index = dev_index

        self._device = None

    async def run(self):

        try:
            import evdev                                # pylint: disable=import-error

            app = QApplication.instance()

            buffer = ''
            self._device = evdev.InputDevice(self.barcode_device_name)
            self._device.grab()   # become the sole recipient of all incoming input events from this device
            logging.warning(f"self._device:{ self._device }")
            async for event in self._device.async_read_loop():
                keyEvent = evdev.categorize(event)
                type_key_event = evdev.ecodes.EV_KEY   # pylint:  disable=no-member
                if event.type == type_key_event and keyEvent.keystate == 0:  # key_up = 0
                    if keyEvent.keycode == 'KEY_ENTER':
                        if self.barcode_handler:
                            await self.barcode_handler(self.dev_index, buffer)
                        buffer = ''
                    else:
                        buffer += self.BARCODE_DEVICE_KEY_CODE_MAP.get(keyEvent.keycode, '*')

        except asyncio.CancelledError:
            pass
        except ImportError:
            logging.warning("cannot import evdev, runinng without barcode reader.")
        except Exception as e:                           # pylint: disable=broad-except
            app.handle_exception(e)


class CR6_application(QApplication):   # pylint:  disable=too-many-instance-attributes,too-many-public-methods

    """
    {   'Dispensing_Roller':  {'description': 'Values: 0 = Stop Movement, 1 = Start Movement, 2 = Start Movement till Photocell
            transition LIGHT - DARK ','propertyOrder': 1, 'type': 'number', 'fmt': 'B'},
        'Lifter_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement CW, 2 = Start Movement CW till Photocell
            transition LIGHT - DARK, 3 = Start Movement CCW, 4 = Start Movement CCW till Photocell transition DARK – LIGHT, 5 = Start Movement
            CCW till Photocell transition LIGHT- DARK', 'propertyOrder': 2, 'type': 'number', 'fmt': 'B'},
        'Input_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement, 2 = Start Movement till Photocell transition
            LIGHT - DARK', 'propertyOrder': 3, 'type': 'number', 'fmt': 'B'},
        'Lifter': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement Up till Photocell Up transition LIGHT – DARK, 2 =
            Start Movement Down till Photocell Down transition LIGHT – DARK', 'propertyOrder': 4, 'type': 'number', 'fmt': 'B'},
        'Output_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement CCW till Photocell transition LIGHT – DARK,
            2 = Start Movement CCW till Photocell transition DARK - LIGHT with a Delay', 3 = Start Movement', 'propertyOrder': 5, 'type': 'number',
            'fmt': 'B'}}}},:
    """

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {
        0: "A_TOP_LEFT",
        1: "F_BOTM_LEFT",
        2: "B_TOP_CENTER",
        3: "E_BOTM_CENTER",
        4: "C_TOP_RIGHT",
        5: "D_BOTM_RIGHT",
    }

    onHeadMsgReceived = pyqtSignal(int, dict)

    def handle_exception(self, e, ui_msg=None, db_event=settings.STORE_EXCEPTIONS_TO_DB_AS_DEFAULT):     # pylint:  disable=no-self-use

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
        # ~ self.__barcode_device = None
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

        self.__tasks = [self.__create_inner_loop_task(), ]

        for dev_index, barcode_device_name in enumerate(settings.BARCODE_DEVICE_NAME_LIST):
            t = self.__create_barcode_task(dev_index, barcode_device_name)
            self.__tasks.append(t)

        for head_index, item in enumerate(settings.MACHINE_HEAD_IPADD_PORTS_LIST):
            if item:
                ip_add, ws_port, http_port = item
                t = self.__create_machine_task(head_index, ip_add, ws_port, http_port)
                self.__tasks.append(t)

        # ~ for head_index, status_file_name in settings.MACHINE_HEAD_IPADD_PORTS_MAP.items():
            # ~ self.__tasks += [self.__create_machine_mockup_task(head_index, status_file_name), ]

        logging.debug(f"self.__tasks:{self.__tasks}")

    def __close_tasks(self, ):

        for m in self.machine_head_dict.values():
            try:
                asyncio.get_event_loop().run_until_complete(m.close())
            except Exception as e:                           # pylint: disable=broad-except
                self.handle_exception(e)

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

    async def __create_barcode_task(self, dev_index, barcode_device_name):

        b = BarCodeReader(dev_index, barcode_device_name, self.on_barcode_read)
        self.barcode_dict[dev_index] = b
        await b.run()
        logging.warning(f" *** terminating barcode reader: {b} *** ")

    async def __create_inner_loop_task(self):
        try:
            while self.run_flag:

                self.processEvents()  # gui events
                self.__clock_tick()    # timer events
                await asyncio.sleep(self.__inner_loop_task_step)

        except asyncio.CancelledError:
            pass
        except Exception as e:                           # pylint: disable=broad-except
            self.handle_exception(e)

    async def __create_machine_task(self, head_index, ip_add, ws_port, http_port):

        m = Machine(head_index, ip_add, ws_port, http_port, msg_handler=self.on_head_msg_received)
        self.machine_head_dict[head_index] = m
        await m.run()
        logging.warning(f" *** terminating machine: {m} *** ")

    async def __update_machine_head_pipes(self):     # pylint: disable=no-self-use

        try:
            for m in self.machine_head_dict.values():

                # TODO: use cached vals, if present
                await m.update_pipes()
        except Exception as e:                           # pylint: disable=broad-except
            self.handle_exception(e)

    async def __jar_task(self, jar):
        
        def update_jar(jar, status=None, pos=None, t0=None):
            if not status is None:
                jar.status = status

            if not pos is None:
                jar.position = pos 

            if not t0 is None:
                jar.description = "d:{:.1f}".format(time.time() - t0)

        t0 = time.time()
        try:
            update_jar(jar, 'NEW', '_', t0)
            await self.move_00_01()
            update_jar(jar, 'PROGRESS', 'IN', t0)
            await self.move_01_02()
            update_jar(jar, 'PROGRESS', 'A', t0)
            await self.get_machine_head_by_letter('A').do_dispense(jar)
            update_jar(jar, 'PROGRESS', 'A_B', t0)
            await self.move_02_03()
            update_jar(jar, 'PROGRESS', 'B', t0)
            await self.get_machine_head_by_letter('B').do_dispense(jar)
            update_jar(jar, 'PROGRESS', 'B_C', t0)
            await self.move_03_04()
            update_jar(jar, 'PROGRESS', 'C', t0)
            await self.get_machine_head_by_letter('C').do_dispense(jar)
            update_jar(jar, 'PROGRESS', 'C_LIFTR', t0)
            await self.move_04_05()
            update_jar(jar, 'PROGRESS', 'LIFTR', t0)
            await self.move_05_06()
            update_jar(jar, 'PROGRESS', 'LIFTR_D', t0)
            await self.move_06_07()
            update_jar(jar, 'PROGRESS', 'D', t0)
            await self.get_machine_head_by_letter('D').do_dispense(jar)
            update_jar(jar, 'PROGRESS', 'D_E', t0)
            await self.move_07_08()
            update_jar(jar, 'PROGRESS', 'E', t0)
            await self.get_machine_head_by_letter('E').do_dispense(jar)
            update_jar(jar, 'PROGRESS', 'E_F', t0)
            await self.move_08_09()
            update_jar(jar, 'PROGRESS', 'F', t0)
            await self.get_machine_head_by_letter('F').do_dispense(jar)
            update_jar(jar, 'PROGRESS', 'F_LIFTL', t0)
            await self.move_09_10()
            update_jar(jar, 'PROGRESS', 'LIFTL', t0)
            await self.move_10_11()
            update_jar(jar, 'PROGRESS', 'LIFTL_OUT', t0)
            await self.move_11_12()
            update_jar(jar, 'DONE', '_', t0)

        except asyncio.CancelledError:
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()

        except Exception as e:                           # pylint: disable=broad-except
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()
            self.handle_exception(e)

        logging.warning("delivering jar:{}".format(jar))
        self.db_session.commit()

    def __clock_tick(self):

        # TODO: check if machine_heads status is deprcated

        for k in [k_ for k_ in self.__jar_runners]:

            task = self.__jar_runners[k]['task']
            # ~ logging.warning("inspecting:{}".format(task))
            if task.done():
                task.cancel()
                logging.warning("deleting:{}".format(self.__jar_runners[k]))
                self.__jar_runners.pop(k)

    async def on_barcode_read(self, dev_index, barcode,         # pylint: disable=no-self-use
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

                logging.warning(" ************ {} {} jar:{}".format(len(self.__jar_runners), barcode, jar))

        except Exception as e:                           # pylint: disable=broad-except
            self.handle_exception(e)

    async def on_head_msg_received(self, head_index, msg_dict):

        if msg_dict.get('type') == 'device:machine:status':
            status = msg_dict.get('value')
            status = dict(status)
            self.main_window.sinottico.update_data(head_index, status)

        self.onHeadMsgReceived.emit(head_index, msg_dict)

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
            self.handle_exception(e)

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

    async def move_00_01(self):  # 'feed'

        A = self.get_machine_head_by_letter('A')
        r = await A.wait_for_jar_photocells_status('JAR_INPUT_ROLLER_PHOTOCELL', on=True, timeout=0.5)
        if not r:
            await A.can_movement({'Input_Roller': 2})
            r = await A.wait_for_jar_photocells_status('JAR_INPUT_ROLLER_PHOTOCELL', on=True, timeout=20)
            if r:
                await A.can_movement()
        else:
            logging.info("A->JAR_INPUT_ROLLER_PHOTOCELL is ON, nothing to do.")

        return r

    async def move_01_02(self):  # 'IN -> A'

        A = self.get_machine_head_by_letter('A')

        await A.can_movement({'Input_Roller': 1, 'Dispensing_Roller': 2})
        # ~ await A.wait_for_status(A.dispense_position_busy, timeout=10)
        r = await A.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True, timeout=10)
        return r

    async def move_02_03(self):  # 'A -> B'

        A = self.get_machine_head_by_letter('A')
        B = self.get_machine_head_by_letter('B')

        # ~ await B.wait_for_status(B.dispense_position_available)
        r = await B.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=False)
        if r:
            await A.can_movement({'Dispensing_Roller': 1})
            await B.can_movement({'Dispensing_Roller': 2})
            # ~ await B.wait_for_status(B.dispense_position_busy)
            r = await B.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await A.can_movement()

        return r

    async def move_03_04(self):  # 'B -> C'

        B = self.get_machine_head_by_letter('B')
        C = self.get_machine_head_by_letter('C')

        # ~ await C.wait_for_status(C.dispense_position_available)
        r = await C.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=False)
        await B.can_movement({'Dispensing_Roller': 1})
        await C.can_movement({'Dispensing_Roller': 2})
        # ~ await C.wait_for_status(C.dispense_position_busy)
        r = await C.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
        await B.can_movement()

        return r

    async def move_04_05(self):  # 'C -> UP'

        C = self.get_machine_head_by_letter('C')
        D = self.get_machine_head_by_letter('D')

        # ~ await D.wait_for_status(D.load_lifter_up)
        r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_UP_PHOTOCELL', on=True)
        if not r:
            await D.can_movement({'Lifter': 1})
            r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_UP_PHOTOCELL', on=True)

        if r:
            # ~ await C.wait_for_status(C.load_lifter_available)
            r = await C.wait_for_jar_photocells_status('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', on=False)
            if r:
                await C.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 2})
                # ~ await C.wait_for_status(C.load_lifter_busy)
                r = await C.wait_for_jar_photocells_status('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', on=True)

        return r

    async def move_05_06(self):  # 'UP -> DOWN'

        D = self.get_machine_head_by_letter('D')

        await D.can_movement({'Lifter': 2})
        # ~ await D.wait_for_status(D.load_lifter_down)
        r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_DOWN_PHOTOCELL', on=True)

        return r

    async def move_06_07(self):  # 'DOWN -> D'

        C = self.get_machine_head_by_letter('C')
        D = self.get_machine_head_by_letter('D')

        # ~ await D.wait_for_status(D.dispense_position_available)
        r = await D.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=False)
        if r:
            await C.can_movement({'Lifter_Roller': 3})
            await D.can_movement({'Dispensing_Roller': 2})
            # ~ await D.wait_for_status(D.dispense_position_busy)
            r = await D.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await C.can_movement()
                await D.can_movement({'Lifter': 1})

        return r

    async def move_07_08(self):  # 'D -> E'

        D = self.get_machine_head_by_letter('D')
        E = self.get_machine_head_by_letter('E')

        # ~ await E.wait_for_status(E.dispense_position_available)
        r = await E.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=False)
        # ~ r = await D.wait_for_status(D.load_lifter_up, timeout=1)
        if r:
            r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_UP_PHOTOCELL', on=True, timeout=1)
            if not r:
                await D.can_movement()
                await D.can_movement({'Lifter': 1, 'Dispensing_Roller': 1})
            else:
                await D.can_movement({'Dispensing_Roller': 1})
            await E.can_movement({'Dispensing_Roller': 2})
            # ~ await E.wait_for_status(E.dispense_position_busy)
            r = await E.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await D.can_movement()
                await D.can_movement({'Lifter': 1})

        return r

    async def move_08_09(self):  # 'E -> F'

        E = self.get_machine_head_by_letter('E')
        F = self.get_machine_head_by_letter('F')

        # ~ await F.wait_for_status(F.dispense_position_available)
        r = await F.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=False)
        if r:
            await E.can_movement({'Dispensing_Roller': 1})
            await F.can_movement({'Dispensing_Roller': 2})
            # ~ await F.wait_for_status(F.dispense_position_busy)
            r = await F.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await E.can_movement()

        return r

    async def move_09_10(self):  # 'F -> DOWN'

        F = self.get_machine_head_by_letter('F')

        # ~ await F.wait_for_status(F.unload_lifter_available)
        r = await F.wait_for_jar_photocells_status('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', on=False)
        if r:
            # ~ await F.wait_for_status(F.unload_lifter_down)
            r = await F.wait_for_jar_photocells_status('UNLOAD_LIFTER_DOWN_PHOTOCELL', on=True)
            if r:
                await F.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 5})

        return r

    async def move_10_11(self):  # 'DOWN -> UP'

        F = self.get_machine_head_by_letter('F')

        # ~ await F.wait_for_status(F.unload_lifter_busy)
        r = await F.wait_for_jar_photocells_status('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', on=True)
        if r:
            # ~ await F.wait_for_status(F.unload_lifter_up)
            r = await F.wait_for_jar_photocells_status('UNLOAD_LIFTER_UP_PHOTOCELL', on=True)
            # ~ r = await F.wait_for_status(F.output_roller_available, timeout=1)
            if r:
                r = await F.wait_for_jar_photocells_status('JAR_OUTPUT_ROLLER_PHOTOCELL', on=False, timeout=1)
                if not r:
                    await F.can_movement()
                    await F.can_movement({'Output_Roller': 2})
                    # ~ await F.wait_for_status(F.output_roller_available)
                    r = await F.wait_for_jar_photocells_status('JAR_OUTPUT_ROLLER_PHOTOCELL', on=False)
                    if r:
                        await F.can_movement()
                        await F.can_movement({'Lifter_Roller': 3, 'Output_Roller': 1})

        return r

    async def move_11_12(self):  # 'UP -> OUT'

        F = self.get_machine_head_by_letter('F')

        # ~ await F.wait_for_status(F.output_roller_busy)
        r = await F.wait_for_jar_photocells_status('JAR_OUTPUT_ROLLER_PHOTOCELL', on=True)
        if r:
            await F.can_movement()
            await F.can_movement({'Lifter': 2, 'Output_Roller': 2})
            # ~ await F.wait_for_status(F.output_roller_available)
            r = await F.wait_for_jar_photocells_status('JAR_OUTPUT_ROLLER_PHOTOCELL', on=False)
            if r:
                # ~ await F.wait_for_status(F.unload_lifter_down)
                r = await F.wait_for_jar_photocells_status('UNLOAD_LIFTER_DOWN_PHOTOCELL', on=True)
                if r:
                    await F.can_movement()

        return r

    async def stop_all(self):

        await self.get_machine_head_by_letter('A').can_movement()
        await self.get_machine_head_by_letter('B').can_movement()
        await self.get_machine_head_by_letter('C').can_movement()
        await self.get_machine_head_by_letter('D').can_movement()
        await self.get_machine_head_by_letter('E').can_movement()
        await self.get_machine_head_by_letter('F').can_movement()

    def run_a_coroutine_helper(self, coroutine_name):
        try:
            _coroutine = getattr(self, coroutine_name)
            _future = _coroutine()
            asyncio.ensure_future(_future)
            logging.warning(f"coroutine_name:{coroutine_name}, _future:{_future}")

        except Exception as e:                           # pylint: disable=broad-except
            self.handle_exception(e)


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=settings.LOG_LEVEL, format=fmt_)

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
