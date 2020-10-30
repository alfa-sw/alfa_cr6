#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QGridLayout, QWidget, QPushButton
from collections import namedtuple

has_evdev=True
try:
    from evdev import UInput, ecodes as e
except:
    has_evdev=False

KeyButton=namedtuple('KeyButton', 'name label posx posy')


class Keyboard(QWidget):
    if has_evdev:
        buttons=[
            KeyButton(e.KEY_Q, 'q', 0, 0),
            KeyButton(e.KEY_W, 'w', 0, 1),
            KeyButton(e.KEY_E, 'e', 0, 2),
            KeyButton(e.KEY_R, 'r', 0, 3),
            KeyButton(e.KEY_T, 't', 0, 4),
            KeyButton(e.KEY_Y, 'y', 0, 5),
            KeyButton(e.KEY_U, 'u', 0, 6),
            KeyButton(e.KEY_I, 'i', 0, 7),
            KeyButton(e.KEY_O, 'o', 0, 8),
            KeyButton(e.KEY_P, 'p', 0, 9),
            KeyButton(e.KEY_C, 'c', 1, 0),
            KeyButton(e.KEY_D, 'd', 1, 1),

            ]
    else:
        buttons=[
            KeyButton('', 'q', 0, 0),
            KeyButton('', 'w', 0, 1),
            KeyButton('', 'e', 0, 2),
            KeyButton('', 'r', 0, 3),
            KeyButton('', 't', 0, 4),
            KeyButton('', 'y', 0, 5),
            KeyButton('', 'u', 0, 6),
            KeyButton('', 'i', 0, 7),
            KeyButton('', 'o', 0, 8),
            KeyButton('', 'p', 0, 9),
            KeyButton('', 'c', 1, 0),
            KeyButton('', 'd', 1, 1),

            ]
            
            
            
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout()
        for button in self.buttons:
            pushButton = QPushButton(button.label)
            pushButton.setFocusPolicy(Qt.NoFocus)
            if has_evdev:
                pushButton.clicked.connect((lambda n: lambda : self.on_pushButton_clicked(n))(button.name))
            layout.addWidget(pushButton, button.posx, button.posy)
        self.setLayout(layout)

        

    def on_pushButton_clicked(self, name):
        if not has_evdev:
            return
        ui = UInput()
        ui.write(e.EV_KEY, name, 1)
        QTimer.singleShot(100, lambda : self.pullUp(name, ui))


    def pullUp(self, name, ui):
        ui.write(e.EV_KEY, name, 0)
        ui.syn()
        ui.close()
