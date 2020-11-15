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


LOG_LEV = logging.INFO

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')
DATA_ROOT = '/opt/alfa_cr6/var/'

def set_settings():
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = None # ":memory:"
    alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"

    alfa_CR6_backend.cr6.settings.MACHINE_HEAD_IPADD_PORTS_LIST=[
        # ~ ('127.0.0.1', 11000, 8080),
        # ~ ('127.0.0.1', 11001, 8080),
        # ~ ('127.0.0.1', 11002, 8080),
        # ~ ('127.0.0.1', 11003, 8080),
        # ~ ('127.0.0.1', 11004, 8080),
        # ~ ('127.0.0.1', 11005, 8080),
        # ~ ('127.0.0.1', 11006, 8080),
        ("192.168.15.156", 11000, 8080),
        ("192.168.15.19",  11000, 8080),
        ("192.168.15.60",  11000, 8080),
        ("192.168.15.61",  11000, 8080),
        ("192.168.15.62",  11000, 8080),
        ("192.168.15.170", 11000, 8080),
    ]
    alfa_CR6_backend.cr6.settings.MOCKUP_FILE_PATH_LIST = [
        # ~ DATA_ROOT + '/machine_status_0.json',
        # ~ DATA_ROOT + '/machine_status_1.json',
        # ~ DATA_ROOT + '/machine_status_2.json',
        # ~ DATA_ROOT + '/machine_status_3.json',
        # ~ DATA_ROOT + '/machine_status_4.json',
        # ~ DATA_ROOT + '/machine_status_5.json',
    ]
    alfa_CR6_backend.cr6.settings.BARCODE_DEVICE_NAME_LIST = [
        # ~ '/dev/input/event7',
        # ~ '/dev/input/event8',
    ]
    alfa_CR6_backend.cr6.settings.DEFAULT_WAIT_FOR_TIMEOUT = 2
    alfa_CR6_backend.cr6.settings.LOG_LEVEL = LOG_LEV

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=LOG_LEV, format=fmt_)



def test_all():

    set_settings()

    APP = alfa_CR6_backend.cr6.CR6_application(sys.argv)
    
    APP.main_window.onLoginBtnClicked()

    APP.main_window.main_window_stack.setCurrentWidget(APP.main_window.debug_status_view.main_frame)
    APP.main_window.debug_status_view.update_status()


    APP.run_forever()

