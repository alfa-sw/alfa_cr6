# coding: utf-8

import sys
import os
import time
import logging
import traceback
import asyncio
import subprocess
import json
import types


class Emulator:

    def __init__(self):
    
        self.default_machine_status = {
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
            "container_presence": true,
            "autocap_status": true,
            "canlift_status": false,
            "doors_status": true,
            "clamp_position": 0,
            "recirculation_status": [],
            "stirring_status": [],
            "slave_status": [],
            "can_on_plate": true,
            "can_lifter_current_height": 419.4304,
            "can_lifter_range": 838.8608,
            "current_temperature": 49.6,
            "current_rel_humidity": 433.6,
            "water_level": true,
            "critical_temperature": true,
            "temperature": 49.6,
            "bases_carriage": false,
            "circuit_engaged": 16,
            "table_steps_position": 47115,
            "autotest_cycles_number": 1280,
            "table_cleaning_status": [
                9
            ],
            "panel_table_status": true,
            "photocells_status": 0,
            "can_available": true,
            "mixer_door_status": true,
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
            "jar_photocells_status": 288,
            "error_message": "NO_ALARM",
            "timestamp": 1603142218.2367265,
            "message_id": 1001758,
            "last_update": "2020-10-19 23:16:58 CEST"
        }

        self.machine_head_status_list = [default_machine_status.copy() for index in range(6)] 
        
        logging.warning(f"self.machine_head_status_list:{self.machine_head_status_list}")

    def handle_command(self, index, command):

    def refresh_status(self, index, command):

    def run():
        while 1:
            for index in range(6):
                cmd_file = '/opt/alfa_cr6/var/machine_command_{}.json'.format(index)
                with open(cmd_file, 'r') as f:
                    command = json.load(f)
                    if command:
                        self.handle_command(index, command)

                with open(cmd_file, 'w') as f:
                    json.dump({}, f)

                self.refresh_status(index):

                status_file = '/opt/alfa_cr6/var/machine_status_{}.json'.format(index)
                with open(status_file, 'w') as f:
                    json.dump(self.machine_head_status_list[index], f, indent=2)

def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)
    
    e = Emulator()
    e.run()
