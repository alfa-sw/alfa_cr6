"""Hardware-free checks for the scale-refill connection precondition."""

import json
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from unittest import mock

from alfa_CR6_backend import globals as globals_module
from alfa_CR6_frontend import dialogs as dialogs_module, home_page
from alfa_CR6_frontend.dialogs import InputDialog


class _Redis:
    def __init__(self, value):
        self.value = value

    def get(self, key):
        if key != globals_module.SCALE_STATUS_REDIS_KEY:
            raise AssertionError(key)
        return self.value


class TestScaleConnectionStatus(unittest.TestCase):
    def _state(self, payload):
        value = None if payload is None else json.dumps(payload).encode()
        with mock.patch.object(
                globals_module.redis, "Redis", return_value=_Redis(value)):
            return globals_module.get_scale_connection_state()

    def test_usb_connection_does_not_mean_scale_is_ready(self):
        self.assertEqual("not_responding", self._state({
            "status_level": "OFF", "connected": True}))
        self.assertEqual("disconnected", self._state({
            "status_level": "ON", "connected": False}))
        self.assertEqual("ready", self._state({
            "status_level": "ON", "connected": True}))

    def test_missing_status_means_disconnected(self):
        self.assertEqual("disconnected", self._state(None))

    def test_old_dispatcher_on_status_remains_compatible(self):
        self.assertEqual("ready", self._state({"status_level": "ON"}))
        self.assertEqual("disconnected", self._state({"status_level": "OFF"}))


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

    def test_disconnected_scale_shows_usb_warning_instead_of_s1(self):
        with mock.patch.object(home_page, "get_scale_connection_state",
                               return_value="disconnected"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self.helper.run()

        self.assertEqual([False], self.main_window.keyboard_states)
        self.assertEqual(1, len(self.main_window.dialogs))
        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxWarning", dialog["icon_name"])
        self.assertIn("No scale was detected", dialog["message"])
        self.assertIsNone(dialog["content"])

    def test_connected_unresponsive_scale_shows_power_warning(self):
        with mock.patch.object(home_page, "get_scale_connection_state",
                               return_value="not_responding"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self.helper.run()

        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxWarning", dialog["icon_name"])
        self.assertIn("Check that it is switched on", dialog["message"])
        self.assertIsNone(dialog["content"])

    def test_ready_scale_opens_first_instruction(self):
        with mock.patch.object(home_page, "get_scale_connection_state",
                               return_value="ready"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self.helper.run()

        self.assertEqual(1, len(self.main_window.dialogs))
        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxQuestion", dialog["icon_name"])
        self.assertIn("Place the open canister", dialog["message"])
        self.assertEqual("", dialog["content"])
        self.assertIs(dialog["ok_requires_content"], True)

    def test_invalid_specific_weight_is_rejected_after_first_barcode(self):
        machine = mock.Mock(name="machine")
        pigment = {
            "customer_id": "PRODUCT-1",
            "specific_weight": 0,
            "pipes": [],
        }
        pipe = {
            "enabled": True,
            "sync": True,
            "effective_specific_weight": 0,
        }
        pigment["pipes"].append(pipe)
        machine.pigment_list = [pigment]
        app = mock.Mock(machine_head_dict={0: machine})
        self.helper._dialog_barcode = mock.Mock(return_value="PRODUCT-1")
        self.helper._show_error = mock.Mock()
        self.helper._prepare_target = mock.Mock()

        with mock.patch.object(
                home_page.QApplication, "instance", return_value=app), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self.helper._on_initial_barcode()

        self.helper._show_error.assert_called_once_with(
            "The product specific weight is not valid.")
        self.helper._prepare_target.assert_not_called()
        self.assertIsNone(self.helper.specific_weight_)

    def test_result_offers_continue_refill_action(self):
        self.helper.machine_ = mock.Mock(name="machine", machine_config={})
        self.helper.machine_.name = "A"
        self.helper.pipe_ = {"maximum_level": 100, "current_level": 20}
        self.helper._refresh_after_refill = mock.Mock(
            return_value=mock.sentinel.refresh)

        with mock.patch.object(home_page, "tr_", side_effect=lambda value: value), \
                mock.patch.object(home_page.asyncio, "ensure_future"):
            self.helper._show_result({}, 10, 5, 2)

        dialog = self.main_window.dialogs[-1]
        self.assertEqual("Continue refill", dialog["action_text"])
        self.assertEqual(
            self.helper._continue_refill, dialog["action_cb"])

    def test_continue_refill_restarts_from_first_instruction(self):
        self.helper.machine_ = mock.sentinel.machine
        self.helper.pigment_ = mock.sentinel.pigment
        self.helper.pipe_ = mock.sentinel.pipe
        self.helper.barcode_ = "PRODUCT-1"
        self.helper.initial_weight_ = 100
        self.helper.specific_weight_ = 1.2
        self.helper.run = mock.Mock()

        self.helper._continue_refill()

        self.assertIsNone(self.helper.machine_)
        self.assertIsNone(self.helper.pigment_)
        self.assertIsNone(self.helper.pipe_)
        self.assertIsNone(self.helper.barcode_)
        self.assertIsNone(self.helper.initial_weight_)
        self.assertIsNone(self.helper.specific_weight_)
        self.helper.run.assert_called_once_with()


class TestInputDialogAction(unittest.TestCase):
    def test_action_callback_is_scheduled_only_once(self):
        callback = mock.Mock()
        dialog = mock.Mock()
        setattr(dialog, "_InputDialog__action_cb", callback)
        setattr(dialog, "_InputDialog__action_cb_args", ["value"])
        loop = mock.Mock()

        with mock.patch.object(
                dialogs_module.asyncio, "get_event_loop", return_value=loop):
            InputDialog.on_action_button_clicked(dialog)
            InputDialog.on_action_button_clicked(dialog)

        loop.call_later.assert_called_once()
        delay, scheduled = loop.call_later.call_args.args
        self.assertEqual(.05, delay)
        scheduled()
        callback.assert_called_once_with("value")

    def test_action_button_is_equidistant_and_has_no_icon(self):
        ui_path = (
            Path(__file__).parents[1]
            / "alfa_CR6_frontend" / "ui" / "input_dialog.ui")
        root = ElementTree.parse(str(ui_path)).getroot()

        geometries = {}
        action_widget = None
        for widget in root.iter("widget"):
            name = widget.get("name")
            if name not in ("esc_button", "action_button", "ok_button"):
                continue
            rect = widget.find("./property[@name='geometry']/rect")
            geometries[name] = {
                key: int(rect.find(key).text)
                for key in ("x", "width")
            }
            if name == "action_button":
                action_widget = widget

        cancel = geometries["esc_button"]
        action = geometries["action_button"]
        ok = geometries["ok_button"]
        left_gap = action["x"] - (cancel["x"] + cancel["width"])
        right_gap = ok["x"] - (action["x"] + action["width"])

        self.assertEqual(left_gap, right_gap)
        self.assertIsNone(action_widget.find("./property[@name='icon']"))


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
