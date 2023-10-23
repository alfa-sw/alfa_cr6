# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=broad-except
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import sys
import os
import logging
import subprocess
import traceback
import importlib
import codecs
import json
import shlex

import redis  # pylint: disable=import-error

from barcode import EAN13                   # pylint: disable=import-error
from barcode.writer import ImageWriter      # pylint: disable=import-error

from alfa_CR6_backend import version

HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "ui")
IMAGES_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "images")
HELP_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "help")
KEYBOARD_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "keyboard")
SCHEMAS_PATH = os.path.join(HERE, "schemas")

CONF_PATH = "/opt/alfa_cr6/conf"

TMP_BARCODE_IMAGE = "/opt/alfa_cr6/tmp/tmp_file.png"
TMP_PIGMENT_IMAGE = "/opt/alfa_cr6/tmp/tmp_pigment_label.png"

if os.environ.get("TMP_FILE_PNG"): # JUST FOR TEST, NOT PRODUCTION!
    TMP_BARCODE_IMAGE = os.environ["TMP_FILE_PNG"]

EPSILON = 0.0002
IMPORTED_LANGUAGE_MODULES = {}

LANGUAGE_MAP = {
    "english": 'en',
    "korean": 'kr',
    "italian": 'it',
    "french": 'fr',
    "german": 'de',
    "spanish": 'es',
}

_ALFA_SN = None

DEFAULT_DEBUG_PAGE_PWD = 'alfa'


def get_application_instance():

    from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module, import-outside-toplevel
    return QApplication.instance()

def get_alfa_serialnumber():

    if os.getenv("IN_DOCKER", False) in ['1', 'true']:
        return os.getenv("MACHINE_SN", "00000000")

    global _ALFA_SN    # pylint: disable=global-statement

    if _ALFA_SN is None:
        try:
            r = redis.Redis()
            alfa_conf = r.get('ALFA_CONFIG')
            if not alfa_conf:
                alfa_conf = r.get('ALFA_CONFIG:1')
            if alfa_conf:
                _ALFA_SN = json.loads(alfa_conf).get('ALFA_SERIAL_NUMBER')
        except Exception:
            logging.error(traceback.format_exc())
            _ALFA_SN = None
    if _ALFA_SN is None:
        try:
            cmd_ = """
            . /opt/alfa/venv/bin/activate;
            python -c "from alfa_common.platform import get_alfa_serialnumber; print(get_alfa_serialnumber())"
            """
            _ALFA_SN = subprocess.check_output(cmd_, shell=True, stderr=subprocess.STDOUT).decode()
            if "ERROR" in _ALFA_SN:
                raise Exception(f"_ALFA_SN:{_ALFA_SN}")
            _ALFA_SN = _ALFA_SN.strip()
        except Exception:
            logging.error(traceback.format_exc())
            _ALFA_SN = None

    return _ALFA_SN or "00000000"


def set_language(lang):
    if lang not in list(LANGUAGE_MAP.values()):
        logging.error("unsupported language")
        return

    if os.getenv("IN_DOCKER", False) in ['1', 'true']:
        s = import_settings()
        fn = s.USER_SETTINGS_JSON_FILE
        us = s.USER_SETTINGS
        us['LANGUAGE'] = lang
        save_user_settings(fn, us)
    else:
        cmd_ = f"""sed -i 's/LANGUAGE.=.".."/LANGUAGE = "{lang}"/g' /opt/alfa_cr6/conf/app_settings.py"""
        os.system(cmd_)

    os.system("kill -9 {}".format(os.getpid()))

def save_user_settings(filename, user_settings_dict):
    try:
       with open(filename, "w") as f:
           f.write(json.dumps(user_settings_dict))
    except:
        logging.error("unable to save user settings")
        traceback.print_exc(file=sys.stderr)

def import_settings():

    sys.path.append(CONF_PATH)
    import app_settings  # pylint: disable=import-error,import-outside-toplevel
    sys.path.remove(CONF_PATH)
    
    if os.getenv("IN_DOCKER", False) in ['1', 'true']:
        fn = app_settings.USER_SETTINGS_JSON_FILE
        logging.info(f"importing user settings from {fn}")
        try:
            user_config_dict = {}
            with open(fn, "r") as f:
                user_settings_dict = json.load(f)
        except:
            logging.error(f"user setting file {fn} loading failed, use defaults")
            user_settings_dict = app_settings.DEFAULT_USER_SETTINGS
            save_user_settings(fn, user_settings_dict)

        for el_name, value in user_settings_dict.items():
            app_settings.__dict__[el_name] = value
        
        app_settings.__dict__['USER_SETTINGS']  = user_settings_dict

    for pth in (app_settings.LOGS_PATH,
                app_settings.TMP_PATH,
                app_settings.DATA_PATH,
                app_settings.CUSTOM_PATH,
                app_settings.WEBENGINE_DOWNLOAD_PATH,
                app_settings.WEBENGINE_CACHE_PATH):

        if not os.path.exists(pth):
            os.makedirs(pth)

    return app_settings


def tr_(lemma):

    lemma_ = lemma

    try:
        s = import_settings()
        if not IMPORTED_LANGUAGE_MODULES.get(s.LANGUAGE):
            pth_to_import = f'alfa_CR6_backend.lang.{s.LANGUAGE}'
            IMPORTED_LANGUAGE_MODULES[s.LANGUAGE] = importlib.import_module(pth_to_import)
        lemma_ = IMPORTED_LANGUAGE_MODULES[s.LANGUAGE].D.get(lemma, lemma)
    except Exception:  # pylint: disable=broad-except
        logging.error(traceback.format_exc())

    return lemma_

def get_version():
    return version.__version__

def get_res(_type, name):

    res = None
    _settings = import_settings()

    if os.path.exists(os.path.join(_settings.CUSTOM_PATH, name)):
        res = os.path.join(_settings.CUSTOM_PATH, name)
    else:
        if _type == 'IMAGE':
            res = os.path.join(IMAGES_PATH, name)
        elif _type == 'HELP':
            res = os.path.join(HELP_PATH, name)
        elif _type == 'UI':
            res = os.path.join(UI_PATH, name)

    return res


def get_encoding(path_to_file, key=None):

    encoding_ = ''
    try:

        cmd_ = ["file", "-b", "--mime-encoding", path_to_file]
        p = subprocess.run(cmd_, stdout=subprocess.PIPE, check=False)
        mime_encoding = p.stdout.decode().strip()
        assert mime_encoding
        encoding_ = mime_encoding

    except Exception:   # pylint: disable=broad-except
        logging.warning(traceback.format_exc())

        encodings = [
            'ascii',
            'utf_32',
            'utf_32_be',
            'utf_32_le',
            'utf_16',
            'utf_16_be',
            'utf_16_le',
            'utf_7',
            'utf_8',
            'utf_8_sig']

        for e in encodings:
            try:
                codecs.lookup(e)
                with codecs.open(path_to_file, 'br', encoding=e) as fd:
                    fd.readlines()
                    assert key is None or key in fd.read()
                    fd.seek(0)
            except (UnicodeDecodeError, UnicodeError):
                logging.info(f"skip e:{e}")
            except Exception:   # pylint: disable=broad-except
                logging.warning(traceback.format_exc())
            else:
                logging.warning(f"path_to_file:{path_to_file}, e:{e}")
                encoding_ = e
                break

    if encoding_ == 'utf-8':
        encoding_ = 'utf-8-sig'

    logging.warning(f"encoding_:{encoding_}, path_to_file:{path_to_file}")

    return encoding_

def _get_page_label():
    """ required when using this app with docker/snowball
        obtain page size from lpoptions' field _PageLabel """

    cmd_ = f"lpoptions"
    logging.info(f'cmd_ : {cmd_}')
    ret = subprocess.run(
        cmd_.split(),
        check=False,
        stdout=subprocess.PIPE)

    if ret.returncode != 0:
        logging.warning(f"failed to get options (command: {cmd_})")
        return None

    response = ret.stdout.decode("UTF-8")

    label = None

    try:
        opts = {}
        for o in shlex.split(response):
            splt = o.split('=', maxsplit=1)
            opts[splt[0]] = '' if len(splt) < 2 else splt[1]

        label = opts['_MediaLabel']

    except BaseException as e:
        logging.warning(f"failed to retrieve printer page label ({str(e)})")

    logging.warning(f"media label is {label}")
    return label

def _get_label_options_from_redis_cache():

    cached_label_options = None

    try:
        r = redis.Redis()
        alfa_conf = r.get('ALFA_CONFIG')
        if not alfa_conf:
            alfa_conf = r.get('ALFA_CONFIG:1')
        if alfa_conf:
            field = 'PRINT_LABEL_OPTIONS'

            if os.getenv("IN_DOCKER", False) in ['1', 'true']:
                if "small" in _get_page_label():
                    field = 'PRINT_LABEL_OPTIONS_SMALL'
                else:
                    field = 'PRINT_LABEL_OPTIONS_BIG'

            cached_label_options = json.loads(alfa_conf).get(field)

    except Exception:
        logging.error(traceback.format_exc())
        cached_label_options = None

    return cached_label_options

def _get_print_label_options():

    settings = import_settings()

    options = {
        'dpi': 250,
        'module_height': 7,
        'font_size': 15,
        'text_distance': 0.75,
        'compress': False,
        'line_lenght': 24,
        'n_of_lines': 3,
        'rotate': 0,
        'print_missing_products': True,
    }

    cached_options = _get_label_options_from_redis_cache()
    if cached_options is not None:
        options.update(cached_options)
    else:
        logging.error("could not retrieve label settings from redis cache, using default values")
        if hasattr(settings, 'PRINT_LABEL_OPTONS') and settings.PRINT_LABEL_OPTONS:
            options.update(settings.PRINT_LABEL_OPTONS)

    logging.warning(f'options:{options}')

    return options

def create_printable_image_for_pigment(barcode_txt, pigment_name, pipe_name):

    options = _get_print_label_options()

    response = None

    if not os.path.exists(TMP_PIGMENT_IMAGE):
        with open(TMP_PIGMENT_IMAGE, 'w', encoding='UTF-8'):
            logging.warning(f'empty file created at:{TMP_PIGMENT_IMAGE}')

    options['module_height'] = 5
    if not barcode_txt:
        barcode_txt = 12*'0'
        options['module_height'] = 0

    lines_to_print = [pigment_name, pipe_name]
    n_of_lines = options.pop('n_of_lines')
    n_to_pad = n_of_lines - len(lines_to_print)
    lines_to_print.extend(["." for i in range(n_to_pad)])

    printable_text = '\n'.join(lines_to_print)

    with open(TMP_PIGMENT_IMAGE, 'wb') as file_:
        rotate = options.pop('rotate')
        EAN13(barcode_txt, writer=ImageWriter()).write(file_, options, printable_text)

        response = TMP_PIGMENT_IMAGE

    if response and rotate:
        from PIL import Image   # pylint: disable=import-outside-toplevel
        Image.open(TMP_PIGMENT_IMAGE).rotate(rotate, expand=1).save(TMP_PIGMENT_IMAGE)

    logging.warning('response: {}'.format(response))

    return response

def create_printable_image_from_jar(jar):

    recipe_barcode = str(jar.barcode)

    options = _get_print_label_options()

    response = None

    if not os.path.exists(TMP_BARCODE_IMAGE):
        with open(TMP_BARCODE_IMAGE, 'w', encoding='UTF-8'):
            logging.warning(f'empty file created at:{TMP_BARCODE_IMAGE}')

    with open(TMP_BARCODE_IMAGE, 'wb') as file_:
        recipe_barcode_text = f'{recipe_barcode}'

        l_lenght = options.pop('line_lenght')
        n_of_lines = options.pop('n_of_lines')
        rotate = options.pop('rotate')

        lines_to_print = [recipe_barcode, ]
        lines_to_print += [f"{l}"[:l_lenght] for l in jar.extra_lines_to_print]
        if options.get('print_missing_products'):
            logging.warning(f'jar.unknown_pigments:{jar.unknown_pigments}')
            if jar.unknown_pigments:
                lines_to_print += [tr_("{} product(s) missing:").format(len(jar.unknown_pigments))]
                lines_to_print += [f"{k}: {v}"[:l_lenght] for k, v in jar.unknown_pigments.items()]

        n_to_pad = n_of_lines + 1 - len(lines_to_print)
        lines_to_print.extend(["." for i in range(n_to_pad)])
        printable_text = '\n'.join(lines_to_print)

        EAN13(recipe_barcode_text, writer=ImageWriter()).write(file_, options, printable_text)

        response = TMP_BARCODE_IMAGE

    if response and rotate:
        from PIL import Image   # pylint: disable=import-outside-toplevel
        Image.open(TMP_BARCODE_IMAGE).rotate(rotate, expand=1).save(TMP_BARCODE_IMAGE)

    logging.warning('response: {}'.format(response))

    return response
