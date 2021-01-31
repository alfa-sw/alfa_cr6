# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines

import sys
import os
import time
import logging
import traceback
import asyncio
import subprocess
import json

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module
from sqlalchemy.orm.exc import NoResultFound  # pylint: disable=import-error

from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode
from alfa_CR6_backend.machine_head import MachineHead
from alfa_CR6_ui.main_window import MainWindow, tr_

HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(HERE, "..", "alfa_CR6_ui", "ui")
IMAGE_PATH = os.path.join(HERE, "..", "alfa_CR6_ui", "images")
KEYBOARD_PATH = os.path.join(HERE, "..", "alfa_CR6_ui", "keyboard")

CONF_PATH = "/opt/alfa_cr6/conf"

EPSILON = 0.00001


def import_settings():
    sys.path.append(CONF_PATH)
    import app_settings  # pylint: disable=import-error,import-outside-toplevel
    sys.path.remove(CONF_PATH)
    return app_settings


def _get_version():

    _ver = None

    try:
        pth = os.path.abspath(os.path.dirname(sys.executable))
        cmd = "{}/pip show alfa_CR6".format(pth)
        for line in (
                subprocess.run(cmd.split(), stdout=subprocess.PIPE, check=True)
                .stdout.decode()
                .split("\n")):
            if "Version" in line:
                _ver = line.split(":")[1]
                _ver = _ver.strip()
    except Exception as exc:  # pylint: disable=broad-except
        logging.error(exc)

    return _ver


def parse_json_order(path_to_json_file, json_schema_name):

    properties = {}
    if json_schema_name == "KCC":

        content = {}
        with open(path_to_json_file) as f:
            content = json.load(f)

        properties["meta"] = {}
        for k in [
                "color to compare",
                "basic information",
                "automobile information",
                "note"]:
            properties["meta"][k] = content.get(k)

        sz = content.get("total", "100")
        sz = "1000" if sz.lower() == "1l" else sz
        properties["size(cc)"] = sz

        properties["ingredients"] = []
        for item in content.get("color information", {}):
            new_item = {}
            new_item["pigment_name"] = item["Color MixingAgen"]
            new_item["description"] = item["Color Mixing Agen Name"]
            new_item["weight(g)"] = item["weight(g)"]
            properties["ingredients"].append(new_item)

    elif json_schema_name == "SW":
        pass

    return properties


class BarCodeReader:  # pylint:  disable=too-many-instance-attributes,too-few-public-methods

    BARCODE_DEVICE_KEY_CODE_MAP = {
        "KEY_SPACE": " ",
        "KEY_1": "1",
        "KEY_2": "2",
        "KEY_3": "3",
        "KEY_4": "4",
        "KEY_5": "5",
        "KEY_6": "6",
        "KEY_7": "7",
        "KEY_8": "8",
        "KEY_9": "9",
        "KEY_0": "0",
    }

    def __init__(self, barcode_handler):

        self.barcode_handler = barcode_handler
        self._device = None

    async def run(self):

        try:
            import evdev  # pylint: disable=import-error, import-outside-toplevel

            app = QApplication.instance()

            buffer = ""
            for path_ in evdev.list_devices():
                device_ = evdev.InputDevice(path_)
                logging.warning(f"device_:{ device_ }")
                if "barcode reader" in str(device_).lower():
                    self._device = device_
                    logging.warning(f"BARCODE DEVICE FOUND. self._device:{ self._device }")
                    break

            if not self._device:
                logging.error(f"****** !!!! BARCODE DEVICE NOT FOUND !!! ******")
            else:
                self._device.grab()  # become the sole recipient of all incoming input events from this device
                async for event in self._device.async_read_loop():
                    keyEvent = evdev.categorize(event)
                    type_key_event = evdev.ecodes.EV_KEY  # pylint:  disable=no-member
                    if event.type == type_key_event and keyEvent.keystate == 0:
                        # key_up = 0
                        if keyEvent.keycode == "KEY_ENTER":
                            buffer = buffer[:12]
                            logging.warning(f"buffer:{buffer}")
                            if self.barcode_handler:
                                await self.barcode_handler(buffer)
                            buffer = ""
                        else:
                            buffer += self.BARCODE_DEVICE_KEY_CODE_MAP.get(
                                keyEvent.keycode, "*"
                            )

        except asyncio.CancelledError:
            pass
        except ImportError:
            logging.warning("cannot import evdev, runinng without barcode reader.")
        except Exception as e:  # pylint: disable=broad-except
            app.handle_exception(e)


class CR6_application(QApplication):  # pylint:  disable=too-many-instance-attributes,too-many-public-methods

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {
        0: "A_TOP_LEFT",
        1: "F_BOTM_LEFT",
        2: "B_TOP_CENTER",
        3: "E_BOTM_CENTER",
        4: "C_TOP_RIGHT",
        5: "D_BOTM_RIGHT",
    }

    def __init__(self, main_window_class, settings, *args, **kwargs):

        logging.debug("settings:{}".format(settings))

        super().__init__(*args, **kwargs)

        self.settings = settings

        self.run_flag = True
        self.ui_path = UI_PATH
        self.images_path = IMAGE_PATH
        self.keyboard_path = KEYBOARD_PATH
        self.db_session = None
        self.ready_to_read_a_barcode = True

        self.__inner_loop_task_step = 0.02  # secs

        self.machine_head_dict = {}

        self.__version = None
        # ~ self.__barcode_device = None
        self.__tasks = []
        self.__runners = []
        self.__jar_runners = {}

        for pth in [self.settings.LOGS_PATH, self.settings.TMP_PATH, self.settings.CONF_PATH]:
            if not os.path.exists(pth):
                os.makedirs(pth)

        if self.settings.SQLITE_CONNECT_STRING:

            from alfa_CR6_backend.models import init_models  # pylint: disable=import-outside-toplevel

            self.db_session = init_models(self.settings.SQLITE_CONNECT_STRING)

        self.__init_tasks()

        self.main_window = main_window_class()
        if hasattr(self.settings, "BYPASS_LOGIN") and self.settings.BYPASS_LOGIN:
            self.main_window.login_clicked()

        self.carousel_frozen = False
        self.main_window.show_carousel_frozen(self.carousel_frozen)

    def __init_tasks(self):

        self.__tasks = [self.__create_inner_loop_task()]

        t = self.__create_barcode_task()
        self.__tasks.append(t)

        for head_index, item in enumerate(self.settings.MACHINE_HEAD_IPADD_PORTS_LIST):
            if item:
                ip_add, ws_port, http_port = item
                t = self.__create_machine_task(head_index, ip_add, ws_port, http_port)
                self.__tasks.append(t)

        # ~ for head_index, status_file_name in self.settings.MACHINE_HEAD_IPADD_PORTS_MAP.items():
        # ~ self.__tasks += [self.__create_machine_mockup_task(head_index, status_file_name), ]

        logging.debug(f"self.__tasks:{self.__tasks}")

    def __close_tasks(self,):

        for m in self.machine_head_dict.values():
            try:
                asyncio.get_event_loop().run_until_complete(m.close())
            except Exception as e:  # pylint: disable=broad-except
                self.handle_exception(e)

        for t in self.__runners[:] + [r["task"] for r in self.__jar_runners.values()]:
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

    async def __create_barcode_task(self):

        b = BarCodeReader(self.on_barcode_read)
        await b.run()
        logging.warning(f" #### terminating barcode reader: {b} #### ")

    async def __create_inner_loop_task(self):
        try:
            while self.run_flag:

                self.processEvents()  # gui events
                self.__clock_tick()  # timer events
                await asyncio.sleep(self.__inner_loop_task_step)

        except asyncio.CancelledError:
            pass
        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

    async def __create_machine_task(self, head_index, ip_add, ws_port, http_port):

        m = MachineHead(
            head_index,
            ip_add,
            ws_port,
            http_port,
            msg_handler=self.on_head_msg_received,
        )
        self.machine_head_dict[head_index] = m
        await m.run()
        logging.warning(f" *** terminating machine: {m} *** ")

    async def __jar_task(self, jar):  # pylint: disable=too-many-statements

        r = None
        try:
            # ~ await self.move_00_01(jar)
            r = await self.move_01_02(jar)
            r = await self.dispense_step(r, "A", jar)
            r = await self.move_02_03(jar)
            r = await self.dispense_step(r, "B", jar)
            r = await self.move_03_04(jar)
            r = await self.dispense_step(r, "C", jar)
            r = await self.move_04_05(jar)
            r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} ++").format('C'))
            r = await self.move_05_06(jar)
            r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} +++").format('C'))
            r = await self.move_06_07(jar)
            r = await self.dispense_step(r, "D", jar)
            r = await self.move_07_08(jar)
            r = await self.dispense_step(r, "E", jar)
            r = await self.move_08_09(jar)
            r = await self.dispense_step(r, "F", jar)
            r = await self.move_09_10(jar)
            r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} ++").format('F'))
            r = await self.move_10_11(jar)
            r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} +++").format('F'))
            r = await self.move_11_12(jar)

            r = await self.wait_for_jar_delivery(jar)

        except asyncio.CancelledError:
            jar.status = "ERROR"
            jar.description = traceback.format_exc()
            logging.error(traceback.format_exc())

        except Exception as e:  # pylint: disable=broad-except

            jar.status = "ERROR"
            jar.description = traceback.format_exc()
            self.handle_exception(e)

    def __clock_tick(self):

        for k in list(self.__jar_runners.keys()):
            j = self.__jar_runners[k]
            task = j["task"]
            if task.done():
                task.cancel()
                logging.warning("deleting:{}".format(j))
                self.__jar_runners.pop(k)

    def check_available_volumes(self, jar):  # pylint: disable=too-many-locals

        ingredient_volume_map = {}
        total_volume = 0
        order_json_properties = json.loads(jar.order.json_properties)
        for i in order_json_properties["ingredients"]:
            pigment_name = i["pigment_name"]
            requested_quantity_gr = float(i["weight(g)"])
            ingredient_volume_map[pigment_name] = {}
            for m in self.machine_head_dict.values():
                available_gr, specific_weight = m.get_available_weight(pigment_name)
                logging.warning(
                    f"{m.name} pigment_name:{pigment_name}, available_gr:{available_gr},"
                    f"requested_quantity_gr:{requested_quantity_gr}")
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

        unavailable_pigment_names = [
            k for k, v in ingredient_volume_map.items() if not v
        ]

        logging.warning(f"unavailable_pigment_names:{unavailable_pigment_names}")

        return ingredient_volume_map, total_volume, unavailable_pigment_names

    async def get_and_check_jar_from_barcode(  # pylint: disable=too-many-locals,too-many-branches
            self, barcode, skip_checks_for_dummy_read=False):

        logging.warning("barcode:{}".format(barcode))
        order_nr, index = decompile_barcode(barcode)
        logging.debug("order_nr:{}, index:{}".format(order_nr, index))

        jar = None
        error = None
        unavailable_pigment_names = []
        try:
            if skip_checks_for_dummy_read:
                q = self.db_session.query(Jar).filter(Jar.status == "NEW")
                jar = q.first()
            else:
                q = self.db_session.query(Jar).filter(Jar.index == index)
                q = q.filter(Jar.status == "NEW")
                q = q.join(Order).filter((Order.order_nr == order_nr))
                jar = q.one()
        except NoResultFound:
            error = f"NoResultFound looking for barcode:{barcode} (is it NEW?)"
            logging.error(traceback.format_exc())

        logging.debug("jar:{}".format(jar))

        if not error:
            if not jar:
                error = f"Jar not found for {barcode}."
            else:
                A = self.get_machine_head_by_letter("A")
                jar_size = A.jar_size_detect
                package_size_list = []
                for m in self.machine_head_dict.values():

                    await m.update_tintometer_data(invalidate_cache=True)
                    logging.warning("{m.name}")

                    for s in [p["size"] for p in m.package_list]:
                        if s not in package_size_list:
                            package_size_list.append(s)

                package_size_list.sort()
                logging.warning(
                    f"jar_size:{jar_size}, package_size_list:{package_size_list}"
                )
                jar_volume = 0
                if len(package_size_list) > jar_size:
                    jar_volume = package_size_list[jar_size]
                ingredient_volume_map, total_volume, unavailable_pigment_names = self.check_available_volumes(
                    jar
                )
                if jar_volume < total_volume:
                    error = tr_(
                        """Jar volume not sufficient for barcode:{}.
                    Please, remove it.
                    {}(cc)<{:.3f}(cc).""").format(
                        barcode, jar_volume, total_volume)

                    jar = None
                # ~ elif unavailable_pigment_names:
                # ~ error = f'Pigments not available for barcode:{barcode}:{unavailable_pigment_names}.'
                # ~ jar = None
                else:
                    json_properties = json.loads(jar.json_properties)
                    json_properties["ingredient_volume_map"] = ingredient_volume_map
                    jar.json_properties = json.dumps(json_properties, indent=2)
                    self.db_session.commit()

                    logging.info(f"jar.json_properties:{jar.json_properties}")

        logging.warning(
            f"jar:{jar}, error:{error}, unavailable_pigment_names:{unavailable_pigment_names}"
        )

        return jar, error, unavailable_pigment_names

    async def on_barcode_read(  # pylint: disable=too-many-locals,unused-argument
            self, barcode, skip_checks_for_dummy_read=False):

        logging.warning(f" ###### barcode:{barcode}")

        if not self.ready_to_read_a_barcode:

            logging.warning(f"not ready to read, skipping barcode:{barcode}")
            self.main_window.show_barcode(f"skipping barcode:{barcode}", is_ok=False)
            return

        try:

            self.main_window.show_barcode(barcode, is_ok=True)

            A = self.get_machine_head_by_letter("A")
            # ~ r = await A.wait_for_jar_photocells_status('JAR_INPUT_ROLLER_PHOTOCELL', on=True)
            r = await A.wait_for_jar_photocells_and_status_lev(
                "JAR_INPUT_ROLLER_PHOTOCELL", on=True, status_levels=["STANDBY"]
            )
            if not r:
                msg_ = tr_("Condition not valid while reading barcode:{}").format(barcode)
                self.main_window.open_alert_dialog(msg_)
                logging.error(msg_)
            else:

                self.ready_to_read_a_barcode = False

                jar, error, unavailable_pigment_names = await self.get_and_check_jar_from_barcode(
                    barcode, skip_checks_for_dummy_read=skip_checks_for_dummy_read
                )

                if not error:
                    if barcode in self.__jar_runners.keys():
                        error = tr_("{} already in progress!"), format(barcode)
                        self.main_window.show_barcode(barcode, is_ok=False)

                if error:
                    self.main_window.open_alert_dialog(error, title="ERROR")
                    logging.error(error)
                elif jar:
                    if unavailable_pigment_names:
                        msg_ = f"Pigments not available for barcode:{barcode}:{unavailable_pigment_names}."
                        self.main_window.open_alert_dialog(msg_)
                        self.main_window.show_barcode(jar.barcode, is_ok=False)

                    # let's run a task that will manage the jar through the entire path inside the system
                    t = self.__jar_task(jar)
                    self.__jar_runners[jar.barcode] = {
                        "task": asyncio.ensure_future(t),
                        "jar": jar,
                    }
                    self.main_window.show_barcode(jar.barcode, is_ok=True)

                    logging.warning(
                        " NEW JAR TASK({}) bc:{} jar:{}, jar.size:{}".format(
                            len(self.__jar_runners), barcode, jar, jar.size
                        )
                    )

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

    async def on_head_msg_received(self, head_index, msg_dict):

        if msg_dict.get("type") == "device:machine:status":
            status = msg_dict.get("value")
            status = dict(status)
            self.main_window.update_status_data(head_index, status)

            # ~ if head_index == 0:
            # ~ self.machine_head_dict[0]
            # ~ if status.get('status_level') == 'ALARM' and status.get('error_code') == 10:
            # ~ for m in self.machine_head_dict.values():
            # ~ if m.index != 0:
            # ~ await m.send_command(cmd_name="ABORT", params={})

        elif msg_dict.get("type") == "answer":
            answer = msg_dict.get("value")
            self.main_window.debug_page.add_answer(head_index, answer)

    def get_machine_head_by_letter(self, letter):  # pylint: disable=inconsistent-return-statements

        for m in self.machine_head_dict.values():
            if m.name[0] == letter:
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

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

        finally:

            self.__close_tasks()

        asyncio.get_event_loop().stop()
        asyncio.get_event_loop().run_until_complete(
            asyncio.get_event_loop().shutdown_asyncgens()
        )
        asyncio.get_event_loop().close()

    def clone_order(self, order_nr, n_of_jars=0):

        cloned_order = None
        if self.db_session:
            try:
                order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).one()
                cloned_order = Order(
                    json_properties=order.json_properties,
                    description=order.description,
                )
                self.db_session.add(cloned_order)
                for j in range(1, n_of_jars + 1):
                    jar = Jar(order=cloned_order, index=j, size=0)
                    self.db_session.add(jar)
                self.db_session.commit()
            except BaseException:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
                order = None
                self.db_session.rollback()

        return cloned_order

    def create_order(self, path_to_json_file=None, json_schema_name="KCC", n_of_jars=0):

        order = None
        if self.db_session:
            try:
                properties = {}
                description = ""
                if path_to_json_file:
                    fname = os.path.split(path_to_json_file)[1]
                    properties = parse_json_order(path_to_json_file, json_schema_name)
                    description = f"{fname}"

                order = Order(
                    json_properties=json.dumps(properties, indent=2),
                    description=description,
                )
                self.db_session.add(order)
                for j in range(1, n_of_jars + 1):
                    jar = Jar(order=order, index=j, size=0)
                    self.db_session.add(jar)
                self.db_session.commit()
            except BaseException:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
                order = None
                self.db_session.rollback()

        return order

    def run_a_coroutine_helper(self, coroutine_name, *args, **kwargs):
        logging.warning(
            f"coroutine_name:{coroutine_name}, args:{args}, kwargs:{kwargs}"
        )
        try:
            _coroutine = getattr(self, coroutine_name)
            _future = _coroutine(*args, **kwargs)
            asyncio.ensure_future(_future)
            logging.warning(f"coroutine_name:{coroutine_name}, _future:{_future}")

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

    def handle_exception(self, e, ui_msg=None, db_event=None):  # pylint:  disable=no-self-use

        if not ui_msg:
            ui_msg = e
        self.main_window.open_alert_dialog(ui_msg, title="ERROR")

        logging.error(traceback.format_exc())

        if db_event is None:
            db_event = self.settings.STORE_EXCEPTIONS_TO_DB_AS_DEFAULT

        if db_event:
            a = QApplication.instance()
            if a and a.db_session:
                try:
                    descr = "{} {}".format(ui_msg, traceback.format_exc())
                    evnt = Event(
                        name=e,
                        level="ERROR",
                        severity="",
                        source="CR6_application",
                        description=descr)
                    a.db_session.add(evnt)
                    a.db_session.commit()
                except BaseException:  # pylint: disable=broad-except
                    a.db_session.rollback()
                    logging.error(traceback.format_exc())

    def toggle_freeze_carousel(self):

        self.freeze_carousel(not self.carousel_frozen)

    def freeze_carousel(self, flag):

        self.carousel_frozen = flag
        if flag:
            logging.error(f"self.carousel_frozen:{self.carousel_frozen}")
            self.main_window.show_carousel_frozen(self.carousel_frozen)
        else:
            logging.warning(f"self.carousel_frozen:{self.carousel_frozen}")
            self.main_window.show_carousel_frozen(self.carousel_frozen)

        if self.main_window.debug_page:
            self.main_window.debug_page.update_status()

    async def wait_for_carousel_not_frozen(self, freeze=False, msg=""):  # pylint: disable=too-many-statements

        if freeze:
            self.freeze_carousel(True)
            self.main_window.open_frozen_dialog(msg)

        if self.carousel_frozen:
            logging.warning(
                f"self.carousel_frozen:{self.carousel_frozen}, start waiting."
            )

        while self.carousel_frozen:
            await asyncio.sleep(0.1)

    async def single_move(self, head_letter, params):

        m = self.get_machine_head_by_letter(head_letter)
        return await m.can_movement(params)

    async def move_00_01(self):  # 'feed'

        A = self.get_machine_head_by_letter("A")

        r = await A.wait_for_jar_photocells_and_status_lev(
            "JAR_INPUT_ROLLER_PHOTOCELL", on=False, status_levels=["STANDBY"], timeout=1
        )
        if r:
            r = await A.wait_for_jar_photocells_and_status_lev(
                "JAR_DISPENSING_POSITION_PHOTOCELL",
                on=False,
                status_levels=["STANDBY"],
                timeout=1,
            )
            if r:
                await A.can_movement({"Input_Roller": 2})
                r = await A.wait_for_jar_photocells_status("JAR_INPUT_ROLLER_PHOTOCELL", on=True, timeout=30)
                if not r:
                    await A.can_movement()
        else:
            logging.warning("A JAR_INPUT_ROLLER_PHOTOCELL is busy, nothing to do.")

        return r

    async def move_01_02(self, jar=None):  # 'IN -> A'

        A = self.get_machine_head_by_letter("A")

        self.__update_jar_position(jar=jar, machine_head=A, status="ENTERING", pos="IN_A")

        r = await A.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            await A.can_movement({"Input_Roller": 1, "Dispensing_Roller": 2})
            r = await A.wait_for_jar_photocells_status(
                "JAR_DISPENSING_POSITION_PHOTOCELL", on=True)

            self.__update_jar_position(jar=jar, machine_head=A, status="PROGRESS", pos="A")

        return r

    async def move_02_03(self, jar=None):  # 'A -> B'

        A = self.get_machine_head_by_letter("A")
        B = self.get_machine_head_by_letter("B")

        r = await B.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:

            await A.can_movement({"Dispensing_Roller": 1})
            await B.can_movement({"Dispensing_Roller": 2})
            r = await B.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await A.can_movement()
                self.__update_jar_position(jar=jar, machine_head=B, pos="B")

        return r

    async def move_03_04(self, jar=None):  # 'B -> C'

        B = self.get_machine_head_by_letter("B")
        C = self.get_machine_head_by_letter("C")

        def condition():
            flag = not C.jar_photocells_status["JAR_DISPENSING_POSITION_PHOTOCELL"]
            flag = (
                flag and not C.jar_photocells_status["JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"]
            )
            flag = flag and C.status["status_level"] in ["STANDBY"]
            return flag

        logging.warning(f" condition():{condition()}")
        r = await C.wait_for_condition(condition, timeout=60 * 3)
        logging.warning(f" r:{r}")

        if r:
            await B.can_movement({"Dispensing_Roller": 1})
            await C.can_movement({"Dispensing_Roller": 2})
            r = await C.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await B.can_movement()
                self.__update_jar_position(jar=jar, machine_head=C, pos="C")

        return r

    async def move_04_05(self, jar=None):  # 'C -> UP'

        C = self.get_machine_head_by_letter("C")
        D = self.get_machine_head_by_letter("D")

        r = await C.wait_for_jar_photocells_status("JAR_LOAD_LIFTER_ROLLER_PHOTOCELL", on=False)
        if r:
            r = await D.wait_for_jar_photocells_status(
                "LOAD_LIFTER_UP_PHOTOCELL", on=True, timeout=3, show_alert=False)
            if not r:

                r = await D.wait_for_jar_photocells_and_status_lev(
                    "JAR_DISPENSING_POSITION_PHOTOCELL",
                    on=False,
                    status_levels=["STANDBY"],
                )
                if r:
                    await D.can_movement({"Lifter": 1})
                    r = await D.wait_for_jar_photocells_status("LOAD_LIFTER_UP_PHOTOCELL", on=True)
            if r:
                await C.can_movement({"Dispensing_Roller": 1, "Lifter_Roller": 2})
                r = await C.wait_for_jar_photocells_status("JAR_LOAD_LIFTER_ROLLER_PHOTOCELL", on=True)
                self.__update_jar_position(jar=jar, pos="LIFTR_UP")

        return r

    async def move_05_06(self, jar=None):  # 'UP -> DOWN'

        D = self.get_machine_head_by_letter("D")

        r = await D.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            await D.can_movement({"Lifter": 2})
            r = await D.wait_for_jar_photocells_status("LOAD_LIFTER_DOWN_PHOTOCELL", on=True)

            self.__update_jar_position(jar=jar, pos="LIFTR_DOWN")

        return r

    async def move_06_07(self, jar=None):  # 'DOWN -> D'

        C = self.get_machine_head_by_letter("C")
        D = self.get_machine_head_by_letter("D")

        r = await D.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            r = await C.wait_for_status_level(status_levels=["STANDBY"])

            await C.can_movement({"Lifter_Roller": 3})
            await D.can_movement({"Dispensing_Roller": 2})
            r = await D.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await C.can_movement()
                self.__update_jar_position(jar=jar, machine_head=D, pos="D")

        return r

    async def move_07_08(self, jar=None):  # 'D -> E'

        D = self.get_machine_head_by_letter("D")
        E = self.get_machine_head_by_letter("E")

        r = await E.wait_for_jar_photocells_and_status_lev(
            "JAR_DISPENSING_POSITION_PHOTOCELL", on=False, status_levels=["STANDBY"])
        if r:
            r = await D.wait_for_jar_photocells_status(
                "LOAD_LIFTER_UP_PHOTOCELL", on=True, timeout=3, show_alert=False)

            if not r:
                await D.can_movement()
                await D.can_movement({"Dispensing_Roller": 1})
            else:
                await D.can_movement({"Dispensing_Roller": 1})
            await E.can_movement({"Dispensing_Roller": 2})
            r = await E.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
            if r:
                await D.can_movement()
                self.__update_jar_position(jar=jar, machine_head=E, pos="E")

        return r

    async def move_08_09(self, jar=None):  # 'E -> F'

        E = self.get_machine_head_by_letter("E")
        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=False)
        if r:
            r = await F.wait_for_jar_photocells_and_status_lev(
                "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL",
                on=False,
                status_levels=["STANDBY"],
            )
            if r:
                r = await F.wait_for_jar_photocells_status(
                    "UNLOAD_LIFTER_DOWN_PHOTOCELL", on=True, timeout=3, show_alert=False)
                if not r:
                    await F.can_movement({"Lifter": 2})
                    r = await F.wait_for_jar_photocells_and_status_lev(
                        "UNLOAD_LIFTER_DOWN_PHOTOCELL",
                        on=True,
                        status_levels=["STANDBY"],
                    )
                if r:
                    await E.can_movement({"Dispensing_Roller": 1})
                    await F.can_movement({"Dispensing_Roller": 2})
                    r = await F.wait_for_jar_photocells_status("JAR_DISPENSING_POSITION_PHOTOCELL", on=True)
                    if r:
                        await E.can_movement()
                        self.__update_jar_position(jar=jar, machine_head=F, pos="F")

        return r

    async def move_09_10(self, jar=None):  # 'F -> DOWN'  pylint: disable=unused-argument

        F = self.get_machine_head_by_letter("F")
        r = await F.wait_for_jar_photocells_status("JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL", on=False)
        if r:
            r = await F.wait_for_jar_photocells_status("UNLOAD_LIFTER_DOWN_PHOTOCELL", on=True)
            if r:
                await F.can_movement({"Dispensing_Roller": 1, "Lifter_Roller": 5})
            self.__update_jar_position(jar=jar, pos="LIFTL_DOWN")
        return r

    async def move_10_11(self, jar=None):  # 'DOWN -> UP -> OUT'

        F = self.get_machine_head_by_letter("F")
        r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=3, show_alert=False)
        if r:
            r = await F.wait_for_jar_photocells_status("JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL", on=True)
            self.__update_jar_position(jar=jar, machine_head=F, pos="LIFTL_UP")
            if r:
                r = await F.wait_for_jar_photocells_and_status_lev(
                    "UNLOAD_LIFTER_UP_PHOTOCELL", on=True, status_levels=["STANDBY"])
                if r:
                    await F.can_movement({"Output_Roller": 2})
                    r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=False)

                    self.__update_jar_position(jar=jar, machine_head=F, pos="WAIT")

                    if r:
                        await F.can_movement()
                        await F.can_movement({"Lifter_Roller": 3, "Output_Roller": 1})
                        r = await F.wait_for_status_level(status_levels=["STANDBY"])
                    else:
                        raise Exception("JAR_OUTPUT_ROLLER_PHOTOCELL busy timeout")
        else:
            r = await F.wait_for_status_level(status_levels=["STANDBY"])
            self.__update_jar_position(jar=jar, machine_head=F, pos="OUT")

        return r

    async def move_11_12(self, jar=None):  # 'UP -> OUT'

        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_status_level(status_levels=["STANDBY"], timeout=3, show_alert=False)
        if r:
            r = await F.wait_for_jar_photocells_status(
                "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL",
                on=True,
                timeout=3,
                show_alert=False,
            )
            if r:
                r = await F.wait_for_jar_photocells_status(
                    "JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=3, show_alert=False)
                if r:
                    await F.can_movement({"Output_Roller": 2})

                r = await F.wait_for_jar_photocells_and_status_lev(
                    "JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, status_levels=["STANDBY"])
                if r:
                    await F.can_movement({"Lifter_Roller": 3, "Output_Roller": 1})

        self.__update_jar_position(jar=jar, machine_head=None, status="DONE", pos="OUT")

        return r

    async def move_12_00(self, jar=None):  # 'deliver' # pylint: disable=unused-argument

        F = self.get_machine_head_by_letter("F")

        r = await F.wait_for_jar_photocells_and_status_lev(
            "JAR_OUTPUT_ROLLER_PHOTOCELL",
            on=True,
            status_levels=["STANDBY"],
            timeout=3,
            show_alert=False)
        if r:
            F = self.get_machine_head_by_letter("F")
            await F.can_movement({"Output_Roller": 2})
        else:
            msg_ = f"cannot move output roller"
            logging.warning(msg_)
            self.main_window.open_alert_dialog(msg_)

    async def wait_for_jar_delivery(self, jar):

        F = self.get_machine_head_by_letter("F")

        try:
            r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=True, timeout=60, show_alert=True)
            if r:
                r = await F.wait_for_jar_photocells_status("JAR_OUTPUT_ROLLER_PHOTOCELL", on=False, timeout=24 * 60 * 60)

            jar.update_live(pos="_")

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

    async def stop_all(self):

        await self.get_machine_head_by_letter("A").can_movement()
        await self.get_machine_head_by_letter("B").can_movement()
        await self.get_machine_head_by_letter("C").can_movement()
        await self.get_machine_head_by_letter("D").can_movement()
        await self.get_machine_head_by_letter("E").can_movement()
        await self.get_machine_head_by_letter("F").can_movement()

    async def dispense_step(self, r, machine_letter, jar):

        m = self.get_machine_head_by_letter(machine_letter)
        self.main_window.update_status_data(m.index, m.status)

        logging.warning(f"{m.name}")

        await m.update_tintometer_data(invalidate_cache=True)

        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} -").format(machine_letter))
        _, _, unavailable_pigment_names = self.check_available_volumes(jar)

        if unavailable_pigment_names:

            msg_ = tr_('Missing material for barcode {}.\n please refill pigments:{} on head {}.').format(
                jar.barcode, unavailable_pigment_names, machine_letter)

            logging.warning(msg_)
            r = await self.wait_for_carousel_not_frozen(True, msg_)

            await m.update_tintometer_data(invalidate_cache=True)

            ingredient_volume_map, _, _ = self.check_available_volumes(jar)
            json_properties = json.loads(jar.json_properties)
            json_properties["ingredient_volume_map"] = ingredient_volume_map
            jar.json_properties = json.dumps(json_properties, indent=2)

        r = await m.do_dispense(jar)
        r = await self.wait_for_carousel_not_frozen(not r, tr_("position: HEAD {} +").format(machine_letter))

        return r

    def __update_jar_position(self, jar, machine_head=None, status=None, pos=None):

        if jar is not None:
            m_name = machine_head.name[0] if machine_head else None
            logging.warning(f"jar:{jar}, machine_head:{m_name}, status:{status}, pos:{pos}")
            try:
                for j in self.__jar_runners.values():
                    if pos == j["jar"].position and jar.barcode != j["jar"].barcode:
                        raise Exception(tr_("duplicate {} in jar position list!").format(pos))
                jar.update_live(machine_head=machine_head, status=status, pos=pos, t0=time.time())

            except Exception as e:  # pylint: disable=broad-except
                self.handle_exception(e)

    def ask_for_refill(self, head_index):

        name = self.MACHINE_HEAD_INDEX_TO_NAME_MAP[head_index]
        msg = f"freezing carousel for refill of head {name}"
        logging.warning(msg)
        self.main_window.open_alert_dialog(msg, title="INFO")
        self.freeze_carousel(True)

    def show_reserve(self, head_index, flag):
        self.main_window.show_reserve(head_index, flag)

    def delete_jar_runner(self, barcode):

        j = self.__jar_runners.get(barcode)
        if j:
            try:
                t = j["task"]
                t.cancel()

                async def _coro(_):
                    await _
                asyncio.ensure_future(_coro(t))
                self.__jar_runners.pop(barcode)
            except Exception as e:  # pylint: disable=broad-except
                self.handle_exception(e)

    def get_jar_runners(self):

        return self.__jar_runners


def main():

    settings = import_settings()

    logging.basicConfig(
        stream=sys.stdout, level=settings.LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    app = CR6_application(MainWindow, settings, sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
