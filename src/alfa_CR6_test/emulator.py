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

        self.pigment_list = []

        pth = os.path.join(DATA_ROOT, f"{self.letter}_pigment_list.json")
        with open(pth) as f:
            self.pigment_list = json.load(f)

        # ~ logging.info("{} {}, {}".format(self.index, self.letter, self.pigment_list))

        if self.letter == "D":
            def _start_load_liftr_up():
                msg_out_dict = {
                    "command": "CRX_OUTPUTS_MANAGEMENT",
                    "params": {"Output_Number": 1, "Output_Action": 2}
                }
                asyncio.ensure_future(self.handle_command(msg_out_dict))
                msg_out_dict = {
                    "command": "CRX_OUTPUTS_MANAGEMENT",
                    "params": {"Output_Number": 1, "Output_Action": 0}
                }
                asyncio.ensure_future(self.handle_command(msg_out_dict))
            asyncio.get_event_loop().call_later(3, _start_load_liftr_up)

        elif self.letter == "F":
            def _start_unload_liftr_down():
                msg_out_dict = {
                    "command": "CRX_OUTPUTS_MANAGEMENT",
                    'params': {'Output_Number': 3, 'Output_Action': 5}
                }
                asyncio.ensure_future(self.handle_command(msg_out_dict))
                msg_out_dict = {
                    "command": "CRX_OUTPUTS_MANAGEMENT",
                    'params': {'Output_Number': 3, 'Output_Action': 0}
                }
                asyncio.ensure_future(self.handle_command(msg_out_dict))

            asyncio.get_event_loop().call_later(5, _start_unload_liftr_down)

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
        try:
            def fmt(x):
                if isinstance(x, int):
                    ret = f"0x{x:02X}"
                else:
                    ret = f"{x}"
                return ret
                    
            logging.info("{}:{}, params:{}.".format(self.index, self.letter, {k: fmt(v) for k, v in params.items()}))
            self.status.update(params)
            await self.dump_status()
        except:
            logging.error(traceback.format_exc())

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

    def get_pipes_from_pig_name(self, pig_name, weight):

        SLAVES_ADDRESSES = {}
        base_pipe_addresses = { "B%02d"%(i + 1): i for i in range(0, 8)}
        colorant_pipe_addresses = { "C%02d"%(i - 7): i for i in range(8, 32)}
        SLAVES_ADDRESSES.update(base_pipe_addresses)
        SLAVES_ADDRESSES.update(colorant_pipe_addresses)

        pipes_ = []
        for pig in self.pigment_list:
            if pig["name"] == pig_name:
                pipes_ += [SLAVES_ADDRESSES[p["name"]] for p in pig["pipes"]]
        return [(p, weight / len(pipes_)) for p in pipes_]

    async def handle_command(self, msg_out_dict):  # pylint: disable=too-many-branches,too-many-statements

        logging.info("{} {}, {}".format(self.index, self.letter, msg_out_dict))

        if msg_out_dict["command"] == "ENTER_DIAGNOSTIC":
            await self.do_move(duration=0.5, tgt_level="DIAGNOSTIC")

        elif msg_out_dict["command"] == "SIMULATE_ALARM":
            await self.update_status(
                params={"status_level": "ALARM", "error_code": 0xFF, "error_message": "TIMERMG_TEST_FAILED",})

        elif msg_out_dict["command"] == "KILL_EMULATOR":
            raise KeyboardInterrupt

        elif msg_out_dict["command"] in ("DISPENSATION", "DISPENSE_FORMULA", "PURGE"):

            logging.warning("{} {}, {}".format(self.index, self.letter, msg_out_dict))
            try:
                pipes_ = []
                for pig_name, weight in msg_out_dict.get('params', {}).get('ingredients', {}).items():
                    pipes__ = self.get_pipes_from_pig_name(pig_name, weight)
                    pipes_ += pipes__
            except Exception:
                logging.error(traceback.format_exc())
            logging.warning(f"pipes_:{pipes_}")

            async def simulate_circuit_engagement():
                for p in pipes_:
                    
                    pars = {"circuit_engaged": p[0]}
                    logging.warning(f"pars:{pars}")
                    await self.update_status(params=pars)
                    await asyncio.sleep(2)

                    pars = {"circuit_engaged": 0}
                    logging.warning(f"pars:{pars}")
                    await self.update_status(params=pars)
                    await asyncio.sleep(2)

            asyncio.ensure_future(simulate_circuit_engagement())

            await self.do_move(duration=0.5, tgt_level="DISPENSING")

            if 'failure' in sys.argv:
                await asyncio.sleep(3)
                await self.update_status(
                    params={"status_level": "ALARM", "error_code": 0xFF, "error_message": "******",})
            else:
                await self.do_move(duration=1.0 + 4 * len(pipes_), tgt_level="STANDBY")

        elif msg_out_dict["command"] == "RESET":

            if self.index == 5:
                self.status["jar_photocells_status"] = 0x0010  # set load_lifter_up_pc
            elif self.index == 1:
                self.status["jar_photocells_status"] = 0x0020  # set load_lifter_down_pc
            else:
                self.status["jar_photocells_status"] = 0x0000  # set load_lifter_up_pc
            
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
                            tgt_level="JAR_POSITIONING")
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
                if self.status["crx_outputs_status"] & mask:
                    logging.error(f'{self.letter} msg_out_dict["params"]:{msg_out_dict["params"]}, {self.status["crx_outputs_status"]}, {mask}')

                crx_outputs_status = self.status["crx_outputs_status"] | mask
                status_level = 'JAR_POSITIONING'
            else:
                crx_outputs_status = self.status["crx_outputs_status"] & ~mask
                status_level = 'STANDBY'

            await self.update_status(params={"status_level": status_level, "crx_outputs_status": crx_outputs_status})

            # ~ logging.warning("{} {}, crx_outputs_status:{}".format(self.index, self.letter, self.status["crx_outputs_status"]))

            asyncio.get_event_loop().call_later(2.0, self.do_move_by_crx_outputs, *[output_number, output_action])


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
                if 'fail_on_transfer' in sys.argv and self.letter in sys.argv:
                    logging.warning(f"sys.argv:{sys.argv}")
                    sys.argv.remove('fail_on_transfer')
                    # ~ sys.argv.remove(self.letter)
                    logging.warning(f"sys.argv:{sys.argv}")
                else:
                    pars["jar_photocells_status"] = self.status["jar_photocells_status"] | DISPENSING_POSITION_MASK
            elif output_action in (3, 6):
                pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~DISPENSING_POSITION_MASK

            if self.status["jar_photocells_status"] & DISPENSING_POSITION_MASK:
                pars["container_presence"] = True
            else:
                pars["container_presence"] = False

        else:
            if self.letter == 'A':
                if output_number == 1:
                    if output_action in (1, 3):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] & ~INPUT_ROLLER_MASK
                    elif output_action in (2, ):
                        if self.status["jar_photocells_status"] & INPUT_ROLLER_MASK:
                            jar_photocells_status = self.status["jar_photocells_status"] & ~INPUT_ROLLER_MASK
                            t = self.update_status(params={"jar_photocells_status": jar_photocells_status})
                            asyncio.ensure_future(t)
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

                    # ~ if output_action in (1, 4):
                        # ~ pars["jar_photocells_status"] = self.status["jar_photocells_status"] ^ OUTPUT_ROLLER_MASK
                    if output_action in (1, ):
                        pars["jar_photocells_status"] = self.status["jar_photocells_status"] ^ OUTPUT_ROLLER_MASK
                    elif output_action in (4, ):
                        if 'buffer_full' in sys.argv:
                            pars["jar_photocells_status"] = self.status["jar_photocells_status"] | OUTPUT_ROLLER_MASK
                        else:
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

        if not pars:
            logging.warning(f"{self.letter}, output_number:{output_number}, output_action:{output_action}, pars:{pars}")

        t = self.update_status(params=pars)
        asyncio.ensure_future(t)

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

        # ~ asyncio.ensure_future(self.handle_command(msg_out_dict))
        await self.handle_command(msg_out_dict)

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
            try:
                await client.send(message)
                logging.debug("{}, message:{}.".format(self.letter, message))
            except Exception:
                logging.error(traceback.format_exc())
                time.sleep(10)


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


def main(log_level):

    fmt_ = (
        "[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s"
    )
    logging.basicConfig(stream=sys.stdout, level=log_level, format=fmt_)

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


main(log_level=logging.WARNING)
