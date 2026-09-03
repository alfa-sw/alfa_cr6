# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=logging-fstring-interpolation, consider-using-f-string


import os
import sys
import logging
import asyncio
import json
import traceback
import time
import copy


import aiohttp  # pylint: disable=import-error
import async_timeout  # pylint: disable=import-error

import websockets  # pylint: disable=import-error

from alfa_CR6_backend.globals import EPSILON, tr_, get_application_instance, store_data_on_restore_machine_helper

DEFAULT_WAIT_FOR_TIMEOUT = 6 * 60


class MachineHead:  # pylint: disable=too-many-instance-attributes,too-many-public-methods

    def __init__(  # pylint: disable=too-many-arguments
            self, index, ip_add, ws_port, http_port, ws_msg_handler=None, mockup_files_path=None):

        self.index = index
        self.app = get_application_instance()
        self.name = self.app.MACHINE_HEAD_INDEX_TO_NAME_MAP[index]

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
        self.ws_msg_handler = ws_msg_handler
        self.mockup_files_path = mockup_files_path

        self.websocket = None
        self.__ws_id = None
        self.__last_recv_msg = None
        self.__msg_excp_cntr = 0
        self.last_answer = None
        self.cmd_answers = []
        self.callback_on_macro_answer = None
        self.cntr = 0
        self.time_stamp = 0
        self.expired_products = None
        self.table_belt_health_msg = None

        self.owned_barcodes = []

        self.__crx_inner_status = [
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
            {'value': 0, 'locked': 0, 'timeout': 0, 't0': 0},
        ]

        self.machine_config = None

        self._current_circuit_engaged = None
        self._current_runner = None

    def __str__(self):
        return f"[{self.index}:{self.name}]"

    def get_names_by_circuit_id(self, circuit_id):

        base_pipe_id_name_map = {i: "B%02d" % (i + 1) for i in range(0, 8)}
        colorant_pipe_id_name_map = {i: "C%02d" % (i - 7) for i in range(8, 32)}

        pipe_id_name_map = base_pipe_id_name_map
        pipe_id_name_map.update(colorant_pipe_id_name_map)

        ret = None
        pipe_name = pipe_id_name_map.get(circuit_id)
        for pig in self.pigment_list:
            for pipe in pig["pipes"]:
                if pipe["name"] == pipe_name:
                    ret = (pipe["name"], pig["name"])
                    break
            if ret is not None:
                break

        return ret

    def get_specific_weight(self, pigment_name):

        specific_weight = -1
        for pig in self.pigment_list:
            if pig["name"] == pigment_name:
                specific_weight = pig["specific_weight"]
                for pipe in pig["pipes"]:
                    if pipe["enabled"]:
                        if pipe["effective_specific_weight"] > EPSILON:
                            specific_weight = pipe["effective_specific_weight"]

        # ~ logging.warning(f"{self.name} {pigment_name} specific_weight:{specific_weight}")

        return float(specific_weight)

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
                            0, pipe["current_level"] - pipe["minimum_level"])
                        if available_cc > EPSILON:
                            available_gr += available_cc * specific_weight

        # ~ logging.warning(f"{self.name} {pigment_name} available_gr:{available_gr}")

        return available_gr

    def handle_dispensing_photocell_transition(self, new_flag):

        dt = time.time() - self.app.timer_01_02
        logging.warning(f"new_flag:{new_flag}, dt:{dt}, self.app.timer_01_02:{self.app.timer_01_02}.")
        if new_flag and self.index == 0:
            if hasattr(self.app.settings, "MOVE_01_02_TIME_INTERVAL"):
                timeout_ = float(self.app.settings.MOVE_01_02_TIME_INTERVAL)
                if dt < timeout_:
                    self.app.double_can_alert = True

    async def get_machine_config(self):

        if self.machine_config is None:
            machine_config = {}
            ret = await self.call_api_rest("apiV1/config", "GET", {}, timeout=15)
            if ret:
                for obj in ret.get("objects", []):
                    try:
                        machine_config[obj['name']] = json.loads(obj['json_info'])
                    except Exception:  # pylint: disable=broad-except
                        logging.error(traceback.format_exc())

            self.machine_config = machine_config

            pth_ = os.path.join(self.app.settings.TMP_PATH, f"{self.name}_machine_config.json")
            with open(pth_, "w", encoding='UTF-8') as f:
                json.dump(machine_config, f, indent=2)

    async def update_tintometer_data(self, invalidate_cache=True, silent=1):

        # ~ logging.warning(
        # ~ f"{self.name} invalidate_cache:{invalidate_cache} {[p['name'] for p in self.pigment_list]}")
        await self.get_machine_config()

        if invalidate_cache:
            pigment_list = []
            low_level_pipes = []
            package_list = []
            ret = await self.call_api_rest("apiV1/pigment", "GET", {}, timeout=15)
            if ret:
                for pig in ret.get("objects", []):

                    enabled_and_synced_pipes = [pipe
                                                for pipe in pig["pipes"]
                                                if pipe["enabled"] and pipe["sync"]]

                    if enabled_and_synced_pipes:
                        pigment_list.append(pig)

                        not_low_level_pipes = [pipe
                                               for pipe in enabled_and_synced_pipes
                                               if pipe["current_level"] > pipe["reserve_level"]]

                        if not not_low_level_pipes:
                            low_level_pipes += [(pipe["name"], pig["name"])
                                                for pipe in enabled_and_synced_pipes]

            ret = await self.call_api_rest("apiV1/package", "GET", {})
            if ret:
                package_list = ret.get("objects", [])

            pth_ = os.path.join(self.app.settings.TMP_PATH, f"{self.name}_package_list.json")
            with open(pth_, "w", encoding='UTF-8') as f:
                json.dump(package_list, f, indent=2)

            pth_ = os.path.join(self.app.settings.TMP_PATH, f"{self.name}_pigment_list.json")
            with open(pth_, "w", encoding='UTF-8') as f:
                json.dump(pigment_list, f, indent=2)

            pth_ = os.path.join(self.app.settings.TMP_PATH, f"{self.name}_low_level_pipes.json")
            with open(pth_, "w", encoding='UTF-8') as f:
                json.dump(low_level_pipes, f, indent=2)

            self.pigment_list = pigment_list
            self.low_level_pipes = low_level_pipes
            self.package_list = package_list

        self.app.show_reserve(self.index, bool(self.low_level_pipes))

        if self.low_level_pipes and not silent:
            logging.warning(f"{self.name} low_level_pipes:{self.low_level_pipes}")
            args, fmt = (self.name, self.low_level_pipes), "{} Please, Check Pipe Levels: low_level_pipes:{}"
            self.app.main_window.open_alert_dialog(args, fmt=fmt)

    async def update_status(self, status):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        logging.debug("status:{}".format(status))

        if not self.status:
            asyncio.ensure_future(self.update_tintometer_data(silent=False))

        if (status.get("status_level") == "ALARM"
                and self.status.get("status_level") != "ALARM"):

            self.app.freeze_carousel(True)
            m_fmt = "{} ALARM. {}: {}, {}: {}"
            m_args = (self.name, 'error_code', status.get(
                "error_code"), 'error_message', status.get("error_message"))

            logging.error(m_fmt.format(*m_args))

            error_code = status.get("error_code")
            if getattr(self.app.settings, "TROUBLESHOOTING", True) and error_code is not None:
                def _cb():
                    from alfa_CR6_frontend.dialogs import TroubleshootingDialog
                    url = "http://127.0.0.1:8090/troubleshooting/{}".format(error_code)
                    dlg = TroubleshootingDialog(
                        url=url,
                        title=f"Troubleshooting - Error {error_code}",
                        parent=self.app.main_window,
                    )
                    dlg.exec_()
            else:
                _cb = None

            self.app.main_window.open_frozen_dialog(
                message_args=m_args, message_fmt=m_fmt,
                force_explicit_restart=True, hp_callback=_cb,
                localize_args=True, show_cancel_btn=False
            )

            try:
                get_application_instance().insert_db_event(
                    name="HEAD",
                    level="ALARM",
                    severity=status.get("error_code", ''),
                    source=self.name,
                    description=status.get("error_message", '')
                )
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

            logging.warning('')

            if self.index == 0:
                if status.get("error_code") in (10, "USER_INTERRUPT"):  # user button interrupt
                    for m in self.app.machine_head_dict.values():
                        if m and m.index != 0:
                            t = m.send_command(cmd_name="ABORT", params={})
                            asyncio.ensure_future(t)

        if (status.get("status_level") == "RESET"
                and self.status.get("status_level") != "RESET"):
            await self.update_tintometer_data(silent=False)

            # self.app.main_window.open_alert_dialog((self.name, ), fmt="{} RESETTING")

        old_flag = self.status.get("jar_photocells_status", 0) & 0x001
        new_flag = status.get("jar_photocells_status", 0) & 0x001
        if old_flag and not new_flag:
            logging.warning("JAR_INPUT_ROLLER_PHOTOCELL transition DARK -> LIGHT")
            self.app.ready_to_read_a_barcode = True
            if self.index == 0:
                reset_shuttle_cycle = getattr(
                    self.app, "_reset_shuttle_barcode_cycle", None)
                if reset_shuttle_cycle:
                    reset_shuttle_cycle()

        old_flag_1 = self.status.get("jar_photocells_status", 0) & 0x100
        new_flag_1 = status.get("jar_photocells_status", 0) & 0x100
        if old_flag_1 != new_flag_1:
            logging.warning(f"JAR_DISPENSING_POSITION_PHOTOCELL transition {old_flag} -> {new_flag}")
            self.handle_dispensing_photocell_transition(new_flag)

        try:
            crx_outputs_status = status.get('crx_outputs_status', 0x0)
            for output_number in range(4):
                mask_ = 0x1 << output_number
                if not int(crx_outputs_status) & mask_:
                    self.__crx_inner_status[output_number]['value'] = 0
                    self.__crx_inner_status[output_number]['timeout'] = 0
                    self.__crx_inner_status[output_number]['t0'] = 0

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

        if logging.getLogger().isEnabledFor(logging.INFO):
            diff = {k: status[k] for k in status if status[k] != self.status.get(k)}
        else:
            diff = None

        self.status = status

        # ~ logging.warning("self.jar_photocells_status:{}".format(self.jar_photocells_status))

        if status.get("status_level") == "DISPENSING":
            new_circuit_engaged = status.get("circuit_engaged")

            if new_circuit_engaged != self._current_circuit_engaged:
                if new_circuit_engaged == 0:
                    if self._current_circuit_engaged and self._current_runner:
                        self._current_runner.setdefault('running_engaged_circuits', [])
                        self._current_runner['running_engaged_circuits'].append(self._current_circuit_engaged)
                self._current_circuit_engaged = new_circuit_engaged
            if self._current_runner:
                logging.warning(
                    f"new_circuit_engaged:{new_circuit_engaged}, running_engaged_circuits:{self._current_runner.get('running_engaged_circuits')}")

        return diff

    async def handle_ws_recv(self):

        msg = None
        try:
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=30)
        except asyncio.TimeoutError:
            logging.warning(f"{self.name} time out while waiting in websocket.recv.")

        if msg is not None:
            self.__last_recv_msg = msg

        self.cntr += 1

        try:
            await self.__process_ws_msg(msg)
        except websockets.exceptions.ConnectionClosed:
            raise
        except Exception as e:  # pylint: disable=broad-except
            # a faulty message must not tear down the websocket:
            # log, record the first occurrences, keep the connection alive
            logging.error(f"{self.name} e:{e}")
            logging.error(traceback.format_exc())
            self.__msg_excp_cntr += 1
            if self.__msg_excp_cntr <= 3:
                extra = self.__exception_log_extra(e, self.websocket)
                extra["phase"] = "message processing (recovered)"
                extra["msg_excp_cntr"] = self.__msg_excp_cntr
                self.__log_document("WS_MSG_EXCP", extra)

    async def __process_ws_msg(self, msg):     # pylint: disable=too-many-branches

        propagate_to_ws_msg_handler = True

        if msg:
            msg_dict = dict(json.loads(msg))
            msg_type = msg_dict.get("type")

            if msg_type == "device:machine:status":
                status = msg_dict.get("value")
                status = dict(status)
                if status:
                    diff = await self.update_status(status)
                    if diff:
                        logging.info("%s diff:%s", self.name, diff)

            elif msg_type == "answer":
                answer = msg_dict.get("value")
                answer = dict(answer)
                logging.warning(f"{self.name} answer:{answer}")

                if self.callback_on_macro_answer and callable(self.callback_on_macro_answer):
                    try:
                        if answer.get('answer'):
                            self.callback_on_macro_answer(answer['answer'])
                            self.callback_on_macro_answer = None
                    except Exception:  # pylint: disable=broad-except
                        logging.error(traceback.format_exc())

                if (answer and answer.get("status_code") is not None
                        and answer.get("command") is not None):

                    self.last_answer = answer
                    # ~ self.cmd_answers.append(answer)

            elif msg_type == "time":
                propagate_to_ws_msg_handler = False
                time_stamp = msg_dict.get("value")
                if time_stamp:
                    self.time_stamp = time_stamp

            elif msg_type == "expired_products":
                expired_products = msg_dict.get("value")
                if self.expired_products != expired_products:
                    self.expired_products = expired_products
                else:
                    propagate_to_ws_msg_handler = False

            elif msg_type == "table_belt_health":
                value = msg_dict.get("value")
                if self.table_belt_health_msg != value:
                    self.table_belt_health_msg = value
                else:
                    propagate_to_ws_msg_handler = False

            else:
                logging.warning(f"{self.name} unknown type for msg_dict:{msg_dict}")

            if propagate_to_ws_msg_handler and self.ws_msg_handler:
                await self.ws_msg_handler(self.index, msg_dict)

    async def call_api_rest(self,   # pylint: disable=too-many-arguments
                            path: str, method: str, data: dict, timeout=40, expected_ret_type='json'):

        url = "http://{}:{}/{}".format(self.ip_add, self.http_port, path)
        logging.warning(f" url:{url}")
        ret = None
        try:

            if self.aiohttp_clientsession is None:
                self.aiohttp_clientsession = aiohttp.ClientSession()

            async with async_timeout.timeout(timeout) as cm:

                if method.upper() == "GET":
                    callable_ = self.aiohttp_clientsession.get
                    args = [url, ]
                    kwargs = {}
                elif method.upper() == "POST":
                    callable_ = self.aiohttp_clientsession.post
                    args = [url, ]
                    kwargs = {
                        "headers": {'content-type': 'application/json'},
                        "data": json.dumps(data),
                    }

                while ret is None:
                    try:
                        async with callable_(*args, **kwargs) as response:
                            r = response
                            if expected_ret_type == 'json':
                                ret = {}
                                ret = await r.json()
                            else:
                                ret = await r.text()
                            assert r.reason == "OK", \
                                f"method:{method}, url:{url}, data:{data}, status:{r.status}, reason:{r.reason}"
                    except aiohttp.client_exceptions.ClientError as e:
                        logging.warning(f"exception while retrieving response from {url} {e}; retrying")
                        await asyncio.sleep(1)

        except asyncio.TimeoutError as e:
            logging.error(f"{url}, timeout!")

            # due to misconfigured exception handling we cannot
            # trigger default handler or raise exception here
            # ~ self.app.handle_exception(f"{url}, timeout")

        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(f"{url}, {e}")

        if cm.expired or ret is None:
            self.app.handle_exception(f"{url}, timeout")

        return ret

    async def crx_outputs_management(self, output_number, output_action, timeout=30, silent=True):

        # ~ id_ = random.randint(1, 10000)
        # ~ logging.warning(f" {self.name} owned_barcodes:{self.owned_barcodes}, id_:{id_}")

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
            self.__crx_inner_status[output_number]['locked'] = True
            # ~ logging.warning(f" {self.name} ({output_number}, {output_action}) id_:{id_},   LOCKED")

            if ret:
                previous_stop_state = None
                if output_action == 0:
                    previous_stop_state = {
                        key: self.__crx_inner_status[output_number][key]
                        for key in ('value', 'timeout', 't0')
                    }

                try:
                    if output_action and timeout:
                        self.__crx_inner_status[output_number]['timeout'] = timeout
                        self.__crx_inner_status[output_number]['t0'] = time.time()

                    params = {"Output_Number": output_number, "Output_Action": output_action}
                    r = await self.send_command("CRX_OUTPUTS_MANAGEMENT", params)
                    self.__crx_inner_status[output_number]['value'] = output_action
                    mask_ = 0x1 << output_number
                    msg_ = "{} waiting for CRX_OUTPUTS_MANAGEMENT({}, {}) execution. crx_outputs_status:{}"
                    args = (self.name, output_number, output_action, self.status.get('crx_outputs_status', 0x0))
                    if output_action:
                        def condition():
                            return self.status.get('crx_outputs_status', 0x0) & mask_
                        r = await self.app.wait_for_condition(condition, timeout=7.3, show_alert=False, stability_count=1, step=0.1)
                    else:
                        def condition():
                            return not self.status.get('crx_outputs_status', 0x0) & mask_
                        r = await self.app.wait_for_condition(condition, timeout=7.3, show_alert=False, stability_count=1, step=0.1)

                    if not r:
                        logging.error(f"msg_:{msg_}")
                        if not silent:
                            self.app.main_window.open_alert_dialog(args, fmt=msg_)

                except Exception as e:  # pylint: disable=broad-except
                    self.app.handle_exception(e)
                finally:
                    if output_action == 0:
                        output_is_stopped = not (
                            self.status.get('crx_outputs_status', 0x0)
                            & mask_
                        )
                        if output_is_stopped:
                            self.__crx_inner_status[output_number].update({
                                'value': 0, 'timeout': 0, 't0': 0,
                            })
                        else:
                            self.__crx_inner_status[output_number].update(
                                previous_stop_state
                            )

            self.__crx_inner_status[output_number]['locked'] = False
            # ~ logging.warning(f" {self.name} ({output_number}, {output_action}) id_:{id_}, UNLOCKED")

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

    async def send_command(  # pylint: disable=too-many-arguments
            self, cmd_name: str, params: dict, type_="command", channel="machine", callback_on_macro_answer=None):
        """ param 'type_' can be 'command' or 'macro'

            examples:
                self.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
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

                # ~ logging.warning(f"{self.name} cmd:{msg}")
                self.last_answer = None
                ret = await self.websocket.send(json.dumps(msg))

                if type_ == "command":
                    expected_commands = {cmd_name + "_END"}
                    if channel == "scale":
                        # The scale dispatcher historically replies without
                        # the _END suffix used by machine commands.
                        expected_commands.add(cmd_name)

                    def condition():
                        if (self.last_answer is not None
                                and self.last_answer["status_code"] == 0
                                and self.last_answer["command"] in expected_commands):
                            return True
                        return False
                    msg_ = tr_("{} waiting for answer to cmd:{}").format(self.name, cmd_name)

                    # ~ ret = await self.app.wait_for_condition(condition, timeout=30, extra_info=msg_)
                    ret = await self.app.wait_for_condition(condition, timeout=30, extra_info=msg_, show_alert=False)
                    logging.warning(f"{self.name} ret:{ret}, answer:{self.last_answer}")
                else:
                    self.callback_on_macro_answer = callback_on_macro_answer
                    ret = True

        except websockets.exceptions.ConnectionClosed as e:
            # expected during connection teardown (the race window past the
            # "if self.websocket" guard): record it, do not bother the operator
            logging.error(f"{self.name} send_command cmd:{cmd_name} on closed websocket, e:{e}")
            extra = self.__exception_log_extra(e, self.websocket)
            extra["phase"] = "send_command"
            extra["cmd_name"] = cmd_name
            extra["cmd_type"] = type_
            self.__log_document("WS_SEND_FAIL", extra)
            ret = None
        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)
            ret = None

        return ret

    async def read_stable_weight(self):
        """Read a stable scale value and return it in grams."""
        ret = await self.send_command(
            cmd_name="STABLE_WEIGHT", params={}, type_="command", channel="scale")
        answer = self.last_answer
        try:
            if (not ret or not answer or answer.get("status_code") != 0
                    or answer.get("command") not in (
                        "STABLE_WEIGHT", "STABLE_WEIGHT_END")):
                return None
            value, unit = answer.get("params", [])
            if str(unit).lower() != "g":
                return None
            return float(value)
        except (TypeError, ValueError):
            logging.error("%s invalid STABLE_WEIGHT answer: %s", self.name, answer)
            return None

    async def get_ingredients_for_purge_all(self, jar):

        ingredients = []
        missing_ingredients = []
        ret = await self.call_api_rest("apiV1/pipe", "GET", {}, timeout=15)
        for p in ret.get("objects", []):
            if p['enabled'] and p['pigment'] and p['sync']:
                ingredient = {
                    'name': p['name'],
                    'qtity': p['purge_volume'],
                    'pigment_name': p['pigment']['name'],
                }
                if p['current_level'] - p['minimum_level'] > p['purge_volume']:
                    ingredients.append(ingredient)
                else:
                    missing_ingredients.append(ingredient)

        jar_json_properties = json.loads(jar.json_properties)

        jar_json_properties["PURGE ALL"] = True

        jar_json_properties.setdefault(self.name, {})
        jar_json_properties[self.name]["ingredients"] = ingredients
        jar_json_properties[self.name]["missing_ingredients"] = missing_ingredients
        jar.json_properties = json.dumps(jar_json_properties, indent=2, ensure_ascii=False)

        get_application_instance().db_session.commit()

        return ingredients

    def get_splitted_dispense_params(self, pars, step):
        """
        {
            "package_name": "******* not valid name ****",
            "ingredients": {
                "5301": 0.4464,
                "5602": 0.1942
            }
        }
        """

        pars_copy_ = copy.deepcopy(pars)

        for pig_name in pars["ingredients"].keys():
            p_types = [p.get('type') for p in self.pigment_list if p['name'] == pig_name]
            p_type = p_types and p_types[0]
            if (p_type == 'colorant' and step == 0) or (p_type != 'colorant' and step != 0):
                pars_copy_["ingredients"].pop(pig_name)

        if logging.getLogger().isEnabledFor(logging.INFO):
            logging.info("step:%s, ingredients:%s", step, json.dumps(pars_copy_['ingredients']))

        return pars_copy_

    async def do_dispense(self, jar, restore_machine_helper=None):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements

        if jar.order and jar.order.description and "PURGE ALL" in jar.order.description.upper():
            ingredients = await self.get_ingredients_for_purge_all(jar)
        else:
            ingredients = jar.get_ingredients_for_machine(self)

        pars = {
            "package_name": "******* not valid name ****",
            "ingredients": ingredients,
        }
        # ~ logging.warning(f"{self.name} pars:{pars}")
        params_ = pars.copy()
        params_['ref_size'] = 100
        data = {'action': 'get_pipe_formula_from_pigment_formula', 'params': params_}
        ret = await self.call_api_rest("apiV1/ad_hoc", "POST", data, timeout=5)
        # ~ logging.warning(f"ret:{ret}")
        pipe_formula_ml = ret.get('result') == 'OK' and ret.get('pipe_formula')

        self._current_runner = self.app._BaseApplication__jar_runners.get(jar.barcode)  # pylint: disable=protected-access

        r = True

        if not ingredients and self.name == 'A':
            allowed_status_levels_ = ['DIAGNOSTIC', 'STANDBY', 'POSITIONING', 'JAR_POSITIONING']
            def before_dispense_condition():
                flag = self.jar_photocells_status["JAR_DISPENSING_POSITION_PHOTOCELL"]
                flag = flag and self.status["status_level"] in allowed_status_levels_
                flag = flag and self.status["container_presence"]
                return flag
            r = await self.app.wait_for_condition(
                before_dispense_condition, timeout=2.5,
                show_alert=False
            )
            if not r:
                jar.update_live(machine_head=self, status='ERROR', pos=None, t0=None)
                fmt = "Jar not detected from the ultrasonic sensor under nozzle."
                self.app.main_window.open_alert_dialog((), fmt=fmt, title="ALERT")

        if ingredients:

            json_properties = json.loads(jar.json_properties)

            dispensation_outcomes = json_properties.get("dispensation_outcomes", [])

            failed_disps_ = [(head_name, outcome) for head_name, outcome in
                             dispensation_outcomes if "success" not in outcome]

            if not list(failed_disps_):
                # ~ allowed_status_levels_ = ['DIAGNOSTIC', 'STANDBY', 'POSITIONING', 'DISPENSING', 'JAR_POSITIONING']
                allowed_status_levels_ = ['DIAGNOSTIC', 'STANDBY', 'POSITIONING', 'JAR_POSITIONING']

                def before_dispense_condition():
                    flag = self.jar_photocells_status["JAR_DISPENSING_POSITION_PHOTOCELL"]
                    flag = flag and self.status["status_level"] in allowed_status_levels_
                    flag = flag and self.status["container_presence"]
                    return flag

                def get_error_messages_for_specific_dispense_condition():
                    error_messages = []

                    if not self.jar_photocells_status["JAR_DISPENSING_POSITION_PHOTOCELL"]:
                        error_messages.append(tr_("Jar is not in the roller dispensing position."))

                    if self.status["status_level"] not in allowed_status_levels_:
                        error_messages.append(tr_(f"Status '{self.status['status_level']}' is not allowed for dispensing."))

                    if not self.status["container_presence"]:
                        error_messages.append(tr_("Jar not detected from the ultrasonic sensor under nozzle."))

                    if not error_messages:
                        return None

                    return "\n".join(error_messages)

                step = 0
                outcome_ = ''
                result_ = ''
                cancelled = False
                engaged_circuits_ = []
                disp_type_map = {1: "order", 2: "purge"}
                dispense_timeout = 60 * 24
                try:
                    while step < 2:
                        disp_type = None
                        # msg_ = get_error_messages_for_specific_dispense_condition()
                        msg_ = ""
                        r = await self.app.wait_for_condition(
                            before_dispense_condition, timeout=31,
                            show_alert=False
                        )
                        if r:
                            # ~ jar.update_live(machine_head=self, status='DISPENSING', pos=None, t0=None)
                            jar.update_live(machine_head=self, pos=None, t0=None)

                            if "PURGE ALL" in jar.order.description.upper():

                                pars['items'] = pars.pop("ingredients")

                                r = await self.send_command(
                                    cmd_name="PURGE", type_="macro", params=pars)

                                step = 2

                                disp_type = disp_type_map.get(2)

                            else:

                                _splitted_pars = self.get_splitted_dispense_params(pars, step)
                                step += 1
                                if _splitted_pars.get("ingredients"):

                                    r = await self.send_command(
                                        cmd_name="DISPENSE_FORMULA", type_="macro", params=_splitted_pars)
                                    disp_type = disp_type_map.get(1)
                                else:
                                    continue

                            if r:
                                r = await self.wait_for_status_level(
                                    ["DISPENSING"], timeout=41, show_alert=False
                                )
                                msg_ = tr_("Problem during the start of dispensing. Head status not in standby.")

                                if r:

                                    store_data_on_restore_machine_helper(restore_machine_helper, jar, self.name, "ongoing", disp_type)

                                    self._current_runner['running_engaged_circuits'] = []

                                    # ~ r = await self.wait_for_status_level(["STANDBY"], timeout=60 * 6)
                                    def break_condition():
                                        return self.status["status_level"] in ['ALARM', 'RESET']

                                    r = await self.wait_for_status_level(
                                        ["STANDBY"], timeout=dispense_timeout, show_alert=False, break_condition=break_condition)

                                    engaged_circuits_ += self._current_runner['running_engaged_circuits'][:]
                                    self._current_runner['running_engaged_circuits'] = None
                                    self._current_circuit_engaged = None

                                    if r:
                                        outcome_ += tr_('success (step:{}) ').format(step)
                                        result_ = 'OK'
                                        store_data_on_restore_machine_helper(restore_machine_helper, jar, self.name, "done", disp_type)
                                    else:
                                        outcome_ += tr_('failure during dispensation (step:{}) ').format(step)
                                        outcome_ += "{}, {} ".format(self.status.get("error_code"),
                                                                     tr_(self.status.get("error_message")))
                                        result_ = 'NOK'
                                        store_data_on_restore_machine_helper(restore_machine_helper, jar, self.name, "dispensation_failure", disp_type)
                                        break

                                else:
                                    outcome_ += tr_('failure waiting for dispensation to start (step:{}) ').format(step)
                                    result_ = 'NOK'
                                    store_data_on_restore_machine_helper(restore_machine_helper, jar, self.name, "dispensation_failure", disp_type)
                                    break
                            else:
                                outcome_ += tr_('failure in sending "DISPENSE_FORMULA" command (step:{}) ').format(step)
                                result_ = 'NOK'
                                store_data_on_restore_machine_helper(restore_machine_helper, jar, self.name, "dispensation_failure", disp_type)
                                break
                        else:
                            msg_ = get_error_messages_for_specific_dispense_condition()
                            outcome_ += tr_('failure in waiting for dispensing condition (step:{}) ').format(step)
                            result_ = 'NOK'
                            store_data_on_restore_machine_helper(restore_machine_helper, jar, self.name, "dispensation_failure", disp_type)
                            break
                except asyncio.CancelledError:
                    cancelled = True
                    logging.warning(f"do_dispense cancelled for jar {jar.barcode} on head {self.name}")

                    if self.status.get("status_level") == "DISPENSING":
                        logging.warning(f"waiting for head {self.name} to finish dispensing before cleanup")
                        try:
                            await asyncio.shield(
                                self.wait_for_status_level(
                                    ["STANDBY"], timeout=dispense_timeout,
                                    show_alert=False
                                )
                            )
                            outcome_ += tr_('success (step:{}) ').format(step)
                            result_ = 'OK'
                        except asyncio.CancelledError:
                            logging.warning(f"shield cancelled, head {self.name} may still be dispensing")
                            outcome_ += tr_('cancelled during dispensation (step:{}) ').format(step)
                            result_ = 'NOK'
                    else:
                        outcome_ += tr_('cancelled (step:{}) ').format(step)
                        result_ = 'NOK'

                    if self._current_runner and self._current_runner.get('running_engaged_circuits') is not None:
                        engaged_circuits_ += self._current_runner['running_engaged_circuits'][:]
                        self._current_runner['running_engaged_circuits'] = None
                    self._current_circuit_engaged = None

                ingredients = jar.get_ingredients_for_machine(self)
                if cancelled and result_ == 'OK':
                    # only count ingredients from completed steps (0..step-1)
                    completed_ingredients = {}
                    for completed_step in range(step):
                        step_pars = self.get_splitted_dispense_params(pars, completed_step)
                        for k, v in step_pars.get("ingredients", {}).items():
                            if k in ingredients:
                                completed_ingredients[k] = ingredients[k]
                    ingredients = completed_ingredients

                dispensed_quantities_gr = json_properties.get("dispensed_quantities_gr", {})
                visited_head_names = json_properties.get("visited_head_names", [])
                visited_head_names.append(self.name)

                error_msg = ''
                # ~ if outcome_ == 'success':
                if result_ == 'OK':
                    if "PURGE ALL" not in jar.order.description.upper():
                        json_properties.setdefault("specific_weights", {})
                        json_properties["specific_weights"][self.name] = {}
                        for k, v in ingredients.items():
                            specific_weight = self.get_specific_weight(k)
                            dispensed_quantities_gr[k] = dispensed_quantities_gr.get(
                                k, 0) + round(v * specific_weight, 5)
                            json_properties["specific_weights"][self.name][k] = specific_weight

                        json_properties["dispensed_quantities_gr"] = dispensed_quantities_gr
                        if not cancelled:
                            jar.update_live(machine_head=self, status='PROGRESS', pos=None, t0=None)
                else:
                    error_msg = tr_("ERROR in dispensing:\n") + outcome_
                    if not cancelled:
                        jar.update_live(machine_head=self, status='ERROR', pos=None, t0=None)

                json_properties.setdefault("dispensation_outcomes", [])
                json_properties["dispensation_outcomes"].append((self.name, outcome_))

                json_properties.setdefault("effective_engaged_circuits", {})
                l_ = {ec: self.get_names_by_circuit_id(ec) for ec in engaged_circuits_}
                json_properties["effective_engaged_circuits"][self.name] = l_

                json_properties.setdefault("pipe_formula_ml", {})
                json_properties["pipe_formula_ml"][self.name] = pipe_formula_ml

                json_properties.setdefault("not_dispensed_ingredients", {})
                json_properties["not_dispensed_ingredients"] = jar.get_not_dispensed_ingredients(l_)

                json_properties["visited_head_names"] = visited_head_names
                jar.json_properties = json.dumps(json_properties, indent=2, ensure_ascii=False)
                if not cancelled:
                    dispense_not_successful = True if result_ == 'NOK' else False
                    self.app.update_jar_properties(jar, dispense_not_successful=dispense_not_successful)

                logging.warning(f"error_msg: {error_msg}")
                logging.warning(f"msg_: {msg_}")
                if error_msg and not cancelled:
                    await self.app.wait_for_carousel_not_frozen(
                        True,
                        message_args=(),
                        message_fmt=msg_
                    )

                if cancelled:
                    self._current_runner = None
                    raise asyncio.CancelledError()

        self._current_runner = None
        return True

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
                    logging.warning(f"{self.name}, {output_number}, output:{output}")
                    await self.crx_outputs_management(output_number, 0, timeout=0)

    def __reset_state(self):
        self.status = {}
        self.photocells_status = {}
        self.jar_photocells_status = {}
        self.jar_size_detect = None
        self.websocket = None
        self.last_answer = None

    def __log_document(self, doc_type, extra=None):
        try:
            props = {"index": self.index, "head_name": self.name,
                     "ip": self.ip_add, "ws_port": self.ws_port, "http_port": self.http_port}
            if extra:
                props.update(extra)
            self.app.insert_db_document(
                name=f"MachineHead {self.name}",
                type=doc_type,
                json_properties=json.dumps(props, ensure_ascii=False),
            )
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    @staticmethod
    def __safe_getattr(obj, name, default=None):
        try:
            return getattr(obj, name, default)
        except Exception:  # pylint: disable=broad-except
            return default

    @classmethod
    def __json_safe(cls, value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        name = cls.__safe_getattr(value, "name")
        if name:
            return name
        return str(value)

    @classmethod
    def __close_frame_info(cls, close_frame):
        if close_frame is None:
            return None
        return {
            "code": cls.__safe_getattr(close_frame, "code"),
            "reason": cls.__safe_getattr(close_frame, "reason"),
        }

    @classmethod
    def __websocket_close_info(cls, websocket):
        if websocket is None:
            return {}

        return {
            "websocket_state": cls.__json_safe(cls.__safe_getattr(websocket, "state")),
            "websocket_open": cls.__json_safe(cls.__safe_getattr(websocket, "open")),
            "websocket_closed": cls.__json_safe(cls.__safe_getattr(websocket, "closed")),
            "websocket_close_code": cls.__safe_getattr(websocket, "close_code"),
            "websocket_close_reason": cls.__safe_getattr(websocket, "close_reason"),
            "websocket_close_rcvd": cls.__close_frame_info(cls.__safe_getattr(websocket, "close_rcvd")),
            "websocket_close_sent": cls.__close_frame_info(cls.__safe_getattr(websocket, "close_sent")),
            "websocket_close_rcvd_then_sent": cls.__json_safe(
                cls.__safe_getattr(websocket, "close_rcvd_then_sent")
            ),
        }

    @classmethod
    def __connection_closed_info(cls, exc):
        rcvd = cls.__safe_getattr(exc, "rcvd")
        sent = cls.__safe_getattr(exc, "sent")
        rcvd_frame = cls.__close_frame_info(rcvd)
        sent_frame = cls.__close_frame_info(sent)

        close_code = rcvd_frame["code"] if rcvd_frame else cls.__safe_getattr(exc, "code")
        close_reason = rcvd_frame["reason"] if rcvd_frame else cls.__safe_getattr(exc, "reason")
        if close_code is None:
            close_code = 1006
        if close_reason is None and rcvd_frame is None:
            close_reason = "abnormal closure (no close frame received)"

        return {
            "close_code": close_code,
            "close_reason": close_reason,
            "close_rcvd": rcvd_frame,
            "close_sent": sent_frame,
            "close_rcvd_then_sent": cls.__json_safe(cls.__safe_getattr(exc, "rcvd_then_sent")),
        }

    @staticmethod
    def __printable_msg(msg, limit=2000):
        if msg is None:
            return None
        if isinstance(msg, bytes):
            msg = msg.decode("utf-8", errors="replace")
        if not isinstance(msg, str):
            msg = str(msg)
        if len(msg) > limit:
            msg = msg[:limit] + "...[truncated]"
        return msg

    def __exception_log_extra(self, exc, websocket=None):
        extra = {
            "exception_type": type(exc).__name__,
            "error": str(exc),
            "status": self.status,
            "photocells_status": self.photocells_status,
            "jar_photocells_status": self.jar_photocells_status,
            "ws_id": self.__ws_id,
            "recv_cntr": self.cntr,
            "last_recv_msg": self.__printable_msg(self.__last_recv_msg),
            "traceback": traceback.format_exc(),
        }
        extra.update(self.__websocket_close_info(websocket))
        if isinstance(exc, websockets.exceptions.ConnectionClosed):
            extra.update(self.__connection_closed_info(exc))
        return extra

    async def run(self):
        watchdog_task = asyncio.ensure_future(self.__watch_dog_task())
        websocket_task = asyncio.ensure_future(self.__run_ws_loop())
        supervised_tasks = (
            ("watchdog", watchdog_task),
            ("websocket", websocket_task),
        )
        try:
            done, _pending = await asyncio.wait(
                [task for _label, task in supervised_tasks],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Entrambi i task sono progettati per essere permanenti. Se uno
            # termina, anche normalmente, la testa non puo' proseguire con
            # meta' del proprio runtime attivo.
            for label, task in supervised_tasks:
                if task not in done:
                    continue
                if task.cancelled():
                    raise RuntimeError(
                        "{} task cancelled unexpectedly".format(label)
                    )
                try:
                    task.result()
                except Exception:  # pylint: disable=broad-except
                    logging.error(
                        "%s %s task failed",
                        getattr(self, "name", "MachineHead"), label,
                        exc_info=True,
                    )
                    raise
                raise RuntimeError(
                    "{} task terminated unexpectedly".format(label)
                )
        finally:
            for _label, task in supervised_tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                *(task for _label, task in supervised_tasks),
                return_exceptions=True,
            )

    async def __run_ws_loop(self):

        ws_url = f"ws://{ self.ip_add }:{ self.ws_port }/device:machine:status"
        while True:
            ws_body_exception_id = None
            try:
                # close_timeout low on purpose: on loopback a healthy peer answers the
                # close handshake in ms; a mute peer will never answer and each extra
                # second extends the window in which self.websocket points to a dead socket
                websocket = await websockets.connect(ws_url, close_timeout=5)
                try:
                    self.websocket = websocket
                    self.__ws_id = str(id(websocket))
                    self.__msg_excp_cntr = 0
                    self.__log_document("WS_CONNECTED", {"ws_id": self.__ws_id})
                    try:
                        while True:
                            await self.handle_ws_recv()
                    except asyncio.CancelledError:
                        raise
                    except websockets.exceptions.ConnectionClosed:
                        raise
                    except Exception as e:  # pylint: disable=broad-except
                        ws_body_exception_id = id(e)
                        logging.error(f"{self.name} e:{e}")
                        logging.error(traceback.format_exc())
                        extra = self.__exception_log_extra(e, websocket)
                        extra["phase"] = "websocket message loop"
                        self.__log_document("WS_EXCP", extra)
                        raise
                finally:
                    # equivalent to the async-with __aexit__ (close()), but timed and
                    # logged: WS_CTX_EXIT records who triggered the local close (the
                    # "sent 1000") and whether the peer ever answered the handshake
                    exit_trigger = sys.exc_info()[1]
                    close_t0 = time.time()
                    try:
                        await websocket.close()
                    finally:
                        # fast-fail for send_command during the reconnect window,
                        # instead of raising on a dead socket
                        self.websocket = None
                        extra = self.__websocket_close_info(websocket)
                        extra.update({
                            "ws_id": self.__ws_id,
                            "close_duration": round(time.time() - close_t0, 3),
                            "exit_trigger": type(exit_trigger).__name__ if exit_trigger is not None else None,
                            "exit_trigger_error": str(exit_trigger) if exit_trigger is not None else None,
                        })
                        self.__log_document("WS_CTX_EXIT", extra)
            except asyncio.CancelledError:
                raise
            except (OSError, ConnectionRefusedError,
                    websockets.exceptions.ConnectionClosed) as e:
                logging.error(f"{self.name} e:{e}")
                extra = self.__exception_log_extra(e)
                extra["description"] = "TCP connection failure (ECONNREFUSED) - no service listening on target port" if isinstance(e, ConnectionRefusedError) else None
                self.__log_document("WS_CLOSED", extra)
                # self.__reset_state()
                await asyncio.sleep(5)
            except Exception as e:  # pylint: disable=broad-except
                if ws_body_exception_id != id(e):
                    logging.error(f"{self.name} e:{e}")
                    logging.error(traceback.format_exc())
                    self.__log_document("WS_EXCP", self.__exception_log_extra(e))
                # self.__reset_state()
                await asyncio.sleep(2)
        logging.warning(" *** exiting *** ")

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
                args = (self.name, bit_name, on, status_levels, timeout)
                fmt = 'timeout expired!\n{} bit_name:{}, on:{}, status_levels:{}, timeout:{}.'
                self.app.main_window.open_alert_dialog(args, fmt=fmt, title="ALERT")

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

            ret = await self.app.wait_for_condition(condition, timeout=timeout, show_alert=False)
            logging.warning(f"{self.name} bit_name:{bit_name}, on:{on}, ret:{ret}")

            if not ret and show_alert:
                args = (self.name, bit_name, on, timeout)
                fmt = 'timeout expired!\n{} bit_name:{}, on:{}, timeout:{}.'
                self.app.main_window.open_alert_dialog(args, fmt=fmt, title="ALERT")

            return ret
        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)

    async def get_stabilized_jar_size(self, time_out_sec=3., max_cntr=5):

        t0 = time.time()
        _jar_size_detect = None
        cntr = 0
        ret = None
        while True:

            if _jar_size_detect != self.jar_size_detect:
                _jar_size_detect = self.jar_size_detect
                cntr = 0
            else:
                cntr += 1

            if cntr >= max_cntr:
                ret = self.jar_size_detect
                break

            if time.time() - t0 > time_out_sec:
                break

            await asyncio.sleep(.1)

        return ret

    async def wait_for_status_level(     # pylint: disable=too-many-arguments
            self, status_levels, on=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT, show_alert=True, break_condition=None):

        logging.warning(
            f"{self.name} status_levels:{status_levels}, on:{on}, timeout:{timeout}")

        try:

            def condition():
                flag = self.status["status_level"] in status_levels
                return flag if on else not flag

            ret = await self.app.wait_for_condition(
                condition, timeout=timeout, show_alert=show_alert, break_condition=break_condition)
            logging.warning(
                f"{self.name} status_levels:{status_levels}, on:{on}, ret:{ret}")

            if not ret and show_alert:
                args = (self.name, on, status_levels, timeout)
                fmt = 'timeout expired!\n{} on:{}, status_levels:{}, timeout:{}.'
                self.app.main_window.open_alert_dialog(args, fmt=fmt)

            return ret
        except Exception as e:  # pylint: disable=broad-except
            self.app.handle_exception(e)

    def check_alarm_923(self):

        # ~ 923: 'TINTING_PANEL_TABLE_ERROR'

        status_level = self.status.get("status_level")
        error_code = self.status.get("error_code")
        flag = status_level in ['ALARM', ]
        flag = flag and error_code in [923, '923', 'TINTING_PANEL_TABLE_ERROR']

        return flag

    def get_pigment_list(self):
        result = []
        for _pigment in self.pigment_list:
            colorant_name = _pigment.get('name', '')
            pipe_names = [pipe.get('name', '') for pipe in _pigment.get('pipes', {})]
            for pipe_name in pipe_names:
                result.append((colorant_name, pipe_name))
        return result

    @staticmethod
    def check_jar_photocells_status(status_code, photocell_name):

        photocells_map = {
            "JAR_INPUT_ROLLER_PHOTOCELL": 0x001,
            "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL": 0x002,
            "JAR_OUTPUT_ROLLER_PHOTOCELL": 0x004,
            "LOAD_LIFTER_DOWN_PHOTOCELL": 0x008,
            "LOAD_LIFTER_UP_PHOTOCELL": 0x010,
            "UNLOAD_LIFTER_DOWN_PHOTOCELL": 0x020,
            "UNLOAD_LIFTER_UP_PHOTOCELL": 0x040,
            "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL": 0x080,
            "JAR_DISPENSING_POSITION_PHOTOCELL": 0x100,
            "JAR_DETECTION_MICROSWITCH_1": 0x200,
            "JAR_DETECTION_MICROSWITCH_2": 0x400,
        }

        if photocell_name not in photocells_map:
            raise ValueError(f"Invalid photocell name: {photocell_name}")

        mask = photocells_map[photocell_name]

        # Restituisce True se la photocell è attiva, altrimenti False
        return bool(status_code & mask)

    def get_machine_pigments(self):
        machine_pigments = [p['name'] for p in self.pigment_list if 'name' in p]
        return machine_pigments
