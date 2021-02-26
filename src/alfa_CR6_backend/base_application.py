# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines

import os
import time
import logging
import traceback
import asyncio
import json
import codecs

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module
from sqlalchemy.orm.exc import NoResultFound  # pylint: disable=import-error

from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode
from alfa_CR6_backend.globals import (
    UI_PATH,
    KEYBOARD_PATH,
    EPSILON,
    get_version,
    get_encoding,
    tr_)


from alfa_CR6_backend.machine_head import MachineHead


def parse_dat_order(path_to_dat_file):

    def __find_items_in_line(items, l):
        return not [i for i in items if i not in l]

    sw_dat_keys_str = """
    Marca
    Regione
    Codicecolore
    Variante
    Nomecolore
    Secondo-nome
    Anno
    Contrassegno
    Qualità
    Fondo
    Pittogrammi
    Data modifica
    Quantità
    Cumulativo
    """

    sw_dat_keys = [s.strip() for s in sw_dat_keys_str.split('\n')]

    sw_dat_start_line_items = [
        "Tinta Base", "Peso"]
    sw_dat_end_line_items = ["Totale"]

    properties = {
        "meta": {},
        "ingredients": [],
    }
    e = get_encoding(path_to_dat_file)

    with codecs.open(path_to_dat_file, encoding=e) as fd:
        lines = fd.readlines()

    collecting_ingredients = False
    for l in lines[:]:
        toks = l.split(":")
        if collecting_ingredients:
            if __find_items_in_line(sw_dat_end_line_items, l):
                collecting_ingredients = False
            elif l.strip():
                toks = [t.strip() for t in l.split()]
                # ~ logging.warning(f"toks:{toks}")
                if toks:
                    new_item = {}
                    new_item["pigment_name"] = toks[0]
                    new_item["weight(g)"] = round(float(toks[1].replace(",", ".")), 4)
                    new_item["description"] = "" if len(toks) <= 2 else toks[2]
                    properties["ingredients"].append(new_item)
            lines.remove(l)
        elif not collecting_ingredients:
            if __find_items_in_line(sw_dat_start_line_items, l):
                collecting_ingredients = True
                lines.remove(l)
            elif len(toks) == 2:
                k = toks[0].strip()
                v = toks[1].strip()
                if k in sw_dat_keys:
                    properties["meta"][k] = v
                    lines.remove(l)

    properties["meta"]["extra_info"] = [
        l.replace('\n', '').replace('\r', '').replace('\t', '').strip() for l in lines if l.strip()]

    return properties


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


class BaseApplication(QApplication):  # pylint:  disable=too-many-instance-attributes,too-many-public-methods

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {
        0: "A_TOP_LEFT",
        1: "F_BOTM_LEFT",
        2: "B_TOP_CENTER",
        3: "E_BOTM_CENTER",
        4: "C_TOP_RIGHT",
        5: "D_BOTM_RIGHT",
    }
    n_of_active_heads = 0

    def __init__(self, main_window_class, settings, *args, **kwargs):

        logging.debug("settings:{}".format(settings))

        super().__init__(*args, **kwargs)

        self.settings = settings

        self.run_flag = True
        self.ui_path = UI_PATH
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
                self.n_of_active_heads += 1
            else:
                self.machine_head_dict[head_index] = None

    def __close_tasks(self,):

        for m in self.machine_head_dict.values():
            if m:
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

    async def __jar_task(self, barcode):  # pylint: disable=too-many-statements

        r = None
        try:

            cntr = 0
            while cntr < 3:
                cntr += 1
                jar = await self.get_and_check_jar_from_barcode(barcode)
                if not jar:
                    break

                self.__jar_runners[barcode]["jar"] = jar
                json_properties = json.loads(jar.json_properties)
                # ~ unavailable_pigments = json_properties["unavailable_pigments"]
                insufficient_pigments = json_properties["insufficient_pigments"]
                unknown_pigments = json_properties["unknown_pigments"]

                if insufficient_pigments or unknown_pigments:
                    self.main_window.show_barcode(jar.barcode, is_ok=False)
                    msg_ = f"barcode: {barcode}\n"

                    if insufficient_pigments and cntr <= 3:
                        msg_ += tr_("\npigments to be refilled before dispensing:{}. ({}/3)\n").format(
                            list(insufficient_pigments.keys()), cntr)
                    else:
                        cntr = 4

                    if unknown_pigments:
                        msg_ += tr_("\npigments to be added by hand after dispensing:\n{}.").format(
                            list(unknown_pigments.keys()))
                        msg_ += tr_("\nRemember to check the volume.\n")

                    await self.wait_for_carousel_not_frozen(True, msg=msg_)

                else:
                    self.main_window.show_barcode(jar.barcode, is_ok=True)
                    break

            if jar:
                r = await self.execute_carousel_steps(self.n_of_active_heads, jar)
                logging.warning(f"r:{r}")

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

    async def get_and_check_jar_from_barcode(self, barcode):  # pylint: disable=too-many-locals,too-many-branches

        logging.warning("barcode:{}".format(barcode))
        order_nr, index = decompile_barcode(barcode)
        logging.debug("order_nr:{}, index:{}".format(order_nr, index))

        jar = None
        error = None
        try:
            q = self.db_session.query(Jar).filter(Jar.index == index)
            # ~ q = q.filter(Jar.status != "DONE")
            # ~ q = q.filter(~Jar.status.in_(["DONE", "ERROR"]))
            q = q.join(Order).filter((Order.order_nr == order_nr))
            jar = q.one()
        except NoResultFound:
            jar = None
            error = f"NoResultFound looking for barcode:{barcode} (may be already DONE?)"
            logging.error(error)
            logging.error(traceback.format_exc())

        if jar:

            if jar.status in ["DONE", "ERROR"]:
                msg_ = tr_("barcode:{} has status {}.\n").format(barcode, jar.status)
                self.main_window.open_alert_dialog(msg_, title="WARNING")

            A = self.get_machine_head_by_letter("A")
            jar_size = A.jar_size_detect
            package_size_list = []
            for m in [m_ for m_ in self.machine_head_dict.values() if m_]:
                await m.update_tintometer_data(invalidate_cache=True)
                logging.warning(f"{m.name}")

                for s in [p["size"] for p in m.package_list]:
                    if s not in package_size_list:
                        package_size_list.append(s)

            package_size_list.sort()
            logging.warning(f"jar_size:{jar_size}, package_size_list:{package_size_list}")
            jar_volume = 0
            if len(package_size_list) > jar_size:
                jar_volume = package_size_list[jar_size]

            self.update_jar_properties(jar)

            json_properties = json.loads(jar.json_properties)
            total_volume = json_properties["total_volume"]

            if jar_volume < total_volume:
                jar = None
                msg_ = tr_("Jar volume not sufficient for barcode:{}.\nPlease, remove it.\n").format(barcode)
                msg_ += "{}(cc)<{:.3f}(cc).".format(jar_volume, total_volume)
                self.main_window.open_alert_dialog(msg_, title="ERROR")
                logging.error(msg_)
        else:
            jar = None
            msg_ = tr_("barcode:{} not found.\nPlease, remove it.\n").format(barcode)
            self.main_window.open_alert_dialog(msg_, title="ERROR")

        logging.warning(f"jar:{jar}")
        return jar

    async def on_barcode_read(self, barcode):  # pylint: disable=too-many-locals,unused-argument

        if int(barcode) == -1:
            q = self.db_session.query(Jar).filter(~Jar.status.in_(["DONE", "ERROR"]))
            jar = q.first()
            if jar:
                barcode = jar.barcode

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

                if barcode in self.__jar_runners.keys():
                    error = tr_("{} already in progress!").format(barcode)
                    self.main_window.open_alert_dialog(error, title="ERROR")
                    logging.error(error)
                    self.main_window.show_barcode(barcode, is_ok=False)
                else:
                    # let's run a task that will manage the jar through the entire path inside the system
                    t = self.__jar_task(barcode)
                    self.__jar_runners[barcode] = {"task": asyncio.ensure_future(t)}
                    self.main_window.show_barcode(barcode, is_ok=True)
                    logging.warning(" NEW JAR TASK({}) barcode:{}".format(len(self.__jar_runners), barcode))

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

    async def on_head_msg_received(self, head_index, msg_dict):

        if msg_dict.get("type") == "device:machine:status":
            status = msg_dict.get("value")
            status = dict(status)
            self.main_window.update_status_data(head_index, status)

            if head_index == 0:
                if status.get('status_level') == 'ALARM' and status.get('error_code') == 10:
                    for m in self.machine_head_dict.values():
                        if m and m.index != 0:
                            await m.send_command(cmd_name="ABORT", params={})

        elif msg_dict.get("type") == "answer":
            answer = msg_dict.get("value")
            self.main_window.debug_page.add_answer(head_index, answer)

    def get_version(self):

        if not self.__version:
            self.__version = get_version()
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

    def create_order(self, path_to_file=None, json_schema_name="KCC", n_of_jars=0):

        order = None
        if self.db_session:
            try:
                properties = {}
                description = ""
                if path_to_file:
                    split_ext = os.path.splitext(path_to_file)
                    if split_ext[1:] and split_ext[1] == '.json':
                        fname = os.path.split(path_to_file)[1]
                        properties = parse_json_order(path_to_file, json_schema_name)
                    elif split_ext[1:] and split_ext[1] == '.dat':
                        fname = os.path.split(path_to_file)[1]
                        properties = parse_dat_order(path_to_file)
                    else:
                        raise Exception(f"unknown file extension: {ext}")

                    if properties:
                        description = f"{fname}"

                order = Order(
                    json_properties=json.dumps(properties, indent=2),
                    description=description)

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
                        source="crX_Application",
                        description=descr)
                    a.db_session.add(evnt)
                    a.db_session.commit()
                except BaseException:  # pylint: disable=broad-except
                    a.db_session.rollback()
                    logging.error(traceback.format_exc())

    def toggle_freeze_carousel(self):

        self.freeze_carousel(not self.carousel_frozen)

    def freeze_carousel(self, flag):

        if self.carousel_frozen != flag:
            self.carousel_frozen = flag
            if flag:
                logging.error(f"self.carousel_frozen:{self.carousel_frozen}")
                self.main_window.show_carousel_frozen(self.carousel_frozen)
            else:
                logging.warning(f"self.carousel_frozen:{self.carousel_frozen}")
                self.main_window.show_carousel_frozen(self.carousel_frozen)

        if self.main_window.debug_page:
            self.main_window.debug_page.update_status()

    async def stop_all(self):

        await self.get_machine_head_by_letter("A").can_movement()
        await self.get_machine_head_by_letter("B").can_movement()
        await self.get_machine_head_by_letter("C").can_movement()
        await self.get_machine_head_by_letter("D").can_movement()
        await self.get_machine_head_by_letter("E").can_movement()
        await self.get_machine_head_by_letter("F").can_movement()

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

        return {k: j for k, j in self.__jar_runners.items() if j and j.get('jar')}

    async def wait_for_carousel_not_frozen(self, freeze=False, msg=""):  # pylint: disable=too-many-statements

        if freeze and not self.carousel_frozen:
            self.freeze_carousel(True)
            self.main_window.open_frozen_dialog(msg)

        while self.carousel_frozen:
            await asyncio.sleep(0.2)

    def update_jar_properties(self, jar):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        jar_json_properties = json.loads(jar.json_properties)
        order_json_properties = json.loads(jar.order.json_properties)

        order_ingredients = jar_json_properties.get('order_ingredients')
        if order_ingredients is None:
            order_ingredients = order_json_properties.get('ingredients', {})
            jar_json_properties["order_ingredients"] = order_ingredients

        dispensed_quantities_gr = jar_json_properties.get('dispensed_quantities_gr', {})
        visited_head_names = jar_json_properties.get("visited_head_names", [])

        ingredient_volume_map = {}
        insufficient_pigments = {}
        unknown_pigments = {}
        total_volume = 0
        for i in order_ingredients:               # pylint: disable=too-many-nested-blocks
            pigment_name = i["pigment_name"]
            dispensed_quantity_gr = dispensed_quantities_gr.get(pigment_name, 0)
            requested_quantity_gr = float(i["weight(g)"]) - dispensed_quantity_gr

            if requested_quantity_gr < EPSILON:
                continue

            ingredient_volume_map[pigment_name] = {}
            for m in self.machine_head_dict.values():
                if m and m.name not in visited_head_names:
                    specific_weight = m.get_specific_weight(pigment_name)
                    if specific_weight > 0:
                        ingredient_volume_map[pigment_name][m.name] = 0
                        available_gr = m.get_available_weight(pigment_name)
                        if available_gr > EPSILON:
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
                            vol = round(vol, 4)
                            ingredient_volume_map[pigment_name][m.name] = vol
                            total_volume += vol
                            requested_quantity_gr -= _quantity_gr
                            if requested_quantity_gr < EPSILON:
                                break

            if ingredient_volume_map[pigment_name] and requested_quantity_gr > EPSILON:
                # ~ the ingredient is known but not sufficiently available
                insufficient_pigments[pigment_name] = requested_quantity_gr
                ingredient_volume_map[pigment_name] = None
            if ingredient_volume_map[pigment_name] == {}:
                # ~ the ingredient is not known
                unknown_pigments[pigment_name] = requested_quantity_gr

            for k in list(ingredient_volume_map.keys()):
                if not ingredient_volume_map[k]:
                    ingredient_volume_map.pop(k)

        jar_json_properties["ingredient_volume_map"] = ingredient_volume_map
        jar_json_properties["insufficient_pigments"] = insufficient_pigments
        jar_json_properties["unknown_pigments"] = unknown_pigments
        jar_json_properties["total_volume"] = round(total_volume, 4)
        jar.json_properties = json.dumps(jar_json_properties, indent=2)
        self.db_session.commit()

    def update_jar_position(self, jar, machine_head=None, status=None, pos=None):

        if jar is not None:
            m_name = machine_head.name[0] if machine_head else None
            logging.warning(f"jar:{jar}, machine_head:{m_name}, status:{status}, pos:{pos}")
            try:
                for j in self.__jar_runners.values():
                    if j.get("jar"):
                        if pos == j["jar"].position and jar.barcode != j["jar"].barcode:
                            raise Exception(tr_("duplicate {} in jar position list!").format(pos))
                jar.update_live(machine_head=machine_head, status=status, pos=pos, t0=time.time())

                self.db_session.commit()

            except Exception as e:  # pylint: disable=broad-except
                self.handle_exception(e)

    def get_machine_head_by_letter(self, letter):  # pylint: disable=inconsistent-return-statements

        for m in self.machine_head_dict.values():
            if m and m.name[0] == letter:
                return m
