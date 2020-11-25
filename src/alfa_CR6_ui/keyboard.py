#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import traceback

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QApplication, QGridLayout, QWidget, QPushButton, QSizePolicy
from collections import namedtuple
import json

has_evdev = True
try:
    from evdev import UInput, ecodes as e
except BaseException:
    has_evdev = False
    logging.error(traceback.format_exc())

KeyButton = namedtuple('KeyButton', 'key label posx posy endx endy button')
KeyAction = namedtuple('KeyAction', 'key push')


class Keyboard(QWidget):
    buttons = []
    lang = "it"
    shifted = False

    def __init__(self, parent=None):
        super().__init__(parent)
        with open(QApplication.instance().keyboard_path + "/it.json", 'r') as keyboard_json:
            keyboard_def = json.load(keyboard_json)
        self.setFixedSize(900, 256)
        # ~ self.setFixedSize(900, 300)
        self.move(600, 760)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)

        self.setStyleSheet("""
                QWidget {
                    background-color: #FFFFF7;
                    font-size: 20px;
                    font-family: monospace;
                    }
                """)

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
                    pushButton = QPushButton(self.i18n(element), parent=self)
                    button = KeyButton(
                        self.evdev_convert(element),
                        element,
                        (y + yadd) * 4,
                        x * 4,
                        h * 4,
                        w * 4,
                        pushButton)
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
            button.button.setFocusPolicy(Qt.NoFocus)
            button.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            if self.special_key(button.key):
                button.button.clicked.connect((lambda n: lambda: self.change(n))(button.key))
            elif has_evdev:
                button.button.clicked.connect((lambda n: lambda: self.on_pushButton_clicked(n))(button.key))
            layout.addWidget(button.button, button.posx, button.posy, button.endx, button.endy)
        self.setLayout(layout)

        self.uinput = None
        if has_evdev:
            try:
                import getpass
                logging.warning(f"getpass.getuser():{getpass.getuser()}")
                if getpass.getuser() == 'admin':
                    os.system("sudo chgrp input /dev/uinput ; sudo chmod 770 /dev/uinput")
            except Exception:
                logging.error(traceback.format_exc())
            self.uinput = UInput()

        logging.warning(f"self.uinput:{self.uinput}")

    def hide(self):
        super().hide()
        for b in self.buttons:
            b.button.hide()

    def show(self):
        super().show()
        for b in self.buttons:
            b.button.show()

    def ev_definitions(self):
        ev_dict = {  # for chars not handled by e.kEY_<key>
            "LANG": self.lang.upper(),
            "Shift": "Shift",
        }

        return ev_dict  # ev_dict.get(el, el)

    def special_key(self, key):
        if self.ev_definitions().get(key, False):
            return True
        else:
            return False

    def evdev_convert(self, el):
        if self.special_key(el):
            return el
        try:
            r = e.ecodes['KEY_' + el.upper().split('\n')[-1]]
            return r
        except BaseException:
            return el

    def i18n(self, le):

        l = self.ev_definitions().get(le, le)

        latin_korean = {'normal': {
            'q': 'ㅂ', 'w': 'ㅈ', 'e': 'ㄷ', 'r': 'ㄱ', 't': '쇼', 'y': 'ㅕ', 'u': 'ㅑ', 'i': 'ㅐ', 'o': 'ㅔ', 'p': 'ㅁ',
            'a': 'ㅁ', 's': 'ㄴ', 'd': 'ㅇ', 'f': 'ㄹ', 'g': 'ㅎ', 'h': 'ㅗ', 'j': 'ㅓ', 'k': 'ㅏ', 'l': 'ㅣ',
            'z': 'ㅋ', 'x': 'ㅌ', 'c': 'ㅊ', 'v': 'ㅍ', 'b': 'ㅠ', 'n': 'ㅜ', 'm': 'ㅡ'
        },
            'shifted': {
            'q': 'ㅃ', 'w': 'ㅉ', 'e': 'ㄸ', 'r': 'ㄲ', 't': 'ㅆ',
            'o': 'ㅒ', 'p': 'ㅖ'}
        }

        if self.lang == "kr":
            letter = latin_korean['normal'].get(l, l)
            if self.shifted:
                letter = latin_korean['shifted'].get(l, letter)
            return letter
        elif self.lang == "it" and self.shifted:
            return l.upper()

        return l

    def isletter(self, key):
        return key.isalpha() and len(key) == 1

    def redraw_buttons(self):
        for button in self.buttons:
            button.button.setText(self.i18n(button.label))

    def change(self, item):
        if (item == 'Shift'):
            self.shifted = not self.shifted
        elif item == "LANG":
            if self.lang == "it":
                self.lang = "kr"
                self.hangeul_toggle()
            elif self.lang == "kr":
                self.lang = "it"
                self.hangeul_toggle()
        self.redraw_buttons()

    def on_pushButton_clicked(self, key):
        if not has_evdev:
            return
        keys = [KeyAction(key, True),
                KeyAction(key, False)]
        if self.shifted:
            keys = self.shifted_symbol(keys)
        self.pushdispatcher(keys)

    def shifted_symbol(self, keys):
        start = [KeyAction(e.ecodes['KEY_LEFTSHIFT'], True)]
        end = [KeyAction(e.ecodes['KEY_LEFTSHIFT'], False)]
        return start + keys + end

    def hangeul_toggle(self):
        self.pushdispatcher([KeyAction(e.ecodes['KEY_HANGUEL'], True),
                             KeyAction(e.ecodes['KEY_HANGUEL'], False), ])

    def pushdispatcher(self, keys):

        # ~ logging.warning(f"self:{self}, keys:{keys}, self.uinput:{self.uinput}")
        try:
            if keys == []:
                if self.uinput:
                    self.uinput.syn()
                # ~ self.uinput.close()
                return
            if keys[0].push:
                self.push(keys)
            else:
                self.pull(keys)

        except Exception:
            logging.error(traceback.format_exc())

    def push(self, keys):
        if self.uinput:
            self.uinput.write(e.EV_KEY, keys[0].key, 1)
            QTimer.singleShot(50, lambda: self.pushdispatcher(keys[1:]))

    def pull(self, keys):
        if self.uinput:
            self.uinput.write(e.EV_KEY, keys[0].key, 0)
            QTimer.singleShot(50, lambda: self.pushdispatcher(keys[1:]))
