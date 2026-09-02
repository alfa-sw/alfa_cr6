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
    build_shuttle_barcode_size_map,
    get_shuttle_barcode_label_config,
    get_shuttle_barcode_label_info_text,
    get_shuttle_barcode_label_text,
    normalize_shuttle_barcode_label_text,
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

    def test_barcode_info_filters_other_json_info_keys(self):
        package = {
            "name": "Package display name",
            "json_info": json.dumps({
                "other": "must not be displayed",
                "label_barcode": {
                    "quantity": 500.0,
                    "unit": "ML",
                    "decimal_separator": ".",
                },
            }),
        }

        expected = {
            "quantity": 500.0,
            "unit": "ML",
            "decimal_separator": ".",
        }
        self.assertEqual(get_shuttle_barcode_label_config(package), expected)
        self.assertEqual(
            get_shuttle_barcode_label_info_text(package),
            "Quantity: 500\nUnit: ML",
        )
        self.assertNotIn("must not be displayed",
                         get_shuttle_barcode_label_info_text(package))

    def test_ml_barcode_info_does_not_truncate_fractional_quantity(self):
        package = self.package({
            "quantity": 500.5,
            "unit": "ML",
            "decimal_separator": ".",
        })

        self.assertEqual(
            get_shuttle_barcode_label_info_text(package),
            "Quantity: 500.5\nUnit: ML",
        )

    def test_barcode_info_uses_na_for_missing_or_invalid_json_info(self):
        expected = (
            "Quantity: N/A\nUnit: N/A\nDecimal separator: N/A")
        for json_info in (None, "{}", "not-json"):
            with self.subTest(json_info=json_info):
                self.assertEqual(
                    get_shuttle_barcode_label_info_text({
                        "name": "Package display name",
                        "json_info": json_info,
                    }),
                    expected,
                )

    def test_oz_info_includes_decimal_separator(self):
        package = self.package({
            "quantity": 12.5,
            "unit": "OZ",
            "decimal_separator": ".",
        })

        self.assertEqual(
            get_shuttle_barcode_label_info_text(package),
            "Quantity: 12.5\nUnit: OZ\nDecimal separator: .",
        )

    def test_fl_oz_info_includes_decimal_separator(self):
        package = self.package({
            "quantity": 34.5,
            "unit": "FL OZ",
            "decimal_separator": ",",
        })

        self.assertEqual(
            get_shuttle_barcode_label_info_text(package),
            "Quantity: 34.5\nUnit: FL OZ\nDecimal separator: ,",
        )

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

    def test_ounce_units_accept_fractional_quantity_and_selected_separator(self):
        for unit in ("FL OZ", "OZ"):
            for separator, quantity_text in ((".", "12.25"),
                                             (",", "12,25")):
                with self.subTest(unit=unit, separator=separator):
                    package = self.package({
                        "quantity": 12.25,
                        "unit": unit,
                        "decimal_separator": separator,
                    })

                    self.assertEqual(
                        get_shuttle_barcode_label_text(package),
                        "{} {}".format(quantity_text, unit),
                    )

    def test_ounce_units_require_decimal_separator(self):
        for unit in ("FL OZ", "OZ"):
            with self.subTest(unit=unit), self.assertRaisesRegex(
                    ShuttleBarcodeLabelError,
                    "Decimal separator is required"):
                get_shuttle_barcode_label_text(self.package({
                    "quantity": 12.25,
                    "unit": unit,
                }))

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
                "Quantity must be a number"):
            get_shuttle_barcode_label_text(package)

    def test_integer_quantity_is_accepted_for_regular_units(self):
        package = self.package({
            "quantity": 1,
            "unit": "ML",
            "decimal_separator": ".",
        })

        self.assertEqual(get_shuttle_barcode_label_text(package), "1 ML")

    def test_scanned_label_grammar_accepts_all_generated_formats(self):
        cases = {
            "500 ML": "500 ML",
            "0.75 L": "0.75 L",
            "0,75 LT": "0,75 LT",
            "160 GR": "160 GR",
            "34 FL OZ": "34 FL OZ",
            "12.25 FL OZ": "12.25 FL OZ",
            "12,25 FL OZ": "12,25 FL OZ",
            "12 OZ": "12 OZ",
            "12.25 OZ": "12.25 OZ",
            "12,25 OZ": "12,25 OZ",
            " 500 ml ": "500 ML",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(
                    normalize_shuttle_barcode_label_text(value), expected)

    def test_scanned_label_grammar_rejects_noise_and_invalid_units(self):
        for value in (
                None, "", "R4ND0M", "500", "ML", "500ML",
                "500  ML", "500_ML",
                "0 ML", "500 ML500 ML", "260802001001", "12 GAL"):
            with self.subTest(value=value):
                self.assertIsNone(
                    normalize_shuttle_barcode_label_text(value))

    def test_size_map_uses_generated_label_instead_of_package_name(self):
        package = self.package({
            "quantity": 0.75,
            "unit": "LT",
            "decimal_separator": ",",
        }, name="Name must not be used")
        package["size"] = 750

        size_map, duplicates = build_shuttle_barcode_size_map([package])

        self.assertEqual(size_map, {"0,75 LT": 750})
        self.assertEqual(duplicates, set())

    def test_size_map_removes_ambiguous_generated_labels(self):
        packages = []
        for name, size in (("First", 500), ("Second", 750)):
            package = self.package({
                "quantity": 500.0,
                "unit": "ML",
                "decimal_separator": ".",
            }, name=name)
            package["size"] = size
            packages.append(package)

        size_map, duplicates = build_shuttle_barcode_size_map(packages)

        self.assertEqual(size_map, {})
        self.assertEqual(duplicates, {"500 ML"})

    def test_image_generator_passes_decimal_fl_oz_text_to_code128(self):
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
            "quantity": 34.5,
            "unit": "FL OZ",
            "decimal_separator": ",",
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
        self.assertEqual(captured["value"], "34,5 FL OZ")
        self.assertEqual(captured["printable_text"], "34,5 FL OZ")
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
