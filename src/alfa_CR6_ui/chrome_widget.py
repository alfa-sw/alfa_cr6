# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


from PyQt5.uic import loadUi
from PyQt5 import QtCore
from PyQt5.Qt import QUrl      # pylint: disable=no-name-in-module
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineProfile          # pylint: disable=import-error, no-name-in-module
from PyQt5.QtWidgets import QWidget, QFileDialog, QApplication                          # pylint: disable=no-name-in-module
import os


class ChromeWidget(QWidget):
    def __init__(self, parent=None, url="http://kccrefinish.co.kr"):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/chrome.ui", self)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(
            self.on_downloadRequested
        )
        view = QWebEngineView(self)
        view.setUrl(QUrl(url))
        view.resize(1920, 900)

    @QtCore.pyqtSlot("QWebEngineDownloadItem*")
    def on_downloadRequested(self, download):
        path = "/opt/alfa_cr6/data/kcc"
        fname = download.url().path().split("/")[-1]
        if not os.path.exists(path):
            os.makedirs(path)
        download.setPath(path + '/' + fname + '.json')
        download.accept()
        # TODO add callback and feedback on successful download
