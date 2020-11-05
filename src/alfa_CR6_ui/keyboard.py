#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QApplication, QGridLayout, QWidget, QPushButton, QSizePolicy
from collections import namedtuple
import json

has_evdev = True
try:
    from evdev import UInput, ecodes as e
except BaseException:
    has_evdev = False

KeyButton = namedtuple('KeyButton', 'name label posx posy endx endy')


class Keyboard(QWidget):
    buttons = []

    def __init__(self, parent=None):
        super().__init__(parent)
        with open(QApplication.instance().keyboard_path + "/it.json", 'r') as keyboard_json:
            keyboard_def = json.load(keyboard_json)
        print(keyboard_def)
        yadd = 0
        for y, row in enumerate(keyboard_def):
            x = 0
            wtmp = 1
            htmp = 1
            for element in row:
                h = htmp
                w = wtmp
                wtmp = 1
                htmp = 1
                if isinstance(element, str):
                    button = KeyButton(self.evdev_convert(element), element, (y + yadd) * 4, x * 4, h * 4, w * 4)
                    self.buttons.append(button)
                    x += w
                else:
                    if 'x' in element.keys():
                        x += element['x']
                    if 'y' in element.keys():
                        yadd += element['y']
                    if 'h' in element.keys():
                        htmp = element['h']
                    if 'w' in element.keys():
                        wtmp = element['w']

        layout = QGridLayout()
        for button in self.buttons:
            pushButton = QPushButton(button.label)
            pushButton.setFocusPolicy(Qt.NoFocus)
            pushButton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            if has_evdev:
                pushButton.clicked.connect((lambda n: lambda: self.on_pushButton_clicked(n))(button.name))
            layout.addWidget(pushButton, button.posx, button.posy, button.endx, button.endy)
        self.setLayout(layout)

    def evdev_convert(self, el):
        if not has_evdev:
            return ""

        ev_dict = {
            'q': e.KEY_Q,
            'w': e.KEY_W,
            'e': e.KEY_E,
            'r': e.KEY_R,
            't': e.KEY_T,
            'y': e.KEY_Y,
            'u': e.KEY_U,
            'i': e.KEY_I,
            'o': e.KEY_O,
            'p': e.KEY_P,
            'c': e.KEY_C,
            'd': e.KEY_D
        }
        r = ev_dict.get(el, 0)
        return r

    def on_pushButton_clicked(self, name):
        if not has_evdev:
            return
        ui = UInput()
        print(name)
        ui.write(e.EV_KEY, name, 1)
        QTimer.singleShot(100, lambda: self.pullUp(name, ui))

    def pullUp(self, name, ui):
        print(name)
        ui.write(e.EV_KEY, name, 0)
        ui.syn()
        ui.close()
