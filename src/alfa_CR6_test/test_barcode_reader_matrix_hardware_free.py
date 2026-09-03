# coding: utf-8

"""Matrice funzionale dei lettori Yoko e dell'inserimento manuale CRX."""

import asyncio
import json
import os
import sys
import threading
import time
import types
import unittest
from unittest import mock

import alfa_CR6_backend.base_application as app_module
from alfa_CR6_backend.base_application import BarCodeReader, BaseApplication
from alfa_CR6_backend.carousel_motor import CarouselMotor


VALID_FORMULA_BARCODE = "260802001001"
# Identificativi fisici rappresentativi: in produzione i due valori attesi
# arrivano dalla configurazione della singola macchina.
FORMULA_USB_PORT = "usb-0000:01:00.0-1.2.4"
SHUTTLE_USB_PORT = "usb-0000:01:00.0-1.2.5"


def _package(name, size, label_barcode):
    return {
        "name": name,
        "size": size,
        "json_info": json.dumps({"label_barcode": label_barcode}),
    }


class _UsbEvent:

    def __init__(self, keycode, event_type=1, keystate=0):
        self.type = event_type
        self.keycode = keycode
        self.keystate = keystate


def _scan_events(value):
    events = []
    special_keycodes = {
        " ": "KEY_SPACE",
        ",": "KEY_COMMA",
        ".": "KEY_DOT",
    }
    for character in value:
        keycode = special_keycodes.get(character, "KEY_" + character)
        events.append(_UsbEvent(keycode))
    events.append(_UsbEvent("KEY_ENTER"))
    return events


class _UsbDevice:

    def __init__(self, name, physical_port, events):
        self.name = name
        self.physical_port = physical_port
        self.events = list(events)
        self.grabbed = False

    def __str__(self):
        return 'device name "{}", phys "{}"'.format(
            self.name, self.physical_port
        )

    def grab(self):
        self.grabbed = True

    async def async_read_loop(self):
        for event in self.events:
            yield event


def _evdev_stub(devices):
    return types.SimpleNamespace(
        list_devices=lambda: list(devices),
        InputDevice=lambda path: devices[path],
        categorize=lambda event: event,
        ecodes=types.SimpleNamespace(EV_KEY=1),
    )


class TestYokoReaderConfiguration(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _run_configuration(self, env_data, settings=None):
        workers = []
        app = types.SimpleNamespace()
        app.settings = settings or types.SimpleNamespace()
        app.handle_exception = mock.Mock()
        app.on_barcode_read = mock.AsyncMock(name="formula_handler")
        app.on_shuttle_barcode_read = mock.AsyncMock(name="shuttle_handler")

        async def capture_worker(*args):
            workers.append(args)

        setattr(app, "_BaseApplication__barcode_reader_worker", capture_worker)
        create_task = BaseApplication._BaseApplication__create_barcode_task
        json_file = mock.mock_open(read_data=json.dumps(env_data))
        with mock.patch("builtins.open", json_file), mock.patch.dict(
                os.environ,
                {"BARCODE_READER_IDENTIFICATION_STRING": ""},
                clear=False):
            self.loop.run_until_complete(create_task(app))
        return app, workers

    def test_single_yoko_routes_only_formula_with_strict_alfa_validation(self):
        app, workers = self._run_configuration({
            "BARCODE_READER_IDENTIFICATION_STRING": "YOKO-FORMULA",
            "SHUTTLE_BARCODE_READER_IDENTIFICATION_STRING": "DISABLED",
        })

        self.assertEqual(workers, [
            ("YOKO-FORMULA", app.on_barcode_read, False, False),
        ])

    def test_dual_yoko_keeps_formula_and_shuttle_contracts_separate(self):
        app, workers = self._run_configuration({
            "BARCODE_READER_IDENTIFICATION_STRING": "YOKO-FORMULA",
            "SHUTTLE_BARCODE_READER_IDENTIFICATION_STRING": "YOKO-SHUTTLE",
        })

        self.assertEqual(workers, [
            ("YOKO-FORMULA", app.on_barcode_read, False, False),
            ("YOKO-SHUTTLE", app.on_shuttle_barcode_read, True, True),
        ])
        self.assertTrue(app.shuttle_bc_ready_to_read_a_barcode)

    def test_settings_fallback_configures_single_yoko(self):
        settings = types.SimpleNamespace(
            BARCODE_READER_IDENTIFICATION_STRING="YOKO-FROM-SETTINGS",
            SHUTTLE_BARCODE_READER_IDENTIFICATION_STRING="DISABLED",
        )
        workers = []
        app = types.SimpleNamespace(
            settings=settings,
            handle_exception=mock.Mock(),
            on_barcode_read=mock.AsyncMock(),
            on_shuttle_barcode_read=mock.AsyncMock(),
        )

        async def capture_worker(*args):
            workers.append(args)

        setattr(app, "_BaseApplication__barcode_reader_worker", capture_worker)
        with mock.patch("builtins.open", side_effect=OSError("missing file")), \
                mock.patch.dict(
                    os.environ,
                    {"BARCODE_READER_IDENTIFICATION_STRING": ""},
                    clear=False):
            self.loop.run_until_complete(
                BaseApplication._BaseApplication__create_barcode_task(app)
            )

        self.assertEqual(workers, [
            ("YOKO-FROM-SETTINGS", app.on_barcode_read, False, False),
        ])

    def test_two_yoko_usb_streams_are_selected_and_routed_independently(self):
        formula_reads = []
        shuttle_reads = []

        async def formula_handler(value):
            formula_reads.append(value)
            return True

        async def shuttle_handler(value):
            shuttle_reads.append(value)
            return True

        formula_reader = BarCodeReader(formula_handler, "YOKO-FORMULA")
        shuttle_reader = BarCodeReader(
            shuttle_handler,
            "YOKO-SHUTTLE",
            accept_any_len=True,
            skip_alfa_validation=True,
        )

        class FakeEvent:

            type = 1
            keystate = 0

            def __init__(self, keycode):
                self.keycode = keycode

        class FakeDevice:

            def __init__(self, name, value):
                self.name = name
                self.value = value
                self.grabbed = False

            def __str__(self):
                return "usb scanner " + self.name

            def grab(self):
                self.grabbed = True

            async def async_read_loop(self):
                for character in self.value:
                    keycode = "KEY_SPACE" if character == " " else "KEY_" + character
                    yield FakeEvent(keycode)
                yield FakeEvent("KEY_ENTER")

        devices = {
            "/dev/input/formula": FakeDevice("YOKO-FORMULA", VALID_FORMULA_BARCODE),
            "/dev/input/shuttle": FakeDevice("YOKO-SHUTTLE", "500 ML"),
        }
        evdev_stub = types.SimpleNamespace(
            list_devices=lambda: list(devices),
            InputDevice=lambda path: devices[path],
            categorize=lambda event: event,
            ecodes=types.SimpleNamespace(EV_KEY=1),
        )

        with mock.patch.dict(sys.modules, {"evdev": evdev_stub}), \
                mock.patch.object(
                    app_module,
                    "import_settings",
                    return_value=types.SimpleNamespace(MANUAL_BARCODE_INPUT=False),
                ):
            self.loop.run_until_complete(asyncio.gather(
                formula_reader.run(), shuttle_reader.run()
            ))

        self.assertEqual(formula_reads, [VALID_FORMULA_BARCODE])
        self.assertEqual(shuttle_reads, ["500 ML"])
        self.assertTrue(devices["/dev/input/formula"].grabbed)
        self.assertTrue(devices["/dev/input/shuttle"].grabbed)


class _PackageHead:

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def call_api_rest(self, *args):
        self.calls.append(args)
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _AlertWindow:

    def __init__(self):
        self.alerts = []
        self.barcode_updates = []

    def open_alert_dialog(self, *args, **kwargs):
        self.alerts.append((args, kwargs))

    def show_barcode(self, *args, **kwargs):
        self.barcode_updates.append((args, kwargs))


class TestYokoEnumerationAndNoise(unittest.TestCase):

    PACKAGES = {"objects": [_package(
        "Package name unrelated to its label",
        500,
        {"quantity": 500.0, "unit": "ML", "decimal_separator": "."},
    )]}

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _run_readers(self, readers, devices):
        with mock.patch.dict(sys.modules, {"evdev": _evdev_stub(devices)}), \
                mock.patch.object(
                    app_module,
                    "import_settings",
                    return_value=types.SimpleNamespace(MANUAL_BARCODE_INPUT=False),
                ):
            self.loop.run_until_complete(asyncio.gather(*(
                reader.run() for reader in readers
            )))

    def test_changed_event_number_is_accepted_when_physical_port_is_unchanged(self):
        reads = []

        async def handler(value):
            reads.append(value)
            return True

        device = _UsbDevice(
            "Yoko Formula", FORMULA_USB_PORT,
            _scan_events(VALID_FORMULA_BARCODE),
        )
        devices = {"/dev/input/event9": device}
        reader = BarCodeReader(handler, FORMULA_USB_PORT)

        self._run_readers([reader], devices)

        self.assertEqual(reads, [VALID_FORMULA_BARCODE])
        self.assertTrue(device.grabbed)

    def test_ean13_check_digit_is_stripped_before_validation(self):
        # Le etichette jar/pigmento sono stampate in EAN-13: la pistola
        # trasmette 13 cifre (le 12 del barcode Alfa piu' il check digit,
        # che per VALID_FORMULA_BARCODE vale 6) e l'eccedenza va scartata
        # sull'ENTER, prima della validazione a 12.
        reads = []

        async def handler(value):
            reads.append(value)
            return True

        device = _UsbDevice(
            "Yoko Formula", FORMULA_USB_PORT,
            _scan_events(VALID_FORMULA_BARCODE + "6"),
        )
        reader = BarCodeReader(handler, FORMULA_USB_PORT)

        self._run_readers([reader], {"/dev/input/event9": device})

        self.assertEqual(reads, [VALID_FORMULA_BARCODE])

    def test_reader_connected_to_another_physical_port_is_not_selected(self):
        handler = mock.AsyncMock(return_value=True)
        device = _UsbDevice(
            "Yoko Formula", "usb-0000:01:00.0-1.2.3",
            _scan_events(VALID_FORMULA_BARCODE),
        )
        reader = BarCodeReader(handler, FORMULA_USB_PORT)

        self._run_readers([reader], {"/dev/input/event0": device})

        handler.assert_not_awaited()
        self.assertFalse(device.grabbed)
        self.assertIsNone(reader._device)

    def test_missing_reader_produces_no_reading(self):
        handler = mock.AsyncMock(return_value=True)
        reader = BarCodeReader(handler, FORMULA_USB_PORT)

        self._run_readers([reader], {})

        handler.assert_not_awaited()
        self.assertIsNone(reader._device)

    def test_worker_recovers_when_missing_reader_appears_on_retry(self):
        reads = []
        enumerations = []
        sleep_calls = []
        device = _UsbDevice(
            "Yoko Formula", FORMULA_USB_PORT,
            _scan_events(VALID_FORMULA_BARCODE),
        )

        def list_devices():
            enumerations.append(True)
            return [] if len(enumerations) == 1 else ["/dev/input/event8"]

        evdev = _evdev_stub({"/dev/input/event8": device})
        evdev.list_devices = list_devices

        async def handler(value):
            reads.append(value)
            return True

        async def retry_without_real_wait(_seconds):
            sleep_calls.append(True)
            if len(sleep_calls) == 2:
                raise asyncio.CancelledError()

        app = types.SimpleNamespace(handle_exception=mock.Mock())
        worker = BaseApplication._BaseApplication__barcode_reader_worker
        with mock.patch.dict(sys.modules, {"evdev": evdev}), \
                mock.patch.object(
                    app_module,
                    "import_settings",
                    return_value=types.SimpleNamespace(MANUAL_BARCODE_INPUT=False),
                ), mock.patch.object(
                    app_module.asyncio, "sleep", retry_without_real_wait
                ):
            with self.assertRaises(asyncio.CancelledError):
                self.loop.run_until_complete(
                    worker(app, FORMULA_USB_PORT, handler)
                )

        self.assertEqual(len(enumerations), 2)
        self.assertEqual(reads, [VALID_FORMULA_BARCODE])
        self.assertTrue(device.grabbed)

    def test_unrecognized_usb_peripherals_are_not_grabbed(self):
        handler = mock.AsyncMock(return_value=True)
        touchscreen = _UsbDevice(
            "ILITEK-TP", "usb-0000:01:00.0-1.2.2.3/input0", []
        )
        keyboard = _UsbDevice(
            "NOVATEK Keyboard", "usb-0000:01:00.0-1.3.3/input0", []
        )
        devices = {
            "/dev/input/event1": touchscreen,
            "/dev/input/event4": keyboard,
        }
        reader = BarCodeReader(handler, FORMULA_USB_PORT)

        self._run_readers([reader], devices)

        handler.assert_not_awaited()
        self.assertFalse(touchscreen.grabbed)
        self.assertFalse(keyboard.grabbed)

    def test_dual_yoko_on_two_wrong_ports_routes_neither_reader(self):
        formula_handler = mock.AsyncMock(return_value=True)
        shuttle_handler = mock.AsyncMock(return_value=True)
        devices = {
            "/dev/input/event6": _UsbDevice(
                "Yoko Formula", "usb-0000:01:00.0-1.2.6",
                _scan_events(VALID_FORMULA_BARCODE),
            ),
            "/dev/input/event7": _UsbDevice(
                "Yoko Shuttle", "usb-0000:01:00.0-1.2.7",
                _scan_events("500 ML"),
            ),
        }
        readers = [
            BarCodeReader(formula_handler, FORMULA_USB_PORT),
            BarCodeReader(
                shuttle_handler, SHUTTLE_USB_PORT,
                accept_any_len=True, skip_alfa_validation=True,
            ),
        ]

        self._run_readers(readers, devices)

        formula_handler.assert_not_awaited()
        shuttle_handler.assert_not_awaited()
        self.assertFalse(any(device.grabbed for device in devices.values()))

    def test_random_characters_and_event_noise_do_not_corrupt_formula(self):
        reads = []

        async def handler(value):
            reads.append(value)
            return True

        events = []
        events.extend(_scan_events("26X802001001"))  # lettera casuale nel codice
        events.extend(_scan_events(VALID_FORMULA_BARCODE + "9"))
        events.extend(_scan_events("260802"))         # lettura frammentata
        events.extend([
            _UsbEvent("KEY_Z", event_type=4),         # evento non tastiera
            _UsbEvent("KEY_Q", keystate=1),          # key-down, non key-up
            _UsbEvent("KEY_F13"),                     # tasto non mappato
        ])
        events.extend(_scan_events(VALID_FORMULA_BARCODE))
        device = _UsbDevice("Yoko Formula", FORMULA_USB_PORT, events)
        reader = BarCodeReader(handler, FORMULA_USB_PORT)

        self._run_readers([reader], {"/dev/input/event3": device})

        self.assertEqual(reads, [VALID_FORMULA_BARCODE])

    def test_shuttle_reader_preserves_comma_and_point_decimal_separators(self):
        reads = []

        async def handler(value):
            reads.append(value)
            return True

        events = (
            _scan_events("0,4 L")
            + _scan_events("0.75 L")
            + _scan_events("123456,789 ML")
            + _scan_events("12,25 FL OZ")
            + _scan_events("12.25 FL OZ")
            + _scan_events("8,5 OZ")
            + _scan_events("8.5 OZ")
        )
        device = _UsbDevice("Yoko Shuttle", SHUTTLE_USB_PORT, events)
        reader = BarCodeReader(
            handler, SHUTTLE_USB_PORT,
            accept_any_len=True, skip_alfa_validation=True,
        )

        self._run_readers([reader], {"/dev/input/event5": device})

        self.assertEqual(reads, [
            "0,4 L", "0.75 L", "123456,789 ML",
            "12,25 FL OZ", "12.25 FL OZ",
            "8,5 OZ", "8.5 OZ",
        ])

    def test_random_shuttle_text_is_discarded_before_package_lookup(self):
        head = _PackageHead([self.PACKAGES])
        window = _AlertWindow()
        app = types.SimpleNamespace(
            shuttle_bc_ready_to_read_a_barcode=True,
            shuttle_size_from_barcode_scanner=500,
            _shuttle_size_ready_evt=asyncio.Event(),
            get_machine_head_by_letter=lambda _letter: head,
            main_window=window,
            handle_exception=lambda exc: (_ for _ in ()).throw(exc),
        )
        app._shuttle_size_ready_evt.set()

        async def shuttle_handler(value):
            return await BaseApplication.on_shuttle_barcode_read(app, value)

        device = _UsbDevice(
            "Yoko Shuttle", SHUTTLE_USB_PORT, _scan_events("R4ND0M")
        )
        reader = BarCodeReader(
            shuttle_handler, SHUTTLE_USB_PORT,
            accept_any_len=True, skip_alfa_validation=True,
        )

        with mock.patch.dict(os.environ, {"MACHINE_VARIANT": "CR6"}):
            self._run_readers([reader], {"/dev/input/event5": device})

        self.assertEqual(head.calls, [])
        self.assertEqual(window.alerts, [])
        self.assertEqual(app.shuttle_size_from_barcode_scanner, 500)
        self.assertTrue(app._shuttle_size_ready_evt.is_set())

    def test_swapped_formula_and_shuttle_inputs_fail_closed(self):
        formula_reads = []
        head = _PackageHead([self.PACKAGES])
        window = _AlertWindow()
        app = types.SimpleNamespace(
            shuttle_bc_ready_to_read_a_barcode=True,
            shuttle_size_from_barcode_scanner=False,
            _shuttle_size_ready_evt=asyncio.Event(),
            get_machine_head_by_letter=lambda _letter: head,
            main_window=window,
            handle_exception=lambda exc: (_ for _ in ()).throw(exc),
        )

        async def formula_handler(value):
            formula_reads.append(value)
            return True

        async def shuttle_handler(value):
            return await BaseApplication.on_shuttle_barcode_read(app, value)

        # Le porte sono quelle battezzate, ma ricevono la simbologia destinata
        # all'altro ruolo: il software identifica la porta, non il corpo fisico.
        devices = {
            "/dev/input/event0": _UsbDevice(
                "Yoko", FORMULA_USB_PORT, _scan_events("500 ML")
            ),
            "/dev/input/event1": _UsbDevice(
                "Yoko", SHUTTLE_USB_PORT,
                _scan_events(VALID_FORMULA_BARCODE),
            ),
        }
        readers = [
            BarCodeReader(formula_handler, FORMULA_USB_PORT),
            BarCodeReader(
                shuttle_handler, SHUTTLE_USB_PORT,
                accept_any_len=True, skip_alfa_validation=True,
            ),
        ]

        with mock.patch.dict(os.environ, {"MACHINE_VARIANT": "CR6"}):
            self._run_readers(readers, devices)

        self.assertEqual(formula_reads, [])
        self.assertFalse(app.shuttle_size_from_barcode_scanner)
        self.assertEqual(head.calls, [])
        self.assertEqual(window.alerts, [])


class TestDualYokoShuttleLookup(unittest.TestCase):

    PACKAGES = {
        "objects": [
            _package(
                "Customer package 500",
                500,
                {
                    "quantity": 500.0,
                    "unit": "ML",
                    "decimal_separator": ".",
                },
            ),
            _package(
                "Customer package one litre",
                1000,
                {
                    "quantity": 1.0,
                    "unit": "L",
                    "decimal_separator": ".",
                },
            ),
        ]
    }

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.head = _PackageHead([self.PACKAGES])
        self.window = _AlertWindow()
        self.app = types.SimpleNamespace(
            shuttle_bc_ready_to_read_a_barcode=True,
            shuttle_size_from_barcode_scanner=False,
            _shuttle_size_ready_evt=asyncio.Event(),
            get_machine_head_by_letter=lambda _letter: self.head,
            main_window=self.window,
            handle_exception=lambda exc: (_ for _ in ()).throw(exc),
        )

    def tearDown(self):
        self.loop.close()

    def _read(self, value, times=None):
        patcher = mock.patch.object(app_module.time, "time", side_effect=times) \
            if times else mock.patch.object(app_module.time, "time", wraps=time.time)
        with patcher, mock.patch.dict(os.environ, {"MACHINE_VARIANT": "CR6"}):
            return self.loop.run_until_complete(
                BaseApplication.on_shuttle_barcode_read(self.app, value)
            )

    def test_known_shuttle_is_normalized_and_sets_size_ready_event(self):
        self._read("  500 ML  ")

        self.assertEqual(self.app.shuttle_size_from_barcode_scanner, 500)
        self.assertTrue(self.app._shuttle_size_ready_evt.is_set())
        self.assertFalse(self.app.shuttle_bc_ready_to_read_a_barcode)
        self.assertEqual(
            self.head.calls,
            [("apiV1/package", "GET", {}, 1.5)],
        )
        self.assertEqual(self.window.alerts, [])

    def test_shuttle_reader_is_ignored_during_refill(self):
        self.app.barcode_read_blocked_on_refill = True

        self.assertIsNone(self._read("500 ML"))
        self.assertEqual(self.head.calls, [])
        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)
        self.assertFalse(self.app._shuttle_size_ready_evt.is_set())

    def test_unknown_shuttle_clears_size_and_requires_dialog_acknowledgement(self):
        self.app.shuttle_size_from_barcode_scanner = 500
        self.app._shuttle_size_ready_evt.set()

        self._read("750 ml")

        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)
        self.assertFalse(self.app._shuttle_size_ready_evt.is_set())
        self.assertFalse(self.app.shuttle_bc_ready_to_read_a_barcode)
        self.assertEqual(len(self.window.alerts), 1)
        _args, kwargs = self.window.alerts[0]
        self.assertEqual(kwargs["fmt"], "UNKNOWN SHUTTLE: {}")
        kwargs["callback"]()
        self.assertTrue(self.app.shuttle_bc_ready_to_read_a_barcode)

    def test_duplicate_generated_label_fails_explicitly(self):
        duplicate = _package(
            "Another package with the same label",
            750,
            {
                "quantity": 500.0,
                "unit": "ML",
                "decimal_separator": ".",
            },
        )
        self.head = _PackageHead([{
            "objects": self.PACKAGES["objects"] + [duplicate],
        }])

        self._read("500 ML")

        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)
        self.assertFalse(self.app._shuttle_size_ready_evt.is_set())
        self.assertEqual(len(self.window.alerts), 1)
        _args, kwargs = self.window.alerts[0]
        self.assertEqual(
            kwargs["fmt"], "AMBIGUOUS SHUTTLE BARCODE: {}")
        self.assertEqual(kwargs["title"], "ERROR")

    def test_unavailable_package_api_clears_stale_size(self):
        self.head = _PackageHead([None])
        self.app.shuttle_size_from_barcode_scanner = 500
        self.app._shuttle_size_ready_evt.set()

        self._read("500 ml")

        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)
        self.assertFalse(self.app._shuttle_size_ready_evt.is_set())

    def test_package_api_exception_clears_stale_size(self):
        self.head = _PackageHead([RuntimeError("head offline")])
        self.app.shuttle_size_from_barcode_scanner = 500
        self.app._shuttle_size_ready_evt.set()

        self._read("500 ml")

        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)
        self.assertFalse(self.app._shuttle_size_ready_evt.is_set())

    def test_retry_one_second_after_empty_rest_response_can_succeed(self):
        self.head = _PackageHead([None, self.PACKAGES])
        fake_time = mock.Mock(wraps=time)
        fake_time.time.side_effect = (100.0, 101.0)

        with mock.patch.object(app_module, "time", fake_time), \
                mock.patch.dict(os.environ, {"MACHINE_VARIANT": "CR6"}):
            self.loop.run_until_complete(
                BaseApplication.on_shuttle_barcode_read(self.app, "500 ml")
            )
            self.loop.run_until_complete(
                BaseApplication.on_shuttle_barcode_read(self.app, "500 ml")
            )

        self.assertEqual(len(self.head.calls), 2)
        self.assertEqual(self.app.shuttle_size_from_barcode_scanner, 500)
        self.assertTrue(self.app._shuttle_size_ready_evt.is_set())

    def test_retry_one_second_after_rest_exception_can_succeed(self):
        self.head = _PackageHead([
            RuntimeError("head offline"), self.PACKAGES,
        ])
        fake_time = mock.Mock(wraps=time)
        fake_time.time.side_effect = (100.0, 101.0)

        with mock.patch.object(app_module, "time", fake_time), \
                mock.patch.dict(os.environ, {"MACHINE_VARIANT": "CR6"}):
            self.loop.run_until_complete(
                BaseApplication.on_shuttle_barcode_read(self.app, "500 ml")
            )
            self.loop.run_until_complete(
                BaseApplication.on_shuttle_barcode_read(self.app, "500 ml")
            )

        self.assertEqual(len(self.head.calls), 2)
        self.assertEqual(self.app.shuttle_size_from_barcode_scanner, 500)
        self.assertTrue(self.app._shuttle_size_ready_evt.is_set())

    def test_valid_shuttle_read_blocks_repeats_until_next_cycle(self):
        with mock.patch.dict(os.environ, {"MACHINE_VARIANT": "CR6"}):
            self.loop.run_until_complete(
                BaseApplication.on_shuttle_barcode_read(self.app, "500 ML")
            )
            self.loop.run_until_complete(
                BaseApplication.on_shuttle_barcode_read(self.app, " 500 ml ")
            )

        self.assertEqual(len(self.head.calls), 1)

    def test_physical_shuttle_reader_is_ignored_on_crx_variants(self):
        for variant in ("CRX40", "CRX60", "CRX80"):
            with self.subTest(variant=variant), mock.patch.dict(
                    os.environ, {"MACHINE_VARIANT": variant}):
                self.loop.run_until_complete(
                    BaseApplication.on_shuttle_barcode_read(self.app, "500 ml")
                )

        self.assertEqual(self.head.calls, [])
        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)


class TestDualYokoFormulaSynchronization(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.window = _AlertWindow()
        self.app = BaseApplication.__new__(BaseApplication)
        self.app.machine_variant = "CR6"
        self.app.id_bc_shuttle = "YOKO-SHUTTLE"
        self.app.shuttle_bc_ready_to_read_a_barcode = True
        self.app.ready_to_read_a_barcode = False
        self.app.shuttle_size_from_barcode_scanner = False
        self.app._shuttle_size_ready_evt = asyncio.Event()
        self.app.main_window = self.window

    def tearDown(self):
        self.loop.close()

    def _consume(self):
        return BaseApplication._consume_shuttle_size_for_formula(
            self.app, VALID_FORMULA_BARCODE)

    def test_formula_waits_for_slightly_later_shuttle_reading(self):
        async def scan_shuttle_after_formula():
            await asyncio.sleep(0)
            self.app.shuttle_size_from_barcode_scanner = 650
            self.app._shuttle_size_ready_evt.set()

        async def run_pair():
            scan_task = asyncio.create_task(scan_shuttle_after_formula())
            size = await self._consume()
            await scan_task
            return size

        with mock.patch.object(
                app_module, "SHUTTLE_BARCODE_WAIT_TIMEOUT", 0.05):
            size = self.loop.run_until_complete(run_pair())

        self.assertEqual(size, 650)
        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)
        self.assertFalse(self.app._shuttle_size_ready_evt.is_set())
        self.assertFalse(self.app.shuttle_bc_ready_to_read_a_barcode)
        self.assertEqual(self.window.alerts, [])

    def test_formula_without_shuttle_fails_closed_and_rearms_after_ack(self):
        with mock.patch.object(
                app_module, "SHUTTLE_BARCODE_WAIT_TIMEOUT", 0.001):
            size = self.loop.run_until_complete(self._consume())

        self.assertIsNone(size)
        self.assertFalse(self.app.ready_to_read_a_barcode)
        self.assertFalse(self.app.shuttle_bc_ready_to_read_a_barcode)
        self.assertEqual(len(self.window.alerts), 1)
        _args, kwargs = self.window.alerts[0]
        self.assertEqual(kwargs["title"], "ERROR SHUTTLE BARCODE")
        self.assertEqual(kwargs["fmt"], "SHUTTLE BARCODE NOT READ")

        kwargs["callback"]()

        self.assertTrue(self.app.ready_to_read_a_barcode)
        self.assertTrue(self.app.shuttle_bc_ready_to_read_a_barcode)

    def test_input_release_clears_stale_size_and_rearms_shuttle_reader(self):
        self.app.shuttle_size_from_barcode_scanner = 500
        self.app._shuttle_size_ready_evt.set()
        self.app.shuttle_bc_ready_to_read_a_barcode = False

        BaseApplication._reset_shuttle_barcode_cycle(self.app)

        self.assertFalse(self.app.shuttle_size_from_barcode_scanner)
        self.assertFalse(self.app._shuttle_size_ready_evt.is_set())
        self.assertTrue(self.app.shuttle_bc_ready_to_read_a_barcode)

    def test_order_barcode_passes_later_shuttle_size_to_jar_task(self):
        head = types.SimpleNamespace(
            wait_for_jar_photocells_and_status_lev=mock.AsyncMock(
                return_value=True),
        )
        app = BaseApplication.__new__(BaseApplication)
        app.machine_variant = "CR6"
        app.in_docker = True
        app.id_bc_shuttle = "YOKO-SHUTTLE"
        app.shuttle_bc_ready_to_read_a_barcode = True
        app.ready_to_read_a_barcode = True
        app.shuttle_size_from_barcode_scanner = False
        app._shuttle_size_ready_evt = asyncio.Event()
        app._crx_ja_block_sequence_active = False
        app.barcode_read_blocked_on_refill = False
        app.carousel_frozen = False
        app.main_window = self.window
        app.get_machine_head_by_letter = lambda _letter: head
        app._database_cleanup_cancel_event = threading.Event()
        app._BaseApplication__jar_runners = {}
        app._BaseApplication__jar_task = mock.AsyncMock(return_value=None)
        app.handle_exception = lambda exc: (_ for _ in ()).throw(exc)

        async def scan_shuttle_after_formula():
            await asyncio.sleep(0)
            app.shuttle_size_from_barcode_scanner = 650
            app._shuttle_size_ready_evt.set()

        async def run_pair():
            scan_task = asyncio.create_task(scan_shuttle_after_formula())
            result = await BaseApplication.on_barcode_read(
                app, VALID_FORMULA_BARCODE)
            await scan_task
            await asyncio.sleep(0)
            return result

        with mock.patch.object(
                app_module, "SHUTTLE_BARCODE_WAIT_TIMEOUT", 0.05):
            result = self.loop.run_until_complete(run_pair())

        self.assertEqual(result, VALID_FORMULA_BARCODE)
        app._BaseApplication__jar_task.assert_awaited_once_with(
            VALID_FORMULA_BARCODE, shuttle_size=650)
        self.assertFalse(app.shuttle_size_from_barcode_scanner)
        self.assertFalse(app.shuttle_bc_ready_to_read_a_barcode)


class _ManualInputDialog:

    content = ""

    def get_content_text(self):
        return self.content


class _ManualWindow(_AlertWindow):

    def __init__(self, inputs):
        super().__init__()
        self.inputs = list(inputs)
        self.input_dialog = _ManualInputDialog()
        self.prompts = []
        self.hidden_count = 0

    def open_input_dialog(self, **kwargs):
        self.prompts.append(kwargs["message"])
        self.input_dialog.content = self.inputs.pop(0)
        kwargs["ok_cb"]()

    def hide_input_dialog(self):
        self.hidden_count += 1


class TestCrxManualBarcodeFlow(unittest.TestCase):

    PACKAGES = {"objects": [_package(
        "Package name unrelated to its label",
        500,
        {"quantity": 500.0, "unit": "ML", "decimal_separator": "."},
    )]}

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _run_flow(self, inputs, outcomes=None, handler_result=True):
        window = _ManualWindow(inputs)
        head = _PackageHead(outcomes or [self.PACKAGES])
        handler = mock.AsyncMock(return_value=handler_result)
        app = types.SimpleNamespace(
            main_window=window,
            get_machine_head_by_letter=lambda _letter: head,
            shuttle_size_from_barcode_scanner=False,
            ready_to_read_a_barcode=False,
            on_barcode_read=handler,
        )
        self.loop.run_until_complete(
            BaseApplication._handle_crx_barcode_input(app)
        )
        return app, window, head, handler

    def test_valid_manual_shuttle_then_formula_reaches_order_handler(self):
        app, window, _head, handler = self._run_flow([
            " 500 ML ", "26 08 02 001 001",
        ])

        self.assertEqual(app.shuttle_size_from_barcode_scanner, 500)
        self.assertEqual(handler.await_args_list, [mock.call(VALID_FORMULA_BARCODE)])
        self.assertTrue(app.ready_to_read_a_barcode)
        self.assertEqual(window.alerts, [])

    def test_invalid_and_unknown_shuttles_are_retried_before_formula(self):
        app, window, head, handler = self._run_flow([
            "noise", "750 ml", "500 ml", VALID_FORMULA_BARCODE,
        ])

        self.assertEqual(app.shuttle_size_from_barcode_scanner, 500)
        self.assertEqual(len(window.alerts), 2)
        self.assertEqual(len(head.calls), 2)  # "noise" viene scartato prima della REST
        handler.assert_awaited_once_with(VALID_FORMULA_BARCODE)

    def test_api_exception_is_reported_and_manual_shuttle_can_be_retried(self):
        app, window, head, handler = self._run_flow(
            ["500 ml", "500 ml", VALID_FORMULA_BARCODE],
            outcomes=[RuntimeError("head offline"), self.PACKAGES],
        )

        self.assertEqual(app.shuttle_size_from_barcode_scanner, 500)
        self.assertEqual(len(window.alerts), 1)
        self.assertEqual(len(head.calls), 2)
        handler.assert_awaited_once_with(VALID_FORMULA_BARCODE)

    def test_ambiguous_manual_shuttle_is_retried(self):
        duplicate_packages = {"objects": [
            self.PACKAGES["objects"][0],
            _package(
                "Duplicate label",
                750,
                {
                    "quantity": 500.0,
                    "unit": "ML",
                    "decimal_separator": ".",
                },
            ),
        ]}

        _app, window, _head, handler = self._run_flow(
            ["500 ML", "500 ML", VALID_FORMULA_BARCODE],
            outcomes=[duplicate_packages, self.PACKAGES],
        )

        self.assertEqual(len(window.alerts), 1)
        _args, kwargs = window.alerts[0]
        self.assertEqual(
            kwargs["fmt"], "AMBIGUOUS SHUTTLE BARCODE: {}")
        handler.assert_awaited_once_with(VALID_FORMULA_BARCODE)

    def test_spurious_overlong_and_impossible_date_formulae_are_retried(self):
        _app, window, _head, handler = self._run_flow([
            "500 ml",
            VALID_FORMULA_BARCODE + "9",
            "260231001001",
            "ABC",
            VALID_FORMULA_BARCODE,
        ])

        self.assertEqual(len(window.alerts), 3)
        handler.assert_awaited_once_with(VALID_FORMULA_BARCODE)
        rejected = [call_args[0][0] for call_args, _kwargs in window.alerts]
        self.assertEqual(rejected, [
            VALID_FORMULA_BARCODE + "9", "260231001001", "ABC",
        ])

    def test_failed_order_handler_restores_ready_state_for_a_retry(self):
        app, _window, _head, handler = self._run_flow(
            ["500 ml", VALID_FORMULA_BARCODE], handler_result=False
        )

        handler.assert_awaited_once_with(VALID_FORMULA_BARCODE)
        self.assertTrue(app.ready_to_read_a_barcode)

    def test_all_crx_variants_trigger_manual_flow_when_jar_reaches_input(self):
        for variant in ("CRX40", "CRX60", "CRX80"):
            with self.subTest(variant=variant):
                head = types.SimpleNamespace(
                    status={"crx_outputs_status": 0},
                    jar_photocells_status={"JAR_INPUT_ROLLER_PHOTOCELL": True},
                )
                app = types.SimpleNamespace(
                    in_docker=True,
                    machine_variant=variant,
                    get_machine_head_by_letter=lambda _letter: head,
                    _handle_crx_barcode_input=mock.AsyncMock(),
                )

                result = self.loop.run_until_complete(
                    CarouselMotor.move_00_01(app, silent=True)
                )

                self.assertFalse(result)
                app._handle_crx_barcode_input.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main()
