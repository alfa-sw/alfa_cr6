#!/usr/bin/env python
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import QGridLayout, QWidget, QPushButton
from collections import namedtuple
import pyautogui

KeyButton=namedtuple('KeyButton', 'name label posx posy')


class Keyboard(QWidget):
    buttons=[
            KeyButton('q', 'q', 0, 0),
            KeyButton('w', 'w', 0, 1),
            KeyButton('e', 'e', 0, 2),
            KeyButton('r', 'r', 0, 3),
            KeyButton('t', 't', 0, 4),
            KeyButton('y', 'y', 0, 5),
            KeyButton('u', 'u', 0, 6),
            KeyButton('i', 'i', 0, 7),
            KeyButton('o', 'o', 0, 8),
            KeyButton('p', 'p', 0, 9),
            KeyButton('c', 'c', 1, 0),
            KeyButton('d', 'd', 1, 1),

            ]
            
            
            
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QGridLayout()
        for button in self.buttons:
            pushButton = QPushButton(button.label)
            pushButton.clicked.connect((lambda n: lambda : self.on_pushButton_clicked(n))(button.name))
            layout.addWidget(pushButton, button.posx, button.posy)
        self.setLayout(layout)

        

    def on_pushButton_clicked(self, name):
        pyautogui.press(name)
