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

from alfa_CR6_backend.models import Order, Jar, compile_barcode

LOG_LEVEL = logging.WARNING
# ~ LOG_LEVEL = logging.INFO
# ~ LOG_LEVEL = logging.DEBUG

fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL, format=fmt_)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')

def set_settings():
    
    # ~ os.system("rm -f /opt/alfa_cr6/data/cr6_Vx_test.sqlite")
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"

    alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"

    alfa_CR6_backend.cr6.settings.MACHINE_HEAD_IPADD_LIST=[
        "127.0.0.1",
        # ~ "192.168.15.156",
        # ~ "192.168.15.19",
        # ~ "192.168.15.60",
        # ~ "192.168.15.61",
        # ~ "192.168.15.62",
        # ~ "192.168.15.170",
    ]
    alfa_CR6_backend.cr6.settings.MOCKUP_FILE_PATH_LIST = [
        FIXTURES + '/machine_status_0.json',
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
    STORE_EXCEPTIONS_TO_DB_AS_DEFAULT = True

def test_all():
    set_settings()

    APP = alfa_CR6_backend.cr6.CR6_application(sys.argv)
    
    N, M = 3, 2
    barcodes = []
    for i in range(N):
        pth = os.path.join(FIXTURES, "kcc_downloaded_sample.json")
        order = APP.create_order(pth, n_of_jars=M)

    order_cnt = APP.db_session.query(Order).count()
    jar_cnt = APP.db_session.query(Jar).count()

    assert order_cnt == N
    assert jar_cnt == N*M

    for j in APP.db_session.query(Jar).all():
            bc = compile_barcode(j.order.order_nr, j.index)
            barcodes.append(bc)

    def _stop():
        logging.info("Stopping execution.")
        raise KeyboardInterrupt

    def _action(b_code):
        async def t():
            APP.machine_head_dict[0].jar_photocells_status['JAR_INPUT_ROLLER_PHOTOCELL'] = 1
            await APP._CR6_application__on_barcode_read(0, b_code)
            APP.machine_head_dict[0].jar_photocells_status['JAR_INPUT_ROLLER_PHOTOCELL'] = 0

        asyncio.ensure_future(t())
        
    asyncio.get_event_loop().call_later(0.3, APP.main_window.close)

    for i, b in enumerate(barcodes):
        asyncio.get_event_loop().call_later(i*.5, _action, b)

    asyncio.get_event_loop().call_later(5.0 + len(barcodes)*.1, _stop)


    APP.run_forever()
