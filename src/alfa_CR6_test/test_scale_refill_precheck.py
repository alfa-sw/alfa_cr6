"""Hardware-free checks for the scale-refill connection precondition."""

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
        self.assertEqual(
            globals_module.get_res("IMAGE", "refill_scale_warn_unplugged.png"),
            dialog["message_image"])
        self.assertIsNone(dialog["content"])

    def test_connected_unresponsive_scale_shows_power_warning(self):
        with mock.patch.object(home_page, "get_scale_connection_state",
                               return_value="not_responding"), \
                mock.patch.object(home_page, "tr_", side_effect=lambda value: value):
            self.helper.run()

        dialog = self.main_window.dialogs[0]
        self.assertEqual("SP_MessageBoxWarning", dialog["icon_name"])
        self.assertIn("Check that it is switched on", dialog["message"])
        self.assertEqual(
            globals_module.get_res("IMAGE", "refill_scale_warn_off.png"),
            dialog["message_image"])
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
