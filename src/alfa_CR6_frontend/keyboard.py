# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=import-error

import os
import logging
import traceback
from collections import namedtuple
import json

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import QApplication, QGridLayout, QWidget, QPushButton, QSizePolicy

has_evdev = True
try:
    from evdev import UInput, ecodes as e
except Exception:
    has_evdev = False
    logging.error(traceback.format_exc())

KeyButton = namedtuple('KeyButton', 'key label posx posy endx endy button')
KeyAction = namedtuple('KeyAction', 'key push')

""" http://www.keyboard-layout-editor.com/

    Impostazione tastiera
    apt get install ibus-hangul
    Impostazone manuale del Raspberry per usare ibus e di ibus per abilitare il toggle
    hangul; dovrebbe comparire il simbolo relativo in alto a destra si puo' switchare
    manualmente da caratteri latini a coreani con SHIFT - SPACE, in tastiere dove il
    tasto HANGEUL non e' presente per verificare o modificare la tastiera si puo'
    switchare da italiano a coreano e provari i vari tasti con o senza shift
    NOTE:
    alcuni caratteri coreani possono essere shiftati, ma la maggior parte rimangono
    uguali (non esistono lettere maiuscole ma ci sono piu' caratteri che nella tastiera
    QWERTY).Alcuni caratteri si compongono tra loro, quindi bisogna digitarne uno alla
    volta, cancellando i precedenti o aggiungendo uno spazio per evitare di avere dei caratteri composti.
    PARTE CODICE
    la tastera e' realizzata tramite il widget QGridLayout che viene valorizzato tramite
    layout.addWidget( Widget, posX, posY, [endX, endY] ).
    Il layout della tastiera e' definito tramite un json ( riferimento http://www.keyboard-layout-editor.com/ per creare
    il layout della tastiera e di conseguenza il json), con lettere e eventuali opzioni di spaziatura (W: larghezza del
    pulsante, H: altezza, X: spazio tra i tasti)
    La traduzione caratteri latini/coreani e' definita in latin_korean nella funzione i18n()
    Dato che il pulsante KEY_HANGEUL e' solo un toggle, per essere sicuri che lo stato sia quello desiderato
    viene passato un "KEY_ESC", che fa uscire dalla modalita' di input coreana.
    Successivamente viene premuto KEY_HANGEUL alla bisogna, in modo da assicurarsi di avere la situazione
    della tastiera locale sempre corrispondente all'input.

"""


class Keyboard(QWidget):
    buttons = []
    lang = "en"
    shifted = False
    uinput = None

    def __init__(self, parent=None, keyboard_path=None, geometry=[0, 760, 1900, 256]):
        super().__init__(parent)

        self.special_keys_dict = {
            "LANG": self.lang.upper(),
            "Shift": "Shift",
        }

        if keyboard_path is None:
            keyboard_path = QApplication.instance().keyboard_path

        with open(keyboard_path + "/it.json", 'r') as keyboard_json:
            keyboard_def = json.load(keyboard_json)

        self.setGeometry(*geometry)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.hangeul_toggle(set_hangeul=False)

        self.setAutoFillBackground(True)

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

            # ~ logging.warning(f"button:{button}")

            button.button.setFocusPolicy(Qt.NoFocus)
            button.button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            if self.special_key(button.key):
                button.button.clicked.connect((lambda n:
                                               lambda: self.change(n))(button.key))
            elif has_evdev:
                button.button.clicked.connect((lambda n:
                                               lambda: self.on_pushButton_clicked(n))(button.key))

            layout.addWidget(button.button, button.posx, button.posy, button.endx, button.endy)
        self.setLayout(layout)

        self.uinput = None
        if has_evdev:
            try:

                import getpass
                logging.warning(f"getpass.getuser():{getpass.getuser()}")
                if getpass.getuser() == 'admin':
                    os.system("sudo chgrp input /dev/uinput ; sudo chmod 770 /dev/uinput")

                self.uinput = UInput()

            except Exception:
                logging.error(traceback.format_exc())

        logging.warning(f"self.uinput:{self.uinput}")

    def hide(self):
        super().hide()
        for b in self.buttons:
            b.button.hide()

    def show(self):
        super().show()
        for b in self.buttons:
            b.button.show()

    def special_key(self, key):

        # ~ logging.warning(f"key:{key}")

        ret = self.special_keys_dict.get(key, False)
        if ret:
            return True
        else:
            return False

    def symbol_act(self, symbol):
        symbols = {
            "?": "QUESTION",
            "/": "SLASH",
            '\\': "BACKSLASH",
            ".": "DOT",
            "=": "EQUAL",
            ",": "COMMA",
            ":": "COLON",
            ";": "SEMICOLON",
            "-": "MINUS",
            "_": "UNDERBAR",
            " ": "SPACE",

        }
        s = symbol.upper().split('\n')[-1]
        s = symbols.get(s, s)
        try:
            r = e.ecodes['KEY_' + s]
        except BaseException:
            logging.error("key {} not defined".format(s))
            return 0
        return r

    def evdev_convert(self, el):

        if self.special_key(el):
            ret = el
        else:
            ret = self.symbol_act(el.upper().split('\n')[-1])
        return ret

    def i18n(self, le):

        l = self.special_keys_dict.get(le, le)

        latin_korean = {
            'normal': {
                'q': 'ㅂ', 'w': 'ㅈ', 'e': 'ㄷ', 'r': 'ㄱ', 't': 'ㅅ', 'y': 'ㅛ', 'u': 'ㅕ', 'i': 'ㅑ', 'o': 'ㅐ', 'p': 'ㅔ',
                'a': 'ㅁ', 's': 'ㄴ', 'd': 'ㅇ', 'f': 'ㄹ', 'g': 'ㅎ', 'h': 'ㅗ', 'j': 'ㅓ', 'k': 'ㅏ', 'l': 'ㅣ',
                'z': 'ㅋ', 'x': 'ㅌ', 'c': 'ㅊ', 'v': 'ㅍ', 'b': 'ㅠ', 'n': 'ㅜ', 'm': 'ㅡ'},
            'shifted': {
                'q': 'ㅃ', 'w': 'ㅉ', 'e': 'ㄸ', 'r': 'ㄲ', 't': 'ㅆ', 'o': 'ㅒ', 'p': 'ㅖ'}
        }

        if self.shifted:
            if self.lang == "kr":
                non_shifted = latin_korean['normal'].get(l, l)
                l = latin_korean['shifted'].get(l, non_shifted)
            l = l.split('\n')[0]
            l = l[0].upper() + l[1:].upper()
        else:
            if self.lang == "kr":
                l = latin_korean['normal'].get(l, l)
            l = l.split('\n')[-1]

        return l

    def isletter(self, key):
        return key.isalpha() and len(key) == 1

    def redraw_buttons(self):
        for button in self.buttons:
            button.button.setText(self.i18n(button.label))

    def change(self, item):

        if item == 'Shift':
            self.shifted = not self.shifted
        elif item == "LANG":
            # TODO: multi lang NOT implemented
            logging.warning(f"multi lang NOT implemented")
            if 0:
                if self.lang == "en":
                    self.lang = "kr"
                    self.hangeul_toggle(set_hangeul=True)
                elif self.lang == "kr":
                    self.lang = "en"
                    self.hangeul_toggle(set_hangeul=False)

        self.redraw_buttons()

    def on_pushButton_clicked(self, key):

        if has_evdev:
            keys = [KeyAction(key, True),
                    KeyAction(key, False)]
            if self.shifted:
                keys = self.shifted_symbol(keys)
            self.pushdispatcher(keys)

    def shifted_symbol(self, keys):
        start = [KeyAction(e.ecodes['KEY_LEFTSHIFT'], True)]
        end = [KeyAction(e.ecodes['KEY_LEFTSHIFT'], False)]
        return start + keys + end

    def hangeul_toggle(self, set_hangeul=False):
        if not has_evdev:
            return
        actions = [KeyAction(e.ecodes['KEY_ESC'], True),
                   KeyAction(e.ecodes['KEY_ESC'], False), ]
        if set_hangeul:
            actions += [KeyAction(e.ecodes['KEY_HANGEUL'], True),
                        KeyAction(e.ecodes['KEY_HANGEUL'], False), ]
        self.pushdispatcher(actions)

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
