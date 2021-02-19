# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines

import sys
import os
import time
import logging
import traceback
import asyncio
import json

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module
from sqlalchemy.orm.exc import NoResultFound  # pylint: disable=import-error

from alfa_CR6_backend.carousel_motor import CarouselMotor
from alfa_CR6_backend.machine_head import MachineHead
from alfa_CR6_backend.models import Order, Jar, Event, decompile_barcode
from alfa_CR6_backend.globals import (
    UI_PATH,
    KEYBOARD_PATH,
    EPSILON,
    get_version,
    tr_,
    import_settings)

from alfa_CR6_frontend.main_window import MainWindow


def main():

    settings = import_settings()

    logging.basicConfig(
        stream=sys.stdout, level=settings.LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    app = CarouselMotor(MainWindow, settings, sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
