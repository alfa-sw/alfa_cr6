"""Hardware-free checks for the scale-refill connection precondition."""

import json
import unittest
from unittest import mock

from alfa_CR6_backend import globals as globals_module
from alfa_CR6_frontend import home_page
from alfa_CR6_frontend.dialogs import InputDialog


class _Redis:
    def __init__(self, value):
        self.value = value

    def get(self, key):
        if key != globals_module.SCALE_STATUS_REDIS_KEY:
            raise AssertionError(key)
        return self.value


class TestScaleConnectionStatus(unittest.TestCase):
    def _is_connected(self, payload):
        value = None if payload is None else json.dumps(payload).encode()
        with mock.patch.object(
                globals_module.redis, "Redis", return_value=_Redis(value)):
            return globals_module.is_scale_connected()

    def test_explicit_connection_flag_is_authoritative(self):
        self.assertTrue(self._is_connected({
            "status_level": "OFF", "connected": True}))
        self.assertFalse(self._is_connected({
            "status_level": "ON", "connected": False}))

    def test_missing_status_means_not_connected(self):
        self.assertFalse(self._is_connected(None))

    def test_old_dispatcher_on_status_remains_compatible(self):
        self.assertTrue(self._is_connected({"status_level": "ON"}))
        self.assertFalse(self._is_connected({"status_level": "OFF"}))


class _MainWindow:
    def __init__(self):
        self.dialogs = []
        self.keyboard_states = []

    def toggle_keyboard(self, on_off):
        self.keyboard_states.append(on_off)

    def open_input_dialog(self, **kwargs):
        self.dialogs.append(kwargs)


class _Content:
    def __init__(self, text=""):
        self.text = text

    def toPlainText(self):
        return self.text


class _Button:
    def __init__(self):
        self.enabled = None

    def setEnabled(self, enabled):
        self.enabled = enabled


class TestRequiredDialogContent(unittest.TestCase):
    def setUp(self):
        self.callback_calls = []
        self.dialog = mock.Mock(
            ok_requires_content=True,
            ok_on_enter=True,
            content_container=_Content(),
            ok_button=_Button(),
        )
        self.dialog.on_ok_button_clicked = (
            lambda: self.callback_calls.append(True))

    def test_empty_or_whitespace_content_keeps_ok_disabled(self):
        self.dialog.content_container.text = "  \n"
        InputDialog.on_text_cahnged(self.dialog)

        self.assertIs(self.dialog.ok_button.enabled, False)
        self.assertEqual([], self.callback_calls)

    def test_scanned_content_enables_ok_and_submits_on_enter(self):
        self.dialog.content_container.text = "ABC123\n"
        InputDialog.on_text_cahnged(self.dialog)

        self.assertIs(self.dialog.ok_button.enabled, True)
        self.assertEqual([True], self.callback_calls)


class TestScaleRefillPrecheck(unittest.TestCase):
    def setUp(self):
        self.main_window = _MainWindow()
        parent = mock.Mock(main_window=self.main_window)
        self.helper = home_page.ScaleRefillProcedureHelper(parent)

    def test_disconnected_scale_shows_warning_instead_of_s1(self):
        with mock.patch.object(home_page, "is_scale_connected", return_value=False), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self.helper.run()

        self.assertEqual([False], self.main_window.keyboard_states)
        self.assertEqual(1, len(self.main_window.dialogs))
        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxWarning", dialog["icon_name"])
        self.assertIn("No scale was detected", dialog["message"])
        self.assertIsNone(dialog["content"])

    def test_connected_scale_opens_first_instruction(self):
        with mock.patch.object(home_page, "is_scale_connected", return_value=True), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self.helper.run()

        self.assertEqual(1, len(self.main_window.dialogs))
        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxQuestion", dialog["icon_name"])
        self.assertIn("Place the open canister", dialog["message"])
        self.assertEqual("", dialog["content"])
        self.assertIs(dialog["ok_requires_content"], True)


class TestRefillEventGate(unittest.TestCase):
    def _is_active(self, status_level, crx_outputs_status=0):
        app = mock.Mock(
            carousel_frozen=True,
            machine_head_dict={
                0: mock.Mock(status={
                    "status_level": status_level,
                    "crx_outputs_status": crx_outputs_status,
                }),
            },
        )
        with mock.patch.object(home_page.QApplication, "instance", return_value=app), \
                mock.patch.object(
                    home_page.g_settings,
                    "USE_PIGMENT_ID_AS_BARCODE",
                    True,
                    create=True,
                ):
            return home_page.HomePage.refill_lbl_is_active(0)

    def test_standby_head_accepts_refill_event(self):
        self.assertTrue(self._is_active("STANDBY"))

    def test_positioning_head_ignores_refill_event(self):
        self.assertFalse(self._is_active("JAR_POSITIONING"))

    def test_alarm_head_ignores_refill_event(self):
        self.assertFalse(self._is_active("ALARM"))

    def test_active_crx_outputs_ignore_refill_event(self):
        self.assertFalse(self._is_active("STANDBY", crx_outputs_status=1))


if __name__ == "__main__":
    unittest.main()
