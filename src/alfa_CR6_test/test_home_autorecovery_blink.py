# coding: utf-8

"""Home status blinking with real Qt widgets and manually driven timer ticks."""

import os
from pathlib import Path
import types
import unittest
from unittest import mock

from PyQt5.QtCore import QCoreApplication, QEvent, QTimer
from PyQt5.QtWidgets import QApplication, QFrame
from PyQt5.uic import loadUi

import alfa_CR6_frontend.home_page as home_module


class TestHomeAutorecoveryBlink(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.pages = []
        self.app = types.SimpleNamespace(
            _head_safety_states={index: 'STANDBY' for index in range(7)},
            machine_head_dict={},
            carousel_frozen=True,
            freeze_carousel=mock.Mock(),
        )
        self.app_patch = mock.patch.object(
            home_module.QApplication, 'instance', return_value=self.app)
        self.app_patch.start()
        self.translation_patch = mock.patch.object(
            home_module, 'tr_', side_effect=lambda text: text)
        self.translation_patch.start()

    def tearDown(self):
        for page in self.pages:
            page.close()
            page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.translation_patch.stop()
        self.app_patch.stop()

    def _page(self, page_class=home_module.HomePageSixHeads):
        # Load the actual variant's UI without starting business logic, devices,
        # movies or the other independent animations on HomePage.
        page = page_class.__new__(page_class)
        QFrame.__init__(page)
        self.pages.append(page)
        ui_path = Path(home_module.__file__).parent / 'ui' / page_class.ui_file_name
        loadUi(str(ui_path), page)
        page.service_1_btn.setStyleSheet('QPushButton { border: 2px solid #123456; }')
        page._init_autorecovery_blink()
        page.show()
        self.qt_app.processEvents()
        return page

    def test_mixed_outcomes_stop_each_head_independently_and_keep_freeze(self):
        page = self._page()
        original_a = page.service_1_btn.styleSheet()
        original_f = page.service_2_btn.styleSheet()
        self.app._head_safety_states.update({0: 'AUTORECOVERY', 1: 'AUTORECOVERY'})
        page.update_autorecovery_indication()
        timer = page._autorecovery_blink_timer

        self.assertEqual(timer.interval(), 500)
        self.assertTrue(timer.isActive())
        for button in (page.service_1_btn, page.service_2_btn):
            self.assertEqual(button.text(), 'AUTORECOVERY')
            self.assertIn('#FFC857', button.styleSheet())
            self.assertTrue(button.isVisible())

        timer.timeout.emit()
        for button in (page.service_1_btn, page.service_2_btn):
            self.assertEqual(button.text(), 'AUTORECOVERY')
            self.assertNotIn('#FFC857', button.styleSheet())
            self.assertIn('font-weight: bold', button.styleSheet())

        self.app._head_safety_states[0] = 'STANDBY'
        page.update_autorecovery_indication()
        self.assertEqual(page.service_1_btn.text(), 'STANDBY')
        self.assertEqual(page.service_1_btn.styleSheet(), original_a)
        self.assertEqual(page._autorecovery_heads, {1})
        self.assertTrue(timer.isActive())
        timer.timeout.emit()
        self.assertIn('#FFC857', page.service_2_btn.styleSheet())

        self.app._head_safety_states[1] = 'ALARM'
        page.update_autorecovery_indication()
        self.assertEqual(page.service_2_btn.text(), 'ALARM')
        self.assertEqual(page.service_2_btn.styleSheet(), original_f)
        self.assertFalse(timer.isActive())
        self.assertFalse(page._autorecovery_blink_on)
        self.assertTrue(self.app.carousel_frozen)
        self.app.freeze_carousel.assert_not_called()

    def test_added_heads_and_repeated_updates_share_the_current_phase(self):
        page = self._page()
        self.app._head_safety_states[0] = 'AUTORECOVERY'
        page.update_autorecovery_indication()
        timer = page._autorecovery_blink_timer
        timer.timeout.emit()

        self.app._head_safety_states[1] = 'AUTORECOVERY'
        page.update_autorecovery_indication()
        page.update_autorecovery_indication()
        self.assertIs(page._autorecovery_blink_timer, timer)
        self.assertEqual(page.findChildren(QTimer), [timer])
        self.assertFalse(page._autorecovery_blink_on)
        for button in (page.service_1_btn, page.service_2_btn):
            self.assertNotIn('#FFC857', button.styleSheet())

        timer.timeout.emit()
        for button in (page.service_1_btn, page.service_2_btn):
            self.assertIn('#FFC857', button.styleSheet())

    def test_hidden_home_stops_timer_and_rechecks_states_on_show(self):
        self.app._head_safety_states[0] = 'AUTORECOVERY'
        page = self._page()
        timer = page._autorecovery_blink_timer
        self.assertTrue(timer.isActive())

        page.hide()
        self.assertFalse(timer.isActive())
        self.assertFalse(page._autorecovery_blink_on)
        timer.timeout.emit()  # A queued tick cannot restart a hidden page.
        self.assertFalse(timer.isActive())

        self.app._head_safety_states.update({0: 'STANDBY', 1: 'AUTORECOVERY'})
        page.update_autorecovery_indication()
        self.assertFalse(timer.isActive())
        page.show()
        self.qt_app.processEvents()
        self.assertTrue(timer.isActive())
        self.assertEqual(page.service_1_btn.text(), 'STANDBY')
        self.assertNotIn('#FFC857', page.service_1_btn.styleSheet())
        self.assertIn('#FFC857', page.service_2_btn.styleSheet())

        page.hide()
        self.app._head_safety_states[1] = 'ALARM'
        # Re-entry must also handle changes received without a home repaint.
        page.show()
        self.qt_app.processEvents()
        self.assertFalse(timer.isActive())
        self.assertEqual(page.service_2_btn.text(), 'ALARM')

    def test_unverified_head_does_not_keep_blinking_a_stale_raw_status(self):
        self.app._head_safety_states[0] = 'AUTORECOVERY'
        self.app.machine_head_dict[0] = types.SimpleNamespace(
            status={'status_level': 'AUTORECOVERY'})
        page = self._page()
        self.app._head_safety_states[0] = None
        page.update_autorecovery_indication()

        self.assertFalse(page._autorecovery_blink_timer.isActive())
        self.assertEqual(page.service_1_btn.text(), 'NONE')
        self.assertNotIn('#FFC857', page.service_1_btn.styleSheet())
        self.assertTrue(self.app.carousel_frozen)
        self.app.freeze_carousel.assert_not_called()

        self.app._head_safety_states[0] = 'AUTORECOVERY'
        page.update_autorecovery_indication()
        self.assertTrue(page._autorecovery_blink_timer.isActive())
        self.assertIn('#FFC857', page.service_1_btn.styleSheet())

    def test_all_variants_highlight_only_their_present_heads(self):
        variants = (
            (home_module.HomePageSixHeads, {0, 1, 2, 3, 4, 5}),
            (home_module.HomePageFourHeads, {0, 1, 4, 5}),
            (home_module.HomePageCRX60Heads, {0, 2, 4}),
            (home_module.HomePageCRX80Heads, {0, 2, 4, 6}),
            (home_module.HomePageCRX40Heads, {0, 4}),
        )
        self.app._head_safety_states = {index: 'AUTORECOVERY' for index in range(7)}
        for page_class, present in variants:
            with self.subTest(variant=page_class.__name__):
                page = self._page(page_class)
                self.assertEqual(page._autorecovery_heads, present)
                self.assertTrue(page._autorecovery_blink_timer.isActive())
                for index in present:
                    button = page._head_status_buttons[index]
                    self.assertEqual(button.text(), 'AUTORECOVERY')
                    self.assertIn('#FFC857', button.styleSheet())
                page.hide()


if __name__ == '__main__':
    unittest.main()
