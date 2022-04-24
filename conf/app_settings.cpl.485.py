# coding: utf-8

import os
import logging

# ~ LOG_LEVEL=logging.DEBUG,
# ~ LOG_LEVEL=logging.INFO,
LOG_LEVEL = logging.WARNING

LANGUAGE = "en"

BARCODE_READER_IDENTIFICATION_STRING = "usb-0000:01:00.0-1.2.4"

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_FILES_ROOT = os.path.join(HERE, "../")

CONF_PATH = HERE
LOGS_PATH = os.path.join(RUNTIME_FILES_ROOT, "log")
TMP_PATH = os.path.join(RUNTIME_FILES_ROOT, "tmp")
DATA_PATH = os.path.join(RUNTIME_FILES_ROOT, "data")

CUSTOM_PATH =  os.path.join(HERE, "custom_cpl")

WEBENGINE_DOWNLOAD_PATH = os.path.join(DATA_PATH, "web_download")
WEBENGINE_CACHE_PATH = os.path.join(DATA_PATH, "web_cache")

WEBENGINE_CUSTOMER_URL = "https://capellasolutionsgroup.com/"

SQLITE_CONNECT_STRING = f"sqlite:///{DATA_PATH}/CRx_v0.sqlite"

STORE_EXCEPTIONS_TO_DB_AS_DEFAULT = False

MACHINE_HEAD_IPADD_PORTS_LIST = [
    ("127.0.0.1", 11001, 8081),
    ("127.0.0.1", 11002, 8082),
    ("127.0.0.1", 11003, 8083),
    ("127.0.0.1", 11004, 8084),
    ("127.0.0.1", 11005, 8085),
    ("127.0.0.1", 11006, 8086),
]
