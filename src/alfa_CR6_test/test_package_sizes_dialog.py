# coding: utf-8

"""Visual state of PackageSizesDialog label-print controls."""

import json
import os
import unittest
from unittest import mock


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QApplication, QPushButton

from alfa_CR6_frontend.dialogs import PackageSizesDialog


class TestPackageSizesDialog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with mock.patch.object(
                PackageSizesDialog, "_load_package_data_sync"):
            self.dialog = PackageSizesDialog()
        self.dialog.package_table.setRowCount(1)

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

    def _set_package(self, package):
        self.dialog._PackageSizesDialog__set_row(0, package)
        cell = self.dialog.package_table.cellWidget(0, 3)
        return cell.findChild(
            QPushButton, "package_barcode_print_button")

    def test_dialog_uses_larger_default_fonts(self):
        self.assertEqual(self.dialog.title_lbl.font().pointSize(), 28)
        self.assertEqual(self.dialog.esc_button.font().pointSize(), 18)
        self.assertIn(
            "font-size: 26px",
            self.dialog.package_table.horizontalHeader().styleSheet())
        self.assertIn(
            "font-size: 22px", self.dialog.package_table.styleSheet())
        self.assertIn(
            "font-size: 19px", self.dialog._BARCODE_BUTTON_STYLE)

    def test_last_column_header_describes_the_print_action(self):
        self.assertEqual(
            self.dialog.package_table.horizontalHeaderItem(3).text(),
            "PRINT LABEL",
        )

    def test_barcode_info_column_is_wide_enough_for_its_header(self):
        self.assertEqual(self.dialog.package_table.columnWidth(2), 240)

    def test_complete_label_uses_high_contrast_print_button(self):
        package = {
            "name": "650 ml",
            "size": 650,
            "json_info": json.dumps({
                "label_barcode": {
                    "quantity": 650.0,
                    "unit": "ML",
                    "decimal_separator": ".",
                },
            }),
        }
        self.dialog._generate_barcode_label = mock.Mock()

        button = self._set_package(package)

        self.assertEqual(
            self.dialog.package_table.item(0, 2).text(),
            "Quantity: 650\nUnit: ML",
        )
        self.assertIsNotNone(button)
        self.assertTrue(button.isEnabled())
        self.assertEqual(button.text(), "")
        self.assertFalse(button.icon().isNull())
        self.assertIn("background-color: #FFFFFF", button.styleSheet())

        self.dialog.show()
        self.app.processEvents()
        self.assertEqual(button.iconSize(), QSize(
            int(button.width() * 0.75),
            int(button.height() * 0.75),
        ))

        button.click()
        self.dialog._generate_barcode_label.assert_called_once_with(package)

    def test_ounce_decimal_configuration_is_shown_and_printable(self):
        for unit in ("FL OZ", "OZ"):
            with self.subTest(unit=unit):
                package = {
                    "name": "12.25 {}".format(unit),
                    "size": 362,
                    "json_info": json.dumps({
                        "label_barcode": {
                            "quantity": 12.25,
                            "unit": unit,
                            "decimal_separator": ",",
                        },
                    }),
                }

                button = self._set_package(package)

                self.assertEqual(
                    self.dialog.package_table.item(0, 2).text(),
                    "Quantity: 12.25\nUnit: {}\nDecimal separator: ,".format(
                        unit),
                )
                self.assertTrue(button.isEnabled())

    def test_incomplete_label_has_explicit_disabled_state(self):
        package = {
            "name": "Legacy package",
            "size": 650,
            "json_info": "{}",
        }
        self.dialog._generate_barcode_label = mock.Mock()

        button = self._set_package(package)

        self.assertIsNotNone(button)
        self.assertFalse(button.isEnabled())
        self.assertEqual(button.text(), "LABEL DATA MISSING")
        self.assertTrue(button.icon().isNull())
        self.assertIn("border: 3px dashed #5A5A5A", button.styleSheet())

        button.click()
        self.dialog._generate_barcode_label.assert_not_called()


if __name__ == "__main__":
    unittest.main()
