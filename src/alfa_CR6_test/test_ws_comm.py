# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import os
import sys
import time
import logging
import traceback
import asyncio

import alfa_CR6_backend.cr6

LOG_LEVEL = logging.DEBUG

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')

def set_settings():
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"
    alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"
    
    alfa_CR6_backend.cr6.settings.MACHINE_HEAD_IPADD_PORTS_LIST=[
        ('127.0.0.1', 11000, 8080)
        # ~ ("192.168.15.156", 11000, 8080)
        # ~ ("192.168.15.19",  11000, 8080)
        # ~ ("192.168.15.60",  11000, 8080)
        # ~ ("192.168.15.61",  11000, 8080)
        # ~ ("192.168.15.62",  11000, 8080)
        # ~ ("192.168.15.170", 11000, 8080)
    ]

    alfa_CR6_backend.cr6.settings.MOCKUP_FILE_PATH_LIST = [
        # ~ FIXTURES + '/machine_status_0.json',
        # ~ FIXTURES + '/machine_status_1.json',
        # ~ FIXTURES + '/machine_status_2.json',
        # ~ FIXTURES + '/machine_status_3.json',
        # ~ FIXTURES + '/machine_status_4.json',
        # ~ FIXTURES + '/machine_status_5.json',
    ]
    alfa_CR6_backend.cr6.settings.BARCODE_DEVICE_NAME_LIST = [
        # ~ '/dev/input/event7',
        # ~ '/dev/input/event8',
    ]

def test_all():

    set_settings()

    APP = alfa_CR6_backend.cr6.Application(sys.argv)

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL, format=fmt_)

    def _stop():
        logging.warning("Stopping execution.")
        raise KeyboardInterrupt

    def _action_ws():

        try:
            pars = {'items': [{'name': 'B01', 'qtity': 2.1}, {'name': 'C03', 'qtity': 1.1}, ]}
            
            logging.warning(f"APP.machine_head_dict[0].websocket:{APP.machine_head_dict[0].websocket}.")
            c = APP.machine_head_dict[0].send_command(cmd_name="PURGE", params=pars, type_='macro')
            t = asyncio.ensure_future(c)
        except:
            logging.error(traceback.format_exc())

    def _action_api():

        try:

            c = APP.machine_head_dict[0].call_api_rest('apiV1/pipe', 'GET', {})
            t = asyncio.ensure_future(c)
            # ~ logging.warning(f"call_api_rest(() -> t:{t}")

        except:

            logging.error(traceback.format_exc())

    asyncio.get_event_loop().call_later(0.1, APP.main_window.close)

    asyncio.get_event_loop().call_later(.5, _action_ws)
    asyncio.get_event_loop().call_later(.1, _action_api)
    asyncio.get_event_loop().call_later(2., _stop)

    APP.run_forever()
    
