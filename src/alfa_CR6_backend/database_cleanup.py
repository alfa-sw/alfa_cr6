# coding: utf-8

"""Scheduled, bounded cleanup for the application SQLite database."""

import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta

from sqlalchemy.engine.url import make_url  # pylint: disable=import-error


_VALID_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def seconds_until_next_local_midnight(now_timestamp=None):
    """Return elapsed seconds to 00:00 in the system local timezone.

    ``time.mktime`` applies the operating-system daylight-saving rules, keeping
    the run at wall-clock midnight across 23/25-hour days.
    """

    if now_timestamp is None:
        now_timestamp = time.time()
    local_now = datetime.fromtimestamp(now_timestamp)
    next_date = local_now.date() + timedelta(days=1)
    next_midnight = datetime.combine(next_date, datetime.min.time())
    next_timestamp = time.mktime(next_midnight.timetuple())
    return max(0.0, next_timestamp - now_timestamp)


def _database_path(sqlite_connect_string):
    url = make_url(sqlite_connect_string)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("database cleanup requires a file-backed SQLite database")
    return url.database


def _quoted_table_name(table_name):
    if not _VALID_TABLE_NAME.match(table_name):
        raise ValueError("invalid cleanup table name: {!r}".format(table_name))
    return '"{}"'.format(table_name)


def _ordered_tables(pending_limits):
    # Orders must be handled before jars: deleting the oldest orders can already
    # remove enough child jars to satisfy the jar watermark.
    priority = {"order": 0, "jar": 2}
    return sorted(pending_limits, key=lambda name: (priority.get(name, 1), name))


def detect_pending_tables(sqlite_connect_string, table_limits):
    """Return the configured tables whose row count exceeds its limit."""

    pending_limits = {}
    connection = sqlite3.connect(_database_path(sqlite_connect_string), timeout=0.1)
    try:
        connection.execute("PRAGMA busy_timeout=100")
        for table_name, row_limit in table_limits.items():
            table = _quoted_table_name(table_name)
            row_count = connection.execute(
                "SELECT COUNT(*) FROM {}".format(table)).fetchone()[0]
            if row_count > row_limit:
                pending_limits[table_name] = int(row_limit)
                logging.warning(
                    "database cleanup pending for %s: row_count=%s, limit=%s",
                    table_name, row_count, row_limit)
    finally:
        connection.close()

    return pending_limits


def cleanup_pending_database(
        sqlite_connect_string, pending_limits, cancel_event=None,
        batch_size=250, batch_pause_seconds=0.05):
    """Delete old rows in short transactions using a dedicated connection.

    ``pending_limits`` is a ``{table_name: row_limit}`` snapshot produced by
    ``detect_pending_tables``. A pending table is brought to its 90% low
    watermark. Cancellation is observed between transactions, so the current
    transaction remains atomic and holds the SQLite writer lock for one batch.
    """

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")

    result = {
        "completed_tables": [],
        "deleted_rows": {},
        "deleted_child_jars": 0,
        "cancelled": False,
        "busy": False,
        "secure_delete": None,
    }
    connection = sqlite3.connect(_database_path(sqlite_connect_string), timeout=0.1)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=100")
        connection.execute("PRAGMA secure_delete=FAST")
        result["secure_delete"] = connection.execute(
            "PRAGMA secure_delete").fetchone()[0]

        for table_name in _ordered_tables(pending_limits):
            table = _quoted_table_name(table_name)
            row_limit = int(pending_limits[table_name])
            low_watermark = row_limit - int(row_limit * 0.1)
            deleted_rows = 0

            while True:
                if cancel_event is not None and cancel_event.is_set():
                    result["cancelled"] = True
                    break

                row_count = connection.execute(
                    "SELECT COUNT(*) FROM {}".format(table)).fetchone()[0]
                rows_to_delete = row_count - low_watermark
                if rows_to_delete <= 0:
                    result["completed_tables"].append(table_name)
                    break

                current_batch_size = min(batch_size, rows_to_delete)
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    row_ids = [
                        row[0] for row in connection.execute(
                            "SELECT id FROM {} "
                            "ORDER BY date_created, id LIMIT ?".format(table),
                            (current_batch_size,),
                        ).fetchall()
                    ]
                    if not row_ids:
                        connection.rollback()
                        result["completed_tables"].append(table_name)
                        break

                    placeholders = ",".join("?" for _ in row_ids)
                    if table_name == "order":
                        cursor = connection.execute(
                            "DELETE FROM jar WHERE order_id IN ({})".format(
                                placeholders),
                            row_ids,
                        )
                        result["deleted_child_jars"] += max(cursor.rowcount, 0)

                    cursor = connection.execute(
                        "DELETE FROM {} WHERE id IN ({})".format(
                            table, placeholders),
                        row_ids,
                    )
                    deleted_rows += max(cursor.rowcount, 0)
                    connection.commit()
                except sqlite3.OperationalError as exc:
                    connection.rollback()
                    if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                        result["busy"] = True
                        logging.info("database cleanup yielded to another writer: %s", exc)
                        break
                    raise

                if batch_pause_seconds > 0:
                    time.sleep(batch_pause_seconds)

            result["deleted_rows"][table_name] = deleted_rows
            if result["cancelled"] or result["busy"]:
                break
    finally:
        connection.close()

    return result
