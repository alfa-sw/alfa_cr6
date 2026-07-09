# coding: utf-8

# pylint: disable=missing-docstring

"""
Il Cancel sul dialog di freeze deve silenziare la notifica sonora refill.

CONTESTO: l'OK del frozen dialog sblocca il carosello -> il flusso refill
arriva al finally -> release_attention_leds -> stop del suono. Il Cancel
invece chiude il dialog LASCIANDO il freeze: senza aggancio, il suono
continuava fino al timeout del setting. Fix: ModalMessageBox.cancel_callback,
cablato da open_frozen_dialog a sound_player.stop_refill_alarm.

Esecuzione:
    QT_QPA_PLATFORM=offscreen PYTHONPATH=/opt/PROJECTS/alfa_cr6/src \
        /opt/alfa_cr6/venv/bin/python3 -m unittest \
        alfa_CR6_test.test_dialog_cancel_stops_refill -v
"""

import logging
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget  # pylint: disable=no-name-in-module

from alfa_CR6_frontend.dialogs import ModalMessageBox

try:
    import alfa_CR6_frontend.main_window as main_window_module
    MAIN_WINDOW_CLS = main_window_module.MainWindow
except Exception:  # pylint: disable=broad-except
    main_window_module = None
    MAIN_WINDOW_CLS = None


class _FakeApp(QApplication):

    def __init__(self, argv):
        super().__init__(argv)
        self.freeze_calls = []

    def freeze_carousel(self, flag):
        self.freeze_calls.append(flag)

    def insert_db_event(self, **kwargs):
        pass


def _btn(box, name):
    return next(b for b in box.buttons() if b.objectName().lower() == name)


class TestCancelCallback(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or _FakeApp([])
        logging.disable(logging.WARNING)

    @classmethod
    def tearDownClass(cls):
        logging.disable(logging.NOTSET)

    def test_cancel_fires_callback_ok_does_not(self):

        parent = QWidget()
        calls = []
        box = ModalMessageBox(
            parent=parent, msg="m", title="t",
            ok_callback=lambda: calls.append('ok'),
            cancel_callback=lambda: calls.append('cancel'),
        )
        _btn(box, 'esc').click()
        self.assertEqual(calls, ['cancel'])

        box2 = ModalMessageBox(
            parent=parent, msg="m", title="t",
            ok_callback=lambda: calls.append('ok'),
            cancel_callback=lambda: calls.append('cancel'),
        )
        _btn(box2, 'ok').click()
        self.assertEqual(calls, ['cancel', 'ok'])

    def test_frozen_dialog_cancel_stops_refill_alarm(self):

        if MAIN_WINDOW_CLS is None:
            self.skipTest("MainWindow / QtWebEngineWidgets non disponibili")
        if not hasattr(self.app, "freeze_calls"):
            self.skipTest("serve _FakeApp (hook freeze_carousel/insert_db_event)")

        stop_calls = []
        orig = main_window_module.stop_refill_alarm
        main_window_module.stop_refill_alarm = lambda: stop_calls.append(1)
        try:
            class _FakeMainWindow(QWidget):
                open_alert_dialog = MAIN_WINDOW_CLS.open_alert_dialog
                open_frozen_dialog = MAIN_WINDOW_CLS.open_frozen_dialog

            mw = _FakeMainWindow()
            from PyQt5.QtWidgets import QMessageBox  # pylint: disable=no-name-in-module

            # Cancel: suono silenziato, carosello NON sbloccato
            self.app.freeze_calls.clear()
            mw.open_frozen_dialog(("BC1",), message_fmt="please refill {}", title="ALERT")
            box = mw.findChildren(QMessageBox)[-1]
            _btn(box, 'esc').click()
            self.assertEqual(stop_calls, [1])
            self.assertEqual(self.app.freeze_calls, [])

            # OK: sblocca il carosello (lo stop arriva dal release del flusso refill)
            mw.open_frozen_dialog(("BC2",), message_fmt="please refill {}", title="ALERT")
            box = [b for b in mw.findChildren(QMessageBox)][-1]
            _btn(box, 'ok').click()
            self.assertEqual(self.app.freeze_calls, [False])
            self.assertEqual(stop_calls, [1])
        finally:
            main_window_module.stop_refill_alarm = orig


if __name__ == '__main__':
    unittest.main()
