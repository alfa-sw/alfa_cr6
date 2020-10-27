# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


from PyQt5.uic import loadUi
from PyQt5.Qt import QUrl      # pylint: disable=no-name-in-module
from PyQt5.QtWebEngineWidgets import QWebEngineView          # pylint: disable=import-error, no-name-in-module
from PyQt5.QtWidgets import QWidget, QApplication                          # pylint: disable=no-name-in-module


class ChromeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/chrome.ui", self)
        view = QWebEngineView(self)
        view.setUrl(QUrl("http://www.google.com"))
        view.resize(1440, 811)
