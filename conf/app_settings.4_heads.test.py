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

WEBENGINE_DOWNLOAD_PATH = os.path.join(DATA_PATH, "SW_web_download")
WEBENGINE_CACHE_PATH = os.path.join(DATA_PATH, "SW_web_cache")
WEBENGINE_CUSTOMER_URL = "https://www.sherwin-williams.com/"

SQLITE_CONNECT_STRING = f"sqlite:///{DATA_PATH}/CRx_v0_SW.sqlite"

STORE_EXCEPTIONS_TO_DB_AS_DEFAULT = False

MACHINE_HEAD_IPADD_PORTS_LIST = [
    # ~ ("192.168.15.152", 11000, 8080),
    # ~ ("192.168.15.167", 11000, 8080),
    # ~ None,
    # ~ None,
    # ~ ("192.168.15.176", 11000, 8080),
    # ~ ("192.168.15.73",  11000, 8080),

    ("127.0.0.1", 11001, 8080),
    ("127.0.0.1", 11002, 8080),
    None,
    None,
    ("127.0.0.1", 11004, 8080),
    ("127.0.0.1", 11006, 8080),


]
