# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


import sys
import os
import logging
import subprocess

from PyQt5.QtWidgets import QApplication

from alfa_CR6.login import Login


class CR6(QApplication):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.path = os.path.dirname(os.path.abspath(__file__))
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        self.login = Login(self.path)

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

    cr6 = CR6(sys.argv)
    logging.warning("version: {}".format(cr6.get_version()))
    cr6.login.show()
    sys.exit(cr6.exec_())

if __name__=="__main__":
    main()
