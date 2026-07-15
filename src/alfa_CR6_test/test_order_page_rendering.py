# coding: utf-8

"""Regression tests for the Order page header and decoration caches."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QStandardItemModel
from PyQt5.QtWidgets import (
    QApplication,
    QHeaderView,
    QMainWindow,
    QStackedWidget,
    QTableView,
    QWidget,
)

from alfa_CR6_frontend.pages import (
    BaseTableModel,
    FileTableModel,
    ORDER_PAGE_FIXED_COLUMN_WIDTHS,
    ORDER_PAGE_COLUMNS_ORDERS,
    OrderPage,
    _configure_order_table_header,
)


class MainWindowStub(QMainWindow):

    def __init__(self):
        super().__init__()
        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

    def open_alias_dialog(self):
        pass


class OrderPageRenderingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if not hasattr(cls.app, "main_window"):
            cls.app.main_window = QWidget()

    def test_header_widths_follow_column_names_after_reordering(self):
        columns = ["file name", "status", "delete", "order nr.", "edit"]
        table = QTableView()
        table.setModel(QStandardItemModel(0, len(columns), table))

        _configure_order_table_header(table, columns)

        header = table.horizontalHeader()
        self.assertFalse(header.stretchLastSection())
        for section, column_name in enumerate(columns):
            expected_width = ORDER_PAGE_FIXED_COLUMN_WIDTHS.get(column_name)
            if expected_width is None:
                self.assertEqual(header.sectionResizeMode(section), QHeaderView.Stretch)
            else:
                self.assertEqual(header.sectionResizeMode(section), QHeaderView.Fixed)
                self.assertEqual(header.sectionSize(section), expected_width)

        table.deleteLater()

    def test_models_share_pre_scaled_page_icons(self):
        page = QWidget()
        first_model = BaseTableModel(page)
        second_model = BaseTableModel(page)

        self.assertIs(first_model.gray_icon, second_model.gray_icon)
        self.assertIs(first_model.edit_icon, second_model.edit_icon)
        self.assertIs(first_model.barcode_C128_icon, second_model.barcode_C128_icon)
        self.assertIs(first_model.delete_icon, second_model.delete_icon)
        self.assertEqual(first_model.gray_icon.size().width(), 32)
        self.assertEqual(first_model.gray_icon.size().height(), 32)
        self.assertEqual(first_model.edit_icon.size().width(), 32)
        self.assertLessEqual(first_model.barcode_C128_icon.size().width(), 80)
        self.assertLessEqual(first_model.barcode_C128_icon.size().height(), 160)

        page.deleteLater()

    def test_real_order_page_configures_header_only_after_model_install(self):
        app = QApplication.instance()
        previous_main_window = app.main_window
        previous_db_session = getattr(app, "db_session", None)
        main_window = MainWindowStub()
        app.main_window = main_window
        app.db_session = None

        try:
            page = OrderPage(parent=main_window)
            header = page.order_table_view.horizontalHeader()
            self.assertIsNone(page.order_table_view.model())

            page.populate_order_table()

            for section, column_name in enumerate(ORDER_PAGE_COLUMNS_ORDERS["order"]):
                expected_width = ORDER_PAGE_FIXED_COLUMN_WIDTHS.get(column_name)
                if expected_width is None:
                    self.assertEqual(header.sectionResizeMode(section), QHeaderView.Stretch)
                else:
                    self.assertEqual(header.sectionResizeMode(section), QHeaderView.Fixed)
                    self.assertEqual(header.sectionSize(section), expected_width)
        finally:
            app.main_window = previous_main_window
            app.db_session = previous_db_session
            main_window.deleteLater()

    def test_empty_models_keep_headers_without_paint_tracebacks(self):
        app = QApplication.instance()
        previous_main_window = app.main_window
        previous_db_session = getattr(app, "db_session", None)
        main_window = MainWindowStub()
        app.main_window = main_window
        app.db_session = None

        try:
            page = OrderPage(parent=main_window)
            page.populate_order_table()
            page.populate_jar_table()

            with tempfile.TemporaryDirectory() as download_path:
                page.file_model = FileTableModel(page, download_path)
                page.file_table_view.setModel(page.file_model)
                _configure_order_table_header(
                    page.file_table_view,
                    ORDER_PAGE_COLUMNS_ORDERS["file"])

                models = (
                    (page.order_model, ORDER_PAGE_COLUMNS_ORDERS["order"]),
                    (page.jar_model, ORDER_PAGE_COLUMNS_ORDERS["can"]),
                    (page.file_model, ORDER_PAGE_COLUMNS_ORDERS["file"]),
                )
                valid_parent = QStandardItemModel(1, 1).index(0, 0)
                for model, columns in models:
                    self.assertEqual(model.results, [])
                    self.assertEqual(model.rowCount(), 0)
                    self.assertEqual(model.columnCount(), len(columns))
                    self.assertEqual(model.rowCount(valid_parent), 0)
                    self.assertEqual(model.columnCount(valid_parent), 0)

                main_window.show()
                page.show()
                app.processEvents()

                captured_stderr = io.StringIO()
                with redirect_stderr(captured_stderr):
                    page.order_table_view.grab()
                    page.jar_table_view.grab()
                    page.file_table_view.grab()
                    app.processEvents()

                self.assertNotIn("Traceback", captured_stderr.getvalue())
                self.assertNotIn("IndexError", captured_stderr.getvalue())
        finally:
            app.main_window = previous_main_window
            app.db_session = previous_db_session
            main_window.deleteLater()


if __name__ == "__main__":
    unittest.main()
