# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import os
import sys
import logging
import asyncio

import alfa_CR6_backend.cr6

fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')

# ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"
alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"
alfa_CR6_backend.cr6.settings.WS_URL_LIST = [
    "ws://127.0.0.1:11000/device:machine:status",
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

APP = alfa_CR6_backend.cr6.CR6_application(sys.argv)


def _test_create_db_objects():

    from alfa_CR6_backend.models import Order, Jar

    [APP.db_session.add(Order(barcode="%03d" % i)) for i in range(10)]

    APP.db_session.commit()

    APP._CR6_application__on_barcode_read(0, '001')

    order_cnt = APP.db_session.query(Order).count()
    jar_cnt = APP.db_session.query(Jar).count()

    logging.info(f"order_cnt:{order_cnt}, jar_cnt:{jar_cnt}.")

    assert order_cnt == 10
    assert jar_cnt == 1


def _test_run_gui(delay):

    asyncio.get_event_loop().call_later(1 * delay / 3., APP.main_window.login_btn.click)
    asyncio.get_event_loop().call_later(2 * delay / 3., APP.main_window.sinottico.jarInputPressed)

    APP.run_forever()


def test_all():

    def _stop():
        logging.warning("Stopping execution.")
        raise KeyboardInterrupt

    delay = 3.  # secs
    asyncio.get_event_loop().call_later(delay, _stop)

    _test_create_db_objects()
    _test_run_gui(delay)
