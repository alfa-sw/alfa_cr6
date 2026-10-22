# coding: utf-8

"""Regression tests for the home and debug carousel-unlock controls."""

import types
import unittest
from unittest import mock

import alfa_CR6_frontend.debug_page as debug_page_module
import alfa_CR6_frontend.home_page as home_page_module
import alfa_CR6_frontend.main_window as main_window_module


class TestDebugPageUnfreeze(unittest.TestCase):

    def test_main_window_gates_home_button_during_autorecovery(self):
        button = mock.Mock()
        reason = "Autoripristino in corso: teste A, F."
        window = types.SimpleNamespace(
            home_page=types.SimpleNamespace(
                freeze_carousel_btn=button,
            )
        )

        main_window_module.MainWindow.set_carousel_freeze_control_enabled(
            window, False, reason
        )
        main_window_module.MainWindow.set_carousel_freeze_control_enabled(
            window, True
        )

        self.assertEqual(
            button.setEnabled.call_args_list,
            [mock.call(False), mock.call(True)],
        )
        self.assertEqual(
            button.setToolTip.call_args_list,
            [mock.call(reason), mock.call("")],
        )

    def test_unfreeze_button_unlocks_carousel(self):
        app = types.SimpleNamespace(freeze_carousel=mock.Mock())
        page = object.__new__(debug_page_module.DebugPage)
        page.update_status = mock.Mock()
        button = types.SimpleNamespace(text=lambda: "unfreeze\ncarousel")

        with mock.patch.object(
                debug_page_module.QApplication, "instance", return_value=app):
            page.on_button_group_clicked(button)

        app.freeze_carousel.assert_called_once_with(False, force=True)
        page.update_status.assert_called_once_with()

    def test_home_button_offers_unlock_after_autorecovery(self):
        app = types.SimpleNamespace(
            carousel_frozen=True,
            machine_head_dict={},
            toggle_freeze_carousel=mock.Mock(),
        )
        page = types.SimpleNamespace(
            main_window=types.SimpleNamespace(open_input_dialog=mock.Mock())
        )
        button = types.SimpleNamespace(
            objectName=lambda: "freeze_carousel_btn"
        )

        with mock.patch.object(
                home_page_module.QApplication, "instance", return_value=app):
            home_page_module.HomePage.on_action_btn_group_clicked(page, button)

        call = page.main_window.open_input_dialog.call_args
        self.assertIs(call.kwargs["ok_cb"], app.toggle_freeze_carousel)
        self.assertEqual(
            call.kwargs["message"],
            home_page_module.tr_("confirm unfreezing carousel?"),
        )


if __name__ == "__main__":
    unittest.main()
