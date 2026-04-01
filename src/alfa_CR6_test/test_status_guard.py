"""
Regression tests for DONE/ERROR jar transit behavior.

Run from the project root with:
PYTHONPATH=/opt/PROJECTS/alfa_cr6/src python3 -m unittest \
    /opt/PROJECTS/alfa_cr6/src/alfa_CR6_test/test_done_status_guard.py -v

This module stubs optional runtime dependencies so it can run even in a
lightweight development environment.
"""

import asyncio
import json
import sys
import types
import unittest
from types import SimpleNamespace

sys.modules.setdefault("redis", types.SimpleNamespace(from_url=lambda *args, **kwargs: None))
sys.modules.setdefault("aiohttp", types.SimpleNamespace(ClientSession=object, FormData=object))
sys.modules.setdefault(
    "alfa_CR6_backend.models",
    types.SimpleNamespace(
        Order=object,
        Jar=object,
        Event=object,
        Document=object,
        decompile_barcode=lambda barcode: (int(barcode) // 1000 * 1000, int(barcode) % 1000),
    ),
)
sys.modules.setdefault(
    "alfa_CR6_backend.globals",
    types.SimpleNamespace(
        UI_PATH="",
        KEYBOARD_PATH="",
        EPSILON=0.0002,
        get_version=lambda: "test",
        tr_=lambda value: value,
        import_settings=lambda: SimpleNamespace(),
    ),
)
sys.modules.setdefault("alfa_CR6_backend.machine_head", types.SimpleNamespace(MachineHead=object))
sys.modules.setdefault("alfa_CR6_backend.order_parser", types.SimpleNamespace(OrderParser=object))
sys.modules.setdefault("alfa_CR6_backend.ws_server", types.SimpleNamespace(WsServer=object))
sys.modules.setdefault("alfa_CR6_frontend.chromium_wrapper", types.SimpleNamespace(ChromiumWrapper=object))
sys.modules.setdefault("alfa_CR6_frontend.dialogs", types.SimpleNamespace(ModalMessageBox=object))

from alfa_CR6_backend.base_application import BaseApplication


class FakeCommitSession:
    def __init__(self):
        self.commit_calls = 0

    def commit(self):
        self.commit_calls += 1


class FakeTask:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True
        return True


class FakeOrder:
    def __init__(self, status="DONE"):
        self.status = status
        self.updated = False
        self.jars = []

    def update_status(self, session=None):
        self.updated = True
        counters = {}
        for jar in self.jars:
            if jar.position != "DELETED":
                counters.setdefault(jar.status, 0)
                counters[jar.status] += 1

        # Mirror alfa_CR6_backend.models.Order.update_status():
        # DONE + ERROR -> ERROR
        # NEW + PROGRESS -> PROGRESS
        # NEW + DONE -> PARTIAL
        # DONE + DONE -> DONE
        # NEW + NEW -> NEW
        self.status = "NEW"
        if counters.get("ERROR"):
            self.status = "ERROR"
        elif counters.get("PROGRESS"):
            self.status = "PROGRESS"
        elif counters.get("NEW") and counters.get("DONE"):
            self.status = "PARTIAL"
        elif not counters.get("NEW") and counters.get("DONE"):
            self.status = "DONE"
        return self.status


class FakeJar:
    def __init__(self, status="DONE", position="_", barcode="100000000001", order=None):
        self.status = status
        self.position = position
        self.barcode = barcode
        self.order = order or FakeOrder(status=status)
        self.order.jars.append(self)
        self.machine_head = "A"
        self.description = ""
        self.json_properties = json.dumps({
            "insufficient_pigments": {},
            "unknown_pigments": {},
        })

    def update_live(self, machine_head=None, status=None, pos=None, t0=None):
        self.machine_head = machine_head
        if status is not None:
            self.status = status
            self.order.update_status()
        if pos is not None:
            self.position = pos

    def object_to_dict(self, include_relationship=2):
        return {
            "barcode": self.barcode,
            "status": self.status,
            "position": self.position,
        }


class DoneStatusGuardTests(unittest.TestCase):

    def test_order_update_status_covers_all_status_rules(self):
        def make_order_with_statuses(*statuses):
            order = FakeOrder()
            for index, status in enumerate(statuses, start=1):
                FakeJar(
                    status=status,
                    position=f"P{index}",
                    barcode=f"100000000{index:03d}",
                    order=order,
                )
            return order

        cases = [
            (("DONE", "ERROR"), "ERROR"),
            (("NEW", "PROGRESS"), "PROGRESS"),
            (("NEW", "DONE"), "PARTIAL"),
            (("DONE", "DONE"), "DONE"),
            (("NEW", "NEW"), "NEW"),
        ]

        for jar_statuses, expected_order_status in cases:
            with self.subTest(jar_statuses=jar_statuses, expected=expected_order_status):
                order = make_order_with_statuses(*jar_statuses)
                self.assertEqual(order.update_status(), expected_order_status)

    def test_done_jar_task_starts_carousel_steps_but_preserves_status(self):
        barcode = "100000000001"
        jar = FakeJar(status="DONE", barcode=barcode)

        class FakeApp:
            def __init__(self):
                self.jar = jar
                self.n_of_active_heads = 6
                self.main_window = SimpleNamespace(show_barcode=lambda *args, **kwargs: None)
                self._BaseApplication__jar_runners = {
                    barcode: {"task": None, "frozen": True}
                }
                self.execute_calls = 0

            async def get_and_check_jar_from_barcode(self, _barcode):
                return self.jar

            async def execute_carousel_steps(self, *_args, **_kwargs):
                self.execute_calls += 1
                return True

            def handle_exception(self, exc):
                raise exc

        app = FakeApp()

        asyncio.run(BaseApplication._BaseApplication__jar_task(app, barcode))

        self.assertEqual(app.execute_calls, 1)
        self.assertIs(app._BaseApplication__jar_runners[barcode]["jar"], jar)
        self.assertEqual(jar.status, "DONE")
        self.assertFalse(app._BaseApplication__jar_runners[barcode]["frozen"])

    def test_error_jar_task_starts_carousel_steps_but_preserves_status(self):
        barcode = "100000000001"
        jar = FakeJar(status="ERROR", barcode=barcode)

        class FakeApp:
            def __init__(self):
                self.jar = jar
                self.n_of_active_heads = 6
                self.main_window = SimpleNamespace(show_barcode=lambda *args, **kwargs: None)
                self._BaseApplication__jar_runners = {
                    barcode: {"task": None, "frozen": True}
                }
                self.execute_calls = 0

            async def get_and_check_jar_from_barcode(self, _barcode):
                return self.jar

            async def execute_carousel_steps(self, *_args, **_kwargs):
                self.execute_calls += 1
                return True

            def handle_exception(self, exc):
                raise exc

        app = FakeApp()

        asyncio.run(BaseApplication._BaseApplication__jar_task(app, barcode))

        self.assertEqual(app.execute_calls, 1)
        self.assertFalse(app._BaseApplication__jar_runners[barcode]["frozen"])
        self.assertEqual(jar.status, "ERROR")

    def test_update_jar_position_preserves_done_status_and_updates_position(self):
        session = FakeCommitSession()
        published = []
        jar = FakeJar(status="DONE", position="_")

        app = SimpleNamespace(
            machine_head_dict={},
            _BaseApplication__jar_runners={},
            db_session=session,
            redis_publisher=SimpleNamespace(publish_messages=lambda payload: published.append(payload)),
            restore_machine_helper=None,
            main_window=SimpleNamespace(home_page=SimpleNamespace(update_jar_pixmaps=lambda: None)),
            ws_server=SimpleNamespace(refresh_can_list=lambda: None),
            handle_exception=lambda exc: (_ for _ in ()).throw(exc),
        )

        machine_head = SimpleNamespace(name="HEAD_A", owned_barcodes=[])

        BaseApplication.update_jar_position(
            app,
            jar,
            machine_head=machine_head,
            status="PROGRESS",
            pos="A",
        )

        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "A")
        self.assertIs(jar.machine_head, machine_head)
        self.assertEqual(session.commit_calls, 1)
        self.assertEqual(len(published), 1)

    def test_update_jar_position_preserves_error_status_and_updates_position(self):
        session = FakeCommitSession()
        published = []
        jar = FakeJar(status="ERROR", position="_")

        app = SimpleNamespace(
            machine_head_dict={},
            _BaseApplication__jar_runners={},
            db_session=session,
            redis_publisher=SimpleNamespace(publish_messages=lambda payload: published.append(payload)),
            restore_machine_helper=None,
            main_window=SimpleNamespace(home_page=SimpleNamespace(update_jar_pixmaps=lambda: None)),
            ws_server=SimpleNamespace(refresh_can_list=lambda: None),
            handle_exception=lambda exc: (_ for _ in ()).throw(exc),
        )

        machine_head = SimpleNamespace(name="HEAD_A", owned_barcodes=[])

        BaseApplication.update_jar_position(
            app,
            jar,
            machine_head=machine_head,
            status="PROGRESS",
            pos="A",
        )

        self.assertEqual(jar.status, "ERROR")
        self.assertEqual(jar.position, "A")
        self.assertIs(jar.machine_head, machine_head)
        self.assertEqual(session.commit_calls, 1)
        self.assertEqual(len(published), 1)

    def test_update_jar_position_keeps_partial_order_with_mixed_done_and_new_jars(self):
        session = FakeCommitSession()
        order = FakeOrder()
        done_jar = FakeJar(status="DONE", position="_", barcode="100000000001", order=order)
        FakeJar(status="NEW", position="_", barcode="100000000002", order=order)
        published = []

        app = SimpleNamespace(
            machine_head_dict={},
            _BaseApplication__jar_runners={},
            db_session=session,
            redis_publisher=SimpleNamespace(publish_messages=lambda payload: published.append(payload)),
            restore_machine_helper=None,
            main_window=SimpleNamespace(home_page=SimpleNamespace(update_jar_pixmaps=lambda: None)),
            ws_server=SimpleNamespace(refresh_can_list=lambda: None),
            handle_exception=lambda exc: (_ for _ in ()).throw(exc),
        )

        BaseApplication.update_jar_position(
            app,
            done_jar,
            machine_head=SimpleNamespace(name="HEAD_A", owned_barcodes=[]),
            status="PROGRESS",
            pos="A",
        )

        self.assertEqual(done_jar.status, "DONE")
        self.assertEqual(done_jar.position, "A")
        self.assertEqual(order.status, "PARTIAL")
        self.assertEqual(len(published), 1)

    def test_delete_entering_jar_preserves_done_status_but_clears_position(self):
        session = FakeCommitSession()
        task = FakeTask()
        jar = FakeJar(status="DONE", position="A")

        app = SimpleNamespace(
            db_session=session,
            ws_server=SimpleNamespace(refresh_can_list=lambda: None),
        )

        entering_jar = {"jar": jar, "task": task}

        BaseApplication._del_entering_jar(app, entering_jar, jar.barcode)

        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "_")
        self.assertIsNone(jar.machine_head)
        self.assertTrue(jar.order.updated)
        self.assertTrue(task.cancelled)
        self.assertEqual(session.commit_calls, 1)

    def test_delete_entering_jar_keeps_partial_order_for_mixed_done_and_new_jars(self):
        session = FakeCommitSession()
        task = FakeTask()
        order = FakeOrder()
        done_jar = FakeJar(status="DONE", position="A", barcode="100000000001", order=order)
        FakeJar(status="NEW", position="_", barcode="100000000002", order=order)

        app = SimpleNamespace(
            db_session=session,
            ws_server=SimpleNamespace(refresh_can_list=lambda: None),
        )

        BaseApplication._del_entering_jar(app, {"jar": done_jar, "task": task}, done_jar.barcode)

        self.assertEqual(done_jar.status, "DONE")
        self.assertEqual(done_jar.position, "_")
        self.assertEqual(order.status, "PARTIAL")

    def test_delete_entering_jar_keeps_error_order_priority_with_mixed_jars(self):
        session = FakeCommitSession()
        task = FakeTask()
        order = FakeOrder()
        done_jar = FakeJar(status="DONE", position="A", barcode="100000000001", order=order)
        FakeJar(status="ERROR", position="B", barcode="100000000002", order=order)

        app = SimpleNamespace(
            db_session=session,
            ws_server=SimpleNamespace(refresh_can_list=lambda: None),
        )

        BaseApplication._del_entering_jar(app, {"jar": done_jar, "task": task}, done_jar.barcode)

        self.assertEqual(done_jar.status, "DONE")
        self.assertEqual(done_jar.position, "_")
        self.assertEqual(order.status, "ERROR")


if __name__ == "__main__":
    unittest.main()
