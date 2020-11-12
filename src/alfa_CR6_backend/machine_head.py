# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import os
import time
import logging
import asyncio
import json

from PyQt5.QtWidgets import QApplication    # pylint: disable=no-name-in-module

import aiohttp                              # pylint: disable=import-error
import async_timeout                        # pylint: disable=import-error


DEFAULT_WAIT_FOR_TIMEOUT = 8
DATA_ROOT = '/opt/alfa_cr6/var/'


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

    def __init__(self, index, websocket=None, ip_add=None):

        self.index = index
        self.name = QApplication.instance().MACHINE_HEAD_INDEX_TO_NAME_MAP[index]

        self.websocket = websocket
        self.ip_add = ip_add
        self.aiohttp_clientsession = None
        self.status = {}
        self.photocells_status = {}
        self.jar_photocells_status = {}
        self.jar_size_detect = None
        self.pipe_list = []

        self.app = QApplication.instance()

    async def wait_for_jar_photocells_status(self, bit_name, on=True, timeout=DEFAULT_WAIT_FOR_TIMEOUT):
        logging.info(f"{self.name} bit_name:{bit_name}, on:{on}, timeout:{timeout}")

        def condition():
            flag = self.jar_photocells_status[bit_name]
            return flag if on else not flag
        ret = await self.wait_for_condition(condition, timeout=timeout)
        logging.info(f"{self.name} bit_name:{bit_name}, on:{on}, ret:{ret}")
        return ret

    async def wait_for_condition(self, condition, timeout=10):
        t0 = time.time()
        ret = condition()
        while not ret and time.time() - t0 < timeout:
            await asyncio.sleep(.01)
            ret = condition()
        return ret

    async def wait_for_status(self, condition, *args,
                              timeout=DEFAULT_WAIT_FOR_TIMEOUT,
                              msg=None):
        t0 = time.time()
        ret = condition(*args)
        while not ret and time.time() - t0 < timeout:
            await asyncio.sleep(.005)
            ret = condition(*args)
            # ~ logging.info("ret:{}, {:.3f}/{}".format(ret, time.time() - t0, timeout))
        if not ret and msg:
            raise Exception("Timeout on waiting for: {}.".format(msg))
        return ret

    async def trigger_refresh_status_event(self):

        if not hasattr(self, 'refresh_status_event'):
            self.refresh_status_event = asyncio.Event()

        if self.refresh_status_event.is_set():
            self.refresh_status_event.clear()

        self.refresh_status_event.set()
        await asyncio.sleep(.1)  # let the waiters be notified
        self.refresh_status_event.clear()
        logging.warning("{} self.refresh_status_event:{}".format(self.name, self.refresh_status_event))

    async def do_dispense(self, jar):


        logging.warning("self:{}, index:{}, jar:{}".format(self, self.index, jar))
        # TODO: check jar order and dispense, if due

        # ~ await self.send_command(cmd_name="DISPENSE", params={}, type_='command', channel='machine')

        return await asyncio.sleep(3)

    async def update_pipes(self):

        pass
        # ~ ret = await self.call_api_rest('pipe', 'GET', {})
        # ~ self.pipe_list = ret.get('objects', [])

        # ~ logging.debug(f"{self.pipe_list}")

    async def update_status(self, status):

        if not status:
            logging.warning("status:{}".format(status))

        # ~ see doc/machine_status_jsonschema.py

        self.status = status

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

        self.jar_size_detect = (
            status['jar_photocells_status'] & 0x200 +
            status['jar_photocells_status'] & 0x400) >> 9

        # ~ logging.warning("self.jar_photocells_status:{}".format(self.jar_photocells_status))

    async def call_api_rest(self, path: str, method: str, data: dict, timeout=5):

        r_json_as_dict = {}
        if self.ip_add:
            url = "http://{}:{}/{}/{}".format(self.ip_add, 8080, 'apiV1', path)
            if self.aiohttp_clientsession is None:
                self.aiohttp_clientsession = aiohttp.ClientSession()
            r_json_as_dict = {}
            try:
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

    async def send_command(self, cmd_name: str, params: dict, type_='command', channel='machine'):
        """ param 'type_' can be 'command' or 'macro'

            examples:
                self.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
                self.send_command(cmd_name="PURGE", params={'items': [{'name': 'B01', 'qtity': 2.1}, {'name': 'C03', 'qtity': 1.1}, ]}, type_='macro')
        """
        try:
            msg = {
                'type': type_,
                'channel': channel,
                'msg_out_dict': {'command': cmd_name, 'params': params},
            }
            ret = None
            if self.websocket:

                logging.info(f"msg:{msg}")
                t = self.websocket.send(json.dumps(msg))
                asyncio.ensure_future(t)

                # ~ logging.info(f"msg:{msg}")
                # ~ buff = json.dumps(msg).encode()
                # ~ ret = await self.websocket.send(buff)

            else:
                filepth = os.path.join(DATA_ROOT, 'machine_command_{}.json'.format(self.index))
                with open(filepth, 'w') as f:
                    json.dump(msg, f, indent=2)

            return ret

        except Exception as e:                           # pylint: disable=broad-except
            self.app.handle_exception(e)

    async def close(self):

        if self.aiohttp_clientsession:
            await self.aiohttp_clientsession.close()

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

        await self.send_command('CAN_MOVEMENT', default)

        logging.debug("CAN_MOVEMENT index:{}, {}".format(self.index, default))
