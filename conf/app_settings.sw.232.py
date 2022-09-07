import os
import logging

# ~ LOG_LEVEL=logging.DEBUG,
# ~ LOG_LEVEL=logging.INFO,
LOG_LEVEL = logging.WARNING

LANGUAGE = "en"

BARCODE_READER_IDENTIFICATION_STRING = "usb-0000:01:00.0-1.2.4"

ORDER_PAGE_COLUMNS_ORDERS = {
    'file': ["file name", "create order", "view", "delete"],
    'order': ["file name", "status", "edit", "order nr.", "delete"],
    'can': ["view", "status", "barcode", "delete"],
}

PRINT_LABEL_OPTONS = {
    'dpi': 240,
    'module_height': 10,
    'module_width': 0.5,
    'font_size': 22,
    # 'text_distance': 2.,
    'line_lenght': 50,
    'n_of_lines': 11,
    'rotate': 270,
    'font_path': '/usr/share/fonts/truetype/unfonts-core/UnDotumBold.ttf'
}

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME_FILES_ROOT = os.path.join(HERE, "../")

CONF_PATH = HERE
LOGS_PATH = os.path.join(RUNTIME_FILES_ROOT, "log")
TMP_PATH = os.path.join(RUNTIME_FILES_ROOT, "tmp")
DATA_PATH = os.path.join(RUNTIME_FILES_ROOT, "data")

CUSTOM_PATH =  os.path.join(HERE, "custom_sw")

WEBENGINE_DOWNLOAD_PATH = os.path.join(DATA_PATH, "SW_web_download")
WEBENGINE_CACHE_PATH = os.path.join(DATA_PATH, "SW_web_cache")
WEBENGINE_CUSTOMER_URL = "https://www.sherwin-williams.com/"

SQLITE_CONNECT_STRING = f"sqlite:///{DATA_PATH}/CRx_v0_SW.sqlite"

STORE_EXCEPTIONS_TO_DB_AS_DEFAULT = False

MACHINE_HEAD_IPADD_PORTS_LIST = [
    ("192.168.0.1", 11000, 8080),
    ("192.168.0.2", 11000, 8080),
    None,
    None,
    ("192.168.0.5", 11000, 8080),
    ("192.168.0.6", 11000, 8080),
]
