# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import time
import traceback
import asyncio
import json
import logging
import redis

import logging.handlers

from functools import partial
from collections import OrderedDict

from PyQt5.QtCore import QEventLoop      # pylint: disable=no-name-in-module
from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

from sqlalchemy.orm.exc import NoResultFound  # pylint: disable=import-error

import aiohttp  # pylint: disable=import-error

from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode
from alfa_CR6_backend.globals import (
    UI_PATH,
    KEYBOARD_PATH,
    EPSILON,
    get_version,
    tr_,
    import_settings)

from alfa_CR6_backend.machine_head import MachineHead
from alfa_CR6_backend.order_parser import OrderParser
from alfa_CR6_backend.ws_server import WsServer
from alfa_CR6_frontend.chromium_wrapper import ChromiumWrapper
from alfa_CR6_frontend.dialogs import ModalMessageBox

def get_dict_diff(dict1, dict2):
    set1 = set(dict1.items())
    set2 = set(dict2.items())
    diff = set1 ^ set2
    return diff

async def download_KCC_specific_gravity_lot(force_download=False, force_file_xfert=False): # pylint: disable=too-many-locals

    url_ = "https://kccrefinish.co.kr/file/filedownload/1QZUuT7Q003"
    tmp_file_path_ = "/opt/alfa_cr6/tmp/kcc_lot_specific_info.json"
    ret = False

    _hr = int(time.strftime("%H"))

    _skip_condition = not force_download and os.path.exists(tmp_file_path_)
    _skip_condition = _skip_condition and (_hr > 6 or (
                time.time() - int(os.path.getmtime(tmp_file_path_)) < 12 * 60 * 60))

    logging.warning(f'_hr:{_hr}, _skip_condition:{_skip_condition}')

    if not _skip_condition:

        async with aiohttp.ClientSession() as aiohttp_session:
            try:
                async with aiohttp_session.get(url_) as resp:
                    assert resp.ok, f"failure downloading url_:{url_}"

                    content = await resp.text()
                    with open(tmp_file_path_, 'w', encoding='UTF-8') as f:
                        f.write(content)
                        f.flush()

                    if QApplication.instance():
                        for ip, _, port in [i for i in QApplication.instance().settings.MACHINE_HEAD_IPADD_PORTS_LIST if i]:

                            logging.warning(f"ip:port {ip}:{port}")

                            if not force_file_xfert and ip in ["localhost", "127.0.0.1"]:
                                os.system(f"rsync {tmp_file_path_} /opt/alfa/data/KCC_lot_specific_info.json")
                                ret = True
                                break

                            with open(tmp_file_path_, 'rb') as f:
                                try:
                                    data = aiohttp.FormData()
                                    data.add_field('file', f, filename='kcc_lot_specific_info.json',
                                                   content_type='application/json; charset=utf-8')
                                    async with aiohttp_session.post(f'http://{ip}:{port}/admin/upload', data=data) as resp:
                                        resp_json = await resp.json()
                                        assert resp.ok and resp_json.get('result') == 'ok', f"failure uploading to:{ip}:{port}"
                                    ret = True
                                except Exception as e:  # pylint: disable=broad-except
                                    logging.error(traceback.format_exc())
                                    QApplication.instance().insert_db_event(
                                        name=str(e),
                                        level="ERROR",
                                        severity="",
                                        source="download_KCC_specific_gravity_lot",
                                        description="{} | {}".format(
                                            f"http://{ip}:{port}/admin/upload",
                                            traceback.format_exc()))

                                    QApplication.instance().main_window.open_alert_dialog(
                                        (url_, str(e)), fmt="error downloading file from:{}\n {}.\n", title="ERROR")

            except Exception as e:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())
                if QApplication.instance():

                    QApplication.instance().insert_db_event(
                        name="DOWNLOAD", description=str(e), level="ERROR",
                        severity="", source="download_KCC_specific_gravity_lot")

                    QApplication.instance().main_window.open_alert_dialog(
                        (url_, str(e)), fmt="error downloading file from:{}\n {}.\n", title="ERROR")

    return ret


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class RestoreMachineHelper(metaclass=SingletonMeta):

    def __init__(self, parent=None):
        self.json_file_path = self._json_file_path()
        self._ensure_file_exists()
        self.parent = parent

    @staticmethod
    def _json_file_path():
        _settings = import_settings()
        _path = os.path.join(_settings.DATA_PATH, "running_jars.json")

        return _path

    def _ensure_file_exists(self):
        if not os.path.exists(self.json_file_path):
            with open(self.json_file_path, 'w') as file:
                json.dump({}, file)

    def write_data(self, data):
        with open(self.json_file_path, 'w') as file:
            json.dump(data, file)

    def read_data(self):
        try:
            with open(self.json_file_path, 'r') as file:
                data = json.load(file)
                logging.debug(f'>>> data: {dict(data)}')

                ordine_pos = [
                    "OUT", "LIFTL_UP", "LIFTL_DOWN", "F",
                    "E", "D", "LIFTR_DOWN", "LIFTR_UP",
                    "C", "B", "A", "IN_A", "IN"
                ]
                
                def get_position_index(item):
                    return ordine_pos.index(item[1]["pos"])

                sorted_items = sorted(data.items(), key=get_position_index)
                sorted_data = OrderedDict(sorted_items) 
                
                return sorted_data
        except FileNotFoundError:
            return {}

    def update_jar_data_position(self, jcode, updated_pos):
        jdata = dict(self.read_data())

        if jcode in jdata:
            jdata[jcode]["pos"] = updated_pos

        self.write_data(jdata)

    def store_jar_data(self, jar, pos, dispensation=None):

        logging.warning(f'storing data jar {jar} with pos {pos}')
        if jar:
            new_data = {
                f"{jar.barcode}": {
                    "pos": pos,
                    "jar_status": jar.status,
                    "dispensation": dispensation
                }
            }
            existing_data = self.read_data()
            existing_data.update(new_data)
            self.write_data(existing_data)

    def start_restore_mode(self):
        logging.warning('Check conditions to start restore mode ..')
        return self.read_data()

    async def async_read_data(self):
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(None, self.read_data)
        return data

    async def async_write_data(self, new_data):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.write_data, new_data)

    async def async_remove_completed_jar_data(self, jcode):

        data = await self.async_read_data()

        if jcode not in data:
            logging.error(f'Jar code {jcode} not found in data.')
            return

        logging.warning(f'Removing Recovery data for jar {jcode}')
        del data[jcode]

        await self.async_write_data(data)

    def recovery_task_deletion(self, jcode):
        if not self.parent:
            return
        self.parent.delete_jar_runner(jcode)
        running_tasks = self.read_data()
        if jcode in running_tasks:
            del running_tasks[jcode]
            self.write_data(running_tasks)


class RedisOrderPublisher:
    def __init__(self, redis_url='redis://localhost',ch_name='cr_orders'):
        self.redis_url = redis_url
        self.ch_name=ch_name
        self.redis = None
        asyncio.ensure_future(self._setup_comm())

    async def _setup_comm(self):
        self.redis = redis.from_url(  # pylint: disable=no-member
            "redis://localhost")
        cmd_channel = self.redis.pubsub(ignore_subscribe_messages=True)
        await cmd_channel.subscribe(self.ch_name)
        logging.info(f"Subscribed to channel: {self.ch_name}")

    def publish_messages(self, data_message):
        if not self.redis:
            raise RuntimeError("Redis client is not initialized. Ensure the RedisOrderPublisher is properly set up.")
        message = json.dumps(data_message)
        self.redis.publish(self.ch_name, message)
        logging.warning(f"Channel {self.ch_name} - Published message: {message}")


class BarCodeReader: # pylint: disable=too-many-instance-attributes, too-few-public-methods

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

    BARCODE_LEN = 12

    def __init__(self, barcode_handler, identification_string, exception_handler=None):

        self.barcode_handler = barcode_handler
        self._identification_string = identification_string
        self.exception_handler = exception_handler

        self.last_read_event_time = 0
        self.last_read_event_buffer = '-'

        self._device = None

    def __open_device(self, evdev):

        device_list = [evdev.InputDevice(p) for p in evdev.list_devices()]
        device_list.sort(key=str)
        for device_ in device_list:
            logging.warning(f"device_:{ device_ }")
            s_ = str(device_)

            if self._identification_string in s_:
                self._device = device_
                logging.warning(f"BARCODE DEVICE FOUND. self._device:{ self._device }")
                break

    async def __on_buffer_read(self, buffer):
        ret = None
        if len(buffer) != self.BARCODE_LEN:

            logging.warning(f"format mismatch! buffer:{buffer}")

        else:

            t = time.time()
            logging.debug(f"buffer:{buffer}")

            if self.last_read_event_buffer == buffer and t - self.last_read_event_time < 5.0:
                # filter out reading events with the same value, in the time interval of 5 sec
                pass
            else:
                if self.barcode_handler:
                    try:
                        ret = await self.barcode_handler(buffer)
                        if ret:
                            self.last_read_event_buffer = buffer[:]
                            self.last_read_event_time = t

                    except Exception as e:  # pylint: disable=broad-except
                        if self.exception_handler:
                            self.exception_handler(e)
                        else:
                            logging.error(traceback.format_exc())
        return ret

    async def run(self):

        try:

            import evdev  # pylint: disable=import-error, import-outside-toplevel

            self.__open_device(evdev)

            if not self._device:
                logging.error("****** !!!! BARCODE DEVICE NOT FOUND !!! ******")
            else:

                self._device.grab()  # become the sole recipient of all incoming input events from this device
                self.last_read_event_time = 0
                self.last_read_event_buffer = '-'
                buffer = ""
                async for event in self._device.async_read_loop():
                    keyEvent = evdev.categorize(event)
                    type_key_event = evdev.ecodes.EV_KEY  # pylint:  disable=no-member
                    # ~ logging.warning(f"type_key_event:{type_key_event} ({event.type})")
                    if event.type == type_key_event and keyEvent.keystate == 0:  # key_up = 0
                        if keyEvent.keycode == "KEY_ENTER":
                            buffer = buffer[:self.BARCODE_LEN]
                            await self.__on_buffer_read(buffer)
                            buffer = ""
                        else:
                            filtered_ch_ = self.BARCODE_DEVICE_KEY_CODE_MAP.get(keyEvent.keycode)
                            if filtered_ch_:
                                buffer += filtered_ch_

        except asyncio.CancelledError:
            pass
        except ImportError:
            logging.warning("cannot import evdev, runinng without barcode reader.")
        except Exception as e:  # pylint: disable=broad-except
            if self.exception_handler:
                self.exception_handler(e)
            else:
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

    db_session = None

    def __init__(self, main_window_class, settings, *args, **kwargs):

        logging.debug("settings:{}".format(settings))

        super().__init__(*args, **kwargs)

        self.settings = settings

        self.run_flag = True
        self.ui_path = UI_PATH
        self.keyboard_path = KEYBOARD_PATH
        self.ready_to_read_a_barcode = True

        # ~ self.__inner_loop_task_step = 0.02  # secs

        self.machine_head_dict = {}
        self.ws_server = None

        self.__version = None
        # ~ self.__barcode_device = None
        self.__tasks = []
        self.__runners = []
        self.__jar_runners = {}

        self.__tasks_to_freeze = 0
        self.__modal_freeze_msgbox = None

        self.chromium_wrapper = None
        self.restore_machine_helper = None

        if self.settings.SQLITE_CONNECT_STRING:

            from alfa_CR6_backend.models import init_models  # pylint: disable=import-outside-toplevel

            self.db_session = init_models(self.settings.SQLITE_CONNECT_STRING)

        self.__init_tasks()

        self.main_window = main_window_class()
        if hasattr(self.settings, "BYPASS_LOGIN") and self.settings.BYPASS_LOGIN:
            self.main_window.login_clicked()

        self.carousel_frozen = False
        self.main_window.show_carousel_frozen(self.carousel_frozen)
        self.redis_publisher = RedisOrderPublisher()

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

        t = self._create_restore_machine_helper_task()
        self.__tasks.append(t)

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

    async def _create_restore_machine_helper_task(self):
        try:
            self.restore_machine_helper = RestoreMachineHelper(parent=self)
            if self.restore_machine_helper.start_restore_mode():
                self.main_window.show_carousel_recovery_mode(True)
                self.ready_to_read_a_barcode = False
                self.freeze_carousel(True)
        except Exception:
            logging.error(traceback.print_exc())

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

        while 1:

            _bc_identification_string = os.getenv("BARCODE_READER_IDENTIFICATION_STRING", False)
            if not _bc_identification_string:

                if hasattr(self.settings, "BARCODE_READER_IDENTIFICATION_STRING"):
                    _bc_identification_string = self.settings.BARCODE_READER_IDENTIFICATION_STRING

            if not _bc_identification_string or _bc_identification_string == "DISABLED":
                break

            b = BarCodeReader(self.on_barcode_read, _bc_identification_string, exception_handler=self.handle_exception)
            logging.warning(f" #### created barcode reader: {b} #### ")
            await b.run()
            await asyncio.sleep(10)

        logging.warning(f" #### terminating barcode reader: {b} #### ")

    async def __create_inner_loop_task(self):

        timeout_ms = 100
        last_check_KCC_specific_gravity_lot_time = 0
        try:
            while self.run_flag:

                try:
                    if self.hasPendingEvents():
                        self.processEvents(QEventLoop.AllEvents, timeout_ms)
                        dt = 0
                    else:
                        dt = 0.05
                    await asyncio.sleep(dt)
                except Exception as e:  # pylint: disable=broad-except
                    self.handle_exception(e)

                try:
                    self.__check_jars_to_freeze()
                except Exception as e:  # pylint: disable=broad-except
                    self.handle_exception(e)

                if hasattr(self.settings, "DOWNLOAD_KCC_LOT_STEP") and self.settings.DOWNLOAD_KCC_LOT_STEP:
                    if time.time() - last_check_KCC_specific_gravity_lot_time > self.settings.DOWNLOAD_KCC_LOT_STEP:
                        try:
                            last_check_KCC_specific_gravity_lot_time = time.time()
                            logging.warning(
                                f"last_check_KCC_specific_gravity_lot_time:{last_check_KCC_specific_gravity_lot_time}")
                            asyncio.ensure_future(download_KCC_specific_gravity_lot())

                        except Exception as e:  # pylint: disable=broad-except
                            self.handle_exception(e)

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
            ws_msg_handler=self.on_head_msg_received)

        self.machine_head_dict[head_index] = m
        await m.run()
        logging.warning(f" *** terminating machine: {m} *** ")

    async def __create_ws_server_task(self, ws_server_addr, ws_server_port):

        self.ws_server = WsServer(self, ws_server_addr, ws_server_port)

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
                        fmt_insuff_pigmts = self.build_insufficient_pigments_infos(insufficient_pigments)
                        msg_ += tr_("\npigments to be refilled before dispensing:{}. ({}/3)\n").format(
                            fmt_insuff_pigmts, cntr)
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
                self.__jar_runners[barcode]['frozen'] = False
                r = await self.execute_carousel_steps(self.n_of_active_heads, jar)
                logging.warning(f"r:{r}")

        except asyncio.CancelledError:
            logging.warning(f"cancelled: {barcode}")
        except Exception as e:  # pylint: disable=broad-except
            if jar:
                jar.status = "ERROR"
                jar.description = traceback.format_exc()
                self.db_session.commit()

            self.handle_exception(e)
            logging.error(traceback.format_exc())

    def __check_jars_to_freeze(self):

        _tasks_to_freeze = []
        try:
            for k in list(self.__jar_runners.keys()):
                _runner = self.__jar_runners[k]
                _task = _runner["task"]
                if _task.done():
                    _task.cancel()
                    logging.warning("TASK DONE >> deleting:{}".format(_runner))
                    self.__jar_runners.pop(k)
                    _runner = None

                _flag = self.carousel_frozen
                _flag = _flag and _runner
                _flag = _flag and not _runner.get("frozen")
                _flag = _flag and _runner.get("jar")
                _flag = _flag and _runner["jar"].status and _runner["jar"].position
                _flag = _flag and 'ENTER' not in _runner["jar"].status
                _flag = _flag and 'OUT' not in _runner["jar"].status
                _flag = _flag and 'WAIT' not in _runner["jar"].position
                _flag = _flag and '_' not in _runner["jar"].position
                _flag = _flag and _task not in _tasks_to_freeze
                if _flag:
                    _tasks_to_freeze.append((_task, k))

            n = len(_tasks_to_freeze)
            if self.__tasks_to_freeze != n:
                self.__tasks_to_freeze = n
                # ~ logging.warning(f'__tasks_to_freeze:{self.__tasks_to_freeze}'
                # ~ f', {[(t.get_name(), k) for t, k in _tasks_to_freeze]}')

                if self.__tasks_to_freeze:
                    msg = tr_("please, wait while finishing all pending operations ...")
                    msg += "\n{}".format([k for t, k in _tasks_to_freeze])

                    if not self.__modal_freeze_msgbox:
                        self.__modal_freeze_msgbox = ModalMessageBox(parent=self.main_window, msg=msg, title="ALERT")
                        self.__modal_freeze_msgbox.move(self.__modal_freeze_msgbox.geometry().x(), 20)
                    else:
                        self.__modal_freeze_msgbox.setText(f"\n\n{msg}\n\n")
                        self.__modal_freeze_msgbox.show()
                    self.__modal_freeze_msgbox.enable_buttons(False, False)

                    asyncio.get_event_loop().call_later(10, partial(self.__modal_freeze_msgbox.enable_buttons, False, True))

                else:
                    if self.__modal_freeze_msgbox:
                        msg = "\n\n{}\n\n".format(tr_("all operations are paused"))
                        self.__modal_freeze_msgbox.setText(msg)
                logging.warning(
                    f'self.__modal_freeze_msgbox:{self.__modal_freeze_msgbox}, __tasks_to_freeze:{self.__tasks_to_freeze}')

        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)
            logging.error(traceback.format_exc())

        finally:
            if not _tasks_to_freeze and self.__modal_freeze_msgbox:
                self.__modal_freeze_msgbox.enable_buttons(True, True)
                self.__modal_freeze_msgbox.close()

    async def get_and_check_jar_from_barcode(self, barcode):  # pylint: disable=too-many-locals,too-many-branches

        logging.debug("barcode:{}".format(barcode))
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

            A = self.get_machine_head_by_letter("A")
            jar_size = await A.get_stabilized_jar_size()
            if jar_size is None:
                jar = None
                args, fmt = (barcode, ), "barcode:{} cannot read can size from microswitches.\n"
                self.main_window.open_alert_dialog(args, fmt=fmt, title="ERROR")
            else:

                if jar.status in ["DONE", "ERROR"]:
                    args, fmt = (barcode, tr_(jar.status)), "barcode:{} has status {}.\n"
                    self.main_window.open_alert_dialog(args, fmt=fmt, title="WARNING")

                package_size_list = []
                for m in [m_ for m_ in self.machine_head_dict.values() if m_]:
                    await m.update_tintometer_data()
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
                start_ingredient_volume_map = json_properties["start_ingredient_volume_map"]
                insufficient_pigments_map = json_properties["insufficient_pigments"]
                ingredients_total_vol = self.retrive_formula_total_vol(
                    start_ingredient_volume_map, insufficient_pigments_map)

                verified = False

                if jar_volume < ingredients_total_vol:
                    jar = None
                    msg_ = tr_("Jar volume not sufficient for barcode:{}.\nPlease, remove it.\n").format(barcode)
                    msg_ += tr_("Jar volume {}(cc) < Order volume {:.3f}(cc).").format(jar_volume, ingredients_total_vol)
                    self.main_window.open_alert_dialog(msg_, title="ERROR")
                    logging.error(msg_)
                    verified = True

                if not verified and jar_volume < remaining_volume:
                    jar = None
                    msg_ = tr_("Jar volume not sufficient for barcode:{}.\nPlease, remove it.\n").format(barcode)
                    msg_ += "{}(cc)<{:.3f}(cc).".format(jar_volume, remaining_volume)
                    self.main_window.open_alert_dialog(msg_, title="ERROR")
                    logging.error(msg_)

        else:
            jar = None
            args, fmt = (barcode, ), "barcode:{} not found.\nPlease, remove it.\n"
            self.main_window.open_alert_dialog(args, fmt=fmt, title="WARNING")

        logging.warning(f"jar:{jar}")
        return jar

    async def on_barcode_read(self, barcode):  # pylint: disable=too-many-locals

        ret = None
        barcode = str(barcode)
        # ~ logging.warning(f" ###### barcode({type(barcode)}):{barcode}")

        if not barcode or not self.ready_to_read_a_barcode:

            logging.debug(f"skipping barcode:{barcode}")
            self.main_window.show_barcode(tr_("skipping barcode:{}").format(barcode), is_ok=False)

        else:

            try:

                self.main_window.show_barcode(barcode, is_ok=True)

                A = self.get_machine_head_by_letter("A")
                # ~ r = await A.wait_for_jar_photocells_status('JAR_INPUT_ROLLER_PHOTOCELL', on=True)
                r = await A.wait_for_jar_photocells_and_status_lev(
                    "JAR_INPUT_ROLLER_PHOTOCELL", on=True,
                    status_levels=["STANDBY"], show_alert=False
                )
                if not r:
                    args, fmt = (barcode, ), "Condition not valid while reading barcode:{}"
                    self.main_window.open_alert_dialog(args, fmt=fmt)
                    logging.error(fmt.format(*args))
                else:

                    self.ready_to_read_a_barcode = False

                    if barcode in self.__jar_runners:
                        args, fmt = (barcode, ), "{} already in progress!"
                        self.main_window.open_alert_dialog(args, fmt=fmt, title="ERROR")
                        self.main_window.show_barcode(barcode, is_ok=False)
                    else:

                        if self.carousel_frozen:
                            logging.warning(f'carousel is frozen({self.carousel_frozen}) - returning from on_barcode_read ..')
                            return

                        # let's run a task that will manage the jar through the entire path inside the system
                        t = self.__jar_task(barcode)
                        self.__jar_runners[barcode] = {
                            "task": asyncio.ensure_future(t),
                            "frozen": True
                        }

                        self.main_window.show_barcode(barcode, is_ok=True)
                        logging.warning(" NEW JAR TASK({}) barcode:{}".format(len(self.__jar_runners), barcode))
                        ret = barcode
            except Exception as e:  # pylint: disable=broad-except
                self.handle_exception(e)

        return ret

    async def on_head_msg_received(self, head_index, msg_dict):

        if msg_dict.get("type") == "device:machine:status":           # pylint: disable=too-many-nested-blocks
            status = msg_dict.get("value")
            if status is not None:
                status = dict(status)
                self.main_window.update_status_data(head_index, status)

                ret = await self.ws_server.broadcast_msg(f'{msg_dict["type"]}_{head_index}', msg_dict["value"])
                logging.debug("ret:{}".format(ret))
                self.ws_server.refresh_can_list()

                # ~ if head_index == 0:
                    # ~ if status.get('status_level') == 'ALARM' and status.get('error_code') == 10:
                        # ~ for m in self.machine_head_dict.values():
                            # ~ if m and m.index != 0:
                                # ~ await m.send_command(cmd_name="ABORT", params={})

        elif msg_dict.get("type") == "answer":
            answer = msg_dict.get("value")
            self.main_window.debug_page.add_answer(head_index, answer)

        elif msg_dict.get("type") == "expired_products":
            self.main_window.home_page.update_expired_products(head_index)

    def get_version(self):

        if not self.__version:
            self.__version = get_version()
        return self.__version

    def run_forever(self):

        QApplication.instance().insert_db_event(
            name='START',
            level="INFO",
            severity='',
            source="BaseApplication.run_forever",
            description=tr_("started application"))

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

    def do_fill_unknown_pigment_list(self, order):

        _properties = json.loads(order.json_properties)

        _available_pigments = self.get_available_pigments()
        _available_pigment_names = list(_available_pigments.keys())
        _unknown_pigments = {}
        for _item in _properties.get("ingredients", []):
            pigment_name = _item.get("pigment_name")
            weight = _item.get("weight(g)")
            if pigment_name not in _available_pigment_names and pigment_name and weight:
                _unknown_pigments[pigment_name] = float(weight)
        _properties["unknown_pigments"] = _unknown_pigments

        order.json_properties = json.dumps(_properties, indent=2)

        # ~ logging.warning(f"order.json_properties:{order.json_properties}")

    def _do_create_order( # pylint: disable=too-many-arguments
        self, properties, description, n_of_jars, file_name=None, silent=False):

        order = None
        if self.db_session:
            try:

                name_list = [i["pigment_name"] for i in properties.get('ingredients', [])]
                assert len(name_list) == len(set(name_list)), tr_("duplicated name in ingredient list")

                try:
                    order = Order(
                        json_properties=json.dumps(properties, indent=2),
                        description=description, file_name=file_name)

                    if order:
                        self.do_fill_unknown_pigment_list(order)

                        self.db_session.add(order)
                        for j in range(1, n_of_jars + 1):
                            jar = Jar(order=order, index=j, size=0)
                            self.db_session.add(jar)
                        self.db_session.commit()

                except Exception as e:  # pylint: disable=broad-except
                    order = None
                    self.db_session.rollback()
                    if silent:
                        logging.error(traceback.format_exc())
                    else:
                        self.handle_exception(e)

            except Exception as e:  # pylint: disable=broad-except
                order = None
                self.db_session.rollback()
                if silent:
                    logging.error(traceback.format_exc())
                else:
                    self.handle_exception(e)

        return order

    def clone_order(self, order_nr, n_of_jars=0):

        cloned_order = None

        try:
            order = QApplication.instance().db_session.query(Order).filter(Order.order_nr == order_nr).one()
            properties = json.loads(order.json_properties)
            cloned_order = self._do_create_order(properties, order.description, n_of_jars)
        except Exception as e:  # pylint: disable=broad-except
            self.handle_exception(e)

        return cloned_order

    def create_new_order(self, n_of_jars=0):

        return self._do_create_order({}, "", n_of_jars)

    def create_orders_from_file(self, path_to_file=None, n_of_jars=0, silent=False):

        order_list = []
        try:

            _parser = OrderParser(exception_handler=self.handle_exception)
            # ~ properties = _parser.parse(path_to_file)
            # ~ properties_list = properties if isinstance(properties, list) else [properties, ]
            properties_list = _parser.parse(path_to_file)

            for properties in properties_list:
                description = ""
                if properties.get('batchId'):
                    description = properties['batchId']

                file_name = properties.get("meta", {}).get("file name")

                if not properties['meta'].get('error'):
                    order = self._do_create_order(properties, description, n_of_jars, file_name=file_name, silent=silent)
                    order_list.append(order)

        except Exception as e:  # pylint: disable=broad-except
            if silent:
                logging.error(traceback.format_exc())
            else:
                self.handle_exception(e)

        logging.warning(f"path_to_file:{path_to_file}, n_of_jars:{n_of_jars}, order_list:{order_list}.")

        return order_list

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

    # ~ def insert_db_event(self, name="", level="ERROR", severity="", source="", description=""):   # pylint: disable=too-many-arguments
    def insert_db_event(self, **args):

        try:
            evt = Event(**args)
            self.db_session.add(evt)
            self.db_session.commit()
        except BaseException:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.db_session.rollback()

    def handle_exception(self, e):  # pylint:  disable=no-self-use

        if "CancelledError" in traceback.format_exc():
            logging.warning(traceback.format_exc())
            raise  # pylint:  disable=misplaced-bare-raise

        self.main_window.open_alert_dialog(f"{e}", title="ERROR", visibility=0)
        logging.error(traceback.format_exc())

    def toggle_freeze_carousel(self):

        self.freeze_carousel(not self.carousel_frozen)

    def close_modal_freeze_msgbox(self):

        if self.__modal_freeze_msgbox:
            self.__modal_freeze_msgbox.close()

    def freeze_carousel(self, flag):

        if self.carousel_frozen != flag:
            self.carousel_frozen = flag
            if flag:
                logging.error(f"self.carousel_frozen:{self.carousel_frozen}")
                self.main_window.show_carousel_frozen(self.carousel_frozen)
            else:
                logging.warning(f"self.carousel_frozen:{self.carousel_frozen}")
                self.main_window.show_carousel_frozen(self.carousel_frozen)

        if not self.carousel_frozen and self.__modal_freeze_msgbox:
            self.__modal_freeze_msgbox.enable_buttons(True, True)
            self.__modal_freeze_msgbox.close()

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

        args, fmt = (name, ), "freezing carousel for refill of head {}"
        self.main_window.open_alert_dialog(args, fmt=fmt, title="INFO")
        logging.warning(fmt.format(*args))

        self.freeze_carousel(True)

    def show_reserve(self, head_index, flag):
        self.main_window.show_reserve(head_index, flag)

    def _del_entering_jar(self, entering_jar, kode):

        logging.warning(f'kode --> {kode}')
        if entering_jar.get('jar') and entering_jar["jar"].status not in ["ERROR", "DONE"]:
            logging.warning(f'CHANGING STATUS OF JAF {kode}')
            entering_jar["jar"].status = "NEW"
            entering_jar["jar"].position = "_"
            entering_jar["jar"].machine_head = None
            self.db_session.commit()

        entering_jar_order = entering_jar["jar"].order
        if entering_jar_order:
            logging.warning(f'entering_jar_order status: {entering_jar_order.status}')
            order_updated_status = entering_jar_order.update_status(self.db_session)
            logging.warning(f'updated entering_jar_order status: {order_updated_status}')

        logging.warning(f'cancelling:{entering_jar["task"]}')
        r = entering_jar["task"].cancel()
        logging.warning(f"cancelled. r:{r}")

        logging.warning(f"deleting:{entering_jar}")
        del entering_jar
        logging.warning(f"deleted:{kode}")

        self.ws_server.refresh_can_list()

    def delete_entering_jar(self):

        logging.warning(' *** ')

        try:

            for k in list(self.__jar_runners.keys()):

                j = self.__jar_runners[k]

                logging.warning(f'iscurrent:{j["task"] is asyncio.current_task()}, k:{k}, status:{j["jar"].status}, position:{j["jar"].position}.')

                if j["jar"].position in ["IN", "IN_A", "A"]:
                    self._del_entering_jar(j, k)
                    continue

        except Exception as e:  # pylint: disable=broad-except

            self.handle_exception(e)

    def delete_jar_runner(self, barcode):

        try:

            barcode = str(barcode)

            if self.__jar_runners.get(barcode):

                j = self.__jar_runners.pop(barcode)

                j["jar"].status = "ERROR"
                j["jar"].position = "REMOVED"
                j["jar"].machine_head = None
                self.db_session.commit()

                logging.warning(f'cancelling:{j["task"]}')
                r = j["task"].cancel()
                logging.warning(f"cancelled. r:{r}")

                logging.warning(f"deleting:{j}")
                del j
                logging.warning(f"deleted:{barcode}")

                self.ws_server.refresh_can_list()

        except Exception as e:  # pylint: disable=broad-except

            self.handle_exception(e)

    def get_jar_runners(self):

        return {k: j for k, j in self.__jar_runners.items() if j and j.get('jar')}

    async def wait_for_carousel_not_frozen(
            self, freeze=False, msg="", visibility=1,
            show_cancel_btn=True
    ):  # pylint: disable=too-many-statements

        if freeze and not self.carousel_frozen:
            self.freeze_carousel(True)
            self.main_window.open_frozen_dialog(
                msg, visibility=visibility, show_cancel_btn=show_cancel_btn
            )

        _runner = None
        if self.carousel_frozen:
            _t = asyncio.current_task()
            for v in self.__jar_runners.values():
                if _t is v.get('task'):
                    _runner = v
                    _runner['frozen'] = True
                    break

        while self.carousel_frozen:
            await asyncio.sleep(0.2)

        if _runner:
            _runner['frozen'] = False

    def update_jar_properties(self, jar, dispense_not_successful=False):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        jar_json_properties = json.loads(jar.json_properties)
        order_json_properties = json.loads(jar.order.json_properties)

        order_ingredients = jar_json_properties.get('order_ingredients')
        if order_ingredients is None:
            order_ingredients = order_json_properties.get('ingredients', [])
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

            requested_quantity_gr, remaining_volume = self._build_ingredient_volume_map_helper(
                ingredient_volume_map, visited_head_names, pigment_name,
                requested_quantity_gr, remaining_volume, dispense_not_successful)

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

        if jar_json_properties.get("start_ingredient_volume_map") is None:
            jar_json_properties["start_ingredient_volume_map"] = ingredient_volume_map

        jar_json_properties["ingredient_volume_map"] = ingredient_volume_map
        jar_json_properties["insufficient_pigments"] = insufficient_pigments
        jar_json_properties["unknown_pigments"] = unknown_pigments
        jar_json_properties["remaining_volume"] = round(remaining_volume, 4)
        jar.json_properties = json.dumps(jar_json_properties, indent=2)

        d1 = order_json_properties.get("unknown_pigments", {})
        d2 = jar_json_properties.get("unknown_pigments", {})
        _diff = get_dict_diff(d1, d2)
        if _diff:
            msg = f"{jar.barcode}\n"
            msg += tr_("pigments in machine db have changed, check can label. diff:{}").format(_diff)
            self.main_window.open_alert_dialog(f"{msg}", title="ALERT")

        self.db_session.commit()

    def update_jar_position(self, jar, machine_head=None, status=None, pos=None):

        if jar is not None: # pylint: disable=too-many-nested-blocks
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
                if pos is not None:
                    for j in self.__jar_runners.values():
                        if j.get("jar"):
                            if pos == j["jar"].position and jar.barcode != j["jar"].barcode:
                                raise Exception(tr_("duplicate {} in jar position list!").format(pos))

                if jar.status == "ERROR":
                    status = "ERROR"

                jar.update_live(machine_head=machine_head, status=status, pos=pos, t0=time.time())

                self.db_session.commit()

                if jar.status in {"ERROR", "DONE"}:
                    jar_data = jar.object_to_dict(include_relationship=2)
                    self.redis_publisher.publish_messages(jar_data)

                if hasattr(self.restore_machine_helper, 'store_jar_data'):
                    self.restore_machine_helper.store_jar_data(jar, pos)

            except Exception as e:  # pylint: disable=broad-except
                self.handle_exception(e)

            self.main_window.home_page.update_jar_pixmaps()
            self.ws_server.refresh_can_list()

    def get_machine_head_by_letter(self, letter):

        ret = None
        for m in self.machine_head_dict.values():
            if m and m.name[0] == letter:
                ret = m
                break
        return ret

    def create_purge_all_order(self, ):

        properties = {
            'meta': {
                "extra_info": 'PURGE ALL',
                'file name': tr_("PURGE_ALL"),
            },
            "extra_lines_to_print": [tr_("PURGE ALL"), ],
            "ingredients": [],
        }
        description = "PURGE ALL"
        self._do_create_order(properties, description, n_of_jars=0)
        self.main_window.order_page.populate_order_table()

    def _build_ingredient_volume_map_helper(  # pylint: disable=too-many-arguments
            self, ingredient_volume_map,
            visited_head_names, pigment_name,
            requested_quantity_gr, remaining_volume,
            dispense_not_successful
    ):

        for m in self.machine_head_dict.values():
            # if m and m.name not in visited_head_names:
            if m and (dispense_not_successful or m.name not in visited_head_names):
                specific_weight = m.get_specific_weight(pigment_name)
                if specific_weight > 0:
                    ingredient_volume_map[pigment_name][m.name] = 0
                    available_gr = m.get_available_weight(pigment_name)
                    if available_gr > EPSILON:
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
        return requested_quantity_gr, remaining_volume

    def get_available_pigments(self):

        available_pigments = {}
        for m in self.machine_head_dict.values():
            if m:

                for pig in m.pigment_list:
                    available_pigments[pig["name"]] = pig

        return available_pigments

    @staticmethod
    def update_tintometer_data_on_all_heads():

        for m in QApplication.instance().machine_head_dict.values():
            if m:
                if not m.pigment_list:
                    t = m.update_tintometer_data()
                    asyncio.ensure_future(t)

    def retrive_formula_total_vol(self, start_ingredient_volume_map, insufficient_pigments_map):

        total_volume = 0

        for key in start_ingredient_volume_map:
            for position in start_ingredient_volume_map[key]:
                total_volume += start_ingredient_volume_map[key][position]

        for key, insuff_pigmnt_gr in insufficient_pigments_map.items():
            for m in self.machine_head_dict.values():
                if not m:
                    continue
                if key not in m.get_machine_pigments():
                    continue
                specific_weight = m.get_specific_weight(key)
                if specific_weight > 0:
                    insuff_pigmnt_vol = insuff_pigmnt_gr / specific_weight
                    total_volume += insuff_pigmnt_vol

        logging.warning(f'formula total_volume: {total_volume}')
        return total_volume

    def build_insufficient_pigments_infos(self, insufficient_pigments):
        insuff_pigmts = list(insufficient_pigments.keys())
        info_insuff_pigmts = []

        for m in filter(None, self.machine_head_dict.values()):
            # m.get_pigment_list() = [('pigment', 'C01'), ...]
            m_pig_list = m.get_pigment_list()
            for ll_pigmnt, _ in m_pig_list:
                if ll_pigmnt in insuff_pigmts:
                    info_insuff_pigmts.append((ll_pigmnt, m.name))

        logging.debug(f'>>>> info_insuff_pigmts: {info_insuff_pigmts}')
        return info_insuff_pigmts

    def get_restorable_jars_for_recovery_mode(self):
        if not self.restore_machine_helper:
            return []
        
        restorable_jars_dict = self.restore_machine_helper.read_data()
        lista = []
        for key, val in restorable_jars_dict.items():
            pos = val['pos']
            lista.append(f"{key} - {pos}")
        return lista

    def recovery_mode_delete_jar_task(self, jar_code, jar_pos):
        if not self.restore_machine_helper:
            raise RuntimeError("Missing restore_machine_helper ... Aborting")
        self.restore_machine_helper.recovery_task_deletion(jar_code)
        logging.warning(f"jar_pos -> {jar_pos}")
        logging.warning(f"jar_code -> {jar_code}")
        if jar_pos.strip() not in ('IN', 'IN_A'):

            order_nr, index = decompile_barcode(jar_code)
            try:
                order = self.db_session.query(Order).filter(Order.order_nr == order_nr).one()
            except NoResultFound:
                logging.error(f"ERROR: Barcode {jar_code} not found in db!")
                return
            query_ = self.db_session.query(Jar).filter(Jar.order == order).filter(Jar.index == index)
            jar = query_.first()
            logging.warning(f"founded jar: {jar}")
            if jar:
                jar.status = 'ERROR'
                self.db_session.commit()

