from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QMainWindow
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMessageBox
from alfa_CR6.mainwindow import MainWindow

class Login(QMainWindow):
    switch_window = QtCore.pyqtSignal()
    path=None

    def __init__(self, path, parent=None):
        super().__init__(parent)
        loadUi(path+"/ui/login.ui", self)
        self.path=path
        self.login_btn.clicked.connect(self.onLoginBtnClicked)


    def onLoginBtnClicked(self):
        msg = QMessageBox()
        if self.user_edit.text() == '' and self.pass_edit.text() == '':
            self.user_edit.clear()
            self.pass_edit.clear()
            window = MainWindow(self.path)
            window.show()
            self.switch_window.emit()

        else:
            msg.setText('Incorrect Password')
            msg.exec_()
