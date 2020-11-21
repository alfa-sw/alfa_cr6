
import os
import logging

RUNTIME_FILES_ROOT = '/opt/alfa_cr6'

# ~ LOG_LEVEL=logging.DEBUG,
# ~ LOG_LEVEL=logging.INFO,
LOG_LEVEL=logging.WARNING

LOGS_PATH=os.path.join(RUNTIME_FILES_ROOT, 'log')
TMP_PATH=os.path.join(RUNTIME_FILES_ROOT, 'tmp')
CONF_PATH=os.path.join(RUNTIME_FILES_ROOT, 'conf')


# ~ SQLITE_CONNECT_STRING=None
SQLITE_CONNECT_STRING="sqlite:////opt/alfa_cr6/data/cr6_Vx_test.sqlite"

MACHINE_HEAD_IPADD_PORTS_LIST=[
    # ~ ('127.0.0.1', 11000, 8080),

    # ~ ('127.0.0.1', 11001, 8080),
    # ~ ('127.0.0.1', 11002, 8080),
    # ~ ('127.0.0.1', 11003, 8080),
    # ~ ('127.0.0.1', 11004, 8080),
    # ~ ('127.0.0.1', 11005, 8080),
    # ~ ('127.0.0.1', 11006, 8080),

    # ~ ("192.168.15.156", 11000, 8080),
    # ~ ("192.168.15.19", 11000, 8080),
    # ~ ("192.168.15.60", 11000, 8080),
    # ~ ("192.168.15.61", 11000, 8080),
    # ~ ("192.168.15.62", 11000, 8080),
    # ~ ("192.168.15.170", 11000, 8080),

    ("192.168.1.1", 11000, 8080),
    ("192.168.1.2", 11000, 8080),
    ("192.168.1.3", 11000, 8080),
    ("192.168.1.4", 11000, 8080),
    ("192.168.1.5", 11000, 8080),
    ("192.168.1.6", 11000, 8080),

]

BARCODE_DEVICE_NAME_LIST=[
'/dev/input/event0',
# ~ '/dev/input/event8',
]

STORE_EXCEPTIONS_TO_DB_AS_DEFAULT=False
