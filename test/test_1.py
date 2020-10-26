#!/usr/bin/env python

import sys
import logging
import asyncio

import alfa_CR6.cr6
import alfa_CR6.models 
from alfa_CR6.models import Order, Jar

fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=fmt_)

# ~ alfa_CR6.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_V1_test.sqlite"
alfa_CR6.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://' # ":memory:"

APP = alfa_CR6.cr6.CR6_application(sys.argv)
logging.warning("version: {} - Ctrl+C to close me.".format(APP.get_version()))

def test_create_db_objects():

    for _bcode in ["%03d"%i for i in range (10)]:
            
        order = Order(barcode=_bcode)
        APP.db_session.add(order)
        jar = Jar(order=order)
        APP.db_session.add(jar)

    APP.db_session.commit()

    order_cnt = APP.db_session.query(Order).count()
    jar_cnt = APP.db_session.query(Jar).count()
    assert order_cnt == 10
    assert jar_cnt   == 10

def test_run():

    def _stop():
        logging.warning("Stopping execution.")
        raise KeyboardInterrupt

    asyncio.get_event_loop().call_later(1, APP.main_window.login_btn.click)
    asyncio.get_event_loop().call_later(2, APP.main_window.sinottico.onStep2Pressed)
    asyncio.get_event_loop().call_later(3, _stop)

    APP.run_forever()


if __name__ == "__main__":
    test_create_db_objects()
    test_run()
