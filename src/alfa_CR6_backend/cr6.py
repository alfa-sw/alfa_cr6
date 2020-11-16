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

from alfa_CR6_ui.main_window import MainWindow
from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode
from alfa_CR6_backend.machine_head import MachineHead

HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'ui')
IMAGE_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'images')
KEYBOARD_PATH=os.path.join(HERE, '..', 'alfa_CR6_ui', 'keyboard')


sys.path.append("/opt/alfa_cr6/conf")
import settings
sys.path.remove("/opt/alfa_cr6/conf")


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
        self.ui_path = UI_PATH
        self.images_path = IMAGE_PATH
        self.keyboard_path = KEYBOARD_PATH
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

        m = MachineHead(head_index, ip_add, ws_port, http_port, msg_handler=self.on_head_msg_received)
        self.machine_head_dict[head_index] = m
        await m.run()
        logging.warning(f" *** terminating machine: {m} *** ")

    async def __update_machine_head_pipes(self):     # pylint: disable=no-self-use

        try:
            for m in self.machine_head_dict.values():

                # TODO: use cached vals, if present
                await m.update_pipes_and_packages()
        except Exception as e:                           # pylint: disable=broad-except
            self.handle_exception(e)

    async def __jar_task(self, jar):                      # pylint: disable=too-many-statements

        try:
            # ~ await self.move_00_01(jar)
            await self.move_01_02(jar)
            await self.get_machine_head_by_letter('A').do_dispense(jar)
            await self.move_02_03(jar)
            await self.get_machine_head_by_letter('B').do_dispense(jar)
            await self.move_03_04(jar)
            await self.get_machine_head_by_letter('C').do_dispense(jar)
            await self.move_04_05(jar)
            await self.move_05_06(jar)
            await self.move_06_07(jar)
            await self.get_machine_head_by_letter('D').do_dispense(jar)
            await self.move_07_08(jar)
            await self.get_machine_head_by_letter('E').do_dispense(jar)
            await self.move_08_09(jar)
            await self.get_machine_head_by_letter('F').do_dispense(jar)
            await self.move_09_10(jar)
            await self.move_10_11(jar)
            await self.move_11_12(jar)
            jar.update_live(status='DONE', pos='_')

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

            A = self.get_machine_head_by_letter('A')
            r = await A.wait_for_jar_photocells_and_status_lev('JAR_INPUT_ROLLER_PHOTOCELL', on=True, status_levels=['STANDBY'], timeout=1)
            jar_size_detected = A.jar_size_detect

            if skip_checks:
                q = self.db_session.query(Jar).filter(Jar.status == 'NEW')
                jar = q.first()
            else:
                q = self.db_session.query(Jar).filter(Jar.index == index)
                q = q.join(Order).filter((Order.order_nr == order_nr))
                jar = q.one()

            if jar:
                # let's run a task that will manage the jar through the entire path inside the system
                jar.size = jar_size_detected
                t = self.__jar_task(jar)
                self.__jar_runners[barcode] = {'task': asyncio.ensure_future(t), 'jar': jar}

                logging.warning(" ************ {} {} jar:{}, jar.size:{}".format(len(self.__jar_runners), barcode, jar, jar.size))

        except Exception as e:                           # pylint: disable=broad-except
            self.handle_exception(e)

    async def on_head_msg_received(self, head_index, msg_dict):

        if msg_dict.get('type') == 'device:machine:status':
            status = msg_dict.get('value')
            status = dict(status)
            self.main_window.sinottico.update_data(head_index, status)
            self.main_window.debug_status_view.update_status()

        elif msg_dict.get('type') == 'answer':
            answer = msg_dict.get('value')
            self.main_window.debug_status_view.add_answer(head_index, answer)

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

    async def single_move(self, head_letter, params):

        m = self.get_machine_head_by_letter(head_letter)
        return await m.can_movement(params)

    async def move_00_01(self):  # 'feed'

        A = self.get_machine_head_by_letter('A')

        r = await A.wait_for_jar_photocells_and_status_lev('JAR_INPUT_ROLLER_PHOTOCELL', on=False, status_levels=['STANDBY'], timeout=1)
        if r:
            r = await A.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'], timeout=1)
            if r:
                await A.can_movement({'Input_Roller': 2})
                r = await A.wait_for_jar_photocells_status('JAR_INPUT_ROLLER_PHOTOCELL', on=True, timeout=20)
                if not r:
                    await A.can_movement()
        else:
            logging.warning("A JAR_INPUT_ROLLER_PHOTOCELL is busy, nothing to do.")

        return r

    async def move_01_02(self, jar=None):  # 'IN -> A'

        A = self.get_machine_head_by_letter('A')

        if jar is not None:
            jar.update_live(status='PROGRESS', pos='IN_A', t0=time.time())

        r = await A.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'])
        if r:
            await A.can_movement({'Input_Roller': 1, 'Dispensing_Roller': 2})
            r = await A.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)

            if jar is not None:
                jar.update_live(machine_head=A, pos='A')

        return r

    async def move_02_03(self, jar=None):  # 'A -> B'

        A = self.get_machine_head_by_letter('A')
        B = self.get_machine_head_by_letter('B')

        r = await B.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'])
        if r:

            if jar is not None:
                jar.update_live(pos='A_B')

            await A.can_movement({'Dispensing_Roller': 1})
            await B.can_movement({'Dispensing_Roller': 2})
            r = await B.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await A.can_movement()
                if jar is not None:
                    jar.update_live(machine_head=B, pos='B')

        return r

    async def move_03_04(self, jar=None):  # 'B -> C'

        B = self.get_machine_head_by_letter('B')
        C = self.get_machine_head_by_letter('C')

        r = await C.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'])
        if r:

            if jar is not None:
                jar.update_live(pos='B_C')

            await B.can_movement({'Dispensing_Roller': 1})
            await C.can_movement({'Dispensing_Roller': 2})
            r = await C.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await B.can_movement()
                if jar is not None:
                    jar.update_live(machine_head=C, pos='C')

        return r

    async def move_04_05(self, jar=None):  # 'C -> UP'

        C = self.get_machine_head_by_letter('C')
        D = self.get_machine_head_by_letter('D')

        r = await C.wait_for_jar_photocells_status('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', on=False)
        if r:
            r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_UP_PHOTOCELL', on=True, timeout=1)
            if not r:
                r = await D.wait_for_status_level(status_levels=['STANDBY'])
                if r:
                    await D.can_movement({'Lifter': 1})
                    r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_UP_PHOTOCELL', on=True)
            if r:
                if jar is not None:
                    jar.update_live(pos='C_LIFTR')

                await C.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 2})
                r = await C.wait_for_jar_photocells_status('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', on=True)

                if jar is not None:
                    jar.update_live(pos='LIFTR')

        return r

    async def move_05_06(self, jar=None):  # 'UP -> DOWN'

        D = self.get_machine_head_by_letter('D')

        r = await D.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'])
        if r:
            await D.can_movement({'Lifter': 2})
            r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_DOWN_PHOTOCELL', on=True)

            if jar is not None:
                jar.update_live(pos='LIFTR')

        # TODO: remove this delay
        # ~ await asyncio.sleep(1)

        return r

    async def move_06_07(self, jar=None):  # 'DOWN -> D'

        C = self.get_machine_head_by_letter('C')
        D = self.get_machine_head_by_letter('D')

        r = await D.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'])
        if r:

            if jar is not None:
                jar.update_live(pos='LIFTR_D')

            await C.can_movement({'Lifter_Roller': 3})
            await D.can_movement({'Dispensing_Roller': 2})
            r = await D.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await C.can_movement()
                await D.can_movement({'Lifter': 1})

                if jar is not None:
                    jar.update_live(machine_head=D, pos='D')

        return r

    async def move_07_08(self, jar=None):  # 'D -> E'

        D = self.get_machine_head_by_letter('D')
        E = self.get_machine_head_by_letter('E')

        r = await E.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'])
        if r:
            r = await D.wait_for_jar_photocells_status('LOAD_LIFTER_UP_PHOTOCELL', on=True, timeout=1)

            if jar is not None:
                jar.update_live(pos='D_E')

            if not r:
                await D.can_movement()
                await D.can_movement({'Lifter': 1, 'Dispensing_Roller': 1})
            else:
                await D.can_movement({'Dispensing_Roller': 1})
            await E.can_movement({'Dispensing_Roller': 2})
            r = await E.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
            if r:
                await D.can_movement()
                await D.can_movement({'Lifter': 1})

                if jar is not None:
                    jar.update_live(machine_head=E, pos='E')

        return r

    async def move_08_09(self, jar=None):  # 'E -> F'

        E = self.get_machine_head_by_letter('E')
        F = self.get_machine_head_by_letter('F')

        r = await F.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=False)
        if r:
            r = await F.wait_for_jar_photocells_and_status_lev('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', on=False, status_levels=['STANDBY'])
            if r:
                r = await F.wait_for_jar_photocells_status('UNLOAD_LIFTER_DOWN_PHOTOCELL', on=True, timeout=1)
                if not r:
                    await F.can_movement({'Lifter': 2})
                    r = await F.wait_for_jar_photocells_and_status_lev('UNLOAD_LIFTER_DOWN_PHOTOCELL', on=True, status_levels=['STANDBY'])
                if r:

                    if jar is not None:
                        jar.update_live(pos='E_F')

                    await E.can_movement({'Dispensing_Roller': 1})
                    await F.can_movement({'Dispensing_Roller': 2})
                    r = await F.wait_for_jar_photocells_status('JAR_DISPENSING_POSITION_PHOTOCELL', on=True)
                    if r:
                        await E.can_movement()

                        if jar is not None:
                            jar.update_live(machine_head=F, pos='F')

        return r

    async def move_09_10(self, jar=None):  # 'F -> DOWN'

        F = self.get_machine_head_by_letter('F')

        r = await F.wait_for_jar_photocells_status('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', on=False)
        if r:
            r = await F.wait_for_jar_photocells_status('UNLOAD_LIFTER_DOWN_PHOTOCELL', on=True)
            if r:

                if jar is not None:
                    jar.update_live(pos='F_LIFTL')

                await F.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 5})

        return r

    async def move_10_11(self, jar=None):  # 'DOWN -> UP -> OUT'

        F = self.get_machine_head_by_letter('F')

        r = await F.wait_for_jar_photocells_status('JAR_OUTPUT_ROLLER_PHOTOCELL', on=True, timeout=1)
        if r:
            r = await F.wait_for_jar_photocells_status('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', on=True)

            if jar is not None:
                jar.update_live(pos='LIFTL')

            if r:
                r = await F.wait_for_jar_photocells_and_status_lev('UNLOAD_LIFTER_UP_PHOTOCELL', on=True, status_levels=['STANDBY'])
                if r:

                    # TODO: remove this delay
                    # ~ await asyncio.sleep(2)

                    await F.can_movement({'Output_Roller': 2})
                    r = await F.wait_for_jar_photocells_status('JAR_OUTPUT_ROLLER_PHOTOCELL', on=False)
                    if r:

                        if jar is not None:
                            jar.update_live(pos='LIFTL_OUT')

                        await F.can_movement()
                        await F.can_movement({'Lifter_Roller': 3, 'Output_Roller': 1})
                    else:
                        raise Exception('JAR_OUTPUT_ROLLER_PHOTOCELL busy timeout')

                    # ~ r = await F.wait_for_jar_photocells_status('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', on=False)
                    # ~ if r:
                        # ~ r = await F.wait_for_jar_photocells_status('JAR_OUTPUT_ROLLER_PHOTOCELL', on=True)
                        # ~ if r:
                        # ~ await F.can_movement({'Lifter': 2})
        else:
            if jar is not None:
                jar.update_live(pos='F_OUT')

        return r

    async def move_11_12(self, jar=None):  # 'OUT -> OUT'

        if jar is not None:
            jar.update_live(pos='OUT')

    async def stop_all(self):

        await self.get_machine_head_by_letter('A').can_movement()
        await self.get_machine_head_by_letter('B').can_movement()
        await self.get_machine_head_by_letter('C').can_movement()
        await self.get_machine_head_by_letter('D').can_movement()
        await self.get_machine_head_by_letter('E').can_movement()
        await self.get_machine_head_by_letter('F').can_movement()

    def run_a_coroutine_helper(self, coroutine_name, *args, **kwargs):
        try:
            _coroutine = getattr(self, coroutine_name)
            _future = _coroutine(*args, **kwargs)
            asyncio.ensure_future(_future)
            logging.warning(f"coroutine_name:{coroutine_name}, _future:{_future}")

        except Exception as e:                           # pylint: disable=broad-except
            self.handle_exception(e)

    # TODO: remove following methods.
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


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=settings.LOG_LEVEL, format=fmt_)

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
