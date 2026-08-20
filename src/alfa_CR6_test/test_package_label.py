# coding: utf-8

import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

from alfa_CR6_backend.package_label import (
    ShuttleBarcodeLabelError,
    get_shuttle_barcode_label_text,
)


class TestShuttleBarcodeLabel(unittest.TestCase):

    @staticmethod
    def printing_dependency_stubs():
        redis_stub = types.ModuleType("redis")
        arabic_reshaper_stub = types.ModuleType("arabic_reshaper")
        bidi_stub = types.ModuleType("bidi")
        bidi_algorithm_stub = types.ModuleType("bidi.algorithm")
        bidi_algorithm_stub.get_display = lambda value: value
        bidi_stub.algorithm = bidi_algorithm_stub
        barcode_stub = types.ModuleType("barcode")
        barcode_stub.EAN13 = object
        barcode_stub.Code128 = object
        barcode_writer_stub = types.ModuleType("barcode.writer")
        barcode_writer_stub.ImageWriter = object

        return mock.patch.dict(sys.modules, {
            "redis": redis_stub,
            "arabic_reshaper": arabic_reshaper_stub,
            "bidi": bidi_stub,
            "bidi.algorithm": bidi_algorithm_stub,
            "barcode": barcode_stub,
            "barcode.writer": barcode_writer_stub,
        })

    @staticmethod
    def package(label_barcode, name="Package display name", as_json=True):
        json_info = {"label_barcode": label_barcode}
        return {
            "name": name,
            "json_info": json.dumps(json_info) if as_json else json_info,
        }

    def test_integral_float_uses_label_configuration_not_package_name(self):
        package = self.package({
            "quantity": 1.0,
            "unit": "LT",
            "decimal_separator": ".",
        }, name="This name must not be printed")

        self.assertEqual(get_shuttle_barcode_label_text(package), "1 LT")

    def test_decimal_quantity_with_point(self):
        package = self.package({
            "quantity": 0.75,
            "unit": "L",
            "decimal_separator": ".",
        })

        self.assertEqual(get_shuttle_barcode_label_text(package), "0.75 L")

    def test_decimal_quantity_with_comma(self):
        package = self.package({
            "quantity": 0.75,
            "unit": "LT",
            "decimal_separator": ",",
        }, as_json=False)

        self.assertEqual(get_shuttle_barcode_label_text(package), "0,75 LT")

    def test_integer_units_use_the_common_quantity_format(self):
        for unit in ("FL OZ", "OZ"):
            with self.subTest(unit=unit):
                package = self.package({
                    "quantity": 34.0,
                    "unit": unit,
                })

                self.assertEqual(
                    get_shuttle_barcode_label_text(package),
                    "34 {}".format(unit),
                )

    def test_integer_units_ignore_decimal_separator(self):
        for unit in ("FL OZ", "OZ"):
            with self.subTest(unit=unit):
                package = self.package({
                    "quantity": 12.0,
                    "unit": unit,
                    "decimal_separator": ",",
                })

                self.assertEqual(
                    get_shuttle_barcode_label_text(package),
                    "12 {}".format(unit),
                )

    def test_integer_units_reject_fractional_quantity(self):
        for unit in ("FL OZ", "OZ"):
            with self.subTest(unit=unit):
                package = self.package({
                    "quantity": 12.25,
                    "unit": unit,
                })

                with self.assertRaisesRegex(
                        ShuttleBarcodeLabelError,
                        "Quantity must be an integer for {}".format(unit)):
                    get_shuttle_barcode_label_text(package)

    def test_trailing_zeroes_are_not_added(self):
        package = self.package({
            "quantity": 1000.0,
            "unit": "ML",
            "decimal_separator": ".",
        })

        self.assertEqual(get_shuttle_barcode_label_text(package), "1000 ML")

    def test_missing_label_configuration_does_not_fall_back_to_name(self):
        package = {"name": "1 LT", "json_info": "{}"}

        with self.assertRaises(ShuttleBarcodeLabelError) as raised:
            get_shuttle_barcode_label_text(package)

        self.assertEqual(raised.exception.errors, (
            "Quantity is required.",
            "Unit of measure is required.",
            "Decimal separator is required.",
        ))
        self.assertNotIn("1 LT\n", str(raised.exception))

    def test_all_missing_fields_are_reported_together(self):
        with self.assertRaises(ShuttleBarcodeLabelError) as raised:
            get_shuttle_barcode_label_text(self.package({}))

        self.assertEqual(raised.exception.errors, (
            "Quantity is required.",
            "Unit of measure is required.",
            "Decimal separator is required.",
        ))

    def test_all_invalid_fields_are_reported_together(self):
        package = self.package({
            "quantity": 0.0,
            "unit": "GAL",
            "decimal_separator": ";",
        })

        with self.assertRaises(ShuttleBarcodeLabelError) as raised:
            get_shuttle_barcode_label_text(package)

        self.assertEqual(raised.exception.errors, (
            "Quantity must be greater than zero.",
            "Unit of measure 'GAL' is not supported. Allowed values: "
            "ML, L, LT, GR, FL OZ, OZ.",
            "Decimal separator ';' is not supported. Allowed values: "
            "point (.) or comma (,).",
        ))

        message = str(raised.exception)
        for error in raised.exception.errors:
            self.assertIn("- " + error, message)

    def test_invalid_quantity_type_is_reported(self):
        package = self.package({
            "quantity": "1",
            "unit": "ML",
            "decimal_separator": ".",
        })

        with self.assertRaisesRegex(
                ShuttleBarcodeLabelError,
                "Quantity must be a floating-point number"):
            get_shuttle_barcode_label_text(package)

    def test_integer_quantity_is_rejected(self):
        package = self.package({
            "quantity": 1,
            "unit": "ML",
            "decimal_separator": ".",
        })

        with self.assertRaisesRegex(
                ShuttleBarcodeLabelError,
                "Quantity must be a floating-point number"):
            get_shuttle_barcode_label_text(package)

    def test_image_generator_passes_fl_oz_text_to_code128(self):
        with self.printing_dependency_stubs():
            from alfa_CR6_backend import globals as globals_  # pylint: disable=import-outside-toplevel

        captured = {}

        class FakeCode128:

            def __init__(self, value, writer):
                captured["value"] = value
                captured["writer"] = writer

            @staticmethod
            def write(file_, options, printable_text):
                captured["options"] = options
                captured["printable_text"] = printable_text
                file_.write(b"fake image")

        class FakeImage:

            def rotate(self, angle, expand):
                captured["rotation"] = (angle, expand)
                return self

            @staticmethod
            def save(path):
                captured["saved_path"] = path

        pil_image_stub = types.ModuleType("PIL.Image")
        pil_image_stub.open = lambda path: FakeImage()
        pil_stub = types.ModuleType("PIL")
        pil_stub.Image = pil_image_stub

        package = self.package({
            "quantity": 34.0,
            "unit": "FL OZ",
        })

        with tempfile.TemporaryDirectory() as tmp_dir:
            image_path = os.path.join(tmp_dir, "package_barcode.png")
            with mock.patch.object(
                    globals_, "TMP_PACKAGE_BARCODE_IMAGE", image_path), \
                    mock.patch.object(globals_, "Code128", FakeCode128), \
                    mock.patch.dict(sys.modules, {
                        "PIL": pil_stub,
                        "PIL.Image": pil_image_stub,
                    }):
                result = globals_.create_printable_image_for_package(package)

        self.assertEqual(result, image_path)
        self.assertEqual(captured["value"], "34 FL OZ")
        self.assertEqual(captured["printable_text"], "34 FL OZ")
        self.assertEqual(captured["rotation"], (90, True))
        self.assertEqual(captured["saved_path"], image_path)

    def test_printing_response_contains_operator_errors_not_traceback(self):
        with self.printing_dependency_stubs():
            from alfa_CR6_backend.dymo_printer import (  # pylint: disable=import-outside-toplevel
                async_dymo_print_package_label,
            )

        result = asyncio.run(async_dymo_print_package_label(
            {"name": "1 LT", "json_info": "{}"},
            fake=True,
        ))

        self.assertEqual(result["result"], "NOK")
        self.assertIn("- Quantity is required.", result["msg"])
        self.assertIn("- Unit of measure is required.", result["msg"])
        self.assertIn("- Decimal separator is required.", result["msg"])
        self.assertNotIn("Traceback", result["msg"])


if __name__ == "__main__":
    unittest.main()
