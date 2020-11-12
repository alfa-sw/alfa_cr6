# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=broad-except

import sys
import time
import logging
import traceback
import asyncio
import concurrent
import json

import websockets                           # pylint: disable=import-error

from PyQt5.QtWidgets import QApplication # pylint: disable=no-name-in-module

from alfa_CR6_backend.machine_head import MachineHead

MACHINE_LIST = [
    # ~ ('127.0.0.1', 11000, 8080)
    ('127.0.0.1', 11001, 8080),
    ('127.0.0.1', 11002, 8080),
    ('127.0.0.1', 11003, 8080),
    ('127.0.0.1', 11004, 8080),
    ('127.0.0.1', 11005, 8080),
    ('127.0.0.1', 11006, 8080),
    # ~ "192.168.15.156",
    # ~ "192.168.15.19",
    # ~ "192.168.15.60",
    # ~ "192.168.15.61",
    # ~ "192.168.15.62",
    # ~ "192.168.15.170",
]


class Machine(MachineHead):     # pylint: disable=too-many-instance-attributes

    def __init__(self, head_index, ip_add, ws_port, http_port, msg_handler=None, mockup_files_path=None):      # pylint: disable=too-many-arguments

        super().__init__(head_index)

        self.index = head_index
        self.ip_add = ip_add
        self.ws_port = ws_port
        self.http_port = http_port
        self.msg_handler = msg_handler
        self.mockup_files_path = mockup_files_path

        self.websocket = None
        self.last_answer = None
        self.cntr = 0

    async def send_command(self, cmd_name: str, params: dict, type_='command', channel='machine'):
        """ param 'type_' can be 'command' or 'macro'

            examples:
                self.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
                self.send_command(cmd_name="PURGE", params={'items': [{'name': 'B01', 'qtity': 2.1}, {'name': 'C03', 'qtity': 1.1}, ]}, type_='macro')
        """
        ret = None
        try:
            msg = {
                'type': type_,
                'channel': channel,
                'msg_out_dict': {'command': cmd_name, 'params': params},
            }
            ret = None
            if self.websocket:
                # ~ logging.info(f"msg:{msg}")
                # ~ t   = self.websocket.send(json.dumps(msg))
                # ~ asyncio.ensure_future(t)
                logging.warning(f"{self.name} Sending  msg:{msg}")
                ret = await self.websocket.send(json.dumps(msg))
                # ~ logging.warning(f"ret:{ret}")
        except Exception as e:                           # pylint: disable=broad-except
            self.app.handle_exception(e)
        return ret

    async def handle_ws_recv(self):

        msg = None
        try:
            msg = await asyncio.wait_for(self.websocket.recv(), timeout=.5)
        except concurrent.futures._base.TimeoutError as e:     # pylint: disable=protected-access
            logging.debug(f"e:{e}")

        self.cntr += 1

        if msg:
            msg_dict = dict(json.loads(msg))

            if msg_dict.get('type') == 'device:machine:status':
                status = msg_dict.get('value')
                status = dict(status)
                if status:
                    await self.update_status(status)
                    # ~ logging.warning("status_level:{}, cycle_step:{}, autocap_status:{}.".format(
                        # ~ self.status['status_level'], self.status['cycle_step'], self.status['autocap_status']))

            elif msg_dict.get('type') == 'answer':
                # ~ logging.warning(f"msg_dict:{msg_dict}")
                answer = msg_dict.get('value')
                answer = dict(answer)
                if answer:
                    self.last_answer = answer

            elif msg_dict.get('type') == 'time':
                # ~ logging.warning(f"msg_dict:{msg_dict}")
                time_stamp = msg_dict.get('value')
                if time_stamp:
                    self.time_stamp = time_stamp

            if self.msg_handler:
                await self.msg_handler(self.index, msg_dict)

    async def run(self):

        ws_url = f"ws://{ self.ip_add }:{ self.ws_port }/device:machine:status"
        while 1:
            try:
                async with websockets.connect(ws_url) as websocket:
                    self.websocket = websocket
                    while 1:
                        await self.handle_ws_recv()
            except Exception as e:
                logging.error(f"e:{e}")
                logging.error(traceback.format_exc())
                await asyncio.sleep(2)
        logging.warning(f" *** exiting *** ")


class App(object):

    machines = []
    tasks = []

    async def create_machine_task(self, ip_add, ws_port, http_port):

        m = Machine(ip_add, ws_port, http_port)
        self.machines.append(m)
        await m.run()
        logging.warning(f" *** terminating machine: {m} *** ")

    async def create_and_run_tasks(self):

        for ip_add, ws_port, http_port in MACHINE_LIST:
            t = self.create_machine_task(ip_add, ws_port, http_port)
            self.tasks.append(t)

        res = await asyncio.gather(*self.tasks, return_exceptions=True)

        logging.warning(f" *** terminating tasks  *** ")
        return res

    def run(self):

        asyncio.get_event_loop().run_until_complete(self.create_and_run_tasks())
        asyncio.get_event_loop().close()


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

    a = App()
    a.run()


if __name__ == "__main__":
    main()
