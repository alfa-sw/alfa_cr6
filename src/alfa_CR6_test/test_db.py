# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=bad-continuation


import os
import sys
import time
import logging
import traceback
import asyncio
import json

from PyQt5.QtWidgets import QWidget, QLabel, QFrame, QTextBrowser, QButtonGroup, QPushButton   # pylint: disable=no-name-in-module

from PyQt5.QtWidgets import QApplication    # pylint: disable=no-name-in-module
from PyQt5.QtCore import pyqtSlot


import alfa_CR6_backend.cr6

from alfa_CR6_backend.models import Order, Jar, compile_barcode

LOG_LEVEL = logging.WARNING
# ~ LOG_LEVEL = logging.INFO
# ~ LOG_LEVEL = logging.DEBUG


HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')


def set_settings():

    # ~ os.system("rm -f /opt/alfa_cr6/data/cr6_Vx_test.sqlite")
    alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"

    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"

    alfa_CR6_backend.cr6.settings.MACHINE_HEAD_IPADD_PORTS_LIST = [
        # ~ ('127.0.0.1', 11000, 8080)
        # ~ ("192.168.15.156", 11000, 8080)
        # ~ ("192.168.15.19",  11000, 8080)
        # ~ ("192.168.15.60",  11000, 8080)
        # ~ ("192.168.15.61",  11000, 8080)
        # ~ ("192.168.15.62",  11000, 8080)
        # ~ ("192.168.15.170", 11000, 8080)
    ]
    alfa_CR6_backend.cr6.settings.MOCKUP_FILE_PATH_LIST = [
        FIXTURES + '/machine_status_0.json',
        FIXTURES + '/machine_status_1.json',
        FIXTURES + '/machine_status_2.json',
        FIXTURES + '/machine_status_3.json',
        FIXTURES + '/machine_status_4.json',
        FIXTURES + '/machine_status_5.json',
    ]
    alfa_CR6_backend.cr6.settings.BARCODE_DEVICE_NAME_LIST = [
        # ~ '/dev/input/event7',
        # ~ '/dev/input/event8',
    ]
    STORE_EXCEPTIONS_TO_DB_AS_DEFAULT = True




def test_all():

    set_settings()

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL, format=fmt_)

    APP = alfa_CR6_backend.cr6.Application(sys.argv)

    # ~ N, M = 4, 5
    # ~ barcodes = []
    # ~ for i in range(N):
        # ~ pth = "/opt/alfa_cr6/var/P2S_1L.json"
        # ~ order = APP.create_order(pth, n_of_jars=M)

    order_files = [
        '/opt/alfa_cr6/var/ORDINE_1_1.json',
        '/opt/alfa_cr6/var/ORDINE_2_1.json',
        '/opt/alfa_cr6/var/ORDINE_3_1.json',
    # ~ ]
    # ~ order_files = [
        '/opt/alfa_cr6/var/ORDINE_test_1.json',
        '/opt/alfa_cr6/var/ORDINE_test_2.json',
    ]
    M = 3
    barcodes = []
    for pth in order_files:
        order = APP.create_order(pth, n_of_jars=M)

    order_cnt = APP.db_session.query(Order).count()
    jar_cnt = APP.db_session.query(Jar).count()

    # ~ assert order_cnt == len(order_files)
    # ~ assert jar_cnt == order_cnt * M

    for j in APP.db_session.query(Jar).all():
        # ~ bc = compile_barcode(j.order.order_nr, j.index)
        bc = j.barcode
        barcodes.append(bc)
        logging.warning(f"j.barcode:{j.barcode}")

    def _stop():
        logging.info("Stopping execution.")
        raise KeyboardInterrupt

    def _action(b_code):
        async def t():
            # ~ APP.machine_head_dict[0].jar_photocells_status['JAR_INPUT_ROLLER_PHOTOCELL'] = 1
            await APP.on_barcode_read(b_code)
            # ~ APP.machine_head_dict[0].jar_photocells_status['JAR_INPUT_ROLLER_PHOTOCELL'] = 0

        asyncio.ensure_future(t())

    # ~ asyncio.get_event_loop().call_later(0.3, APP.main_window.close)
    asyncio.get_event_loop().call_later(.2, APP.main_window.login_btn.click)

    # ~ for i, b in enumerate(barcodes):
        # ~ asyncio.get_event_loop().call_later(i*.5, _action, b)

    # ~ asyncio.get_event_loop().call_later(5.0 + len(barcodes)*.1, _stop)
    
    # ~ asyncio.get_event_loop().call_later(1, _action, barcodes[0])
    
    asyncio.get_event_loop().call_later(1, _stop)

    APP.run_forever()
