from alfa_CR6.mainwindow import MainWindow
from alfa_CR6.login import Login

class Controller:
    path=None

    def __init__(self, path):
        self.path=path

    def show_login(self):
        self.login = Login(self.path)
        self.login.show()
