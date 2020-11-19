# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

# ~ import os
import time
import logging
import asyncio
import json
import traceback
import concurrent

from PyQt5.QtWidgets import QApplication    # pylint: disable=no-name-in-module

import websockets                           # pylint: disable=import-error
import aiohttp                              # pylint: disable=import-error
import async_timeout                        # pylint: disable=import-error


DEFAULT_WAIT_FOR_TIMEOUT = 3 * 60
DATA_ROOT = '/opt/alfa_cr6/var/'

EPSILON = 0.00001


class MachineHead(object):           # pylint: disable=too-many-instance-attributes,too-many-public-methods

    """
    # "jar photocells_status" mask bit coding:
    # bit0: JAR_INPUT_ROLLER_PHOTOCELL
    # bit1: JAR_LOAD_LIFTER_ROLLER_PHOTOCELL
    # bit2: JAR_OUTPUT_ROLLER_PHOTOCELL
    # bit3: LOAD_LIFTER_DOWN_PHOTOCELL
    # bit4: LOAD_LIFTER_UP_PHOTOCELL
    # bit5: UNLOAD_LIFTER_DOWN_PHOTOCELL
    # bit6: UNLOAD_LIFTER_UP_PHOTOCELL
    # bit7: JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL
    # bit8: JAR_DISPENSING_POSITION_PHOTOCELL
    # bit9: JAR_DETECTION_MICROSWITCH_1
    # bit10:JAR_DETECTION_MICROSWITCH_2
    """

    def __init__(self, index, ip_add, ws_port, http_port, msg_handler=None, mockup_files_path=None):      # pylint: disable=too-many-arguments

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

        self.ip_add = ip_add
        self.ws_port = ws_port
        self.http_port = http_port
        self.msg_handler = msg_handler
        self.mockup_files_path = mockup_files_path

        self.websocket = None
        self.last_answer = None
        self.cntr = 0
        self.time_stamp = 0

    def __str__(self):
        return f"[{self.index}:{self.name}]"

    def get_available_weight(self, pigment_name):

        available_gr = 0
        specific_weight = 1
        for pig in self.pigment_list:
            if pig['name'] == pigment_name:
                specific_weight = pig["specific_weight"]
                for pipe in pig["pipes"]:
                    if pipe['enabled']:
                        if pipe['effective_specific_weight'] > EPSILON:
                            specific_weight = pipe['effective_specific_weight']
                        available_cc = max(0, pipe['current_level'] - pipe['minimum_level'])
                        if available_cc > EPSILON:
                            available_gr += available_cc * specific_weight

        return available_gr, specific_weight

    async def update_tintometer_data(self, invalidate_cache=False):

        # TODO: invalidate cache when needed
        if invalidate_cache:
            self.pigment_list = []
            self.package_list = []

        if not self.pigment_list:
            ret = await self.call_api_rest('pigment', 'GET', {})

            self.pigment_list = []
            for pig in ret.get('objects', []):
                enabled_pipes = [pipe for pipe in pig['pipes'] if pipe['enabled']]
                if enabled_pipes:
                    self.pigment_list.append(pig)

            if self.pigment_list:
                with open(DATA_ROOT + f"{self.name}_pigment_list.json", 'w') as f:
                    json.dump(self.pigment_list, f, indent=2)
            else:
                with open(DATA_ROOT + f"{self.name}_pigment_list.json", 'r') as f:
                    self.pigment_list = json.load(f)

        if not self.package_list:
            ret = await self.call_api_rest('package', 'GET', {})
            self.package_list = ret.get('objects', [])
            if self.package_list:
                with open(DATA_ROOT + f"{self.name}_package_list.json", 'w') as f:
                    json.dump(self.package_list, f, indent=2)
            else:
                with open(DATA_ROOT + f"{self.name}_package_list.json", 'r') as f:
                    self.package_list = json.load(f)

        logging.warning(f"{self.name} {[p['name'] for p in self.pigment_list]}")

    async def update_status(self, status):

        logging.debug("status:{}".format(status))

        diff = {k: status[k] for k in status if status[k] != self.status.get(k)}

        self.status = status

        # ~ see doc/machine_status_jsonschema.py

        self.photocells_status = {
            'THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL': status['photocells_status'] & 0x001 and 1,
            'THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL': status['photocells_status'] & 0x002 and 1,
            'THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL': status['photocells_status'] & 0x004 and 1,
            'THOR TABLE_PHOTOCELL': status['photocells_status'] & 0x008 and 1,
            'THOR VALVE_OPEN_PHOTOCELL': status['photocells_status'] & 0x010 and 1,
            'THOR AUTOCAP_CLOSE_PHOTOCELL': status['photocells_status'] & 0x020 and 1,
            'THOR AUTOCAP_OPEN_PHOTOCELL': status['photocells_status'] & 0x040 and 1,
            'THOR BRUSH_PHOTOCELL': status['photocells_status'] & 0x080 and 1,
        }

        self.jar_photocells_status = {
            'JAR_INPUT_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x001 and 1,
            'JAR_LOAD_LIFTER_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x002 and 1,
            'JAR_OUTPUT_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x004 and 1,
            'LOAD_LIFTER_DOWN_PHOTOCELL': status['jar_photocells_status'] & 0x008 and 1,
            'LOAD_LIFTER_UP_PHOTOCELL': status['jar_photocells_status'] & 0x010 and 1,
            'UNLOAD_LIFTER_DOWN_PHOTOCELL': status['jar_photocells_status'] & 0x020 and 1,
            'UNLOAD_LIFTER_UP_PHOTOCELL': status['jar_photocells_status'] & 0x040 and 1,
            'JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL': status['jar_photocells_status'] & 0x080 and 1,
            'JAR_DISPENSING_POSITION_PHOTOCELL': status['jar_photocells_status'] & 0x100 and 1,
            'JAR_DETECTION_MICROSWITCH_1': status['jar_photocells_status'] & 0x200 and 1,
            'JAR_DETECTION_MICROSWITCH_2': status['jar_photocells_status'] & 0x400 and 1,
        }

        # ~ self.jar_size_detect = (
        # ~ status['jar_photocells_status'] & 0x200 +
        # ~ status['jar_photocells_status'] & 0x400) >> 9
        s1 = status['jar_photocells_status'] & 0x200
        s2 = status['jar_photocells_status'] & 0x400
        self.jar_size_detect = int(s1 + s2) >> 9

        # ~ logging.warning("self.jar_photocells_status:{}".format(self.jar_photocells_status))
        return diff

    async def call_api_rest(self, path: str, method: str, data: dict, timeout=10):

        r_json_as_dict = {}
        try:
            if self.ip_add:
                url = "http://{}:{}/{}/{}".format(self.ip_add, self.http_port, 'apiV1', path)
                if self.aiohttp_clientsession is None:
                    self.aiohttp_clientsession = aiohttp.ClientSession()
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
            self.app.handle_exception(e)

        return r_json_as_dict

    async def can_movement(self, params=None):
        """ extracted from doc/Specifiche_Funzionamento_Car_Refinishing_REV12.pdf :
        (Please, verify current version of the doc)

        'Dispensing_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement, 2 = Start
        Movement till Photocell transition LIGHT - DARK ','propertyOrder': 1, 'type': 'number', 'fmt': 'B'},

        'Lifter_Roller': {'description': 'Values: 0 = Stop Movement, 1 = Start Movement CW, 2 = Start
        Movement CW till Photocell transition LIGHT - DARK, 3 = Start Movement CCW, 4 = Start Movement CCW
        till Photocell transition DARK - LIGHT, 5 = Start Movement CCW till Photocell transition LIGHT- DARK', 'propertyOrder': 2, 'type': 'number', 'fmt': 'B'},

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

        r = await self.send_command('CAN_MOVEMENT', default)

        logging.debug("CAN_MOVEMENT index:{}, {}".format(self.index, default))

        return r

    async def send_command(self, cmd_name: str, params: dict, type_='command', channel='machine'):
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
                'type': type_,
                'channel': channel,
                'msg_out_dict': {'command': cmd_name, 'params': params},
            }
            if self.websocket:

                logging.warning(f"{self.name} cmd:{msg}")
                self.last_answer = None
                ret = await self.websocket.send(json.dumps(msg))

                if type_ == 'command':
                    def condition():
                        if self.last_answer is not None and \
                                self.last_answer['status_code'] == 0 and \
                                self.last_answer['command'] == cmd_name + '_END':
                            return True
                        return False

                    ret = await self.wait_for_condition(condition, timeout=30)
                    logging.warning(f"{self.name} ret:{ret}, answer:{self.last_answer}")
                else:
                    # TODO: wait for answer from macroprocessor
                    ret = True

        except Exception as e:                           # pylint: disable=broad-except
            self.app.handle_exception(e)
        return ret

    async def run(self):

        ws_url = f"ws://{ self.ip_add }:{ self.ws_port }/device:machine:status"
        while 1:
            try:
                async with websockets.connect(ws_url) as websocket:
                    self.websocket = websocket
                    while 1:
                        await self.handle_ws_recv()
            except ConnectionRefusedError as e:
                logging.error(f"e:{e}")
                await asyncio.sleep(1)
            except Exception as e:                   # pylint: disable=broad-except
                logging.error(f"e:{e}")
                logging.error(traceback.format_exc())
                await asyncio.sleep(2)
        logging.warning(f" *** exiting *** ")

    async def handle_ws_recv(self):

        msg = None
        try:
            # TODO: remove
            # ~ msg = await asyncio.wait_for(self.websocket.recv(), timeout=.5)
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=10)
        except concurrent.futures._base.TimeoutError as e:     # pylint: disable=protected-access
            logging.debug(f"e:{e}")

        self.cntr += 1

        if msg:
            msg_dict = dict(json.loads(msg))

            if msg_dict.get('type') == 'device:machine:status':
                status = msg_dict.get('value')
                status = dict(status)
                if status:
                    diff = await self.update_status(status)
                    if diff:
                        logging.info(f"{self.name} diff:{ diff }")

            elif msg_dict.get('type') == 'answer':
                answer = msg_dict.get('value')
                answer = dict(answer)
                if answer and answer.get('status_code') is not None and answer.get('command') is not None:
                    self.last_answer = answer
                    logging.warning(f"{self.name} answer:{answer}")
            elif msg_dict.get('type') == 'time':
                # ~ logging.warning(f"msg_dict:{msg_dict}")
                time_stamp = msg_dict.get('value')
                if time_stamp:
                    self.time_stamp = time_stamp

            if self.msg_handler:
                await self.msg_handler(self.index, msg_dict)

    async def wait_for_jar_photocells_and_status_lev(self, bit_name, on=True, status_levels=None, timeout=DEFAULT_WAIT_FOR_TIMEOUT):

        if status_levels is None:
            status_levels = ['STANDBY']

        logging.warning(f"{self.name} bit_name:{bit_name}, on:{on}, status_levels:{status_levels}, timeout:{timeout}")

        try:
            def condition():
                flag = self.jar_photocells_status[bit_name] and True
                flag = flag if on else not flag
                flag = flag and self.status['status_level'] in status_levels
                return flag
            ret = await self.wait_for_condition(condition, timeout=timeout, show_alert=False)
            logging.warning(f"{self.name} bit_name:{bit_name}, on:{on}, status_levels:{status_levels}, ret:{ret}")

            if not ret:
                _ = f'timeout expired! {self.name} bit_name:{bit_name}, on:{on}, status_levels:{status_levels}, timeout:{timeout}"'
                self.app.show_alert_dialog(_)
                logging.error(_)

            return ret
        except Exception as e:                           # pylint: disable=broad-except
            self.app.handle_exception(e)

    async def wait_for_jar_photocells_status(self, bit_name, on=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT):
        logging.warning(f"{self.name} bit_name:{bit_name}, on:{on}, timeout:{timeout}")

        try:
            def condition():
                flag = self.jar_photocells_status[bit_name]
                return flag if on else not flag
            ret = await self.wait_for_condition(condition, timeout=timeout, show_alert=False)
            logging.warning(f"{self.name} bit_name:{bit_name}, on:{on}, ret:{ret}")

            if not ret:
                _ = f'timeout expired! {self.name} bit_name:{bit_name}, on:{on}, timeout:{timeout}"'
                self.app.show_alert_dialog(_)
                logging.error(_)

            return ret
        except Exception as e:                           # pylint: disable=broad-except
            self.app.handle_exception(e)

    async def wait_for_status_level(self, status_levels, on=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT):
        logging.warning(f"{self.name} status_levels:{status_levels}, on:{on}, timeout:{timeout}")

        try:
            def condition():
                flag = self.status['status_level'] in status_levels
                return flag if on else not flag
            ret = await self.wait_for_condition(condition, timeout=timeout, show_alert=False)
            logging.warning(f"{self.name} status_levels:{status_levels}, on:{on}, ret:{ret}")

            if not ret:
                _ = f'timeout expired! {self.name} status_levels:{status_levels}, on:{on}, timeout:{timeout}"'
                self.app.show_alert_dialog(_)
                logging.error(_)

            return ret
        except Exception as e:                           # pylint: disable=broad-except
            self.app.handle_exception(e)

    async def wait_for_condition(self, condition, timeout=10, show_alert=True):
        t0 = time.time()
        ret = condition()
        while not ret and time.time() - t0 < timeout:
            await asyncio.sleep(.01)
            ret = condition()
        if not ret:
            logging.error(f'{timeout} sec timeout expired!')
            if show_alert:
                self.app.show_alert_dialog(f'{timeout} sec timeout expired!')
        return ret

    async def do_dispense(self, jar):            # pylint: disable=too-many-locals

        jar_properties = json.loads(jar.json_properties)
        ingredient_volume_map = jar_properties['ingredient_volume_map']
        ingredients = {}
        for pigment_name in ingredient_volume_map.keys():
            if ingredient_volume_map[pigment_name].get(self.name):
                ingredients[pigment_name] = ingredient_volume_map[pigment_name][self.name]

        pars = {'package_name': "******* not valid name ****", 'ingredients': ingredients}
        logging.warning(f"{self.name} pars:{pars}")

        if ingredients:

            def condition():
                flag = self.jar_photocells_status['JAR_DISPENSING_POSITION_PHOTOCELL']
                flag = flag and self.status['status_level'] in ['STANDBY', ]
                flag = flag and self.status['container_presence']
                return flag

            logging.warning(f"{self.name} condition():{condition()}")
            r = await self.wait_for_condition(condition, timeout=30)
            logging.warning(f"{self.name} r:{r}")

            if r:
                r = await self.send_command(cmd_name="DISPENSE_FORMULA", type_='macro', params=pars)
                if r:
                    r = await self.wait_for_status_level(['DISPENSING'], timeout=20)
                    if r:
                        r = await self.wait_for_status_level(['STANDBY'], timeout=60 * 6)

        return r

    async def close(self):

        if self.aiohttp_clientsession:
            await self.aiohttp_clientsession.close()
