# coding: utf-8

"""Shared helpers used by manual and scale-based refill procedures."""

import unittest

from alfa_CR6_backend.refill_utils import convert_quantity, get_pipe_index_from_name


class CircuitMappingTest(unittest.TestCase):

    def test_maps_all_circuit_ranges(self):
        expected = {
            "B01": 0,
            "B08": 7,
            "C01": 8,
            "C24": 31,
        }
        for pipe_name, index in expected.items():
            with self.subTest(pipe_name=pipe_name):
                self.assertEqual(get_pipe_index_from_name(pipe_name), index)

    def test_rejects_invalid_circuit_names(self):
        for pipe_name in ("B00", "B09", "C00", "C25", "A01", "B1", None):
            with self.subTest(pipe_name=pipe_name):
                with self.assertRaises(ValueError):
                    get_pipe_index_from_name(pipe_name)


class QuantityConversionTest(unittest.TestCase):

    def test_converts_between_cc_grams_and_fluid_ounces(self):
        options = {"specific_weight": 1.25, "fl_oz_unit": 1000, "fl_oz_fraction": 32}

        self.assertAlmostEqual(convert_quantity(10, "CC", "GR", **options), 12.5)
        self.assertAlmostEqual(convert_quantity(12.5, "GR", "CC", **options), 10)
        self.assertAlmostEqual(convert_quantity(1000, "CC", "FL OZ", **options), 32)
        self.assertAlmostEqual(convert_quantity(32, "FL OZ", "GR", **options), 1250)

    def test_round_trip_preserves_quantity(self):
        options = {"specific_weight": 1.4, "fl_oz_unit": 768, "fl_oz_fraction": 25}
        grams = convert_quantity(123.45, "CC", "GR", **options)
        fluid_ounces = convert_quantity(grams, "GR", "FL OZ", **options)

        self.assertAlmostEqual(
            convert_quantity(fluid_ounces, "FL OZ", "CC", **options),
            123.45)


if __name__ == "__main__":
    unittest.main()
