import sys
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QApplication, QDialog, QMainWindow, QPushButton
from PyQt5 import QtWidgets, uic, QtCore
from PyQt5.Qt import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QLineEdit, QGridLayout, QMessageBox
from PyQt5 import QtGui

class MainWindow(QMainWindow):
    switch_window = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi("src/alfa_CR6/mainwindow.ui", self)
        self.dialog_1_btn.clicked.connect(self.onDialog1BtnClicked)
        self.chrome_btn.clicked.connect(self.onChromeBtnClicked)

    def onDialog1BtnClicked(self):
        dlg = Dialog1(self)
        dlg.exec()

    def onChromeBtnClicked(self):
        dlg = ChromeDialog(self)
        dlg.exec()


class Login(QMainWindow):
    switch_window = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi("src/alfa_CR6/login.ui", self)
        self.login_btn.clicked.connect(self.onLoginBtnClicked)


    def onLoginBtnClicked(self):
        msg = QMessageBox()
        if self.user_edit.text() == '' and self.pass_edit.text() == '':
            self.user_edit.clear()
            self.pass_edit.clear()
            window = MainWindow()
            form = window
            window.show()
            self.switch_window.emit()

        else:
            msg.setText('Incorrect Password')
            msg.exec_()


class Controller:
    def __init__(self):
        pass

    def show_login(self):
        self.login = Login()
        self.login.switch_window.connect(self.show_main)
        self.login.show()

    def show_main(self):
        self.window = MainWindow()
        self.window.show()


class Dialog1(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi("src/alfa_CR6/dialog.ui", self)


class ChromeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi("src/alfa_CR6/chrome.ui", self)
        view = QWebEngineView(self)
        view.setUrl(QUrl("http://www.google.com"))
        view.resize(1440, 730)
        view.show()
        self.cancel_btn.clicked.connect(self.onCancelBtnClicked)


    def onCancelBtnClicked(self):
        self.hide()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = Controller()
    controller.show_login()
    sys.exit(app.exec_())
