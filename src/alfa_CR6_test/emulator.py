# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except

import sys
import os
import time
import logging
import traceback
import asyncio
import json

from asyncinotify import Inotify, Mask  # pylint: disable=import-error

HERE = os.path.dirname(os.path.abspath(__file__))

DATA_ROOT = '/opt/alfa_cr6/var/'


class MachineHeadMockup:

    def __init__(self, index):

        self.index = index
        pth = os.path.join(DATA_ROOT, 'machine_status_{}.json'.format(self.index))
        with open(pth) as f:
            self.status = json.load(f)

        filepth = os.path.join(DATA_ROOT, 'machine_command_{}.json'.format(self.index))
        with open(filepth, 'w') as f:
            json.dump({}, f)

        self.pending_stop = False

        self.update_status({'status_level': 'STANDBY',
                            'jar_photocells_status': 0x0000})  # reset all pc

        if self.index == 5:
            self.update_status({'jar_photocells_status': 0x0010})  # set load_lifter_up_pc

    def delayed_stop(self):
        if self.pending_stop:
            self.status['status_level'] = 'STANDBY'
            self.pending_stop = False
            self.dump_status()

    def update_status(self, params):
        self.status.update(params)
        self.dump_status()

    def dump_status(self):
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
                            self.dump_status()
                    except Exception:
                        logging.error(f"error reading:{filepth}")
                        logging.error(traceback.format_exc())

    def handle_command(self, msg_out_dict):
        logging.warning("{}, {}".format(self.index, msg_out_dict))

        target = None

        if msg_out_dict['command'] == 'CAN_MOVEMENT':

            dispensing_roller = msg_out_dict['params']['Dispensing_Roller']
            lifter_roller = msg_out_dict['params']['Lifter_Roller']
            input_roller = msg_out_dict['params']['Input_Roller']
            lifter = msg_out_dict['params']['Lifter']

            if dispensing_roller + lifter_roller + input_roller + lifter == 0:
                self.status['status_level'] = 'STANDBY'
                self.update_status({'status_level': 'STANDBY'})
            else:
                self.update_status({'status_level': 'JAR_POSITIONING'})

                if self.index == 0:
                    if input_roller == 2 and dispensing_roller == 0:  # feed = move_00_01
                        def target():
                            self.update_status({
                                'jar_photocells_status': self.status['jar_photocells_status'] | 0x0001,   # set load_pc
                                'status_level': 'STANDBY'})
                    elif input_roller == 1 and dispensing_roller == 2:  # feed = move_01_02
                        self.update_status(
                            {'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0001})  # reset load_pc

                        def target():
                            self.update_status({
                                # set dispensig_pc
                                'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                                'status_level': 'STANDBY'})
                    elif input_roller == 0 and dispensing_roller == 1:  # move_02_03(self):  # 'A -> B'
                        def target():
                            # reset dispensig_pc
                            self.update_status(
                                {'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100})
                    else:
                        self.update_status({'status_level': 'STANDBY'})

                if self.index == 2:
                    if dispensing_roller == 2:  # move_02_03(self):  # 'A -> B'
                        def target():
                            self.update_status({
                                # set dispensig_pc
                                'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                                'status_level': 'STANDBY'})
                    if dispensing_roller == 1:  # move_03_04(self):  # 'B -> c'
                        def target():
                            # reset dispensig_pc
                            self.update_status(
                                {'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100})
                    else:
                        self.update_status({'status_level': 'STANDBY'})

                if self.index == 4:
                    if dispensing_roller == 2:  # move_03_04(self):  # 'B -> C'
                        def target():
                            self.update_status({
                                # set dispensig_pc
                                'jar_photocells_status': self.status['jar_photocells_status'] | 0x0100,
                                'status_level': 'STANDBY'})
                    if dispensing_roller == 1 and lifter_roller == 2:  # move_04_05(self):  # 'C -> UP'
                        def target():
                            # reset dispensig_pc
                            self.update_status(
                                {'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0100})
                            self.update_status({
                                # set load_lifter_roller_pc
                                'jar_photocells_status': self.status['jar_photocells_status'] | 0x0002,
                                'status_level': 'STANDBY'})
                    else:
                        self.update_status({'status_level': 'STANDBY'})

                if self.index == 5:
                    if dispensing_roller == 1 and lifter_roller == 2:  # move_04_05(self):  # 'C -> UP'
                        pass
                    if lifter == 2:         # move_05_06(self):  # 'UP -> DOWN'
                        def target():
                            # reset load_lifter_up_pc
                            self.update_status(
                                {'jar_photocells_status': self.status['jar_photocells_status'] & ~ 0x0010})
                            # set load_lifter_down_pc
                            self.update_status({'jar_photocells_status': self.status['jar_photocells_status'] | 0x0008})
                    else:
                        self.update_status({'status_level': 'STANDBY'})

        if target is not None:
            asyncio.get_event_loop().call_later(3, target)


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

    loop = asyncio.get_event_loop()
    try:

        machine_heads = [MachineHeadMockup(i) for i in range(6)]
        for t in [m.command_watcher() for m in machine_heads]:
            asyncio.ensure_future(t)

        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print('shutting down')
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


main()
