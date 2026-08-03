# coding: utf-8

"""Letture barcode valide, assenti dal DB, duplicate e spurie senza USB."""

import asyncio
import json
import os
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

import alfa_CR6_backend.base_application as app_module
from alfa_CR6_backend.base_application import BarCodeReader, BaseApplication
from alfa_CR6_backend.models import Jar, Order, compile_barcode, init_models


class _MainWindow:

    def __init__(self):
        self.alerts = []

    def open_alert_dialog(self, *args, **kwargs):
        self.alerts.append((args, kwargs))


class _Head:

    name = "A"

    def __init__(self):
        self.package_list = [{"name": "500 ml", "size": 500}]
        self.refresh_calls = 0

    async def get_stabilized_jar_size(self):
        return 0

    async def update_tintometer_data(self):
        self.refresh_calls += 1


class TestBarcodeReaderFiltering(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.readings = []
        self.exceptions = []

        async def handler(barcode):
            self.readings.append(barcode)
            return True

        self.reader = BarCodeReader(
            handler,
            identification_string="TEST",
            exception_handler=self.exceptions.append,
            manual_input=True,
        )

    def tearDown(self):
        self.loop.close()

    def _read(self, value):
        self.loop.run_until_complete(self.reader.manual_read(value))

    def test_known_valid_alfa_barcodes_reach_handler(self):
        valid = (
            "201027001001",
            "260802001001",
            "401231999999",
            "200229001001",  # leap day valido
        )

        for barcode in valid:
            with self.subTest(barcode=barcode):
                self._read(barcode)

        self.assertEqual(self.readings, list(valid))
        self.assertEqual(self.exceptions, [])

    def test_spurious_readings_are_discarded_without_exceptions(self):
        spurious = (
            None,
            260802001001,
            b"260802001001",
            "",
            "26080200100",       # corto
            "2608020010019",     # lungo: non va accettato per troncamento
            "26A802001001",      # prima causava ValueError su int(buffer[2])
            "26080200100A",
            " 260802001001",
            "260802001001 ",
            "abcdefghijkl",
            "１９０１０１００１００１",  # cifre Unicode, non input ASCII scanner
            "190101001001",      # anno fuori range
            "410101001001",      # anno fuori range
            "261301001001",      # mese impossibile
            "260231001001",      # giorno impossibile
            "210229001001",      # 2021 non bisestile
        )

        for barcode in spurious:
            with self.subTest(barcode=barcode):
                self._read(barcode)

        self.assertEqual(self.readings, [])
        self.assertEqual(self.exceptions, [])

    def test_duplicate_within_five_seconds_is_delivered_once(self):
        barcode = "260802001001"
        fake_time = mock.Mock(wraps=time)
        fake_time.time.side_effect = (100.0, 103.0)
        with mock.patch.object(app_module, "time", fake_time):
            self._read(barcode)
            self._read(barcode)

        self.assertEqual(self.readings, [barcode])

    def test_same_barcode_after_five_seconds_is_accepted_again(self):
        barcode = "260802001001"
        fake_time = mock.Mock(wraps=time)
        fake_time.time.side_effect = (100.0, 105.0)
        with mock.patch.object(app_module, "time", fake_time):
            self._read(barcode)
            self._read(barcode)

        self.assertEqual(self.readings, [barcode, barcode])

    def test_different_barcodes_are_not_deduplicated(self):
        fake_time = mock.Mock(wraps=time)
        fake_time.time.side_effect = (100.0, 100.1)
        with mock.patch.object(app_module, "time", fake_time):
            self._read("260802001001")
            self._read("260802001002")

        self.assertEqual(self.readings, ["260802001001", "260802001002"])

    def test_failed_handler_result_does_not_poison_retry(self):
        attempts = []

        async def not_found_handler(barcode):
            attempts.append(barcode)
            return False

        reader = BarCodeReader(
            not_found_handler, "TEST", manual_input=True
        )
        barcode = "260802009001"
        fake_time = mock.Mock(wraps=time)
        fake_time.time.side_effect = (100.0, 100.1)
        with mock.patch.object(app_module, "time", fake_time):
            self.loop.run_until_complete(reader.manual_read(barcode))
            self.loop.run_until_complete(reader.manual_read(barcode))

        self.assertEqual(attempts, [barcode, barcode])

    def test_usb_event_stream_rejects_overlong_read_instead_of_truncating_it(self):
        class FakeEvent:

            type = 1
            keystate = 0

            def __init__(self, keycode):
                self.keycode = keycode

        class FakeDevice:

            @staticmethod
            def grab():
                return None

            @staticmethod
            def __str__():
                return "device TEST_SCANNER"

            async def async_read_loop(self):
                streams = ("260802001001", "2608020010019")
                for value in streams:
                    for character in value:
                        yield FakeEvent("KEY_" + character)
                    yield FakeEvent("KEY_ENTER")

        device = FakeDevice()
        evdev_stub = types.SimpleNamespace(
            list_devices=lambda: ["event-test"],
            InputDevice=lambda _path: device,
            categorize=lambda event: event,
            ecodes=types.SimpleNamespace(EV_KEY=1),
        )

        with mock.patch.dict(sys.modules, {"evdev": evdev_stub}), \
                mock.patch.object(
                    app_module, "import_settings",
                    return_value=types.SimpleNamespace(MANUAL_BARCODE_INPUT=False),
                ):
            self.loop.run_until_complete(self.reader.run())

        self.assertEqual(self.readings, ["260802001001"])


class TestBarcodeDatabaseLookup(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(
            prefix="alfa_barcode_", suffix=".sqlite", dir="/tmp"
        )
        os.close(fd)
        os.unlink(self.db_path)
        self.session = init_models("sqlite:///" + self.db_path)

        date_prefix = int(time.strftime("%y%m%d"))
        self.order_nr = date_prefix * 1000000 + 1000
        order = Order(
            order_nr=self.order_nr,
            json_properties=json.dumps({"ingredients": []}),
            description="barcode test",
        )
        self.jar = Jar(order=order, index=1, size=0, json_properties="{}")
        self.session.add(order)
        self.session.add(self.jar)
        self.session.commit()
        self.valid_barcode = compile_barcode(self.order_nr, 1)

        self.head = _Head()
        self.app = BaseApplication.__new__(BaseApplication)
        self.app.db_session = self.session
        self.app.shuttle_size_from_barcode_scanner = False
        self.app.machine_head_dict = {0: self.head}
        self.app.main_window = _MainWindow()
        self.app.handle_exception = lambda exc: (_ for _ in ()).throw(exc)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()
        self.session.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _lookup(self, barcode):
        with mock.patch.object(
            app_module.asyncio, "sleep", new=mock.AsyncMock()
        ):
            return self.loop.run_until_complete(
                BaseApplication.get_and_check_jar_from_barcode(self.app, barcode)
            )

    def test_valid_reading_present_in_database_returns_jar(self):
        result = self._lookup(self.valid_barcode)

        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.jar.id)
        self.assertEqual(self.head.refresh_calls, 1)
        self.assertEqual(self.app.main_window.alerts, [])

    def test_valid_today_barcode_for_missing_order_is_reported_not_found(self):
        missing_order_barcode = compile_barcode(self.order_nr + 1000, 1)

        result = self._lookup(missing_order_barcode)

        self.assertIsNone(result)
        self.assertEqual(len(self.app.main_window.alerts), 1)
        args, kwargs = self.app.main_window.alerts[0]
        self.assertEqual(args[0], (missing_order_barcode,))
        self.assertIn("not found", kwargs["fmt"])
        self.assertEqual(kwargs["title"], "WARNING")

    def test_valid_today_barcode_for_missing_jar_index_is_not_found(self):
        missing_jar_barcode = compile_barcode(self.order_nr, 2)

        result = self._lookup(missing_jar_barcode)

        self.assertIsNone(result)
        self.assertEqual(len(self.app.main_window.alerts), 1)
        self.assertIn("not found", self.app.main_window.alerts[0][1]["fmt"])

    def test_spurious_read_never_reaches_database_lookup(self):
        calls = []

        async def lookup_handler(barcode):
            calls.append(barcode)
            return await BaseApplication.get_and_check_jar_from_barcode(
                self.app, barcode
            )

        reader = BarCodeReader(
            lookup_handler, "TEST", manual_input=True,
            exception_handler=self.app.handle_exception,
        )

        self.loop.run_until_complete(reader.manual_read("26A802001001"))

        self.assertEqual(calls, [])
        self.assertEqual(self.app.main_window.alerts, [])


if __name__ == "__main__":
    unittest.main()
