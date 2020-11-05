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

fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=fmt_)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')

def set_settings():
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"
    alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = None # ":memory:"

    alfa_CR6_backend.cr6.settings.MACHINE_HEAD_IPADD_LIST=[
        # ~ "127.0.0.1",
        "192.168.15.156",
        "192.168.15.19",
        "192.168.15.60",
        "192.168.15.61",
        "192.168.15.62",
        "192.168.15.170",
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

    APP = alfa_CR6_backend.cr6.CR6_application(sys.argv)

    def _stop():
        logging.warning("Stopping execution.")
        raise KeyboardInterrupt

    asyncio.get_event_loop().call_later(1, APP.main_window.login_btn.click)
    # ~ asyncio.get_event_loop().call_later(2, APP.main_window.sinottico.jarInputPressed)
    asyncio.get_event_loop().call_later(3, _stop)

    APP.run_forever()

