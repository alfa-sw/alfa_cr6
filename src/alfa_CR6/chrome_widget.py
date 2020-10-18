from PyQt5.uic import loadUi
from PyQt5.Qt import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import QWidget


class ChromeWidget(QWidget):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        loadUi(path + "/ui/chrome.ui", self)
        view = QWebEngineView(self)
        view.setUrl(QUrl("http://www.google.com"))
        view.resize(1440, 811)
