"""Hardware-free checks for the scale-refill connection precondition."""

import asyncio
import importlib
import json
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from unittest import mock

from PyQt5.QtGui import QFontInfo, QPixmap
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton, QWidget

from alfa_CR6_backend import globals as globals_module
from alfa_CR6_frontend import dialogs as dialogs_module, home_page
from alfa_CR6_frontend.dialogs import InputDialog, RefillDialog
from alfa_CR6_test.alfa_cr6_refill_popup_preview import (
    AVAILABLE_LANGUAGES, PopupGallery, main_window_stylesheet,
)


class TestInputDialogLargeMessageFonts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.parent = QWidget()
        self.parent.setStyleSheet(main_window_stylesheet())
        self.dialog = InputDialog(self.parent)

    def tearDown(self):
        self.parent.close()
        self.parent.deleteLater()
        self.app.processEvents()

    def _show(self, large):
        self.dialog.show_dialog(
            message="Refill instructions", content="Scan the barcode",
            large_message_layout=large)
        self.app.processEvents()

    def _assert_input_font_sizes(self, pixel_size):
        for widget in (self.dialog.message_label, self.dialog.content_container):
            self.assertEqual(QFontInfo(widget.font()).pixelSize(), pixel_size)
        self.assertEqual(
            QFontInfo(self.dialog.content_container.document().defaultFont())
            .pixelSize(), pixel_size)

    def test_large_fonts_override_the_main_window_stylesheet(self):
        self._show(False)
        self._assert_input_font_sizes(24)

        self._show(True)
        self._assert_input_font_sizes(34)
        self.assertEqual(QFontInfo(self.dialog.ok_button.font()).pixelSize(), 24)
        self.assertEqual(self.dialog.message_label.height(), 281)

    def test_reusing_the_dialog_restores_fonts_without_cumulative_scaling(self):
        for large in (True, True, False, True, False):
            self._show(large)
            self._assert_input_font_sizes(34 if large else 24)
            self.assertEqual(
                self.dialog.message_label.height(), 281 if large else 175)
            self.assertEqual(self.dialog.message_label.wordWrap(), large)

    def test_large_result_wraps_the_complete_overflow_message(self):
        self.dialog.show_dialog(
            message=(
                "Quantità rabboccata: 742.35 g<br>"
                "livelli aggiornati: B01: 1000.0 (cc)<br>"
                "Il livello registrato è stato limitato al massimo configurato.<br>"
                "Eseguire il RESET della testa A?"),
            content=None, large_message_layout=True)
        self.app.processEvents()
        label = self.dialog.message_label
        self.assertTrue(label.wordWrap())
        self.assertLessEqual(label.heightForWidth(label.width()), label.height())

    def test_point_fonts_without_a_parent_stylesheet_are_also_scaled(self):
        self.parent.setStyleSheet("")
        dialog = InputDialog(self.parent)
        dialog.show_dialog(message="Instructions", content="Barcode")
        self.app.processEvents()
        standard_sizes = {
            widget: QFontInfo(widget.font()).pixelSize()
            for widget in (dialog.message_label, dialog.content_container)
        }

        dialog.show_dialog(
            message="Instructions", content="Barcode", large_message_layout=True)
        self.app.processEvents()
        for widget, size in standard_sizes.items():
            self.assertEqual(
                QFontInfo(widget.font()).pixelSize(), round(size * 1.40))

        dialog.show_dialog(message="Instructions", content="Barcode")
        self.app.processEvents()
        for widget, size in standard_sizes.items():
            self.assertEqual(QFontInfo(widget.font()).pixelSize(), size)

    def test_message_image_keeps_its_proportions_and_barcode_validation(self):
        image_path = globals_module.get_res("IMAGE", "refill_scale_can_full.png")
        original = QPixmap(image_path)
        self.assertFalse(original.isNull())
        for large in (False, True):
            self.dialog.show_dialog(
                message="Place the canister on the scale.<br>Scan its barcode.",
                content="", ok_requires_content=True,
                large_message_layout=large, message_image=image_path)
            self.app.processEvents()
            image = self.dialog.message_image_label
            pixmap = image.pixmap()
            self.assertFalse(image.isHidden())
            self.assertLess(pixmap.height(), original.height())
            self.assertLessEqual(
                abs(pixmap.width() - pixmap.height()
                    * original.width() / original.height()), 1)
            self.assertFalse(
                self.dialog.message_label.geometry().intersects(image.geometry()))
            self.assertFalse(
                self.dialog.content_container.geometry().intersects(image.geometry()))
            self.assertGreaterEqual(
                image.y(), self.dialog.ok_button.y() + self.dialog.ok_button.height())
            self.assertGreaterEqual(
                self.dialog.content_container.y(), image.y() + image.height())
            self.assertLessEqual(
                self.dialog.message_label.heightForWidth(
                    self.dialog.message_label.width()),
                self.dialog.message_label.height())
            self.assertFalse(self.dialog.ok_button.isEnabled())
            self.dialog.content_container.setPlainText("123456789")
            self.assertTrue(self.dialog.ok_button.isEnabled())

    def test_next_popup_removes_the_image_and_restores_input_position(self):
        original_content_y = self.dialog.content_container.y()
        self.dialog.show_dialog(
            message="Instructions", content="", large_message_layout=True,
            message_image=globals_module.get_res("IMAGE", "refill_scale_can_full.png"))
        self.app.processEvents()
        self.assertFalse(self.dialog.message_image_label.isHidden())

        self.dialog.show_dialog(message="Error", content=None)
        self.app.processEvents()
        self.assertTrue(self.dialog.message_image_label.isHidden())
        self.assertEqual(self.dialog.content_container.y(), original_content_y)
        self.assertEqual(self.dialog.message_label.contentsMargins().left(), 0)
        self.assertFalse(self.dialog.message_label.wordWrap())


class TestRefillPopupPreviewModes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        settings = globals_module.import_settings()
        self.addCleanup(setattr, settings, "LANGUAGE", settings.LANGUAGE)
        self.gallery = PopupGallery(large=True, initial_id="S12", language="it")
        self.gallery.show()
        self.app.processEvents()

    def tearDown(self):
        self.gallery.close()
        self.gallery.deleteLater()
        self.app.processEvents()

    def _select(self, popup_id):
        index = next(i for i, spec in enumerate(self.gallery.specs)
                     if spec["id"] == popup_id)
        self.gallery.selector.setCurrentIndex(index)
        self.app.processEvents()

    def _manual(self):
        self.gallery.mode_selector.setCurrentIndex(
            self.gallery.mode_selector.findData("manual"))
        self.app.processEvents()

    def test_mode_switch_replaces_the_flow_and_restores_the_scale_layout(self):
        self._manual()
        self.assertEqual(self.gallery.specs[0]["id"], "M01")
        self.assertTrue(all(spec["id"].startswith("M") for spec in self.gallery.specs))
        self.assertEqual(self.gallery.selector.count(), 14)
        self.assertFalse(self.gallery.large_checkbox.isEnabled())
        self.assertEqual(self.gallery.dialog.message_label.height(), 175)
        self.assertEqual(QFontInfo(self.gallery.dialog.message_label.font()).pixelSize(), 24)

        self.gallery.mode_selector.setCurrentIndex(
            self.gallery.mode_selector.findData("scale"))
        self.app.processEvents()
        self.assertEqual(self.gallery.selector.count(), 21)
        self.assertTrue(all(spec["id"].startswith("S") for spec in self.gallery.specs))
        self.assertTrue(self.gallery.large_checkbox.isEnabled())
        self.assertEqual(self.gallery.dialog.message_label.height(), 281)
        self.assertEqual(QFontInfo(self.gallery.dialog.message_label.font()).pixelSize(), 34)

    def test_manual_quantity_buttons_and_alert_navigation_remain_interactive(self):
        self._manual()
        self._select("M06")
        self.assertIsInstance(self.gallery.dialog, RefillDialog)
        self.gallery.dialog.findChild(QPushButton, "refill_choice_1").click()
        self.assertEqual(float(self.gallery.dialog.get_content_text()), 750.0)
        self.gallery.dialog.ok_button.click()
        self.app.processEvents()
        self.assertEqual(self.gallery.specs[self.gallery.selector.currentIndex()]["id"], "M07")
        self.assertTrue(self.gallery.dialog.isVisible())

        self._select("M02")
        self.assertIsInstance(self.gallery.dialog, QMessageBox)
        self.assertIsNone(QApplication.activeModalWidget())
        self.assertFalse(self.gallery.dialog.button(QMessageBox.Cancel).isEnabled())
        self.gallery.dialog.button(QMessageBox.Ok).click()
        self.app.processEvents()
        self.assertEqual(self.gallery.specs[self.gallery.selector.currentIndex()]["id"], "M03")
        self.assertTrue(self.gallery.dialog.isVisible())

    def test_language_change_keeps_the_manual_popup_selected(self):
        self._manual()
        self._select("M06")
        italian_text = self.gallery.dialog.message_label.text()
        self.gallery.language_selector.setCurrentIndex(
            self.gallery.language_selector.findData("en"))
        self.app.processEvents()
        self.assertEqual(self.gallery.mode, "manual")
        self.assertEqual(self.gallery.specs[self.gallery.selector.currentIndex()]["id"], "M06")
        self.assertNotEqual(self.gallery.dialog.message_label.text(), italian_text)
        self.assertIn("please, input quantity", self.gallery.dialog.message_label.text())

    def test_manual_circuit_selection_is_localized_in_every_supported_translation(self):
        self._manual()
        self._select("M03")
        for language in sorted(set(AVAILABLE_LANGUAGES) - {"en", "kr"}):
            with self.subTest(language=language):
                self.gallery.language_selector.setCurrentIndex(
                    self.gallery.language_selector.findData(language))
                self.app.processEvents()
                dialog = self.gallery.dialog
                self.assertNotEqual(
                    dialog.message_label.text(), "Multiple circuits found for Rosso")
                self.assertNotEqual(dialog.get_content_text(), "Choose circuit to refill:")
                self.assertNotIn("level", dialog.combo_box.itemText(0))
                self.assertEqual(dialog.get_selected_choice(), "B01")
                dialog.combo_box.setCurrentIndex(1)
                self.assertEqual(dialog.get_selected_choice(), "B02")


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

    def hide_input_dialog(self):
        pass


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
        self.helper._is_active = mock.Mock(return_value=True)
        self.machine = mock.Mock(last_answer={}, machine_config={})
        self.machine.name = "A"
        self.machine.check_scale_connection = mock.AsyncMock(return_value=True)
        self.machine.read_stable_weight = mock.AsyncMock(return_value=100.)
        self.machine.send_command = mock.AsyncMock(return_value=True)
        self.loop = asyncio.new_event_loop()
        self.addCleanup(self.loop.close)

    def _run_start(self):
        app = mock.Mock(machine_head_dict={self.helper.head_index: self.machine})
        with mock.patch.object(home_page.QApplication, "instance", return_value=app), \
                mock.patch.object(home_page.asyncio, "ensure_future",
                                  side_effect=self.loop.run_until_complete):
            self.helper.run()

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
        self.assertEqual(
            globals_module.get_res("IMAGE", "refill_scale_warn_unplugged.png"),
            dialog["message_image"])
        self.assertIsNone(dialog["content"])

    def test_connected_unresponsive_scale_shows_power_warning(self):
        self.machine.check_scale_connection.return_value = False
        with mock.patch.object(home_page, "get_scale_connection_state",
                               return_value="not_responding"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self._run_start()

        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxWarning", dialog["icon_name"])
        self.assertIn("Check that it is switched on", dialog["message"])
        self.assertIn("at the back of the scale", dialog["message"])
        self.assertNotIn("Refill procedure interrupted.", dialog["message"])
        self.assertEqual(
            globals_module.get_res("IMAGE", "refill_scale_warn_off.png"),
            dialog["message_image"])
        self.assertIsNone(dialog["content"])

    def test_ready_scale_opens_first_instruction(self):
        with mock.patch.object(home_page, "get_scale_connection_state",
                               return_value="ready"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self._run_start()

        self.assertEqual(1, len(self.main_window.dialogs))
        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxQuestion", dialog["icon_name"])
        self.assertIn("Place the open canister", dialog["message"])
        self.assertEqual("", dialog["content"])
        self.assertIs(dialog["ok_requires_content"], True)

    def test_stale_ready_status_does_not_skip_the_real_check(self):
        self.machine.check_scale_connection.return_value = False
        with mock.patch.object(home_page, "get_scale_connection_state", return_value="ready"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self._run_start()
        self.machine.check_scale_connection.assert_awaited_once()
        self.assertIn("not responding", self.main_window.dialogs[0]["message"])

    def test_scale_can_recover_from_previous_communication_failure(self):
        with mock.patch.object(home_page, "get_scale_connection_state", return_value="not_responding"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self._run_start()
        self.assertIn("Place the open canister", self.main_window.dialogs[0]["message"])

    def test_usb_loss_in_fresh_answer_uses_s20_despite_stale_status(self):
        self.machine.check_scale_connection.return_value = False
        self.machine.last_answer = {"connected": False}
        with mock.patch.object(home_page, "get_scale_connection_state", return_value="ready"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self._run_start()
        self.assertIn("No scale was detected", self.main_window.dialogs[0]["message"])

    def test_checks_before_each_weight_and_stops_on_lost_communication(self):
        for stage in ("initial", "final"):
            for responding in (True, False):
                with self.subTest(stage=stage, responding=responding):
                    self.main_window.dialogs.clear()
                    self.machine.reset_mock()
                    self.machine.check_scale_connection.return_value = responding
                    self.helper.machine_ = self.machine
                    self.helper.initial_weight_ = 200.
                    self.helper.specific_weight_ = 1.
                    self.helper.pipe_ = {"name": "B01"}
                    self.helper._log_refill = mock.Mock()
                    task = (self.helper._prepare_target(self.machine, {}, {"name": "B01"})
                            if stage == "initial" else self.helper._complete_refill())
                    with mock.patch.object(home_page, "get_scale_connection_state", return_value="ready"), \
                            mock.patch.object(home_page, "tr_", side_effect=lambda value: value), \
                            mock.patch.object(self.helper, "_head_refill_error", return_value=None):
                        self.loop.run_until_complete(task)
                    calls = [call[0] for call in self.machine.mock_calls]
                    self.assertEqual(calls[0], "check_scale_connection")
                    if responding:
                        self.assertEqual(calls[1], "read_stable_weight")
                        self.machine.send_command.assert_awaited_once()
                    else:
                        self.machine.read_stable_weight.assert_not_awaited()
                        self.machine.send_command.assert_not_awaited()
                        self._assert_attempt_cancelled()

    def _assert_attempt_cancelled(self, disconnected=False):
        dialog = self.main_window.dialogs[-1]
        self.assertIn("No scale was detected" if disconnected else "not responding",
                      dialog["message"])
        self.assertTrue(dialog["message"].endswith("<br>Refill procedure interrupted."))
        self.assertEqual("SP_MessageBoxWarning", dialog["icon_name"])
        self.assertEqual(globals_module.get_res(
            "IMAGE", "refill_scale_warn_unplugged.png" if disconnected
            else "refill_scale_warn_off.png"), dialog["message_image"])
        self.assertEqual(self.helper._finish, dialog["ok_cb"])

    def test_usb_loss_during_procedure_shows_s20_and_cancels_the_attempt(self):
        for stage in ("initial", "final"):
            for state, answer in (("disconnected", {}),
                                  ("ready", {"connected": False})):
                with self.subTest(stage=stage, state=state):
                    self.main_window.dialogs.clear()
                    self.machine.reset_mock()
                    self.machine.last_answer = answer
                    self.machine.check_scale_connection.return_value = False
                    self.helper.machine_ = self.machine
                    self.helper.barcode_ = "PRODUCT-1"
                    self.helper.initial_weight_ = 200.
                    self.helper.specific_weight_ = 1.
                    self.helper.pipe_ = {"name": "B01"}
                    task = (self.helper._prepare_target(self.machine, {}, {"name": "B01"})
                            if stage == "initial" else self.helper._complete_refill())
                    with mock.patch.object(home_page, "get_scale_connection_state",
                                           return_value=state), \
                            mock.patch.object(home_page, "tr_", side_effect=lambda value: value), \
                            mock.patch.object(self.helper, "_head_refill_error", return_value=None):
                        self.loop.run_until_complete(task)
                    if state == "disconnected":
                        self.machine.check_scale_connection.assert_not_awaited()
                    else:
                        self.machine.check_scale_connection.assert_awaited_once()
                    self.machine.read_stable_weight.assert_not_awaited()
                    self.machine.send_command.assert_not_awaited()
                    self._assert_attempt_cancelled(disconnected=True)

    def test_closing_the_warning_ends_the_attempt(self):
        app = mock.Mock(barcode_read_blocked_on_refill=True)
        self.helper.parent.scale_refill_helper = self.helper
        with mock.patch.object(home_page, "get_scale_connection_state",
                               return_value="disconnected"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value), \
                mock.patch.object(home_page.QApplication, "instance", return_value=app):
            self.loop.run_until_complete(self.helper._check_scale(
                self.machine, in_progress=True))
            self.main_window.dialogs[-1]["ok_cb"]()
        self.assertIsNone(self.helper.parent.scale_refill_helper)
        self.assertIs(app.barcode_read_blocked_on_refill, False)
        self.machine.read_stable_weight.assert_not_awaited()
        self.machine.send_command.assert_not_awaited()

    def test_failure_before_s01_keeps_the_scale_warnings(self):
        self.machine.check_scale_connection.return_value = False
        with mock.patch.object(home_page, "get_scale_connection_state", return_value="ready"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self._run_start()
        dialog = self.main_window.dialogs[-1]
        self.assertEqual("SP_MessageBoxWarning", dialog["icon_name"])
        self.assertNotIn("Refill procedure interrupted.", dialog["message"])

    def test_scale_warning_messages_are_translated_except_korean(self):
        lemmas = (
            "No scale was detected.<br>"
            "Check the communication cable connection at the back of the scale<br>"
            "or the USB cable connection to the machine.",
            "The scale is not responding.<br>"
            "Check that it is switched on and that the communication cable<br>"
            "is properly connected at the back of the scale.",
            "Refill procedure interrupted.",
        )
        for code in sorted(AVAILABLE_LANGUAGES):
            module = importlib.import_module("alfa_CR6_backend.lang.{}".format(code))
            for lemma in lemmas:
                with self.subTest(language=code, message=lemma):
                    if code == "kr":
                        self.assertNotIn(lemma, module.D)
                        continue
                    self.assertIn(lemma, module.D)
                    if code != "en":
                        self.assertNotEqual(lemma, module.D[lemma])

    def test_unstable_reading_still_uses_s07(self):
        self.machine.read_stable_weight.return_value = None
        with mock.patch.object(home_page, "get_scale_connection_state", return_value="ready"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value), \
                mock.patch.object(self.helper, "_head_refill_error", return_value=None):
            self.loop.run_until_complete(self.helper._prepare_target(
                self.machine, {}, {"name": "B01"}))
        self.assertIn("Unable to read a stable weight", self.main_window.dialogs[-1]["message"])
        self.machine.send_command.assert_not_awaited()

    def test_cancelled_procedure_does_not_continue_after_probe(self):
        self.helper._is_active.side_effect = [True, False]
        with mock.patch.object(home_page, "get_scale_connection_state", return_value="ready"), \
                mock.patch.object(self.helper, "_head_refill_error", return_value=None):
            self.loop.run_until_complete(self.helper._prepare_target(
                self.machine, {}, {"name": "B01"}))
        self.machine.read_stable_weight.assert_not_awaited()
        self.assertEqual([], self.main_window.dialogs)

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
        machine.status = {"status_level": "STANDBY", "crx_outputs_status": 0}
        pigment["pipes"].append(pipe)
        machine.pigment_list = [pigment]
        app = mock.Mock(machine_head_dict={0: machine}, carousel_frozen=True)
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


class TestScaleRefillTargetReadiness(unittest.TestCase):
    def setUp(self):
        self.main_window = _MainWindow()
        self.helper = home_page.ScaleRefillProcedureHelper(
            mock.Mock(main_window=self.main_window))
        self.helper._dialog_barcode = mock.Mock(return_value="PRODUCT-1")
        self.helper._start_target = mock.Mock()
        self.app = mock.Mock(machine_head_dict={}, carousel_frozen=True)
        app_patch = mock.patch.object(
            home_page.QApplication, "instance", return_value=self.app)
        app_patch.start()
        self.addCleanup(app_patch.stop)
        tr_patch = mock.patch.object(home_page, "tr_", side_effect=lambda value: value)
        tr_patch.start()
        self.addCleanup(tr_patch.stop)

    def _head(self, name, status="STANDBY", outputs=0, circuits=("B01",)):
        pigment = {
            "customer_id": "PRODUCT-1", "name": "Red", "specific_weight": 1.2,
            "pipes": [{"name": circuit, "enabled": True, "sync": True}
                      for circuit in circuits],
        }
        machine = mock.Mock(
            status={"status_level": status, "crx_outputs_status": outputs},
            pigment_list=[pigment])
        machine.name = name
        self.app.machine_head_dict[name] = machine
        return machine

    def test_alarm_head_is_reported_before_circuit_selection(self):
        self._head("A", status="ALARM", circuits=("C01", "C02"))

        self.helper._on_initial_barcode()

        self.assertEqual(len(self.main_window.dialogs), 1)
        self.assertEqual(self.main_window.dialogs[0]["message"],
                         "Head A is not ready for refill.")
        self.assertNotIn("choices", self.main_window.dialogs[0])
        self.helper._start_target.assert_not_called()

    def test_active_outputs_are_reported_immediately_after_s01(self):
        self._head("A", outputs=1)

        self.helper._on_initial_barcode()

        self.assertEqual(self.main_window.dialogs[0]["message"],
                         "Head A has an operation in progress.")
        self.helper._start_target.assert_not_called()

    def test_resumed_carousel_is_reported_before_circuit_selection(self):
        self._head("A", circuits=("C01", "C02"))
        self.app.carousel_frozen = False

        self.helper._on_initial_barcode()

        self.assertEqual(self.main_window.dialogs[0]["message"],
                         "Pause the carousel before starting the refill.")
        self.helper._start_target.assert_not_called()

    def test_selector_only_offers_circuits_of_ready_heads(self):
        self._head("A", status="ALARM", circuits=("C01", "C02"))
        standby = self._head("B", circuits=("B01", "B02"))
        diagnostic = self._head("C", status="DIAGNOSTIC", circuits=("C03",))

        self.helper._on_initial_barcode()

        choices = self.main_window.dialogs[0]["choices"]
        self.assertEqual([(target[0].name, target[2]["name"])
                          for target in choices.values()],
                         [(standby.name, "B01"), (standby.name, "B02"),
                          (diagnostic.name, "C03")])
        self.helper._start_target.assert_not_called()

    def test_single_ready_target_skips_selector_when_other_head_is_in_alarm(self):
        self._head("A", status="ALARM")
        ready = self._head("B")

        self.helper._on_initial_barcode()

        self.assertEqual(self.main_window.dialogs, [])
        self.helper._start_target.assert_called_once_with(
            ready, ready.pigment_list[0], ready.pigment_list[0]["pipes"][0])

    def test_state_change_after_selector_is_still_caught_before_weighing(self):
        machine = self._head("A", circuits=("B01", "B02"))
        machine.check_scale_connection = mock.AsyncMock()
        machine.read_stable_weight = mock.AsyncMock()
        self.helper._on_initial_barcode()
        machine.status["status_level"] = "ALARM"

        asyncio.run(self.helper._prepare_target(
            machine, machine.pigment_list[0], machine.pigment_list[0]["pipes"][0]))

        self.assertEqual(self.main_window.dialogs[-1]["message"],
                         "Head A is not ready for refill.")
        machine.check_scale_connection.assert_not_awaited()
        machine.read_stable_weight.assert_not_awaited()

    def test_unknown_barcode_keeps_the_product_not_found_message(self):
        self._head("A", status="ALARM")
        self.helper._dialog_barcode.return_value = "UNKNOWN"

        self.helper._on_initial_barcode()

        self.assertIn("does not match", self.main_window.dialogs[0]["message"])
        self.helper._start_target.assert_not_called()


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
