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

import redis  # pylint: disable=import-error

from barcode import EAN13                   # pylint: disable=import-error
from barcode.writer import ImageWriter      # pylint: disable=import-error

HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "ui")
IMAGES_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "images")
HELP_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "help")
KEYBOARD_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "keyboard")
SCHEMAS_PATH = os.path.join(HERE, "schemas")

CONF_PATH = "/opt/alfa_cr6/conf"

TMP_BARCODE_IMAGE = "/opt/alfa_cr6/tmp/tmp_file.png"

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

def get_alfa_serialnumber():

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

    if lang in list(LANGUAGE_MAP.values()):
        cmd_ = f"""sed -i 's/LANGUAGE.=.".."/LANGUAGE = "{lang}"/g' /opt/alfa_cr6/conf/app_settings.py"""
        os.system(cmd_)
        os.system("kill -9 {}".format(os.getpid()))


def import_settings():

    sys.path.append(CONF_PATH)
    import app_settings  # pylint: disable=import-error,import-outside-toplevel
    sys.path.remove(CONF_PATH)

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

    _ver = None

    try:
        pth = os.path.abspath(os.path.dirname(sys.executable))
        cmd = "{}/pip show alfa_CR6".format(pth)
        for line in (
                subprocess.run(cmd.split(), stdout=subprocess.PIPE, check=True)
                .stdout.decode()
                .split("\n")):
            if "Version" in line:
                _ver = line.split(":")[1]
                _ver = _ver.strip()
    except Exception as exc:  # pylint: disable=broad-except
        logging.error(exc)

    return _ver


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

    cmd_ = ["file", "-b", "--mime-encoding", path_to_file]
    try:
        p = subprocess.run(cmd_, stdout=subprocess.PIPE, check=False)
        mime_encoding = p.stdout.decode().strip()
        # ~ logging.warning(f"cmd_:{cmd_}, mime_encoding:{mime_encoding}")
        assert mime_encoding
        return mime_encoding
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
            return e

    return ''


def create_printable_image_from_jar(jar):

    recipe_barcode = str(jar.barcode)

    settings = import_settings()

    response = None

    if not os.path.exists(TMP_BARCODE_IMAGE):
        with open(TMP_BARCODE_IMAGE, 'w', encoding='UTF-8'):
            pass
        logging.warning(f'empty file created at:{TMP_BARCODE_IMAGE}')

    options = {
        'dpi': 250,
        'module_height': 7,
        'font_size': 15,
        'text_distance': 0.75,
        'compress': False,
        'line_lenght': 24,
        'n_of_lines': 3,
        'rotate': 0,
    }

    if hasattr(settings, 'PRINT_LABEL_OPTONS') and settings.PRINT_LABEL_OPTONS:
        options.update(settings.PRINT_LABEL_OPTONS)

    logging.warning(f'options:{options}')

    with open(TMP_BARCODE_IMAGE, 'wb') as file_:
        recipe_barcode_text = f'{recipe_barcode}'

        l_lenght = options.pop('line_lenght')
        n_of_lines = options.pop('n_of_lines')
        rotate = options.pop('rotate')

        lines_to_print = [recipe_barcode, ]
        lines_to_print += [f"{l}"[:l_lenght] for l in jar.extra_lines_to_print]
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
