import json
import os
import tempfile
import unittest
import warnings
from unittest import mock

from alfa_CR6_backend.models import Jar, Order, init_models
from alfa_CR6_backend.order_parser import OrderParser


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REAL_KCC_PDF_DIR = os.path.join(PROJECT_ROOT, "doc", "__hidden__", "kcc_multi_coat")


class KccDoubleOrderTests(unittest.TestCase):

    def test_parse_kcc_pdf_double_coat_returns_distinct_orders(self):
        lines = [
            "KCC Color Navi Formulation",
            "Number : 010 ABT",
            "CANDIDATE : 01",
            "__________________________",
            "01 : K703      7.15(G)",
            "02 : K702      5.15(G)",
            "__________________________",
            "Total",
            "100.00(G)",
            "Current Weight 100.00(G)",
            "2021-01-29 09:24",
            "SECOND COAT",
            "Number : 010 ABT",
            "CANDIDATE : 02",
            "__________________________",
            "01 : K900      1.25(G)",
            "02 : K901      2.50(G)",
            "__________________________",
            "Total",
            "100.00(G)",
            "Current Weight 100.00(G)",
            "2021-01-29 09:25",
        ]

        first, has_second = OrderParser.parse_kcc_pdf(lines)
        second, _ = OrderParser.parse_kcc_pdf(lines, has_second)

        self.assertTrue(has_second)
        self.assertEqual(["K703", "K702"], [i["pigment_name"] for i in first["ingredients"]])
        self.assertEqual(["K900", "K901"], [i["pigment_name"] for i in second["ingredients"]])
        self.assertEqual("FIRST COAT", first["extra_lines_to_print"][-1])
        self.assertEqual("SECOND COAT", second["extra_lines_to_print"][-1])
        self.assertNotIn("K900", " ".join(first["extra_lines_to_print"]))

    def test_two_orders_can_be_committed_without_status_side_effect_warning(self):
        fd, db_path = tempfile.mkstemp(prefix="alfa_kcc_orders_", suffix=".sqlite", dir="/tmp")
        os.close(fd)
        os.unlink(db_path)
        session = init_models("sqlite:///" + db_path)

        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                created = []
                for pigment_name in ("FIRST", "SECOND"):
                    properties = {
                        "meta": {"file name": "kcc_double.pdf"},
                        "ingredients": [{"pigment_name": pigment_name, "weight(g)": 1.0}],
                        "extra_lines_to_print": [pigment_name],
                    }
                    order = Order(
                        json_properties=json.dumps(properties),
                        description="",
                        file_name="kcc_double.pdf",
                    )
                    session.add(order)
                    session.add(Jar(order=order, index=1, size=0))
                    session.commit()
                    created.append(order)

            self.assertEqual(2, len(created))
            self.assertNotEqual(created[0].order_nr, created[1].order_nr)
            self.assertEqual(["FIRST", "SECOND"], [
                json.loads(order.json_properties)["ingredients"][0]["pigment_name"]
                for order in created
            ])
            self.assertFalse([
                warning for warning in caught
                if "Attribute history events accumulated" in str(warning.message)
            ])
        finally:
            session.close()
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_real_kcc_multi_coat_pdfs_parse_as_distinct_orders(self):
        expected = {
            "UYH - 3COAT.pdf": [
                ["K616(LS K608)", "K406(LS K405)", "K205(LS K204)", "K100", "BINDER"],
                ["K903", "K901", "K904", "K060", "BINDER"],
            ],
            "SWP-1.pdf": [
                ["K406(LS K405)", "K616(LS K608)", "K205(LS K204)", "K701(LS K700)", "K100", "BINDER"],
                ["K903", "K926", "K913", "K060", "BINDER"],
            ],
        }

        if not os.path.isdir(REAL_KCC_PDF_DIR):
            self.skipTest(f"real KCC PDF directory not available: {REAL_KCC_PDF_DIR}")

        parser = OrderParser()
        for filename, expected_ingredients in expected.items():
            path = os.path.join(REAL_KCC_PDF_DIR, filename)
            if not os.path.exists(path):
                self.skipTest(f"real KCC PDF not available: {path}")

            with self.subTest(filename=filename):
                properties_list = parser.parse(path)

                self.assertEqual(2, len(properties_list))
                for properties in properties_list:
                    self.assertIsNone(properties.get("meta", {}).get("error"))

                self.assertEqual(["FIRST COAT", "SECOND COAT"], [
                    properties["extra_lines_to_print"][-1]
                    for properties in properties_list
                ])
                self.assertEqual(expected_ingredients, [
                    [ingredient["pigment_name"] for ingredient in properties["ingredients"]]
                    for properties in properties_list
                ])


class OrderStatusSideEffectTests(unittest.TestCase):
    """Root-cause guard for the KCC double-coat bug.

    Reading ``Order.status`` / ``Order.deleted`` must never commit the session.
    In the rc131 implementation the read path called ``update_status(session)``,
    whose hidden ``session.commit()`` was re-entered during the INSERT flush of
    the 2nd coat (``generate_order_nr`` stringifies the 1st order -> ``__str__``
    -> ``status``) and closed the transaction (ResourceClosedError). This test
    fails on that implementation and passes once the read path is side-effect
    free.
    """

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(prefix="alfa_status_inv_", suffix=".sqlite", dir="/tmp")
        os.close(fd)
        os.unlink(self.db_path)
        self.session = init_models("sqlite:///" + self.db_path)

    def tearDown(self):
        self.session.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _persist_new_order(self):
        order = Order(
            json_properties=json.dumps({"meta": "", "ingredients": []}),
            description="",
            file_name="kcc_double.pdf",
        )
        self.session.add(order)
        self.session.add(Jar(order=order, index=1, size=0))
        # leave inner_status / is_deleted NULL so the property takes the
        # recompute branch - the one that used to commit on read.
        order.inner_status = None
        order.is_deleted = None
        self.session.commit()
        return order

    def test_reading_status_and_deleted_does_not_commit(self):
        order = self._persist_new_order()

        with mock.patch.object(self.session, "commit", wraps=self.session.commit) as commit_spy:
            status = order.status
            deleted = order.deleted

        self.assertEqual("NEW", status)
        self.assertEqual("", deleted)
        commit_spy.assert_not_called()
        # the transaction is still open and usable after the reads
        self.assertEqual(1, self.session.query(Order).count())

    def test_reading_status_does_not_persist_inner_status(self):
        order = self._persist_new_order()
        order_nr = order.order_nr

        _ = order.status  # pure read: must not write inner_status to the DB

        # read the column straight from the DB, bypassing the identity map
        row = self.session.execute(
            "SELECT inner_status FROM \"order\" WHERE order_nr = :n", {"n": order_nr}
        ).fetchone()
        self.assertIsNone(row[0])


if __name__ == "__main__":
    unittest.main()
