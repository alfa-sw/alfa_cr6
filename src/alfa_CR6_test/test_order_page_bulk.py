# coding: utf-8
"""Check the Order page's bulk conversion and print request without hardware."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget

from alfa_CR6_frontend import pages


class MainWindowStub(QMainWindow):

    def __init__(self):
        super().__init__()
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)
        self.confirmation = None
        self.alerts = []

    def open_alias_dialog(self):
        pass

    def open_input_dialog(self, **kwargs):
        self.confirmation = kwargs

    def open_alert_dialog(self, args, **kwargs):
        self.alerts.append((args, kwargs))


class OrderPageBulkTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_button_visibility_requires_both_settings(self):
        app = self.app
        old_main_window = getattr(app, "main_window", None)
        old_db_session = getattr(app, "db_session", None)
        try:
            with tempfile.TemporaryDirectory() as folder, \
                    patch.object(pages.g_settings, "WEBENGINE_DOWNLOAD_PATH", folder):
                with open(os.path.join(folder, "order.json"), "w") as stream:
                    stream.write("{}")
                window = MainWindowStub()
                app.main_window = window
                app.db_session = None
                with patch.object(pages.g_settings, "ENABLE_BTN_CREATE_ALL_ORDERS", False, create=True), \
                        patch.object(pages.g_settings, "FORCE_ORDER_JAR_TO_ONE", True, create=True):
                    page = pages.OrderPage(parent=window)
                    self.assertTrue(page.create_all_orders_btn.isHidden())
                    self.assertEqual(page.search_file_line.width(), 461)
                    pages.g_settings.ENABLE_BTN_CREATE_ALL_ORDERS = True
                    pages.g_settings.FORCE_ORDER_JAR_TO_ONE = False
                    page.toggle_order_and_purge_btns()
                    self.assertTrue(page.create_all_orders_btn.isHidden())
                    pages.g_settings.FORCE_ORDER_JAR_TO_ONE = True
                    page.toggle_order_and_purge_btns()
                    self.assertFalse(page.create_all_orders_btn.isHidden())
                    self.assertEqual(page.search_file_line.width(), 331)
                    page.deleteLater()
                window.deleteLater()
        finally:
            app.main_window = old_main_window
            app.db_session = old_db_session

    def test_converts_entire_queue_and_submits_one_print_job_in_both_modes(self):
        app = self.app
        old_main_window = getattr(app, "main_window", None)
        old_db_session = getattr(app, "db_session", None)
        old_convert = getattr(app, "create_orders_from_file", None)
        try:
            for in_docker in ("0", "1"):
                with self.subTest(in_docker=in_docker), tempfile.TemporaryDirectory() as folder:
                    for index in range(51):
                        with open(os.path.join(folder, "order_{:02}.json".format(index)), "w") as stream:
                            stream.write("{}")
                    with open(os.path.join(folder, "bad.json"), "w") as stream:
                        stream.write("bad")
                    os.mkdir(os.path.join(folder, "subdirectory"))

                    window = MainWindowStub()
                    app.main_window = window
                    app.db_session = None
                    converted = []
                    printed = []

                    def convert(path, n_of_jars, silent):
                        self.assertEqual(n_of_jars, 1)
                        self.assertTrue(silent)
                        converted.append(os.path.basename(path))
                        if path.endswith("bad.json"):
                            return []
                        barcode = os.path.basename(path)
                        return [SimpleNamespace(jars=[SimpleNamespace(barcode=barcode)])]

                    def submit_print(jars):
                        printed.append(list(jars))
                        async def done():
                            return {"result": "OK"}
                        return done()

                    def schedule(coroutine):
                        coroutine.close()

                    app.create_orders_from_file = convert
                    with patch.dict(os.environ, {"IN_DOCKER": in_docker}), \
                            patch.object(pages.g_settings, "WEBENGINE_DOWNLOAD_PATH", folder), \
                            patch.object(pages.g_settings, "ENABLE_BTN_CREATE_ALL_ORDERS", True, create=True), \
                            patch.object(pages.g_settings, "FORCE_ORDER_JAR_TO_ONE", True, create=True), \
                            patch.object(pages, "async_dymo_print_jars", submit_print), \
                            patch.object(pages.asyncio, "ensure_future", schedule):
                        page = pages.OrderPage(parent=window)
                        button = page.create_all_orders_btn
                        self.assertFalse(button.isHidden())
                        self.assertEqual(button.text(), "ALL")
                        self.assertFalse(button.icon().isNull())
                        page.search_file_line.setText("bad")
                        page.populate_file_table()
                        page.create_all_orders_btn.click()
                        self.assertEqual(len(converted), 0)
                        self.assertEqual(len(window.confirmation["ok_cb_args"][0]), 52)
                        self.assertEqual(len(window.confirmation["message"].splitlines()), 3)
                        window.confirmation["ok_cb"](*window.confirmation["ok_cb_args"])

                        self.assertEqual(len(converted), 52)
                        self.assertEqual(len(printed), 1)
                        self.assertEqual(len(printed[0]), 51)
                        self.assertEqual(set(os.listdir(folder)), {"bad.json", "subdirectory"})
                        self.assertEqual(window.alerts[-1][0], (51, 51, 1))
                        self.assertEqual(len(window.alerts[-1][1]["fmt"].splitlines()), 3)
                        self.assertEqual(page.file_model.rowCount(), 1)
                        page.deleteLater()
                    window.deleteLater()
        finally:
            app.main_window = old_main_window
            app.db_session = old_db_session
            if old_convert is None:
                del app.create_orders_from_file
            else:
                app.create_orders_from_file = old_convert


if __name__ == "__main__":
    unittest.main()
