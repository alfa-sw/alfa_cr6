import sys
import os
from PyQt5.QtWidgets import QApplication
from alfa_CR6.controller import Controller


PATH = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def main():
    app = QApplication(sys.argv)
    controller = Controller(PATH)
    controller.show_login()
    sys.exit(app.exec_())

