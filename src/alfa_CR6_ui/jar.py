from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.uic import loadUi

class Jar(QWidget):

    def __init__(self, parent=None):

        super().__init__(parent)
        loadUi(QApplication.instance().ui_path + "/jar.ui", self)
