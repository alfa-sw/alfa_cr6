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

from alfa_CR6_backend.models import Order, Jar

LOG_LEVEL = logging.INFO
# ~ LOG_LEVEL = logging.DEBUG

fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL, format=fmt_)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, 'fixtures')

def set_settings():
    # ~ alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = "sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"
    alfa_CR6_backend.cr6.settings.SQLITE_CONNECT_STRING = 'sqlite://'  # ":memory:"
    alfa_CR6_backend.cr6.settings.MACHINE_HEAD_IPADD_LIST=[
        "127.0.0.1",
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

def test_all():
    set_settings()

    APP = alfa_CR6_backend.cr6.CR6_application(sys.argv)
    
    for i in range(3):
        order = Order(status="NEW", order_nr=201030000000 + i * 1000)
        APP.db_session.add(order) 
        APP.db_session.commit()

        for j in range (3):
            # ~ APP.db_session.add(Jar(order_id=order.id, index=i)) 
            jar = Jar(order=order, index=j, size=0)
            APP.db_session.add(jar) 
            logging.info(f"jar:{jar}.")
            APP.db_session.commit()

        logging.info(f"APP.db_session.query(Order).count():{APP.db_session.query(Order).count()}.")

    order_cnt = APP.db_session.query(Order).count()
    jar_cnt = APP.db_session.query(Jar).count()

    logging.info(f"order_cnt:{order_cnt}, jar_cnt:{jar_cnt}.")
    logging.info(f"jars:{[j for j in APP.db_session.query(Jar).all()]}.")

    assert order_cnt == 3
    assert jar_cnt == 9

    def _stop():
        logging.info("Stopping execution.")
        raise KeyboardInterrupt

    def _action(b_code):
        t = APP._CR6_application__on_barcode_read(0, b_code)
        asyncio.ensure_future(t)
        
    asyncio.get_event_loop().call_later(0.3, APP.main_window.close)

    asyncio.get_event_loop().call_later(0.5, _action, 201030000001)
    asyncio.get_event_loop().call_later(1.0, _action, 201030001001)
    asyncio.get_event_loop().call_later(1.3, _action, 201030001002)
    asyncio.get_event_loop().call_later(2.0, _action, 201030002000)
    asyncio.get_event_loop().call_later(2.2, _action, 201030002001)
    asyncio.get_event_loop().call_later(2.4, _action, 201030002002)

    asyncio.get_event_loop().call_later(4., _stop)


    APP.run_forever()
