# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


import sys
import os
import logging
import traceback
import asyncio
import subprocess

from PyQt5.QtWidgets import QApplication  # pylint: disable=no-name-in-module

from alfa_CR6.login import Login


class CR6(QApplication):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.run_flag = True
        self.ui_path = os.path.dirname(os.path.abspath(__file__)) + '/ui'
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        self.login = Login()

    def exit(self):    # pylint: disable=no-self-use

        logging.warning("")
        super().exit()

    def get_version(self):    # pylint: disable=no-self-use

        ver = None
        try:
            pth = os.path.abspath(os.path.dirname(sys.executable))
            cmd = '{}/pip show alfa_CR6'.format(pth)
            for line in subprocess.run(cmd.split(), stdout=subprocess.PIPE).stdout.decode().split('\n'):
                if 'Version' in line:
                    ver = line.split(":")[1]
                    ver = ver.strip()
        except Exception as exc:  # pylint: disable=broad-except
            logging.error(exc)

        return ver


def main():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.WARNING, format=fmt_)

    async def qt_loop(app):
        while app.run_flag:
            app.processEvents()
            await asyncio.sleep(0.02)
        asyncio.get_event_loop().stop()

    cr6 = CR6(sys.argv)
    logging.warning("version: {}".format(cr6.get_version()))
    cr6.login.show()

    qt_loop_task = asyncio.ensure_future(qt_loop(cr6))
    evt_loop = asyncio.get_event_loop()
    try:
        evt_loop.run_forever()
    finally:
        evt_loop.run_until_complete(evt_loop.shutdown_asyncgens())
        evt_loop.close()
