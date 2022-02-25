import os
import logging

# ~ LOG_LEVEL=logging.DEBUG,
# ~ LOG_LEVEL=logging.INFO,
LOG_LEVEL = logging.WARNING

LANGUAGE = "it"

# ~ BARCODE_READER_IDENTIFICATION_STRING = "usb-0000:01:00.0-1.2.4"
BARCODE_READER_IDENTIFICATION_STRING = "Barcode"

# ~ DOWNLOAD_KCC_LOT_STEP = 10*60
DOWNLOAD_KCC_LOT_STEP = 60 * 60

# ~ BARCODE_READER_IDENTIFICATION_STRING = "usb-0000:01:00.0-1.2.4"
HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_FILES_ROOT = os.path.join(HERE, "../")

CONF_PATH = HERE
LOGS_PATH = os.path.join(RUNTIME_FILES_ROOT, "log")
TMP_PATH = os.path.join(RUNTIME_FILES_ROOT, "tmp")
DATA_PATH = os.path.join(RUNTIME_FILES_ROOT, "data")

CUSTOM_PATH =  os.path.join(HERE, "custom_kcc")     # "custom_sk" "custom_sw" "custom_kcc"

# ~ WEBENGINE_DOWNLOAD_PATH = os.path.join(DATA_PATH, "mcm")
# ~ WEBENGINE_CACHE_PATH = os.path.join(DATA_PATH, "webengine")
# ~ WEBENGINE_CUSTOMER_URL = "https://cloud.e-mixing.eu/"

WEBENGINE_DOWNLOAD_PATH = os.path.join(DATA_PATH, "kcc")
WEBENGINE_CACHE_PATH = os.path.join(DATA_PATH, "webengine")
WEBENGINE_CUSTOMER_URL = "http://kccrefinish.co.kr/"


SQLITE_CONNECT_STRING = f"sqlite:///{DATA_PATH}/cr6_Vx_test.sqlite"

STORE_EXCEPTIONS_TO_DB_AS_DEFAULT = False

MACHINE_HEAD_IPADD_PORTS_LIST = [

    # ~ ("127.0.0.1", 11001, 8080),
    # ~ ("127.0.0.1", 11002, 8080),
    # ~ None,
    # ~ None,
    # ~ ("127.0.0.1", 11005, 8080),
    # ~ ("127.0.0.1", 11006, 8080),

    # ~ ("127.0.0.1", 11000, 8080),
    # ~ ("127.0.0.1", 11000, 8080),
    # ~ ("127.0.0.1", 11000, 8080),
    # ~ ("127.0.0.1", 11000, 8080),
    # ~ ("127.0.0.1", 11000, 8080),
    # ~ ("127.0.0.1", 11000, 8080),
    ("127.0.0.1", 11001, 8081),
    ("127.0.0.1", 11002, 8082),
    ("127.0.0.1", 11003, 8083),
    ("127.0.0.1", 11004, 8084),
    ("127.0.0.1", 11005, 8085),
    ("127.0.0.1", 11006, 8086),

    # ~ ("10.31.0.2", 11000, 8080),
    # ~ ("10.31.0.3", 11000, 8080),
    # ~ ("10.31.0.4", 11000, 8080),
    # ~ ("10.31.0.5", 11000, 8080),
    # ~ ("10.31.0.6", 11000, 8080),
    # ~ ("10.31.0.7", 11000, 8080),
]
