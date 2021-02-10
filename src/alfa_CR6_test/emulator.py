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

import websockets  # pylint: disable=import-error

from asyncinotify import Inotify, Mask  # pylint: disable=import-error

HERE = os.path.dirname(os.path.abspath(__file__))

DATA_ROOT = "/opt/alfa_cr6/tmp/"

ID_MAP = [
    ("127.0.0.1", 11001, 8081),
    ("127.0.0.1", 11002, 8082),
    ("127.0.0.1", 11003, 8083),
    ("127.0.0.1", 11004, 8084),
    ("127.0.0.1", 11005, 8085),
    ("127.0.0.1", 11006, 8086),
    # ~ "192.168.15.156",
    # ~ "192.168.15.19",
    # ~ "192.168.15.60",
    # ~ "192.168.15.61",
    # ~ "192.168.15.62",
    # ~ "192.168.15.170",
]


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

    'Dispensing_Roller': {'description': 'Values:
            0 = Stop Movement,
            1 = Start Movement,
            2 = Start Movement till Photocell transition LIGHT - DARK ','propertyOrder': 1, 'type': 'number', 'fmt': 'B'},

    'Lifter_Roller': {'description': 'Values:
        0 = Stop Movement,
        1 = Start Movement CW,
        2 = Start Movement CW till Photocell transition LIGHT - DARK,
        3 = Start Movement CCW,
        4 = Start Movement CCW till Photocell transition DARK – LIGHT,
        5 = Start Movement CCW till Photocell transition LIGHT- DARK', 'propertyOrder': 2, 'type': 'number', 'fmt': 'B'},

    'Input_Roller': {'description': 'Values:
        0 = Stop Movement,
        1 = Start Movement,
        2 = Start Movement till Photocell transition LIGHT - DARK', 'propertyOrder': 3, 'type': 'number', 'fmt': 'B'},

    'Lifter': {'description': 'Values:
        0 = Stop Movement,
        1 = Start Movement Up till Photocell Up transition LIGHT – DARK,
        2 = Start Movement Down till Photocell Down transition LIGHT – DARK', 'propertyOrder': 4, 'type': 'number', 'fmt': 'B'},

    'Output_Roller': {'description': 'Values:
        0 = Stop Movement,
        1 = Start Movement CCW till Photocell transition LIGHT – DARK,
        2 = Start Movement CCW till Photocell transition DARK - LIGHT with a Delay',
        3 = Start Movement', 'propertyOrder': 5, 'type': 'number', 'fmt': 'B'}}}},:
"""

FULL_MASK = 0xFFFFFF
EMPTY_MASK = 0x0000
INPUT_ROLLER_MASK = 0x0001
LOAD_LIFTER_ROLLER_MASK = 0x0002
OUTPUT_ROLLER_MASK = 0x0004
LOAD_LIFTER_DOWN_MASK = 0x0008
LOAD_LIFTER_UP_MASK = 0x0010
UNLOAD_LIFTER_DOWN_MASK = 0x0020
UNLOAD_LIFTER_UP_MASK = 0x0040
UNLOAD_LIFTER_ROLLER_MASK = 0x0080
DISPENSING_POSITION_MASK = 0x0100


class MachineHeadMockup:

    def __init__(self, index):

        self.index = index
        self.letter = ["A", "F", "B", "E", "C", "D"][index]

        self.pending_stop = False

        self.status = {
            "status_level": "STANDBY",
            "cycle_step": 0,
            "error_code": 0,
            "cover_reserve": [0],
            "cover_availability": [1],
            "cover_enabled": [0, 1],
            "container_reserve": [2],
            "container_availability": [0, 2],
            "container_enabled": [1, 2],
            "color_reserve": [],
            "container_presence": False,
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
            "table_cleaning_status": [9],
            "panel_table_status": True,
            "photocells_status": 0,
            "can_available": True,
            "mixer_door_status": True,
            "slave_enable_mask": [1, 11, 18, 19, 24, 25, 26, 27, 28, 29],
            "jar_photocells_status": 0,
            "crx_outputs_status": 0x0,
            "error_message": "NO_ALARM",
            "timestamp": 1603142218.2367265,
            "message_id": 1001758,
            "last_update": "2020-10-19 23:16:58 CEST",
        }

        if self.index == 5:
            self.status["jar_photocells_status"] = 0x0010  # set load_lifter_up_pc
        elif self.index == 1:
            self.status["jar_photocells_status"] = 0x0020  # set load_lifter_down_pc
        else:
            self.status["jar_photocells_status"] = 0x0000  # set load_lifter_up_pc

    def delayed_stop(self):
        if self.pending_stop:
            self.status["status_level"] = "STANDBY"
            self.pending_stop = False
            t = self.dump_status()
            asyncio.ensure_future(t)

    async def update_status(self, params=None):
        if params is None:
            params = {}
        logging.warning("{}, params:{}.".format(self.index, params))
        self.status.update(params)
        await self.dump_status()

    async def do_move(self, mask=EMPTY_MASK, set_or_reset="", duration=0, tgt_level="STANDBY"):

        logging.warning("{} - mask:0x{:04X}, , set_or_reset:{}, , duration:{}, , tgt_level:{}".format(self.letter,
                                                                                                      mask, set_or_reset, duration, tgt_level))

        await asyncio.sleep(duration)
        pars = {"status_level": tgt_level}
        if mask != EMPTY_MASK:
            if set_or_reset == "set":
                pars["jar_photocells_status"] = (
                    self.status["jar_photocells_status"] | mask
                )
            elif set_or_reset == "reset":
                pars["jar_photocells_status"] = (
                    self.status["jar_photocells_status"] & ~mask
                )
            elif set_or_reset == "toggle":
                pars["jar_photocells_status"] = self.status["jar_photocells_status"] ^ mask
            if mask == DISPENSING_POSITION_MASK:
                if set_or_reset == "set":
                    pars["container_presence"] = True
                else:
                    pars["container_presence"] = False

        await self.update_status(params=pars)

    async def handle_command(self, msg_out_dict):  # pylint: disable=too-many-branches,too-many-statements
        logging.warning("{} {}, {}".format(self.index, self.letter, msg_out_dict))

        if msg_out_dict["command"] == "ENTER_DIAGNOSTIC":
            await self.do_move(duration=0.5, tgt_level="DIAGNOSTIC")

        elif msg_out_dict["command"] == "KILL_EMULATOR":
            raise KeyboardInterrupt

        elif msg_out_dict["command"] == "DISPENSATION":
            await self.do_move(duration=0.5, tgt_level="DISPENSING")
            await self.do_move(duration=5, tgt_level="STANDBY")
        elif msg_out_dict["command"] == "RESET":
            await self.do_move(FULL_MASK, "reset", duration=0.1, tgt_level="RESET")
            if self.index == 5:
                await self.do_move(
                    LOAD_LIFTER_UP_MASK, "set", duration=3, tgt_level="STANDBY"
                )
            elif self.index == 1:
                await self.do_move(
                    UNLOAD_LIFTER_DOWN_MASK, "set", duration=3, tgt_level="STANDBY"
                )
                # ~ await self.do_move(OUTPUT_ROLLER_MASK, 'set', duration=3, tgt_level='STANDBY')
            else:
                await self.do_move(duration=3, tgt_level="STANDBY")

        elif msg_out_dict["command"] == "CAN_MOVEMENT":
            dispensing_roller = msg_out_dict["params"]["Dispensing_Roller"]
            lifter_roller = msg_out_dict["params"]["Lifter_Roller"]
            input_roller = msg_out_dict["params"]["Input_Roller"]
            lifter = msg_out_dict["params"]["Lifter"]
            output_roller = msg_out_dict["params"]["Output_Roller"]

            await self.update_status({"status_level": "JAR_POSITIONING"})
            if dispensing_roller + lifter_roller + input_roller + lifter + output_roller == 0:
                await self.do_move(EMPTY_MASK, "set", duration=0.4)
            else:

                if dispensing_roller == 2:
                    await self.do_move(DISPENSING_POSITION_MASK, "set", duration=2)
                elif dispensing_roller == 1:
                    await self.do_move(
                        DISPENSING_POSITION_MASK, "reset", duration=1, tgt_level="JAR_POSITIONING")

                if lifter_roller == 4:
                    await self.do_move(LOAD_LIFTER_ROLLER_MASK, "reset", duration=1)
                    await self.do_move(UNLOAD_LIFTER_ROLLER_MASK, "reset", duration=1)
                elif lifter_roller in (2, 5):
                    await self.do_move(LOAD_LIFTER_ROLLER_MASK, "set", duration=2)
                    await self.do_move(UNLOAD_LIFTER_ROLLER_MASK, "set", duration=2)
                elif lifter_roller in (1, 3):
                    await self.do_move(LOAD_LIFTER_ROLLER_MASK, "toggle", duration=2)
                    await self.do_move(UNLOAD_LIFTER_ROLLER_MASK, "toggle", duration=2)

                if self.index == 1:  # F

                    if lifter == 1:
                        await self.do_move(
                            UNLOAD_LIFTER_DOWN_MASK,
                            "reset",
                            duration=1,
                            tgt_level="JAR_POSITIONING",
                        )
                        await self.do_move(UNLOAD_LIFTER_UP_MASK, "set", duration=2)
                    elif lifter == 2:
                        await self.do_move(
                            UNLOAD_LIFTER_UP_MASK,
                            "reset",
                            duration=1,
                            tgt_level="JAR_POSITIONING",
                        )
                        await self.do_move(UNLOAD_LIFTER_DOWN_MASK, "set", duration=2)
                    elif dispensing_roller == 1 and lifter_roller == 5:
                        await self.do_move(
                            UNLOAD_LIFTER_DOWN_MASK,
                            "reset",
                            duration=1,
                            tgt_level="JAR_POSITIONING",
                        )
                        await self.do_move(UNLOAD_LIFTER_UP_MASK, "set", duration=2)
                        await self.do_move(OUTPUT_ROLLER_MASK, "set", duration=2)

                elif self.index == 5:  # C
                    if lifter == 1:  # 'DOWN -> UP'
                        await self.do_move(
                            LOAD_LIFTER_DOWN_MASK, "reset", duration=1, tgt_level="JAR_POSITIONING")
                        await self.do_move(LOAD_LIFTER_UP_MASK, "set", duration=2)
                    elif lifter == 2:  # 'UP -> DOWN'
                        await self.do_move(
                            LOAD_LIFTER_UP_MASK, "reset", duration=1, tgt_level="JAR_POSITIONING")
                        await self.do_move(LOAD_LIFTER_DOWN_MASK, "set", duration=2)

                if input_roller == 2:  # feed = move_00_01 or -> IN
                    await self.do_move(INPUT_ROLLER_MASK, "set", duration=2)
                elif input_roller == 1 and dispensing_roller == 2:  # move_01_02 or IN -> A
                    await self.do_move(
                        INPUT_ROLLER_MASK,
                        "reset",
                        duration=1,
                        tgt_level="JAR_POSITIONING",
                    )
                    await self.do_move(DISPENSING_POSITION_MASK, "set", duration=2)
                elif input_roller == 0 and dispensing_roller == 1:  # move_02_03 or  # 'A -> B'
                    await self.do_move(DISPENSING_POSITION_MASK, "reset", duration=2)

                if output_roller == 1:
                    await self.do_move(OUTPUT_ROLLER_MASK, "set", duration=2)
                elif output_roller == 2:
                    await self.do_move(OUTPUT_ROLLER_MASK, "reset", duration=4)
        elif msg_out_dict["command"] == "CRX_OUTPUTS_MANAGEMENT":
            output_number = int(msg_out_dict["params"]["Output_Number"])
            output_action = int(msg_out_dict["params"]["Output_Action"])
            mask = 0x1 << output_number

            if output_action:
                crx_outputs_status = self.status["crx_outputs_status"] | mask
            else:
                crx_outputs_status = self.status["crx_outputs_status"] & ~mask

            await self.update_status(params={"crx_outputs_status": crx_outputs_status})

            await asyncio.sleep(2)
            pars = self.do_move_by_crx_outputs(output_number, output_action)
            await self.update_status(params=pars)

    def do_move_by_crx_outputs(self, output_number, output_action):  # pylint: disable=too-many-branches,too-many-statements

        """
        # ~ 'Output_Number': {'propertyOrder': 1, 'type': 'number', 'fmt': 'B',
        # ~ 'description': "Outupt (roller or lifter) identification number related to a dispensing head. Values comprised between 0 - 3"},
        # ~ 'Output_Action': {'propertyOrder': 2, 'type': 'number', 'fmt': 'B',
        # ~ 'description': "Values:
        # ~ 0 = Stop Movement,
        # ~ 1 = Start Movement CW,
        # ~ 2 = Start Movement CW or UP till Photocell transition LIGHT - DARK,
        # ~ 3 = Start Movement CW or UP till Photocell transition DARK - LIGHT,
        # ~ 4 = Start Movement CCW,
        # ~ 5 = Start Movement CCW or DOWN till Photocell transition LIGHT - DARK,
        # ~ 6 = Start Movement CCW or DOWN till Photocell transition DARK - LIGHT"}}}},

        # Outputs meaning for each dispensing head:
        # TESTA1: A 0 = DOSING ROLLER, 1 = INPUT ROLLER,
        # TESTA2: F 0 = DOSING ROLLER, 1 = LIFTER_ROLLER, 2 = OUTPUT_ROLLER, 3 = LIFTER
        # TESTA3: B 0 = DOSING ROLLER
        # TESTA4: E 0 = DOSING ROLLER
        # TESTA5: C 0 = DOSING ROLLER, 1 = LIFTER_ROLLER,
        # TESTA6: D 0 = DOSING ROLLER, 1 = LIFTER
        """

        pars = {}

        if output_number == 0:
            if output_action in (1, 4):
                current_bit_val = self.status["jar_photocells_status"] & DISPENSING_POSITION_MASK
                pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~current_bit_val
            elif output_action in (2, 5):
                pars["jar_photocells_status"] = self.status["jar_photocells_status"] | DISPENSING_POSITION_MASK
            elif output_action in (3, 6):
                pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~DISPENSING_POSITION_MASK
        else:
            if self.letter == 'A':
                if output_number == 1:
                    if output_action in (1, 3):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~INPUT_ROLLER_MASK
                    elif output_action in (2, ):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | INPUT_ROLLER_MASK

                    pars["crx_outputs_status"] = self.status["crx_outputs_status"] & ~0x02

            elif self.letter == 'B':
                pass

            elif self.letter == 'C':
                if output_number == 1:
                    if output_action in (1, 4):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] ^ LOAD_LIFTER_ROLLER_MASK
                    elif output_action in (2, 5):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | LOAD_LIFTER_ROLLER_MASK
                    elif output_action in (3, 6):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~LOAD_LIFTER_ROLLER_MASK

            elif self.letter == 'D':
                if output_number == 1:
                    if output_action in (2, 3):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | LOAD_LIFTER_UP_MASK
                        pars["jar_photocells_status"] = pars["jar_photocells_status"] & ~LOAD_LIFTER_DOWN_MASK
                    elif output_action in (5, 6):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | LOAD_LIFTER_DOWN_MASK
                        pars["jar_photocells_status"] = pars["jar_photocells_status"] & ~LOAD_LIFTER_UP_MASK

                    pars["crx_outputs_status"] = self.status["crx_outputs_status"] & ~0x02

            elif self.letter == 'E':
                pass

            elif self.letter == 'F':
                if output_number == 1:
                    if output_action in (1, 4):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] ^ UNLOAD_LIFTER_ROLLER_MASK
                    elif output_action in (2, 5):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | UNLOAD_LIFTER_ROLLER_MASK
                    elif output_action in (3, 6):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~UNLOAD_LIFTER_ROLLER_MASK

                    pars["crx_outputs_status"] = self.status["crx_outputs_status"] & ~0x02

                elif output_number == 2:
                    if output_action in (1, 4):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] ^ OUTPUT_ROLLER_MASK
                    elif output_action in (2, 5):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | OUTPUT_ROLLER_MASK
                    elif output_action in (3, 6):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~OUTPUT_ROLLER_MASK

                    pars["crx_outputs_status"] = self.status["crx_outputs_status"] & ~0x04

                elif output_number == 3:
                    if output_action in (2, 3):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | UNLOAD_LIFTER_UP_MASK
                        pars["jar_photocells_status"] = pars["jar_photocells_status"] & ~UNLOAD_LIFTER_DOWN_MASK
                    elif output_action in (5, 6):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] | UNLOAD_LIFTER_DOWN_MASK
                        pars["jar_photocells_status"] = pars["jar_photocells_status"] & ~UNLOAD_LIFTER_UP_MASK

                    pars["crx_outputs_status"] = self.status["crx_outputs_status"] & ~0x08

        logging.warning(f"{self.letter}, pars:{pars}")
        return pars

    async def dump_status(self):
        raise Exception(f"to be overidden in {self}")


class MachineHeadMockupWsSocket(MachineHeadMockup):
    def __init__(self, index):

        self.index = index

        self.ws_host, self.ws_port = ID_MAP[index][0], ID_MAP[index][1]
        logging.warning(
            "self.ws_host:{}, self.ws_port:{}".format(self.ws_host, self.ws_port)
        )

        self.ws_clients = []
        self.timer_step = 1

        asyncio.ensure_future(self._time_notifier())

        super().__init__(index)

    async def _time_notifier(self):

        while True:
            ts_ = datetime.now().astimezone().strftime("%d %b %Y (%I:%M:%S %p) %Z")
            value = "{}".format(ts_)
            message = json.dumps({"type": "time", **{"value": value}})
            for client in self.ws_clients:
                asyncio.ensure_future(client.send(message))
            await asyncio.sleep(self.timer_step)

    async def _handle_client_msg(self, ws_client, msg):

        msg_dict = json.loads(msg)
        # ~ logging.warning("msg_dict:{}".format(msg_dict))
        # ~ channel = msg_dict['channel']
        msg_out_dict = msg_dict["msg_out_dict"]

        await self.handle_command(msg_out_dict)

        answer = {
            "status_code": 0,
            "error": "no error",
            "reply_to": None,
            "ref_id": 42,
            "timestamp": time.time(),
            "command": msg_out_dict["command"] + "_END",
        }

        msg = json.dumps({"type": "answer", "value": answer})
        # ~ logging.warning("{} msg:{}".format(self.index, msg))
        asyncio.ensure_future(ws_client.send(msg))

    async def _new_client_handler(self, ws_client, path):

        self.ws_clients.append(ws_client)
        logging.warning(
            "self.ws_host:{}, self.ws_port:{}, self.ws_clients:{}, path:{}".format(
                self.ws_host, self.ws_port, self.ws_clients, path
            )
        )

        await self.dump_status()
        async for message in ws_client:  # start listening for messages from ws client
            await self._handle_client_msg(ws_client, message)

    async def command_watcher(self,):

        await websockets.serve(self._new_client_handler, self.ws_host, self.ws_port)
        # ~ ensure_future(websockets.serve(self._new_client_handler, self.ws_host, self.ws_port))

    async def dump_status(self):

        message = json.dumps(
            {"type": "device:machine:status", **{"value": self.status}}
        )
        for client in self.ws_clients:
            await client.send(message)


class MachineHeadMockupFile(MachineHeadMockup):
    def __init__(self, index):

        pth = os.path.join(DATA_ROOT, "machine_status_{}.json".format(self.index))
        with open(pth) as f:
            self.status = json.load(f)

        filepth = os.path.join(DATA_ROOT, "machine_command_{}.json".format(self.index))
        with open(filepth, "w") as f:
            json.dump({}, f)

        super().__init__(index)
        self.update_status(
            {"status_level": "IDLE", "jar_photocells_status": 0x0000}
        )  # reset all pc

    async def dump_status(self):
        pth = os.path.join(DATA_ROOT, "machine_status_{}.json".format(self.index))
        with open(pth, "w") as f:
            json.dump(self.status, f, indent=2)
            logging.warning(
                "index:{} status_level:{}".format(
                    self.index, self.status["status_level"]
                )
            )

    async def command_watcher(self,):
        filepth = os.path.join(DATA_ROOT, "machine_command_{}.json".format(self.index))
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
                            self.handle_command(msg["msg_out_dict"])
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

    fmt_ = (
        "[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s"
    )
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

    loop = asyncio.get_event_loop()
    tasks = []
    try:
        tasks = create_and_run_tasks()
        for t in tasks:
            asyncio.ensure_future(t)
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("KeyboardInterrupt: shutting down")
    except Exception as e:
        print(f"Exception:{e}")
    finally:
        loop.call_later(1, loop.stop)
        loop.run_until_complete(loop.shutdown_asyncgens())


main()
