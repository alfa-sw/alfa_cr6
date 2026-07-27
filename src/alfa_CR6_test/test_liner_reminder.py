# coding: utf-8

"""Regression tests for the optional PPS liner reminder."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from alfa_CR6_frontend import home_page


class _FakeApplication:

    def __init__(self):
        self.commands = []

    def run_a_coroutine_helper(self, command):
        self.commands.append(command)


class _FakeQApplication:

    application = None

    @staticmethod
    def instance():
        return _FakeQApplication.application


class _FakeMainWindow:

    def __init__(self):
        self.alerts = []

    def open_alert_dialog(self, args, **kwargs):
        self.alerts.append((args, kwargs))


class _HomePageHarness:

    _on_feed_jar_clicked = home_page.HomePage._on_feed_jar_clicked
    _start_feed_jar = staticmethod(home_page.HomePage._start_feed_jar)

    def __init__(self):
        self.main_window = _FakeMainWindow()


class LinerReminderTest(unittest.TestCase):

    def setUp(self):
        self.application = _FakeApplication()
        _FakeQApplication.application = self.application

    def test_disabled_setting_starts_feed_without_popup(self):
        page = _HomePageHarness()
        settings = SimpleNamespace(REMINDER_LINER=False)

        with patch.object(home_page, "g_settings", settings), \
                patch.object(home_page, "QApplication", _FakeQApplication):
            page._on_feed_jar_clicked()

        self.assertEqual(self.application.commands, ["move_00_01"])
        self.assertEqual(page.main_window.alerts, [])

    def test_enabled_setting_starts_feed_and_shows_wide_ok_only_popup(self):
        page = _HomePageHarness()
        settings = SimpleNamespace(REMINDER_LINER=True)

        with patch.object(home_page, "g_settings", settings), \
                patch.object(home_page, "QApplication", _FakeQApplication):
            page._on_feed_jar_clicked()

            self.assertEqual(self.application.commands, ["move_00_01"])
            self.assertEqual(len(page.main_window.alerts), 1)
            args, options = page.main_window.alerts[0]
            self.assertEqual(args, ())
            self.assertEqual(options["fmt"], home_page.LINER_REMINDER_MESSAGE)
            self.assertEqual(options["title"], "REMINDER")
            self.assertFalse(options["show_cancel_btn"])
            self.assertTrue(options["show_ok_btn"])
            self.assertEqual(options["image_name"], "reminder_pps_liner.png")
            self.assertTrue(options["ok_only"])
            self.assertEqual(options["width_scale"], 1.5)
            self.assertTrue(options["bold_message"])


if __name__ == "__main__":
    unittest.main()
