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


class ChromeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/chrome.ui", self)
        QWebEngineProfile.defaultProfile().downloadRequested.connect(
            self.on_downloadRequested
        )
        view = QWebEngineView(self)
        view.setUrl(QUrl("http://www.google.com"))
        view.resize(1440, 811)

    @QtCore.pyqtSlot("QWebEngineDownloadItem*")
    def on_downloadRequested(self, download):
        #TODO: use fixed path instead of asking the user
        old_path = download.url().path()  # download.path()
        # suffix = QtCore.QFileInfo(old_path).suffix()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save File", old_path, "*.json"
        )
        if path:
            download.setPath(path)
            download.accept()
