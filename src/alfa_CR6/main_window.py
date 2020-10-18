from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QMainWindow
from PyQt5 import QtCore

class MainWindow(QMainWindow):
    switch_window = QtCore.pyqtSignal(str)
    browser=False

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(parent.path+"/ui/mainwindow.ui", self)
        self.dialog_1_btn.clicked.connect(self.onDialog1BtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)
        self.bar1.mousePressEvent=self.onDialog1BtnClicked
        self.tabs.setCurrentIndex(0)

    def onDialog1BtnClicked(self, other):
        dlg = Dialog1(self)
        dlg.exec()

    def onChromeBtnClicked(self):
        if self.browser:
            self.browser=False
            self.tabs.setCurrentIndex(0)
            self.mainlayout.removeWidget(self.view)
        else:
            self.browser=True
            self.view = ChromeWidget(self)
            self.mainlayout.addWidget(self.view)
            self.tabs.setCurrentIndex(1)
