# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long

import sys
import logging
import platform
import os

from alfa_CR6_backend.carousel_motor import CarouselMotor
from alfa_CR6_backend.globals import import_settings

def pre_load_libGLX_on_banana():

    logging.warning("platform.release():{}".format(platform.release()))

    sys_releases = ["4.9", "5.10"]
    if any(x in platform.release() for x in sys_releases) and 'bananapi' in platform.node():
        import ctypes # pylint:  disable=import-outside-toplevel
        ctypes.CDLL('libGLX_mesa.so.0', ctypes.RTLD_GLOBAL)

def main():

    settings = import_settings()

    logging.basicConfig(
        stream=sys.stdout, level=settings.LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    if not os.getenv("IN_DOCKER", False) in ['1', 'true']:
        pre_load_libGLX_on_banana()

    from alfa_CR6_frontend.main_window import MainWindow    # pylint: disable=import-outside-toplevel
    app = CarouselMotor(MainWindow, settings, sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))
    app.run_forever()


if __name__ == "__main__":
    main()
