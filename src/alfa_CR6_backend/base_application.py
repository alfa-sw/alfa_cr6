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
import subprocess

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

import websockets      # pylint: disable=import-error

import magic       # pylint: disable=import-error

from flask import Markup  # pylint: disable=import-error

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
from alfa_CR6_frontend.chromium_wrapper import ChromiumWrapper

class OrderParser:

    sikkens_txt_header = 'Octoral Information Services'
    sikkens_pdf_header = 'Anteprima Formula'
    kcc_pdf_header = "KCC Color Navi Formulation"

    @staticmethod
    def parse_sikkens_txt(lines):

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

    @staticmethod
    def parse_kcc_pdf(lines):

        section_separator = "__________________________"
        section = 0
        section_cntr = 0
        meta = {}
        ingredients = []
        extra_info = []
        properties = {}
        for l in lines:

            if not l:
                continue

            if section_separator in l:
                section += 1
                section_cntr = 0
            else:
                if section == 0:
                    toks = [t_ for t_ in [t.strip() for t in l.split(":")] if t_]
                    if len(toks) == 2:
                        meta[toks[0]] = toks[1]
                elif section == 1:
                    if section_cntr % 2 == 0:
                        toks = [t_ for t_ in [t.strip() for t in l.split(":")] if t_]
                        description = toks[0]
                        name = toks[1]
                    else:
                        value = round(float(l.split('(G)')[0]), 4)
                        new_item = {}
                        new_item["pigment_name"] = name
                        new_item["weight(g)"] = value
                        new_item["description"] = description
                        ingredients.append(new_item)
                elif section == 2:
                    extra_info.append(l)
                section_cntr += 1

        meta["extra_info"] = extra_info
        properties = {
            "meta": meta,
            "ingredients": ingredients,
        }

        return properties


    @staticmethod
    def parse_sikkens_pdf(lines):     # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        properties = {}
        section = 0
        offset_value = 0
        section_cntr = 0
        meta = {}
        ingredients = []
        extra_info = []
        formula_type = None
        for l in lines:
            if not l:
                continue
            l = l.strip()
            if section == 0:
                section_cntr += 1
                if "Formula Colore" in l:
                    toks = l.split(":")
                    if toks[1:]:
                        formula_type = toks[1].strip()
                    section = 1
                    section_cntr = 0
                else:
                    if section_cntr > 3:
                        meta[section_cntr - 3] = [t.strip() for t in l.split("   ") if t]
                    else:
                        extra_info.append(l)

            elif section == 1:
                section_cntr += 1
                if "Messaggi" in l:
                    section = 2
                    section_cntr = 0
                    extra_info.append(l)

                elif formula_type:
                    toks = [t.strip() for t in l.split(" ")]
                    if toks[2:]:
                        value_ = toks[-1]
                        if 'cumulativa' in formula_type.lower():
                            value = float(value_) - offset_value
                            offset_value += value
                        else:
                            value = float(value_)
                        new_item = {}
                        new_item["pigment_name"] = toks[0]
                        new_item["weight(g)"] = round(value, 4)
                        new_item["description"] = " ".join([t for t in toks[1:-1] if t])
                        ingredients.append(new_item)
            elif section == 2:
                section_cntr += 1
                extra_info.append(l)

        meta["extra_info"] = ["\t".join([t.strip() for t in l.split("   ") if t]) for l in extra_info]
        properties = {
            "meta": meta,
            "ingredients": ingredients,
        }

        total_lt = float(properties['meta'][1][1].split(' ')[0])
        total_gr = sum([i["weight(g)"] for i in properties['ingredients']])
        if total_gr < total_lt * 800 or total_gr > total_lt * 1200:
            logging.error(f"total_lt:{total_lt}, total_gr:{total_gr}")
            properties = {}

        return properties


    @classmethod
    def parse_pdf_order(cls, path_to_pdf_file, fixed_pitch=5):

        path_to_txt_file = "{0}.txt".format(path_to_pdf_file)

        cmd_ = " ".join(["pdftotext", "-fixed", f"{fixed_pitch}", path_to_pdf_file, path_to_txt_file]).split(' ')
        logging.warning(f"cmd_:{cmd_}")

        subprocess.run(cmd_, check=False)
        e = get_encoding(path_to_txt_file)

        properties = {}

        try:

            with codecs.open(path_to_txt_file, encoding=e) as fd:
                lines = [l.strip() for l in fd.readlines()]

            if cls.sikkens_pdf_header in lines[0]:
                properties = cls.parse_sikkens_pdf(lines)
            elif cls.kcc_pdf_header.split(' ') == [t.strip() for t in lines[0].split(' ') if t]:
                properties = cls.parse_kcc_pdf(lines)


        except Exception:              # pylint: disable=broad-except

            logging.error(f"fmt error in file:{path_to_txt_file}")
            logging.error(traceback.format_exc())

        return properties


    @classmethod
    def parse_txt_order(cls, path_to_dat_file):  # pylint: disable=too-many-locals

        properties = {}
        lines = []

        e = get_encoding(path_to_dat_file)
        with codecs.open(path_to_dat_file, encoding=e) as fd:
            lines = fd.readlines()

        logging.warning(f"cls.sikkens_txt_header:{cls.sikkens_txt_header}, lines[0]:{lines[0]}")
        if cls.sikkens_txt_header in lines[0]:
            logging.warning(" ok ")
            properties = cls.parse_sikkens_txt(lines)

        return properties

    @staticmethod
    def parse_json_order(path_to_json_file):

        properties = {}

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

        return properties

    def parse(self, path_to_file):

        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(path_to_file)
        logging.warning(f"path_to_file:{path_to_file}, mime_type:{mime_type}")

        properties = {}
        if mime_type == 'application/json':
            properties = self.parse_json_order(path_to_file)
        elif mime_type == 'application/pdf':
            for fp in (0, 5):
                logging.warning(f"trying fp:{fp} ...")
                properties = self.parse_pdf_order(path_to_file, fp)
                if properties.get('ingredients'):
                    break
        elif mime_type == 'text/plain':
            properties = self.parse_txt_order(path_to_file)
        else:
            raise Exception(f"unknown mime_type:{mime_type}")

        if properties.get('meta'):
            properties['meta']['file name'] = os.path.split(path_to_file)[1]
        else:
            logging.error(f"path_to_file:{path_to_file}, properties:{properties}")

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


class WsServer:   # pylint: disable=too-many-instance-attributes

    def __init__(self, ws_host, ws_port):

        self.ws_host = ws_host
        self.ws_port = ws_port
        asyncio.ensure_future(websockets.serve(self.new_client_handler, self.ws_host, self.ws_port))

        self.ws_clients = []

        self.__version__ = get_version()

    def _format_to_html(self, type_, msg):

        html_ = ""
        html_ += '<div>'

        logging.debug(f"self:{self} type_:{type_}")
        logging.debug(f" msg:{msg}")

        if "device:machine:status" in type_:
            if isinstance(msg, dict):
                status_list = list(msg.items())
            elif isinstance(msg, list):
                status_list = msg

            for k, v in status_list:

                if k in ('status_level',
                         'cycle_step',
                         'error_code',
                         'error_code',
                         'current_temperature',
                         'circuit_engaged',
                         'container_presence',
                         'error_message',
                         'timestamp',
                         'message_id',
                         'last_update'):
                    html_ += "<b>{}</b>: {}<br/>".format(k, v)

                elif k in ('photocells_status',
                           'jar_photocells_status',
                           'crx_outputs_status'):

                    val_ = int(v)
                    html_ += "<b>{}</b>: {:04b} {:04b} {:04b} | 0x{:04X}<br/>".format(
                        k, 0xF & (val_ >> 8), 0xF & (val_ >> 4), 0xF & (val_ >> 0), val_)

                else:
                    continue
        elif type_ == "live_can_list" and isinstance(msg, list):
            for i in msg:
                # ~ html_ += "<tr><td>{}</td></tr>".format(i)
                html_ += "{}<br/>".format(i)

        # ~ html_ += "</table>"
        html_ += "</div>"

        return Markup(html_)

    async def broadcast_msg(self, type_, msg):

        if self.ws_clients:
            message = json.dumps({
                'type': type_,
                'value': self._format_to_html(type_, msg),
                'server_time': "{} - ver.:{} - paused: {}.".format(
                    time.strftime("%Y-%m-%d %H:%M:%S (%Z)"),
                    self.__version__, QApplication.instance().carousel_frozen),
            })
            # ~ logging.warning("message:{}.".format(message))

            for client in self.ws_clients:
                await client.send(message)

        return True

    async def __refresh_client_info(self):

        try:

            for m in QApplication.instance().machine_head_dict.values():
                if m:
                    await self.broadcast_msg(f'device:machine:status_{m.index}', dict(m.status))

            live_can_list = [
                f"{k} ({j['jar'].position[0]}) {j['jar'].status}" for k, j in
                QApplication.instance().get_jar_runners().items() if
                j and j.get('jar') and j['jar'].position]

            await self.broadcast_msg("live_can_list", live_can_list)

        except BaseException:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def new_client_handler(self, websocket, path):
        try:
            logging.warning("appending websocket:{}, path:{}.".format(websocket, path))
            self.ws_clients.append(websocket)

            await self.__refresh_client_info()

            async for message in websocket:  # start listening for messages from ws client
                await self.__handle_client_msg(websocket, message)

        except BaseException:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
        finally:
            logging.warning("removing websocket:{}, path:{}.".format(websocket, path))
            self.ws_clients.remove(websocket)

    async def __handle_client_msg(self, websocket, msg):
        logging.warning("websocket:{}, msg:{}.".format(websocket, msg))
        try:
            msg_dict = json.loads(msg)  # TODO: implement message handler
            logging.debug(f"msg_dict:{msg_dict}")
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())


class BaseApplication(QApplication):  # pylint:  disable=too-many-instance-attributes,too-many-public-methods

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {
        0: "A",
        1: "F",
        2: "B",
        3: "E",
        4: "C",
        5: "D", }

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
        self.ws_server = None

        self.__version = None
        # ~ self.__barcode_device = None
        self.__tasks = []
        self.__runners = []
        self.__jar_runners = {}

        self.chromium_wrapper = None

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

        if hasattr(self.settings, 'CHROMIUM_WRAPPER') and self.settings.CHROMIUM_WRAPPER:
            t = self.__create_chromium_wrapper_task()
            self.__tasks.append(t)

        t = self.__create_barcode_task()
        self.__tasks.append(t)

        t = self.__create_ws_server_task('0.0.0.0', 13000)
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

    async def __create_chromium_wrapper_task(self):

        chromium_exe = self.settings.CHROMIUM_EXE
        path_to_extension_kb = self.settings.PATH_TO_EXTENSION_KB
        url_ = self.settings.WEBENGINE_CUSTOMER_URL

        self.chromium_wrapper = ChromiumWrapper()

        await self.chromium_wrapper.start(
            # ~ window_name="Sherwin-Williams",
            # ~ window_name="chromium",
            url=url_, opts='', chromium_exe=chromium_exe, path_to_extension_kb=path_to_extension_kb)

        while True:
            try:

                if self.chromium_wrapper.process.returncode is not None:
                    await self.chromium_wrapper.start(
                        url=url_, opts='', chromium_exe=chromium_exe, path_to_extension_kb=path_to_extension_kb)

                await asyncio.sleep(5.0)
            except Exception:                # pylint: disable=broad-except
                logging.error(traceback.format_exc())

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
            msg_handler=self.on_head_msg_received)

        self.machine_head_dict[head_index] = m
        await m.run()
        logging.warning(f" *** terminating machine: {m} *** ")

    async def __create_ws_server_task(self, ws_server_addr, ws_server_port):

        self.ws_server = WsServer(ws_server_addr, ws_server_port)

    async def __jar_task(self, barcode):  # pylint: disable=too-many-statements

        r = None
        jar = None
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
            if jar:
                jar.status = "ERROR"
                # ~ jar.description = traceback.format_exc()
            logging.error(traceback.format_exc())
        except Exception as e:  # pylint: disable=broad-except
            if jar:
                jar.status = "ERROR"
                jar.description = traceback.format_exc()
            self.handle_exception(e)
            logging.error(traceback.format_exc())

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
            remaining_volume = json_properties["remaining_volume"]

            if jar_volume < remaining_volume:
                jar = None
                msg_ = tr_("Jar volume not sufficient for barcode:{}.\nPlease, remove it.\n").format(barcode)
                msg_ += "{}(cc)<{:.3f}(cc).".format(jar_volume, remaining_volume)
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
            q = self.db_session.query(Jar).filter(Jar.status.in_(["NEW"]))
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

        if msg_dict.get("type") == "device:machine:status":           # pylint: disable=too-many-nested-blocks
            status = msg_dict.get("value")
            if status is not None:
                status = dict(status)
                self.main_window.update_status_data(head_index, status)

                ret = await self.ws_server.broadcast_msg(f'{msg_dict["type"]}_{head_index}', msg_dict["value"])
                logging.debug("ret:{}".format(ret))

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

    def create_order(self, path_to_file=None, n_of_jars=0):

        order = None
        if self.db_session:
            try:
                properties = {}
                description = ""
                if path_to_file:

                    _parser = OrderParser()
                    properties = _parser.parse(path_to_file)

                    if properties:
                        description = os.path.split(path_to_file)[1]

                order = Order(
                    json_properties=json.dumps(properties, indent=2),
                    description=description)

                self.db_session.add(order)
                for j in range(1, n_of_jars + 1):
                    jar = Jar(order=order, index=j, size=0)
                    self.db_session.add(jar)
                self.db_session.commit()

            except Exception as e:  # pylint: disable=broad-except
                order = None
                self.db_session.rollback()
                self.handle_exception(e)

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
                        source="BaseApplication.handle_exception",
                        description=descr)
                    a.db_session.add(evnt)
                    a.db_session.commit()
                except BaseException:  # pylint: disable=broad-except
                    logging.error(traceback.format_exc())
                    a.db_session.rollback()

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

        t = self.ws_server.broadcast_msg("", None)
        asyncio.ensure_future(t)

    async def stop_all(self):

        for m in self.machine_head_dict.values():
            if m:
                await m.can_movement()

        # ~ await self.get_machine_head_by_letter("A").can_movement()
        # ~ await self.get_machine_head_by_letter("B").can_movement()
        # ~ await self.get_machine_head_by_letter("C").can_movement()
        # ~ await self.get_machine_head_by_letter("D").can_movement()
        # ~ await self.get_machine_head_by_letter("E").can_movement()
        # ~ await self.get_machine_head_by_letter("F").can_movement()

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
        old_insufficient_pigments = jar_json_properties.get("insufficient_pigments", {})

        ingredient_volume_map = {}
        insufficient_pigments = {}
        unknown_pigments = {}
        remaining_volume = 0
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
                            else:
                                _quantity_gr = available_gr
                            vol = _quantity_gr / specific_weight
                            vol = round(vol, 4)
                            ingredient_volume_map[pigment_name][m.name] = vol
                            remaining_volume += vol
                            requested_quantity_gr -= _quantity_gr
                            if requested_quantity_gr < EPSILON:
                                break

            if ingredient_volume_map[pigment_name] and requested_quantity_gr > EPSILON:
                # ~ the ingredient is known but not sufficiently available
                insufficient_pigments[pigment_name] = float(i["weight(g)"]) - dispensed_quantity_gr
                ingredient_volume_map.pop(pigment_name)

            if ingredient_volume_map.get(pigment_name) is not None and not ingredient_volume_map[pigment_name]:
                if old_insufficient_pigments.get(pigment_name):
                    insufficient_pigments[pigment_name] = old_insufficient_pigments[pigment_name]
                else:
                    # ~ the ingredient is not known
                    unknown_pigments[pigment_name] = requested_quantity_gr
                ingredient_volume_map.pop(pigment_name)

        for k in list(ingredient_volume_map.keys()):
            if not ingredient_volume_map[k]:
                ingredient_volume_map.pop(k)

        jar_json_properties["ingredient_volume_map"] = ingredient_volume_map
        jar_json_properties["insufficient_pigments"] = insufficient_pigments
        jar_json_properties["unknown_pigments"] = unknown_pigments
        jar_json_properties["remaining_volume"] = round(remaining_volume, 4)
        jar.json_properties = json.dumps(jar_json_properties, indent=2)
        self.db_session.commit()

    def update_jar_position(self, jar, machine_head=None, status=None, pos=None):

        if jar is not None:
            for m in self.machine_head_dict.values():
                if m:
                    if m == machine_head:
                        if jar.barcode not in m.owned_barcodes:
                            m.owned_barcodes.append(jar.barcode)
                    else:
                        if jar.barcode in m.owned_barcodes:
                            m.owned_barcodes.remove(jar.barcode)

            m_name = machine_head.name[0] if machine_head else None
            logging.warning(f"jar:{jar}, machine_head:{m_name}, status:{status}, pos:{pos}")
            try:
                for j in self.__jar_runners.values():
                    if j.get("jar"):
                        if pos == j["jar"].position and jar.barcode != j["jar"].barcode:
                            raise Exception(tr_("duplicate {} in jar position list!").format(pos))

                if jar.status == "ERROR":
                    status = "ERROR"

                jar.update_live(machine_head=machine_head, status=status, pos=pos, t0=time.time())

                self.db_session.commit()

            except Exception as e:  # pylint: disable=broad-except
                self.handle_exception(e)

            self.main_window.home_page.update_jar_pixmaps()

            live_can_list = [f"{k} ({j['jar'].position[0]}) {j['jar'].status}"
                             for k, j in self.get_jar_runners().items() if j['jar'].position]
            t = self.ws_server.broadcast_msg("live_can_list", live_can_list)
            asyncio.ensure_future(t)

    def get_machine_head_by_letter(self, letter):  # pylint: disable=inconsistent-return-statements

        for m in self.machine_head_dict.values():
            if m and m.name[0] == letter:
                return m
