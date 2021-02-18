# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


import logging
import asyncio
import json
import traceback
import time


from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

import websockets  # pylint: disable=import-error
import aiohttp  # pylint: disable=import-error
import async_timeout  # pylint: disable=import-error

from alfa_CR6_backend.globals import EPSILON, tr_

DEFAULT_WAIT_FOR_TIMEOUT = 6 * 60


class MachineHead:  # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(  # pylint: disable=too-many-arguments
            self, index, ip_add, ws_port, http_port, msg_handler=None, mockup_files_path=None):

        self.index = index
        self.name = QApplication.instance().MACHINE_HEAD_INDEX_TO_NAME_MAP[index]
        self.app = QApplication.instance()

        self.aiohttp_clientsession = None

        self.status = {}
        self.photocells_status = {}
        self.jar_photocells_status = {}
        self.jar_size_detect = None
        self.pipe_list = []
        self.package_list = []
        self.pigment_list = []
        self.low_level_pipes = []

        self.ip_add = ip_add
        self.ws_port = ws_port
        self.http_port = http_port
        self.msg_handler = msg_handler
        self.mockup_files_path = mockup_files_path

        self.websocket = None
        self.last_answer = None
        self.cntr = 0
        self.time_stamp = 0

        self.__crx_inner_status = [
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
        ]

    def __str__(self):
        return f"[{self.index}:{self.name}]"

    def get_available_weight(self, pigment_name):

        available_gr = 0
        specific_weight = -1
        for pig in self.pigment_list:
            if pig["name"] == pigment_name:
                specific_weight = pig["specific_weight"]
                for pipe in pig["pipes"]:
                    if pipe["enabled"]:
                        if pipe["effective_specific_weight"] > EPSILON:
                            specific_weight = pipe["effective_specific_weight"]
                        available_cc = max(
                            0, pipe["current_level"] - pipe["minimum_level"]
                        )
                        if available_cc > EPSILON:
                            available_gr += available_cc * specific_weight

        return available_gr, specific_weight

    async def update_tintometer_data(self, invalidate_cache=True):

        # ~ logging.warning(
        # ~ f"{self.name} invalidate_cache:{invalidate_cache} {[p['name'] for p in self.pigment_list]}")

        if invalidate_cache:
            ret = await self.call_api_rest("pigment", "GET", {})
            pigment_list = []
            low_level_pipes = []
            for pig in ret.get("objects", []):

                enabled_pipes = [pipe for pipe in pig["pipes"] if pipe["enabled"]]

                low_level_pipes += [
                    pipe["name"]
                    for pipe in enabled_pipes
                    if pipe["current_level"] < pipe["reserve_level"]
                ]

                if enabled_pipes:
                    pigment_list.append(pig)

            with open(self.app.settings.TMP_PATH + f"{self.name}_pigment_list.json", "w") as f:
                json.dump(pigment_list, f, indent=2)

            ret = await self.call_api_rest("package", "GET", {})
            package_list = ret.get("objects", [])
            with open(
                    self.app.settings.TMP_PATH + f"{self.name}_package_list.json", "w") as f:

                json.dump(self.package_list, f, indent=2)

        self.pigment_list = pigment_list
        self.low_level_pipes = low_level_pipes
        self.package_list = package_list

        # ~ logging.warning(f"{self.name} {[p['name'] for p in self.pigment_list]}")
        if self.low_level_pipes:
            logging.warning(f"{self.name} low_level_pipes:{self.low_level_pipes}")
            self.app.main_window.open_alert_dialog(
                f"{self.name} Please, Check Pipe Levels: low_level_pipes:{self.low_level_pipes}")
            self.app.show_reserve(self.index, True)
        else:
            self.app.show_reserve(self.index, False)

    async def update_status(self, status):

        logging.debug("status:{}".format(status))

        if not self.status:
            asyncio.ensure_future(self.update_tintometer_data())

        if (status.get("status_level") == "ALARM"
                and self.status.get("status_level") != "ALARM"):

            self.app.freeze_carousel(True)
            msg_ = "{} ALARM. error_code:{}, error_message:{}".format(
                self.name, status.get("error_code"), status.get("error_message"))
            logging.error(msg_)
            self.app.main_window.open_frozen_dialog(msg_)

            if self.index == 0:
                if status.get("error_code") == 10:  # user button interrupt
                    for m in self.app.machine_head_dict.values():
                        if m and m.index != 0:
                            t = m.send_command(cmd_name="ABORT", params={})
                            asyncio.ensure_future(t)

        if (status.get("status_level") == "RESET"
                and self.status.get("status_level") != "RESET"):
            await self.update_tintometer_data(invalidate_cache=True)
            self.app.main_window.open_alert_dialog(f"{self.name} RESETTING")

        old_flag = self.status.get("jar_photocells_status", 0) & 0x001
        new_flag = status.get("jar_photocells_status", 0) & 0x001
        if old_flag and not new_flag:
            logging.warning("JAR_INPUT_ROLLER_PHOTOCELL transition DARK -> LIGHT")
            self.app.ready_to_read_a_barcode = True

        try:
            crx_outputs_status = self.status.get('crx_outputs_status')
            for output_number in range(4):
                mask_ = 0x1 << output_number
                if not (int(crx_outputs_status) & mask_):
                    self.__crx_inner_status[output_number] = {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0}

            self.photocells_status = {
                "THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL": status["photocells_status"] & 0x001 and 1,
                "THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL": status["photocells_status"] & 0x002 and 1,
                "THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL": status["photocells_status"] & 0x004 and 1,
                "THOR TABLE_PHOTOCELL": status["photocells_status"] & 0x008 and 1,
                "THOR VALVE_OPEN_PHOTOCELL": status["photocells_status"] & 0x010 and 1,
                "THOR AUTOCAP_CLOSE_PHOTOCELL": status["photocells_status"] & 0x020 and 1,
                "THOR AUTOCAP_OPEN_PHOTOCELL": status["photocells_status"] & 0x040 and 1,
                "THOR BRUSH_PHOTOCELL": status["photocells_status"] & 0x080 and 1,
            }

            self.jar_photocells_status = {
                "JAR_INPUT_ROLLER_PHOTOCELL": status["jar_photocells_status"] & 0x001 and 1,
                "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL": status["jar_photocells_status"] & 0x002 and 1,
                "JAR_OUTPUT_ROLLER_PHOTOCELL": status["jar_photocells_status"] & 0x004 and 1,
                "LOAD_LIFTER_DOWN_PHOTOCELL": status["jar_photocells_status"] & 0x008 and 1,
                "LOAD_LIFTER_UP_PHOTOCELL": status["jar_photocells_status"] & 0x010 and 1,
                "UNLOAD_LIFTER_DOWN_PHOTOCELL": status["jar_photocells_status"] & 0x020 and 1,
                "UNLOAD_LIFTER_UP_PHOTOCELL": status["jar_photocells_status"] & 0x040 and 1,
                "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL": status["jar_photocells_status"] & 0x080 and 1,
                "JAR_DISPENSING_POSITION_PHOTOCELL": status["jar_photocells_status"] & 0x100 and 1,
                "JAR_DETECTION_MICROSWITCH_1": status["jar_photocells_status"] & 0x200 and 1,
                "JAR_DETECTION_MICROSWITCH_2": status["jar_photocells_status"] & 0x400 and 1,
            }

            s1 = status["jar_photocells_status"] & 0x200
            s2 = status["jar_photocells_status"] & 0x400
            self.jar_size_detect = int(s1 + s2) >> 9

        except Exception as e:  # pylint: disable=broad-except
            # ~ self.app.handle_exception(e)
            logging.debug(e)

        diff = {k: status[k] for k in status if status[k] != self.status.get(k)}

        self.status = status

        # ~ logging.warning("self.jar_photocells_status:{}".format(self.jar_photocells_status))
        return diff

    async def handle_ws_recv(self):

        msg = None
        try:
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=30)
        except asyncio.TimeoutError:
            logging.warning(f"{self.name} time out while waiting in websocket.recv.")

        self.cntr += 1

        if msg:
            msg_dict = dict(json.loads(msg))

            if msg_dict.get("type") == "device:machine:status":
                status = msg_dict.get("value")
                status = dict(status)
                if status:
                    diff = await self.update_status(status)
                    if diff:
                        logging.info(f"{self.name} diff:{ diff }")

            elif msg_dict.get("type") == "answer":
                answer = msg_dict.get("value")
                answer = dict(answer)
                if (answer and answer.get("status_code") is not None
                        and answer.get("command") is not None):

                    self.last_answer = answer
                    logging.warning(f"{self.name} answer:{answer}")

            elif msg_dict.get("type") == "time":
                # ~ logging.warning(f"msg_dict:{msg_dict}")
                time_stamp = msg_dict.get("value")
                if time_stamp:
                    self.time_stamp = time_stamp
                    
            else:
                logging.warning(f"{self.name} msg_dict:{anmsg_dictswer}")

            if self.msg_handler:
                await self.msg_handler(self.index, msg_dict)

    async def call_api_rest(self, path: str, method: str, data: dict, timeout=10):

        r_json_as_dict = {}
        try:
            if self.ip_add:
                url = "http://{}:{}/{}/{}".format(
                    self.ip_add, self.http_port, "apiV1", path
                )
                if self.aiohttp_clientsession is None:
                    self.aiohttp_clientsession = aiohttp.ClientSession()
                with async_timeout.timeout(timeout):
                    if method.upper() == "GET":
                        context_mngr = self.aiohttp_clientsession.get
                        args = [url]
                    elif method.upper() == "POST":
                        context_mngr = self.aiohttp_clientsession.post
                        args = [url, data]

                    async with context_mngr(*args) as response:
                        r = response
                        r_json_as_dict = await r.json()

                    assert (
                        r.reason == "OK"
                    ), f"method:{method}, url:{url}, data:{data}, status:{r.status}, reason:{r.reason}"
        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)

        return r_json_as_dict

    async def crx_outputs_management(self, output_number, output_action, timeout=30):

        r = None
        mask_ = 0x1 << output_number
        # ~ if self.__crx_inner_status[output_number]['value'] != 0 and output_action:
        if self.status.get('crx_outputs_status', 0x0) & mask_ != 0 and output_action:
            logging.error(
                f"{self.name} SKIPPING CMD output_number:{output_number}, output_action:{output_action}, self.__crx_inner_status:{self.__crx_inner_status}")
        else:

            def condition_1():
                flag = not self.__crx_inner_status[output_number]['locked']
                return flag
            msg_ = tr_("{} waiting for {} to get unlocked.").format(self.name, output_number)
            ret = await self.app.wait_for_condition(condition_1, timeout=5, extra_info=msg_, stability_count=1)

            if ret:
                self.__crx_inner_status[output_number]['locked'] = True
                try:
                    if output_action == 0:
                        self.__crx_inner_status[output_number]['timeout'] = 0
                        self.__crx_inner_status[output_number]['t0'] = 0
                    elif timeout:
                        self.__crx_inner_status[output_number]['timeout'] = timeout
                        self.__crx_inner_status[output_number]['t0'] = time.time()

                    params = {"Output_Number": output_number, "Output_Action": output_action}
                    r = await self.send_command("CRX_OUTPUTS_MANAGEMENT", params)
                    self.__crx_inner_status[output_number]['value'] = output_action
                    mask_ = 0x1 << output_number
                    msg_ = tr_("{} waiting for CRX_OUTPUTS_MANAGEMENT({}, {}) execution. crx_outputs_status:{}").format(
                        self.name, output_number, output_action, self.status.get('crx_outputs_status', 0x0))

                    if output_action:
                        def condition():
                            return self.status.get('crx_outputs_status', 0x0) & mask_
                        r = await self.app.wait_for_condition(condition, timeout=3.3, show_alert=False, stability_count=1, step=0.1)
                    else:
                        def condition():
                            return not self.status.get('crx_outputs_status', 0x0) & mask_
                        r = await self.app.wait_for_condition(condition, timeout=3.3, show_alert=False, stability_count=1, step=0.1)

                    if not r:
                        logging.error(f"msg_:{msg_}")

                except Exception as e:  # pylint: disable=broad-except
                    self.app.handle_exception(e)

                self.__crx_inner_status[output_number]['locked'] = False

        return r

    async def can_movement(self, params=None):

        default = {
            "Dispensing_Roller": 0,
            "Lifter_Roller": 0,
            "Input_Roller": 0,
            "Lifter": 0,
            "Output_Roller": 0,
        }
        if params:
            default.update(params)

        r = await self.send_command("CAN_MOVEMENT", default)

        logging.debug("CAN_MOVEMENT index:{}, {}".format(self.index, default))

        return r

    async def send_command(self, cmd_name: str, params: dict, type_="command", channel="machine"):
        """ param 'type_' can be 'command' or 'macro'

            examples:
                self.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
                self.send_command(cmd_name="PURGE", params={'items': [{'name': 'B01', 'qtity': 2.1}, {'name': 'C03', 'qtity': 1.1}, ]}, type_='macro')
                self.send_command(cmd_name="PURGE", params={'items': [{'name': 'B01', 'qtity': 2.1}, {'name': 'C03', 'qtity': 1.1}, ]}, type_='macro')
                self.send_command(cmd_name='DISPENSE_FORMULA', type_='macro', params={'package_name': '******* not valid name ****', 'ingredients': {'K205': 85.5859375}})
        """
        ret = None
        try:
            msg = {
                "type": type_,
                "channel": channel,
                "msg_out_dict": {"command": cmd_name, "params": params},
            }
            if self.websocket:

                logging.warning(f"{self.name} cmd:{msg}")
                self.last_answer = None
                ret = await self.websocket.send(json.dumps(msg))

                if type_ == "command":

                    def condition():
                        if (self.last_answer is not None
                                and self.last_answer["status_code"] == 0
                                and self.last_answer["command"] == cmd_name + "_END"):
                            return True
                        return False

                    ret = await self.app.wait_for_condition(condition, timeout=30)
                    logging.warning(f"{self.name} ret:{ret}, answer:{self.last_answer}")
                else:
                    # TODO: wait for answer from macroprocessor
                    ret = True

        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)
        return ret

    async def do_dispense(self, jar):  # pylint: disable=too-many-locals

        jar_properties = json.loads(jar.json_properties)
        ingredient_volume_map = jar_properties["ingredient_volume_map"]
        ingredients = {}
        for pigment_name in ingredient_volume_map.keys():
            try:
                val_ = ingredient_volume_map \
                    and ingredient_volume_map.get(pigment_name) \
                    and ingredient_volume_map[pigment_name].get(self.name)
                if val_:
                    ingredients[pigment_name] = val_
            except Exception as e:  # pylint: disable=broad-except
                self.app.handle_exception(e)

        pars = {
            "package_name": "******* not valid name ****",
            "ingredients": ingredients,
        }
        logging.warning(f"{self.name} pars:{pars}")

        r = True
        if ingredients:

            # ~ allowed_status_levels = ['DIAGNOSTIC', 'STANDBY','POSITIONING','DISPENSING','JAR_POSITIONING']
            allowed_status_levels = ['DIAGNOSTIC', 'STANDBY', 'POSITIONING', 'JAR_POSITIONING']

            def condition():
                flag = self.jar_photocells_status["JAR_DISPENSING_POSITION_PHOTOCELL"]
                flag = flag and self.status["status_level"] in allowed_status_levels
                flag = flag and self.status["container_presence"]
                return flag

            logging.warning(f"{self.name} condition():{condition()}")
            msg_ = tr_(" before dispensing. Please check jar.")
            r = await self.app.wait_for_condition(condition, timeout=31, extra_info=msg_)
            logging.warning(f"{self.name} r:{r}")

            if r:
                r = await self.send_command(
                    cmd_name="DISPENSE_FORMULA", type_="macro", params=pars)
                if r:
                    r = await self.wait_for_status_level(["DISPENSING"], timeout=41)
                    if r:
                        r = await self.wait_for_status_level(["STANDBY"], timeout=60 * 6)

        return r

    async def close(self):

        if self.aiohttp_clientsession:
            await self.aiohttp_clientsession.close()

    async def __watch_dog_task(self):

        while True:
            await asyncio.sleep(1)
            for output_number, output in enumerate(self.__crx_inner_status):
                timeout = output['timeout']
                t0 = output['t0']
                if (timeout > 0 and t0 > 0) and (time.time() - t0 > timeout):
                    self.crx_outputs_management(output_number, 0, timeout=0)

    async def run(self):
        t = self.__watch_dog_task()
        asyncio.ensure_future(t)

        ws_url = f"ws://{ self.ip_add }:{ self.ws_port }/device:machine:status"
        while True:
            try:
                async with websockets.connect(ws_url) as websocket:
                    self.websocket = websocket
                    while True:
                        await self.handle_ws_recv()
            except (OSError, ConnectionRefusedError,
                    websockets.exceptions.ConnectionClosedError) as e:
                logging.error(f"e:{e}")
                await asyncio.sleep(5)
            except Exception as e:  # pylint: disable=broad-except
                logging.error(f"e:{e}")
                logging.error(traceback.format_exc())
                await asyncio.sleep(2)
        logging.warning(f" *** exiting *** ")

    async def wait_for_jar_photocells_and_status_lev(  # pylint: disable=too-many-arguments
            self, bit_name, on=True, status_levels=None, timeout=DEFAULT_WAIT_FOR_TIMEOUT, show_alert=True):

        if status_levels is None:
            status_levels = ["STANDBY"]

        logging.warning(
            f"{self.name} bit_name:{bit_name}, on:{on}, status_levels:{status_levels}, timeout:{timeout}")

        try:

            def condition():
                flag = self.jar_photocells_status.get(bit_name, False) and True
                flag = flag if on else not flag
                flag = flag and self.status["status_level"] in status_levels
                return flag

            ret = await self.app.wait_for_condition(condition, timeout=timeout, show_alert=False)
            logging.warning(
                f"{self.name} bit_name:{bit_name}, on:{on}, status_levels:{status_levels}, ret:{ret}"
            )

            if not ret and show_alert:
                _ = tr_('timeout expired!\n{} bit_name:{}, on:{}, status_levels:{}, timeout:{}.').format(
                    self.name, bit_name, on, status_levels, timeout)
                self.app.main_window.open_alert_dialog(_)
                logging.error(_)

            return ret
        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)

    async def wait_for_jar_photocells_status(
            self, bit_name, on=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT, show_alert=True):

        logging.warning(f"{self.name} bit_name:{bit_name}, on:{on}, timeout:{timeout}")

        try:

            def condition():
                flag = self.jar_photocells_status.get(bit_name, False)
                return flag if on else not flag

            ret = await self.app.wait_for_condition(
                condition, timeout=timeout, show_alert=False
            )
            logging.warning(f"{self.name} bit_name:{bit_name}, on:{on}, ret:{ret}")

            if not ret and show_alert:
                _ = tr_('timeout expired!\n{} bit_name:{}, on:{}, timeout:{}.').format(
                    self.name, bit_name, on, timeout)
                self.app.main_window.open_alert_dialog(_)
                logging.error(_)

            return ret
        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)

    async def wait_for_status_level(
            self, status_levels, on=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT, show_alert=True):

        logging.warning(
            f"{self.name} status_levels:{status_levels}, on:{on}, timeout:{timeout}")

        try:

            def condition():
                flag = self.status["status_level"] in status_levels
                return flag if on else not flag

            ret = await self.app.wait_for_condition(
                condition, timeout=timeout, show_alert=show_alert
            )
            logging.warning(
                f"{self.name} status_levels:{status_levels}, on:{on}, ret:{ret}"
            )

            if not ret and show_alert:
                _ = tr_('timeout expired!\n{} on:{}, status_levels:{}, timeout:{}.').format(
                    self.name, on, status_levels, timeout)
                self.app.main_window.open_alert_dialog(_)
                logging.error(_)

            return ret
        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)
