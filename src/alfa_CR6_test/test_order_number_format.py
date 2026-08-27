# coding: utf-8

"""Regression tests for standard machine-generated order numbers."""

import unittest
from datetime import date
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alfa_CR6_backend import models
from alfa_CR6_backend.models import Base, Order, compile_barcode


class OrderNumberFormatTest(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.previous_global_session = models.global_session
        models.set_global_session(self.session)

    def tearDown(self):
        models.set_global_session(self.previous_global_session)
        self.session.close()
        self.engine.dispose()

    def _generate_for_july_27_2026(self):
        with mock.patch.object(models, "date") as mocked_date:
            mocked_date.today.return_value = date(2026, 7, 27)
            return models.generate_order_nr()

    def _add_order(self, order_nr):
        self.session.add(Order(order_nr=order_nr))
        self.session.commit()

    def test_first_order_and_jar_barcodes_use_standard_format(self):
        order_nr = self._generate_for_july_27_2026()

        self.assertEqual(order_nr, 260727001000)
        self.assertEqual(compile_barcode(order_nr, 1), "260727001001")
        self.assertEqual(compile_barcode(order_nr, 9), "260727001009")

    def test_foreign_date_prefix_does_not_affect_new_order(self):
        self._add_order(990727024600)

        self.assertEqual(self._generate_for_july_27_2026(), 260727001000)

    def test_future_standard_order_does_not_affect_current_day(self):
        self._add_order(260728001000)

        self.assertEqual(self._generate_for_july_27_2026(), 260727001000)

    def test_sequence_uses_only_standard_orders_from_same_day(self):
        self._add_order(260727001000)
        self._add_order(260727002000)
        self._add_order(260727999999)
        self._add_order(990727024600)

        self.assertEqual(self._generate_for_july_27_2026(), 260727003000)

    def test_daily_sequence_exhaustion_raises_explicit_error(self):
        self._add_order(260727999000)

        with self.assertRaisesRegex(
                RuntimeError, "daily order number sequence exhausted"):
            self._generate_for_july_27_2026()


if __name__ == "__main__":
    unittest.main()
