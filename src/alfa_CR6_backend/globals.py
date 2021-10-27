# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation

import sys
import os
import logging
import subprocess
import traceback
import importlib


HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "ui")
IMAGES_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "images")
HELP_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "help")
KEYBOARD_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "keyboard")

CONF_PATH = "/opt/alfa_cr6/conf"

EPSILON = 0.0002
IMPORTED_LANGUAGE_MODULES = {}

LANGUAGES = ["it", 'en', 'kr', 'de']

def set_language(lang):

    if lang in LANGUAGES:
        cmd_ = f"""sed -i 's/LANGUAGE.=.".."/LANGUAGE = "{lang}"/g' /opt/alfa_cr6/conf/app_settings.py"""
        os.system(cmd_)
        os.system("kill -9 {}".format(os.getpid()))

def import_settings():

    sys.path.append(CONF_PATH)
    import app_settings  # pylint: disable=import-error,import-outside-toplevel
    sys.path.remove(CONF_PATH)

    for pth in (app_settings.LOGS_PATH,
                app_settings.TMP_PATH ,
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
        s.LANGUAGE
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

def get_res(type, name):

    res = None
    _settings = import_settings()

    if os.path.exists(os.path.join(_settings.CUSTOM_PATH, name)):
        res = os.path.join(_settings.CUSTOM_PATH, name)
    else:
        if type == 'IMAGE':
            res = os.path.join(IMAGES_PATH, name)
        elif type == 'HELP': 
            res = os.path.join(HELP_PATH, name)
        elif type == 'UI': 
            res = os.path.join(UI_PATH, name)

    return res

def get_encoding(path_to_file, key=None):

    cmd_ = ["file", "-b", "--mime-encoding", path_to_file]
    try:
        p = subprocess.run(cmd_, stdout=subprocess.PIPE)
        mime_encoding = p.stdout.decode().strip()
        # ~ logging.warning(f"cmd_:{cmd_}, mime_encoding:{mime_encoding}")
        assert mime_encoding
        return mime_encoding
    except Exception:
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
            fd = codecs.open(path_to_file, 'br', encoding=e)
            fd.readlines()
            assert key is None or key in fd.read()
            fd.seek(0)
        except (UnicodeDecodeError, UnicodeError):
            logging.info(f"skip e:{e}")
        except Exception:
            logging.warning(traceback.format_exc())
        else:
            logging.warning(f"path_to_file:{path_to_file}, e:{e}")
            return e


