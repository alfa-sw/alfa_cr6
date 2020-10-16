from alfa_CR6.mainwindow import MainWindow
from alfa_CR6.login import Login

class Controller:
    path=None

    def __init__(self, path):
        self.path=path

    def show_login(self):
        self.login = Login(self.path)
        self.login.switch_window.connect(self.show_main)
        self.login.show()

    def show_main(self):
        self.window = MainWindow(self.path)
        self.window.show()
