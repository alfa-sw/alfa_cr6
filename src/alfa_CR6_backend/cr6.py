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

from PyQt5.QtWidgets import QApplication, QMessageBox    # pylint: disable=no-name-in-module

from alfa_CR6_ui.main_window import MainWindow
from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode
from alfa_CR6_backend.machine_head import MachineHead

sys.path.append("/opt/alfa_cr6/conf")
import app_settings as settings             # pylint: disable=import-error,wrong-import-position
sys.path.remove("/opt/alfa_cr6/conf")


HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(HERE, '..', 'alfa_CR6_ui', 'ui')
IMAGE_PATH = os.path.join(HERE, '..', 'alfa_CR6_ui', 'images')
KEYBOARD_PATH = os.path.join(HERE, '..', 'alfa_CR6_ui', 'keyboard')

EPSILON = 0.00001


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

    # TODO implement other parser(s)

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

    def show_alert_dialog(self, msg, modal=False, title="ALERT"):

        ret = False

        if self.alert_msgbox is None:
            self.alert_msgbox = QMessageBox()
            def button_clicked(btn):
                logging.warning(f"btn:{btn}, btn.text():{btn.text()}")
            self.alert_msgbox.buttonClicked.connect(button_clicked)

        self.alert_msgbox.setIcon(QMessageBox.Information)
        self.alert_msgbox.setText(msg)
        self.alert_msgbox.setWindowTitle(title)
        self.alert_msgbox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        self.alert_msgbox.setModal(modal)
        self.alert_msgbox.show()
        # ~ returnValue = self.alert_msgbox.exec()
        # ~ if returnValue == QMessageBox.Ok:
        # ~ ret = True

        return ret

    def show_frozen_dialog(self, msg, modal=False, title="ALERT"):

        ret = False

        if self.frozen_msgbox is None:
            self.frozen_msgbox = QMessageBox()
            def button_clicked(btn):
                logging.warning(f"btn:{btn}, btn.text():{btn.text()}")
                if "ok" in btn.text().lower():
                    self.freeze_carousel(False)
            self.frozen_msgbox.buttonClicked.connect(button_clicked)

        self.frozen_msgbox.setIcon(QMessageBox.Information)
        self.frozen_msgbox.setText(msg)
        self.frozen_msgbox.setWindowTitle(title)
        self.frozen_msgbox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        self.frozen_msgbox.setModal(modal)
        self.frozen_msgbox.show()
        # ~ returnValue = self.frozen_msgbox.exec()
        # ~ if returnValue == QMessageBox.Ok:
        # ~ ret = True

        return ret

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
        self.alert_msgbox = None
        self.frozen_msgbox = None

        self.__inner_loop_task_step = 0.02  # secs
        self.carousel_frozen = False

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

    async def __jar_task(self, jar):                      # pylint: disable=too-many-statements

        try:
            # ~ await self.move_00_01(jar)
            r = await self.move_01_02(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD A -")
            r = await self.get_machine_head_by_letter('A').do_dispense(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD A +")
            r = await self.move_02_03(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD B -")
            r = await self.get_machine_head_by_letter('B').do_dispense(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD B +")
            r = await self.move_03_04(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD C -")
            r = await self.get_machine_head_by_letter('C').do_dispense(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD C +")
            r = await self.move_04_05(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD C ++")
            r = await self.move_05_06(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD C +++")
            r = await self.move_06_07(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD D -")
            r = await self.get_machine_head_by_letter('D').do_dispense(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD D +")
            r = await self.move_07_08(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD E -")
            r = await self.get_machine_head_by_letter('E').do_dispense(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD E +")
            r = await self.move_08_09(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD F -")
            r = await self.get_machine_head_by_letter('F').do_dispense(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD F +")
            r = await self.move_09_10(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD F ++")
            r = await self.move_10_11(jar)
            r = await self.wait_for_carousel_not_frozen(not r, "HEAD F +++")
            r = await self.move_11_12(jar)
            r = jar.update_live(status='DONE', pos='_')

        except asyncio.CancelledError:
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()

        except Exception as e:                           # pylint: disable=broad-except
            jar.status = 'ERROR'
            jar.description = traceback.format_exc()
            self.handle_exception(e)

        logging.warning("delivering jar:{}, r:{}".format(jar, r))
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

    def check_available_volumes(self, jar):                # pylint: disable=too-many-locals

        ingredient_volume_map = {}
        total_volume = 0
        order_json_properties = json.loads(jar.order.json_properties)
        for i in order_json_properties["color information"]:
            pigment_name = i["Color MixingAgen"]
            requested_quantity_gr = float(i["weight(g)"])
            ingredient_volume_map[pigment_name] = {}
            for m in self.machine_head_dict.values():
                available_gr, specific_weight = m.get_available_weight(pigment_name)
                if available_gr >= requested_quantity_gr:
                    _quantity_gr = requested_quantity_gr
                elif available_gr > 0:
                    _quantity_gr = available_gr
                else:
                    continue
                vol = _quantity_gr / specific_weight
                ingredient_volume_map[pigment_name][m.name] = vol
                total_volume += vol
                requested_quantity_gr -= _quantity_gr
                if requested_quantity_gr < EPSILON:
                    break

            if requested_quantity_gr > EPSILON:
                ingredient_volume_map[pigment_name] = None

        return ingredient_volume_map, total_volume

    async def get_and_check_jar_from_barcode(self, barcode, skip_checks_for_dummy_read=False):     # pylint: disable=too-many-locals

        jar = None
        error = None

        logging.warning("barcode:{}".format(barcode))
        order_nr, index = decompile_barcode(barcode)
        logging.debug("order_nr:{}, index:{}".format(order_nr, index))

        if skip_checks_for_dummy_read:
            q = self.db_session.query(Jar).filter(Jar.status == 'NEW')
            jar = q.first()
        else:
            q = self.db_session.query(Jar).filter(Jar.index == index)
            q = q.join(Order).filter((Order.order_nr == order_nr))
            jar = q.one()

        logging.debug("jar:{}".format(jar))

        if not jar:
            error = f'Jar not found for {barcode}.'
        else:
            A = self.get_machine_head_by_letter('A')
            jar_size = A.jar_size_detect
            package_size_list = []
            for m in self.machine_head_dict.values():

                await m.update_tintometer_data()
                logging.debug("")

                for s in [p['size'] for p in m.package_list]:
                    if s not in package_size_list:
                        package_size_list.append(s)

            package_size_list.sort()
            logging.warning(f"jar_size:{jar_size}, package_size_list:{package_size_list}")

            if len(package_size_list) > jar_size:
                jar_volume = package_size_list[jar_size]

            ingredient_volume_map, total_volume = self.check_available_volumes(jar)

            logging.warning(f"jar_volume:{jar_volume}, total_volume:{total_volume:.3f}, ingredient_volume_map:{ingredient_volume_map}")

            unavailable_pigment_names = [k for k, v in ingredient_volume_map.items() if not v]
            if jar_volume < total_volume:
                error = f'Jar volume is not sufficient for barcode:{barcode}. {jar_volume}(cc)<{total_volume}(cc).'
                jar = None
            elif unavailable_pigment_names:
                error = f'Pigments not available for barcode:{barcode}:{unavailable_pigment_names}.'
                jar = None
            else:
                json_properties = json.loads(jar.json_properties)
                json_properties['ingredient_volume_map'] = ingredient_volume_map
                jar.json_properties = json.dumps(json_properties, indent=2)
                self.db_session.commit()

                logging.info(f"jar.json_properties:{jar.json_properties}")

        logging.warning(f"jar:{jar}, error:{error}")

        return jar, error

    async def on_barcode_read(self, dev_index, barcode, skip_checks_for_dummy_read=False):     # pylint: disable=too-many-locals

        try:
            A = self.get_machine_head_by_letter('A')
            r = await A.wait_for_jar_photocells_and_status_lev('JAR_INPUT_ROLLER_PHOTOCELL', on=True, status_levels=['STANDBY'], timeout=1)
            assert r, f"Condition not valid while reading barcode:{barcode}"

            jar, error = await self.get_and_check_jar_from_barcode(barcode, skip_checks_for_dummy_read=skip_checks_for_dummy_read)

            if error:
                # TODO: send error notification to UI
                logging.error(error)
            elif jar:
                # let's run a task that will manage the jar through the entire path inside the system
                t = self.__jar_task(jar)
                self.__jar_runners[barcode] = {'task': asyncio.ensure_future(t), 'jar': jar}

                logging.warning(
                    " ************ {} {} jar:{}, jar.size:{}".format(len(self.__jar_runners), barcode, jar, jar.size))

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

        # ~ r = await C.wait_for_jar_photocells_and_status_lev('JAR_DISPENSING_POSITION_PHOTOCELL', on=False, status_levels=['STANDBY'])
        # ~ r = await C.wait_for_jar_photocells_and_status_lev('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', on=False, status_levels=['STANDBY'])
        def condition():
            flag = not C.jar_photocells_status['JAR_DISPENSING_POSITION_PHOTOCELL']
            flag = flag and not C.jar_photocells_status['JAR_LOAD_LIFTER_ROLLER_PHOTOCELL']
            flag = flag and C.status['status_level'] in ['STANDBY', ]
            return flag

        logging.warning(f" condition():{condition()}")
        r = await C.wait_for_condition(condition, timeout=60*3)
        logging.warning(f" r:{r}")

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

            r = await C.wait_for_status_level(status_levels=['STANDBY'])

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

    def freeze_carousel(self, flag):

        self.carousel_frozen = flag
        if flag:
            logging.error(f"self.carousel_frozen:{self.carousel_frozen}")
        else:
            logging.warning(f"self.carousel_frozen:{self.carousel_frozen}")

        if self.main_window.debug_status_view:
            self.main_window.debug_status_view.update_status()

    async def wait_for_carousel_not_frozen(self, freeze=False, msg=""):                      # pylint: disable=too-many-statements

        if freeze:
            self.freeze_carousel(True)
            _ = f'ALERT: carousel is frozen in {msg}! hit "OK" to unfreeze it'
            r = self.show_frozen_dialog(_)
            logging.error(_)
            if r:
                asyncio.get_event_loop().call_later(1, self.freeze_carousel, False)

        if self.carousel_frozen:
            logging.warning(f"self.carousel_frozen:{self.carousel_frozen}, start waiting.")

        while self.carousel_frozen:
            await asyncio.sleep(.1)


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=settings.LOG_LEVEL, format=fmt_)

    app = CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
