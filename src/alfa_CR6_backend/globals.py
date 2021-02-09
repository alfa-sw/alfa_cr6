# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation

import sys
import os
import logging
import subprocess


HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "ui")
IMAGES_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "images")
HELP_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "help")
KEYBOARD_PATH = os.path.join(HERE, "..", "alfa_CR6_frontend", "keyboard")

CONF_PATH = "/opt/alfa_cr6/conf"

EPSILON = 0.00001

def tr_(lemma):
    return lemma

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

