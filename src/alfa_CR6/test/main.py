#!/usr/bin/env python

import sys
import logging
import asyncio

import alfa_CR6.cr6

fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)


# ~ alfa_CR6.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_V1_test.sqlite"
alfa_CR6.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"
alfa_CR6.cr6.settings.WS_URL_LIST = [
    # ~ "ws://127.0.0.1:11000/device:machine:status",
]
alfa_CR6.cr6.settings.MOCKUP_FILE_PATH_LIST = [
    # ~ '/opt/alfa_cr6/var/machine_status_0.json',
    # ~ '/opt/alfa_cr6/var/machine_status_1.json',
]
alfa_CR6.cr6.settings.BARCODE_DEVICE_NAME_LIST = [
    # ~ '/dev/input/event7',
    # ~ '/dev/input/event8',
]

APP = alfa_CR6.cr6.CR6_application(sys.argv)


def _test_create_db_objects():

    import alfa_CR6.models
    from alfa_CR6.models import Order, Jar

    for _bcode in ["%03d" % i for i in range(10)]:

        order = Order(barcode=_bcode)
        APP.db_session.add(order)
        jar = Jar(order=order)
        APP.db_session.add(jar)

    APP.db_session.commit()

    order_cnt = APP.db_session.query(Order).count()
    jar_cnt = APP.db_session.query(Jar).count()

    logging.info(f"order_cnt:{order_cnt}, jar_cnt:{jar_cnt}.")

    assert order_cnt == 10
    assert jar_cnt == 10


def _test_run(delay):

    asyncio.get_event_loop().call_later(1 * delay / 3., APP.main_window.login_btn.click)
    asyncio.get_event_loop().call_later(2 * delay / 3., APP.main_window.sinottico.onStep2Pressed)

    APP.run_forever()


def test_all():

    def _stop():
        logging.warning("Stopping execution.")
        raise KeyboardInterrupt

    delay = 3.  # secs
    asyncio.get_event_loop().call_later(delay, _stop)

    _test_create_db_objects()
    _test_run(delay)
