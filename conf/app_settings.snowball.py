import os
import logging

# ~ LOG_LEVEL=logging.DEBUG,
# ~ LOG_LEVEL=logging.INFO,
LOG_LEVEL = logging.WARNING

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_FILES_ROOT = os.path.join(HERE, "../")

CONF_PATH = HERE
LOGS_PATH = os.path.join(RUNTIME_FILES_ROOT, "log")
TMP_PATH = os.path.join(RUNTIME_FILES_ROOT, "tmp")
DATA_PATH = os.path.join(RUNTIME_FILES_ROOT, "data")

CUSTOM_PATH = os.path.join(DATA_PATH, "custom")

WEBENGINE_DOWNLOAD_PATH = os.path.join(DATA_PATH, "orders")
WEBENGINE_CACHE_PATH = os.path.join(TMP_PATH, "SW_web_cache")


SQLITE_CONNECT_STRING = f"sqlite:///{DATA_PATH}/cr6_Vx_test.sqlite"

STORE_EXCEPTIONS_TO_DB_AS_DEFAULT = False

MACHINE_HEAD_IPADD_PORTS_LIST = [

    ("127.0.0.1", 11001, 8081),
    ("127.0.0.1", 11002, 8082),
    ("127.0.0.1", 11003, 8083) if os.getenv('MACHINE_VARIANT') == "CR6" else None,
    ("127.0.0.1", 11004, 8084) if os.getenv('MACHINE_VARIANT') == "CR6" else None,
    ("127.0.0.1", 11005, 8085),
    ("127.0.0.1", 11006, 8086),

]

USER_SETTINGS_JSON_FILE = os.path.join(DATA_PATH, "user_settings.json")

DEFAULT_USER_SETTINGS = {
   # ~ "BARCODE_READER_IDENTIFICATION_STRING": "usb-0000:01:00.0-1.2.4"
   "BARCODE_READER_IDENTIFICATION_STRING": "Barcode", 
   "DOWNLOAD_KCC_LOT_STEP": 1200,
   "WEBENGINE_CUSTOMER_URL": "http://alfadispenser.com/",
   "LANGUAGE": "it"
}

