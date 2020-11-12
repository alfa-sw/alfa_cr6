# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except
# pylint: disable=function-redefined

import sys
import os
import time
import logging
import traceback
import asyncio
import json

from datetime import datetime

import websockets      # pylint: disable=import-error

from asyncinotify import Inotify, Mask  # pylint: disable=import-error

HERE = os.path.dirname(os.path.abspath(__file__))

DATA_ROOT = '/opt/alfa_cr6/var/'

ID_MAP = [
    ('127.0.0.1', 11001, 8081),
    ('127.0.0.1', 11002, 8082),
    ('127.0.0.1', 11003, 8083),
    ('127.0.0.1', 11004, 8084),
    ('127.0.0.1', 11005, 8085),
    ('127.0.0.1', 11006, 8086),
    # ~ "192.168.15.156",
    # ~ "192.168.15.19",
    # ~ "192.168.15.60",
    # ~ "192.168.15.61",
    # ~ "192.168.15.62",
    # ~ "192.168.15.170",
]


class MachineHeadMockup:

    """
        # bit0: JAR_INPUT_ROLLER_PHOTOCELL         0000 0000 0001  | 0x0001
        # bit1: JAR_LOAD_LIFTER_ROLLER_PHOTOCELL   0000 0000 0010  | 0x0002
        # bit2: JAR_OUTPUT_ROLLER_PHOTOCELL        0000 0000 0100  | 0x0004
        # bit3: LOAD_LIFTER_DOWN_PHOTOCELL         0000 0000 1000  | 0x0008
        # bit4: LOAD_LIFTER_UP_PHOTOCELL           0000 0001 0000  | 0x0010
        # bit5: UNLOAD_LIFTER_DOWN_PHOTOCELL       0000 0010 0000  | 0x0020
        # bit6: UNLOAD_LIFTER_UP_PHOTOCELL         0000 0100 0000  | 0x0040
        # bit7: JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL 0000 1000 0000  | 0x0080
        # bit8: JAR_DISPENSING_POSITION_PHOTOCELL  0001 0000 0000  | 0x0100
        # bit9: JAR_DETECTION_MICROSWITCH_1        0010 0000 0000  | 0x0200
        # bit10:JAR_DETECTION_MICROSWITCH_2        0100 0000 0000  | 0x0400
    """

    def __init__(self, index):

        self.index = index
        self.pending_stop = False

        self.status = {
            "status_level": "STANDBY",
            "cycle_step": 0,
            "error_code": 0,
            "cover_reserve": [
                0
            ],
            "cover_availability": [
                1
            ],
            "cover_enabled": [
                0,
                1
            ],
            "container_reserve": [
                2
            ],
            "container_availability": [
                0,
                2
            ],
            "container_enabled": [
                1,
                2
            ],
            "color_reserve": [],
            "container_presence": True,
            "autocap_status": True,
            "canlift_status": False,
            "doors_status": True,
            "clamp_position": 0,
            "recirculation_status": [],
            "stirring_status": [],
            "slave_status": [],
            "can_on_plate": True,
            "can_lifter_current_height": 419.4304,
            "can_lifter_range": 838.8608,
            "current_temperature": 49.6,
            "current_rel_humidity": 433.6,
            "water_level": True,
            "critical_temperature": True,
            "temperature": 49.6,
            "bases_carriage": False,
            "circuit_engaged": 16,
            "table_steps_position": 47115,
            "autotest_cycles_number": 1280,
            "table_cleaning_status": [
                9
            ],
            "panel_table_status": True,
            "photocells_status": 0,
            "can_available": True,
            "mixer_door_status": True,
            "slave_enable_mask": [
                1,
                11,
                18,
                19,
                24,
                25,
                26,
                27,
                28,
                29
            ],
            "jar_photocells_status": 0,
            "error_message": "NO_ALARM",
            "timestamp": 1603142218.2367265,
            "message_id": 1001758,
            "last_update": "2020-10-19 23:16:58 CEST"
        }

        if self.index == 5:
            self.status['jar_photocells_status'] = 0x0010  # set load_lifter_up_pc
        elif self.index == 1:
            self.status['jar_photocells_status'] = 0x0020  # set load_lifter_down_pc
        else:
            self.status['jar_photocells_status'] = 0x0000  # set load_lifter_up_pc

    def delayed_stop(self):
        if self.pending_stop:
            self.status['status_level'] = 'STANDBY'
            self.pending_stop = False
            t = self.dump_status()
            asyncio.ensure_future(t)

    async def update_status(self, params):
        logging.warning("{}, params:{}.".format(self.index, params))
        self.status.update(params)
        # ~ t = self.dump_status()
        # ~ asyncio.ensure_future(t)
        await self.dump_status()

    async def handle_command(self, msg_out_dict):       # pylint: disable=too-many-branches,too-many-statements
        logging.warning("{}, {}".format(self.index, msg_out_dict))

        target = None
        args = []
        delay = 0

        if msg_out_dict['command'] == 'KILL_EMULATOR':
            self.__close_app()
        elif msg_out_dict['command'] == 'ENTER_DIAGNOSTIC':
            target = self.update_status
            args = [{"status_level": "DIAGNOSTIC"}, ]
            delay = .5

        elif msg_out_dict['command'] == 'DISPENSE':
            await self.update_status({'status_level': 'JAR_POSITIONING'})
            target = self.update_status
            args = [{"status_level": "STANDBY"}, ]
            delay = 2

        elif msg_out_dict['command'] == 'RESET':

            if self.index == 5:
                self.status['jar_photocells_status'] = 0x0010  # set load_lifter_up_pc
            elif self.index == 1:
                self.status['jar_photocells_status'] = 0x0020  # set load_lifter_down_pc
            else:
                self.status['jar_photocells_status'] = 0x0000  # set load_lifter_up_pc

            await self.update_status({"status_level": "RESET"})
            target = self.update_status
            args = [{"status_level": "STANDBY"}, ]
            delay = 2

        elif msg_out_dict['command'] == 'CAN_MOVEMENT':

            dispensing_roller = msg_out_dict['params']['Dispensing_Roller']
            lifter_roller = msg_out_dict['params']['Lifter_Roller']
            input_roller = msg_out_dict['params']['Input_Roller']
            lifter = msg_out_dict['params']['Lifter']
            output_roller = msg_out_dict['params']['Output_Roller']

            if dispensing_roller + lifter_roller + input_roller + lifter == 0:
                await self.update_status({'status_level': 'STANDBY'})
            else:
                await self.update_status({'status_level': 'JAR_POSITIONING'})

                delay = 2
                target = self.update_status
                args = []

                if self.index == 0:  # A
                    if input_roller == 2 and dispensing_roller == 0:  # feed = move_00_01
                        args += [{  # set load_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] | 0x0001,
                            'status_level': 'STANDBY'}, ]
                    elif input_roller == 1 and dispensing_roller == 2:  # feed = move_01_02
                        args += [{  # reset load_pc # set dispensig_pc
                            'jar_photocells_status': (self.status['jar_photocells_status'] & ~ 0x0001) | 0x0100,
                            'status_level': 'STANDBY'}, ]
                    elif input_roller == 0 and dispensing_roller == 1:  # move_02_03(self):  # 'A -> B'
                        args += [{  # reset dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100}, ]
                    else:
                        await self.update_status({'status_level': 'STANDBY'})

                if self.index == 2:  # B
                    if dispensing_roller == 2:  # move_02_03(self):  # 'A -> B'
                        args += [{  # set dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                            'status_level': 'STANDBY'}, ]
                    if dispensing_roller == 1:  # move_03_04(self):  # 'B -> c'
                        args += [{  # reset dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100}, ]

                if self.index == 4:  # C
                    if dispensing_roller == 2:  # move_03_04(self):  # 'B -> C'
                        args += [{  # set dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                            'status_level': 'STANDBY'}, ]

                    if dispensing_roller == 1:
                        args += [{  # reset dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100}, ]

                    if lifter_roller == 1 or lifter_roller == 5:
                        args += [{  # reset load_lifter_roller_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0002}, ]

                    if lifter_roller == 2 or lifter_roller == 3:
                        args += [{  # set load_lifter_roller_pc
                            'jar_photocells_status': (self.status['jar_photocells_status'] | 0x0002) & ~ 0x0100,
                            'status_level': 'STANDBY'}, ]

                if self.index == 5:  # D
                    if dispensing_roller == 2:  # move_02_03(self):  # 'A -> B'
                        args += [{  # set dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                            'status_level': 'STANDBY'}, ]
                    if dispensing_roller == 1:  # move_03_04(self):  # 'B -> c'
                        args += [{  # reset dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100}, ]

                    if lifter == 1:         # 'DOWN -> UP'
                        args += [{  # set load_lifter_up_pc # reset load_lifter_down_pc
                            'jar_photocells_status': (self.status['jar_photocells_status'] | 0x0010) & ~ 0x0008,
                            'status_level': 'STANDBY'}, ]
                    if lifter == 2:         # 'UP -> DOWN'
                        args += [{  # reset load_lifter_up_pc # set load_lifter_down_pc
                            'jar_photocells_status': (self.status['jar_photocells_status'] & ~ 0x0010) | 0x0008,
                            'status_level': 'STANDBY'}, ]
                if self.index == 3:  # E
                    if dispensing_roller == 2:
                        args += [{  # set dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                            'status_level': 'STANDBY'}, ]
                    if dispensing_roller == 1:
                        args += [{  # reset dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100}, ]

                if self.index == 1:  # F

                    # ~ await F.can_movement({'Dispensing_Roller': 2})                              move_08_09
                    # ~ await F.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 5})          move_09_10
                    # ~ await F.can_movement({'Output_Roller': 2})                                  move_10_11
                    # ~ await F.can_movement({'Lifter_Roller': 3, 'Output_Roller': 1})              move_10_11
                    # ~ await F.can_movement({'Lifter': 2, 'Output_Roller': 2})                     move_11_12
                    if dispensing_roller == 2:                              # move_08_09
                        args += [{  # set dispensig_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                            'status_level': 'STANDBY'}, ]
                    elif dispensing_roller == 1 and lifter_roller == 5:   # move_09_10
                        args += [{  # set load_lifter_roller_pc
                            'jar_photocells_status': (self.status['jar_photocells_status'] | 0x0080) & ~ 0x0100,}, ]
                        args += [{  # set dispensig_pc
                            'jar_photocells_status': (self.status['jar_photocells_status'] & ~ 0x0008) | 0x0010}, ]
                        args += [{  # reset load_lifter_roller_pc
                            'jar_photocells_status': (self.status['jar_photocells_status'] & ~ 0x0080) | 0x0004}, ]
                    elif lifter == 2 and output_roller == 2:  # move_11_12
                        args += [{  # set load_lifter_roller_pc
                            'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0004,
                            'status_level': 'STANDBY'}, ]

        if target is not None:
            for arg in args:
                await asyncio.sleep(delay)
                await target(arg)
                logging.warning("{}, delay:{}, arg:{}.".format(self.index, delay, arg))
            # ~ asyncio.get_event_loop().call_later(delay, target, *args)

    async def dump_status(self):
        raise Exception(f"to be overidden in {self}")


    def __close_app(self):
        raise KeyboardInterrupt

class MachineHeadMockupWsSocket(MachineHeadMockup):

    def __init__(self, index):

        self.index = index

        self.ws_host, self.ws_port = ID_MAP[index][0], ID_MAP[index][1]
        logging.warning("self.ws_host:{}, self.ws_port:{}".format(self.ws_host, self.ws_port))

        self.ws_clients = []
        self.timer_step = 1

        asyncio.ensure_future(self._time_notifier())

        super().__init__(index)

    async def _time_notifier(self):

        while 1:
            ts_ = datetime.now().astimezone().strftime("%d %b %Y (%I:%M:%S %p) %Z")
            value = "{}".format(ts_)
            message = json.dumps({'type': 'time', **{'value': value}})
            for client in self.ws_clients:
                asyncio.ensure_future(client.send(message))
            await asyncio.sleep(self.timer_step)

    async def _handle_client_msg(self, ws_client, msg):

        msg_dict = json.loads(msg)
        # ~ logging.warning("msg_dict:{}".format(msg_dict))
        # ~ channel = msg_dict['channel']
        msg_out_dict = msg_dict['msg_out_dict']

        await self.handle_command(msg_out_dict)

        answer = {
            "status_code": 0,
            "error": "no error",
            "reply_to": None,
            "ref_id": 42,
            "timestamp": time.time(),
            "command": msg_out_dict["command"] + "_END"
        }

        msg = json.dumps({'type': 'answer', 'value': answer})
        # ~ logging.warning("{} msg:{}".format(self.index, msg))
        asyncio.ensure_future(ws_client.send(msg))

    async def _new_client_handler(self, ws_client, path):

        self.ws_clients.append(ws_client)
        logging.warning(
            "self.ws_host:{}, self.ws_port:{}, self.ws_clients:{}, path:{}".format(
                self.ws_host, self.ws_port, self.ws_clients, path))

        await self.dump_status()
        async for message in ws_client:  # start listening for messages from ws client
            await self._handle_client_msg(ws_client, message)

    async def command_watcher(self,):

        await websockets.serve(self._new_client_handler, self.ws_host, self.ws_port)
        # ~ ensure_future(websockets.serve(self._new_client_handler, self.ws_host, self.ws_port))

    async def dump_status(self):

        message = json.dumps({'type': 'device:machine:status', **{'value': self.status}})
        for client in self.ws_clients:
            await client.send(message)


class MachineHeadMockupFile(MachineHeadMockup):

    def __init__(self, index):

        pth = os.path.join(DATA_ROOT, 'machine_status_{}.json'.format(self.index))
        with open(pth) as f:
            self.status = json.load(f)

        filepth = os.path.join(DATA_ROOT, 'machine_command_{}.json'.format(self.index))
        with open(filepth, 'w') as f:
            json.dump({}, f)

        super().__init__(index)
        self.update_status({'status_level': 'IDLE', 'jar_photocells_status': 0x0000})  # reset all pc

    async def dump_status(self):
        pth = os.path.join(DATA_ROOT, 'machine_status_{}.json'.format(self.index))
        with open(pth, 'w') as f:
            json.dump(self.status, f, indent=2)
            logging.warning("index:{} status_level:{}".format(self.index, self.status['status_level']))

    async def command_watcher(self,):
        filepth = os.path.join(DATA_ROOT, 'machine_command_{}.json'.format(self.index))
        with Inotify() as inotify:
            # ~ inotify.add_watch(filepth, Mask.MODIFY)
            inotify.add_watch(filepth, Mask.CLOSE)
            # ~ inotify.add_watch(filepth,  Mask.CREATE)
            t0 = 0
            async for event in inotify:
                logging.debug(f"event:{event}")
                if time.time() - t0 > 0.010:
                    t0 = time.time()
                    try:
                        with open(filepth) as f:
                            msg = json.load(f)
                            self.handle_command(msg['msg_out_dict'])
                            await self.dump_status()
                    except Exception:
                        logging.error(f"error reading:{filepth}")
                        logging.error(traceback.format_exc())


def create_and_run_tasks():

    machine_heads = [MachineHeadMockupWsSocket(i) for i in range(6)]
    tasks = [m.command_watcher() for m in machine_heads]
    # ~ asyncio.ensure_future(t)

    # ~ res = await asyncio.gather(*tasks, return_exceptions=True)

    # ~ logging.warning(f" *** terminating tasks  *** ")
    return tasks 


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

    loop = asyncio.get_event_loop()
    tasks = []
    try:
        tasks = create_and_run_tasks()
        for t in tasks:
            asyncio.ensure_future(t)
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print('KeyboardInterrupt: shutting down')
    except Exception as e:
        print(f'Exception:{e}')
    finally:
        loop.call_later(1, loop.stop)
        loop.run_until_complete(loop.shutdown_asyncgens())


main()
