# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name

import os
import time

from PyQt5.uic import loadUi
from PyQt5 import QtCore
from PyQt5.Qt import QUrl      # pylint: disable=no-name-in-module
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile          # pylint: disable=import-error, no-name-in-module
from PyQt5.QtWidgets import QWidget, QApplication                          # pylint: disable=no-name-in-module

# ~ from alfa_CR6_ui.keyboard import Keyboard


class ChromeWidget(QWidget):
    download_callback = {}

    def __init__(self, parent, url="http://kccrefinish.co.kr"):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/chrome.ui", self)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(
            self.on_downloadRequested
        )
        self.view = QWebEngineView(self)
        self.view.setUrl(QUrl(url))
        self.view.resize(1920, 1000)

    def setDownloadCallback(self, callback):
        self.download_callback = callback

    @QtCore.pyqtSlot("QWebEngineDownloadItem*")
    def on_downloadRequested(self, download):
        path = "/opt/alfa_cr6/data/kcc"
        if not os.path.exists(path):
            os.makedirs(path)
        full_name = path + '/' + time.asctime().replace(":", "_").replace(" ", "_") + '.json'
        download.setPath(full_name)
        download.accept()
        self.download_callback(full_name)
