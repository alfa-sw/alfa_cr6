import os
import tempfile
import unittest

from sqlalchemy import create_engine, inspect, text

from alfa_CR6_backend.models import Base, Jar, apply_table_alterations


JAR_LOOKUP_INDEX = "ix_jar_order_id_index"
CLEANUP_INDEXES = {
    "document": "ix_document_date_created_id",
    "event": "ix_event_date_created_id",
    "jar": "ix_jar_date_created_id",
    "order": "ix_order_date_created_id",
}


class DatabaseIndexTests(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(
            prefix="alfa_cr6_indexes_", suffix=".sqlite", dir="/tmp")
        os.close(fd)
        os.unlink(self.db_path)
        self.engine = create_engine("sqlite:///" + self.db_path)

    def tearDown(self):
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_jar_model_declares_composite_lookup_index(self):
        indexes = {
            index.name: tuple(column.name for column in index.columns)
            for index in Jar.__table__.indexes
        }

        self.assertEqual(("order_id", "index"), indexes[JAR_LOOKUP_INDEX])

    def test_existing_database_gets_lookup_index_idempotently(self):
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("DROP INDEX ix_jar_order_id_index"))

        self.assertNotIn(
            JAR_LOOKUP_INDEX,
            {item["name"] for item in inspect(self.engine).get_indexes("jar")},
        )

        apply_table_alterations(self.engine)
        apply_table_alterations(self.engine)

        indexes = inspect(self.engine).get_indexes("jar")
        matching_indexes = [
            item for item in indexes if item["name"] == JAR_LOOKUP_INDEX
        ]
        self.assertEqual(1, len(matching_indexes))
        self.assertEqual(
            ["order_id", "index"], matching_indexes[0]["column_names"])

        with self.engine.connect() as connection:
            plan = connection.execute(text(
                'EXPLAIN QUERY PLAN SELECT id FROM jar '
                'WHERE order_id = :order_id AND "index" = :jar_index'
            ), {"order_id": "order-id", "jar_index": 1}).fetchall()

        self.assertIn(JAR_LOOKUP_INDEX, " ".join(str(row) for row in plan))

    def test_existing_database_gets_cleanup_indexes(self):
        Base.metadata.create_all(self.engine)

        apply_table_alterations(self.engine)
        apply_table_alterations(self.engine)

        for table_name, index_name in CLEANUP_INDEXES.items():
            matching_indexes = [
                item for item in inspect(self.engine).get_indexes(table_name)
                if item["name"] == index_name
            ]
            self.assertEqual(1, len(matching_indexes), table_name)
            self.assertEqual(
                ["date_created", "id"],
                matching_indexes[0]["column_names"],
                table_name,
            )


if __name__ == "__main__":
    unittest.main()
