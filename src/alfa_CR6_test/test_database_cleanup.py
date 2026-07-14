import os
import sqlite3
import tempfile
import threading
import time
import unittest

from alfa_CR6_backend.database_cleanup import (
    cleanup_pending_database, detect_pending_tables,
    seconds_until_next_local_midnight)
from alfa_CR6_backend.models import (
    DATABASE_CLEANUP_MODELS, Document, Event, Jar, Order, init_models)


class DatabaseCleanupTests(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(
            prefix="alfa_cr6_cleanup_", suffix=".sqlite", dir="/tmp")
        os.close(fd)
        os.unlink(self.db_path)
        self.sqlite_connect_string = "sqlite:///" + self.db_path
        self.original_limits = {
            Document: Document.row_count_limt,
            Event: Event.row_count_limt,
            Jar: Jar.row_count_limt,
            Order: Order.row_count_limt,
        }
        Document.row_count_limt = 10
        Event.row_count_limt = 10
        Jar.row_count_limt = 10
        Order.row_count_limt = 10
        self.session = init_models(self.sqlite_connect_string)

    def tearDown(self):
        self.session.close()
        self.session.bind.dispose()
        for model_class, row_limit in self.original_limits.items():
            model_class.row_count_limt = row_limit
        for suffix in ("", "-journal", "-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                os.unlink(path)

    def _add_events(self, count):
        self.session.add_all([
            Event(name="TEST_{}".format(index))
            for index in range(count)
        ])

    def _add_orders_and_jars(self, count):
        for index in range(count):
            order = Order(
                order_nr=260714000000 + (index + 1) * 1000,
                inner_status="DONE",
                file_name="cleanup-test.pdf",
            )
            order.jars.append(Jar(index=1, size=0, status="DONE", position="_"))
            self.session.add(order)

    def _table_limits(self):
        return {
            model_class.__tablename__: model_class.row_count_limt
            for model_class in DATABASE_CLEANUP_MODELS
        }

    def _detect_pending_tables(self, table_limits=None):
        return detect_pending_tables(
            self.sqlite_connect_string,
            table_limits or self._table_limits(),
        )

    def test_detection_returns_only_tables_above_their_limit(self):
        self._add_events(11)
        self.session.commit()

        self.assertEqual(11, self.session.query(Event).count())
        self.assertEqual({"event": 10}, self._detect_pending_tables())

    def test_worker_deletes_to_low_watermark_in_bounded_batches(self):
        self._add_events(11)
        self.session.commit()

        result = cleanup_pending_database(
            self.sqlite_connect_string,
            self._detect_pending_tables(),
            batch_size=1,
            batch_pause_seconds=0,
        )

        self.session.expire_all()
        self.assertEqual(9, self.session.query(Event).count())
        self.assertEqual(2, result["deleted_rows"]["event"])
        self.assertEqual(["event"], result["completed_tables"])
        self.assertIn(result["secure_delete"], (1, 2))

    def test_document_uses_the_same_daily_cleanup_flow(self):
        self.session.add_all([
            Document(name="TEST_{}".format(index), type="TEST")
            for index in range(11)
        ])
        self.session.commit()

        self.assertEqual({"document": 10}, self._detect_pending_tables())
        result = cleanup_pending_database(
            self.sqlite_connect_string,
            self._detect_pending_tables(),
            batch_size=1,
            batch_pause_seconds=0,
        )

        self.session.expire_all()
        self.assertEqual(9, self.session.query(Document).count())
        self.assertEqual(2, result["deleted_rows"]["document"])

    def test_order_cleanup_removes_children_before_orders(self):
        self._add_orders_and_jars(11)
        self.session.commit()

        self.assertEqual(
            {"jar": 10, "order": 10}, self._detect_pending_tables())
        result = cleanup_pending_database(
            self.sqlite_connect_string,
            self._detect_pending_tables(),
            batch_size=1,
            batch_pause_seconds=0,
        )

        self.session.expire_all()
        self.assertEqual(9, self.session.query(Order).count())
        self.assertEqual(9, self.session.query(Jar).count())
        self.assertEqual(2, result["deleted_rows"]["order"])
        self.assertEqual(2, result["deleted_child_jars"])
        self.assertEqual({"jar", "order"}, set(result["completed_tables"]))
        connection = sqlite3.connect(self.db_path)
        try:
            self.assertEqual([], connection.execute(
                "PRAGMA foreign_key_check").fetchall())
        finally:
            connection.close()

    def test_worker_observes_cancellation_before_first_batch(self):
        self._add_events(11)
        self.session.commit()
        cancel_event = threading.Event()
        cancel_event.set()

        result = cleanup_pending_database(
            self.sqlite_connect_string,
            self._detect_pending_tables(),
            cancel_event=cancel_event,
            batch_size=1,
            batch_pause_seconds=0,
        )

        self.assertTrue(result["cancelled"])
        self.assertEqual([], result["completed_tables"])
        self.assertEqual(11, self.session.query(Event).count())

    def test_pending_snapshot_reaches_watermark_after_partial_retry(self):
        class CancelAfterFirstBatch:

            def __init__(self):
                self.check_count = 0

            def is_set(self):
                self.check_count += 1
                return self.check_count > 1

        self._add_events(11)
        self.session.commit()
        pending_limits = self._detect_pending_tables()

        first_result = cleanup_pending_database(
            self.sqlite_connect_string,
            pending_limits,
            cancel_event=CancelAfterFirstBatch(),
            batch_size=1,
            batch_pause_seconds=0,
        )

        self.assertTrue(first_result["cancelled"])
        self.assertEqual([], first_result["completed_tables"])
        self.assertEqual(10, self.session.query(Event).count())

        second_result = cleanup_pending_database(
            self.sqlite_connect_string,
            pending_limits,
            batch_size=1,
            batch_pause_seconds=0,
        )

        self.session.expire_all()
        self.assertEqual(["event"], second_result["completed_tables"])
        self.assertEqual(9, self.session.query(Event).count())

    def test_existing_excess_is_detected_after_restart(self):
        self._add_events(11)
        self.session.commit()
        self.session.close()
        self.session.bind.dispose()

        self.session = init_models(self.sqlite_connect_string)

        self.assertEqual({"event": 10}, self._detect_pending_tables())

    def test_only_requested_tables_are_managed(self):
        self.assertEqual(
            {Document, Event, Jar, Order},
            set(DATABASE_CLEANUP_MODELS),
        )

    def test_detection_does_not_include_unconfigured_tables(self):
        self._add_events(11)
        self.session.add_all([
            Document(name="TEST_{}".format(index), type="TEST")
            for index in range(11)
        ])
        self.session.commit()

        self.assertEqual(
            {"event": 10},
            self._detect_pending_tables({"event": 10}),
        )

    def test_next_midnight_uses_local_timezone_and_dst(self):
        if not hasattr(time, "tzset"):
            self.skipTest("time.tzset is not available")

        original_timezone = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "Europe/Rome"
            time.tzset()

            summer_2330 = time.mktime(
                (2026, 7, 14, 23, 30, 0, -1, -1, -1))
            spring_midnight = time.mktime(
                (2026, 3, 29, 0, 0, 0, -1, -1, -1))
            autumn_midnight = time.mktime(
                (2026, 10, 25, 0, 0, 0, -1, -1, -1))

            self.assertEqual(
                30 * 60,
                seconds_until_next_local_midnight(summer_2330),
            )
            self.assertEqual(
                23 * 60 * 60,
                seconds_until_next_local_midnight(spring_midnight),
            )
            self.assertEqual(
                25 * 60 * 60,
                seconds_until_next_local_midnight(autumn_midnight),
            )
        finally:
            if original_timezone is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = original_timezone
            time.tzset()


if __name__ == "__main__":
    unittest.main()
