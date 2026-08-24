# coding: utf-8

"""Logica testa CR6 provata senza REST server, websocket, pompe o sensori."""

import asyncio
import json
import tempfile
import types
import unittest
from unittest import mock

import alfa_CR6_backend.machine_head as machine_head_module


class _MainWindow:

    def __init__(self):
        self.alerts = []

    def open_alert_dialog(self, *args, **kwargs):
        self.alerts.append((args, kwargs))


class _FakeApp:

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {0: "A"}

    def __init__(self, tmp_path):
        self.settings = types.SimpleNamespace(TMP_PATH=tmp_path)
        self.main_window = _MainWindow()
        self.reserve_updates = []
        self.exceptions = []

    def show_reserve(self, index, enabled):
        self.reserve_updates.append((index, enabled))

    def handle_exception(self, exc):
        self.exceptions.append(exc)

    async def wait_for_condition(self, condition, **_kwargs):
        return bool(condition())


class TestMachineHeadHardwareFree(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = _FakeApp(self.temp_dir.name)
        self.app_patch = mock.patch.object(
            machine_head_module, "get_application_instance", return_value=self.app
        )
        self.app_patch.start()
        self.head = machine_head_module.MachineHead(
            0, "127.0.0.1", 11001, 8081
        )
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()
        self.app_patch.stop()
        self.temp_dir.cleanup()

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    def test_effective_specific_weight_and_available_quantity(self):
        self.head.pigment_list = [{
            "name": "RED",
            "specific_weight": 1.5,
            "pipes": [
                {
                    "enabled": True, "effective_specific_weight": 2.0,
                    "current_level": 8.0, "minimum_level": 3.0,
                },
                {
                    "enabled": False, "effective_specific_weight": 9.0,
                    "current_level": 100.0, "minimum_level": 0.0,
                },
            ],
        }]

        self.assertEqual(self.head.get_specific_weight("RED"), 2.0)
        self.assertEqual(self.head.get_available_weight("RED"), 10.0)
        self.assertEqual(self.head.get_specific_weight("UNKNOWN"), -1.0)
        self.assertEqual(self.head.get_available_weight("UNKNOWN"), 0)

    def test_dispense_split_separates_bases_from_colorants(self):
        self.head.pigment_list = [
            {"name": "BASE", "type": "base"},
            {"name": "RED", "type": "colorant"},
            {"name": "ADDITIVE", "type": "additive"},
        ]
        params = {
            "package_name": "P1",
            "ingredients": {"BASE": 10, "RED": 2, "ADDITIVE": 1},
        }

        first_step = self.head.get_splitted_dispense_params(params, step=0)
        second_step = self.head.get_splitted_dispense_params(params, step=1)

        self.assertEqual(first_step["ingredients"], {"BASE": 10, "ADDITIVE": 1})
        self.assertEqual(second_step["ingredients"], {"RED": 2})
        self.assertEqual(
            params["ingredients"], {"BASE": 10, "RED": 2, "ADDITIVE": 1}
        )

    def test_cancellation_during_dispense_waits_for_safe_standby(self):
        self.head.pigment_list = [{
            "name": "RED",
            "type": "colorant",
            "specific_weight": 1.0,
            "pipes": [{
                "name": "C01",
                "enabled": True,
                "effective_specific_weight": 1.0,
            }],
        }]
        self.head.status = {
            "status_level": "STANDBY",
            "container_presence": True,
        }
        self.head.jar_photocells_status = {
            "JAR_DISPENSING_POSITION_PHOTOCELL": True,
        }
        self.head.call_api_rest = mock.AsyncMock(return_value={
            "result": "OK",
            "pipe_formula": {"RED": 1.0},
        })
        self.head.send_command = mock.AsyncMock(return_value=True)
        self.app.update_jar_properties = mock.Mock()

        jar = types.SimpleNamespace(
            barcode="260803001001",
            order=types.SimpleNamespace(description=""),
            json_properties=json.dumps({}),
            get_ingredients_for_machine=mock.Mock(
                return_value={"RED": 1.0}
            ),
            get_not_dispensed_ingredients=mock.Mock(return_value={}),
            update_live=mock.Mock(),
        )
        runner = {"running_engaged_circuits": []}
        self.app._BaseApplication__jar_runners = {jar.barcode: runner}

        dispensing_wait_started = asyncio.Event()
        standby_waits = []

        async def wait_for_status(levels, **_kwargs):
            if levels == ["DISPENSING"]:
                self.head.status["status_level"] = "DISPENSING"
                return True
            self.assertEqual(levels, ["STANDBY"])
            standby_waits.append(True)
            if len(standby_waits) == 1:
                dispensing_wait_started.set()
                await asyncio.Future()
            self.head.status["status_level"] = "STANDBY"
            return True

        self.head.wait_for_status_level = wait_for_status

        async def cancel_while_dispensing():
            task = asyncio.create_task(self.head.do_dispense(jar))
            await dispensing_wait_started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self._run(cancel_while_dispensing())

        self.assertEqual(len(standby_waits), 2)
        self.assertEqual(self.head.status["status_level"], "STANDBY")
        self.assertIsNone(runner["running_engaged_circuits"])

    def test_tintometer_refresh_filters_disabled_pipes_and_reports_reserve(self):
        pigments = [{
            "name": "RED",
            "specific_weight": 1.1,
            "pipes": [
                {
                    "name": "C01", "enabled": True, "sync": True,
                    "current_level": 5, "reserve_level": 5,
                },
                {
                    "name": "C02", "enabled": False, "sync": True,
                    "current_level": 100, "reserve_level": 1,
                },
            ],
        }, {
            "name": "UNSYNCED",
            "specific_weight": 1.0,
            "pipes": [{
                "name": "C03", "enabled": True, "sync": False,
                "current_level": 100, "reserve_level": 1,
            }],
        }]
        packages = [{"name": "SMALL", "size": 500}]

        async def fake_rest(path, _method, _data, **_kwargs):
            if path == "apiV1/config":
                return {"objects": []}
            if path == "apiV1/pigment":
                return {"objects": pigments}
            if path == "apiV1/package":
                return {"objects": packages}
            self.fail(path)

        self.head.call_api_rest = fake_rest

        self._run(self.head.update_tintometer_data(silent=False))

        self.assertEqual([p["name"] for p in self.head.pigment_list], ["RED"])
        self.assertEqual(self.head.low_level_pipes, [("C01", "RED")])
        self.assertEqual(self.head.package_list, packages)
        self.assertEqual(self.app.reserve_updates, [(0, True)])
        self.assertEqual(len(self.app.main_window.alerts), 1)

    def test_output_command_updates_watchdog_and_unlocks_channel(self):
        sent = []
        self.head.status = {"crx_outputs_status": 0}

        async def send_command(name, params):
            sent.append((name, params))
            mask = 1 << params["Output_Number"]
            if params["Output_Action"]:
                self.head.status["crx_outputs_status"] |= mask
            else:
                self.head.status["crx_outputs_status"] &= ~mask
            return True

        self.head.send_command = send_command

        started = self._run(
            self.head.crx_outputs_management(2, 4, timeout=12)
        )
        stopped = self._run(
            self.head.crx_outputs_management(2, 0, timeout=12)
        )

        self.assertTrue(started)
        self.assertTrue(stopped)
        self.assertEqual(sent, [
            ("CRX_OUTPUTS_MANAGEMENT", {"Output_Number": 2, "Output_Action": 4}),
            ("CRX_OUTPUTS_MANAGEMENT", {"Output_Number": 2, "Output_Action": 0}),
        ])
        inner = self.head._MachineHead__crx_inner_status[2]
        self.assertEqual(inner["value"], 0)
        self.assertEqual(inner["timeout"], 0)
        self.assertEqual(inner["t0"], 0)
        self.assertFalse(inner["locked"])

    def test_unconfirmed_stop_preserves_watchdog_state_for_retry(self):
        self.head.status = {"crx_outputs_status": 0x04}
        inner = self.head._MachineHead__crx_inner_status[2]
        inner.update({"value": 4, "timeout": 5, "t0": 100})
        self.head.send_command = mock.AsyncMock(return_value=None)

        stopped = self._run(
            self.head.crx_outputs_management(2, 0, timeout=0)
        )

        self.assertFalse(stopped)
        self.assertEqual(inner["value"], 4)
        self.assertEqual(inner["timeout"], 5)
        self.assertEqual(inner["t0"], 100)
        self.assertFalse(inner["locked"])

    def test_output_telemetry_clears_watchdog_only_on_off_state(self):
        status = {
            "status_level": "JAR_POSITIONING",
            "photocells_status": 0,
            "jar_photocells_status": 0,
            "crx_outputs_status": 0x04,
        }
        self.head.status = dict(status, crx_outputs_status=0)
        inner = self.head._MachineHead__crx_inner_status[2]
        inner.update({"value": 4, "timeout": 5, "t0": 100})

        self._run(self.head.update_status(dict(status)))

        self.assertEqual(inner["value"], 4)
        self.assertEqual(inner["timeout"], 5)
        self.assertEqual(inner["t0"], 100)

        self._run(self.head.update_status(
            dict(status, crx_outputs_status=0)
        ))

        self.assertEqual(inner["value"], 0)
        self.assertEqual(inner["timeout"], 0)
        self.assertEqual(inner["t0"], 0)

    def test_head_a_input_release_rearms_formula_and_shuttle_cycle(self):
        status = {
            "status_level": "JAR_POSITIONING",
            "photocells_status": 0,
            "jar_photocells_status": 0,
            "crx_outputs_status": 0,
        }
        self.head.status = dict(status, jar_photocells_status=1)
        self.app.ready_to_read_a_barcode = False
        self.app._reset_shuttle_barcode_cycle = mock.Mock()

        self._run(self.head.update_status(status))

        self.assertTrue(self.app.ready_to_read_a_barcode)
        self.app._reset_shuttle_barcode_cycle.assert_called_once_with()

    def test_watchdog_stops_an_output_after_its_timeout(self):
        inner_status = self.head._MachineHead__crx_inner_status
        inner_status[2].update({"value": 4, "timeout": 5, "t0": 100})
        self.head.crx_outputs_management = mock.AsyncMock()
        sleep_calls = []

        async def run_one_watchdog_cycle(_seconds):
            sleep_calls.append(True)
            if len(sleep_calls) > 1:
                raise asyncio.CancelledError()

        with mock.patch.object(
                machine_head_module.asyncio, "sleep", run_one_watchdog_cycle
        ), mock.patch.object(machine_head_module.time, "time", return_value=106):
            with self.assertRaises(asyncio.CancelledError):
                self._run(self.head._MachineHead__watch_dog_task())

        self.head.crx_outputs_management.assert_awaited_once_with(
            2, 0, timeout=0
        )

    def test_watchdog_ignores_outputs_without_an_expired_timer(self):
        inner_status = self.head._MachineHead__crx_inner_status
        inner_status[0].update({"value": 4, "timeout": 0, "t0": 90})
        inner_status[1].update({"value": 4, "timeout": 20, "t0": 100})
        self.head.crx_outputs_management = mock.AsyncMock()
        sleep_calls = []

        async def run_one_watchdog_cycle(_seconds):
            sleep_calls.append(True)
            if len(sleep_calls) > 1:
                raise asyncio.CancelledError()

        with mock.patch.object(
                machine_head_module.asyncio, "sleep", run_one_watchdog_cycle
        ), mock.patch.object(machine_head_module.time, "time", return_value=110):
            with self.assertRaises(asyncio.CancelledError):
                self._run(self.head._MachineHead__watch_dog_task())

        self.head.crx_outputs_management.assert_not_awaited()

    def test_active_output_rejects_second_start_command(self):
        sent = []
        self.head.status = {"crx_outputs_status": 0x02}

        async def send_command(name, params):
            sent.append((name, params))
            return True

        self.head.send_command = send_command

        result = self._run(self.head.crx_outputs_management(1, 2))

        self.assertIsNone(result)
        self.assertEqual(sent, [])

    def test_alarm_923_accepts_all_controller_encodings(self):
        for error_code in (923, "923", "TINTING_PANEL_TABLE_ERROR"):
            with self.subTest(error_code=error_code):
                self.head.status = {
                    "status_level": "ALARM", "error_code": error_code
                }
                self.assertTrue(self.head.check_alarm_923())

        self.head.status = {"status_level": "STANDBY", "error_code": 923}
        self.assertFalse(self.head.check_alarm_923())

    def test_every_documented_photocell_mask_can_be_checked(self):
        names = (
            "JAR_INPUT_ROLLER_PHOTOCELL",
            "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL",
            "JAR_OUTPUT_ROLLER_PHOTOCELL",
            "LOAD_LIFTER_DOWN_PHOTOCELL",
            "LOAD_LIFTER_UP_PHOTOCELL",
            "UNLOAD_LIFTER_DOWN_PHOTOCELL",
            "UNLOAD_LIFTER_UP_PHOTOCELL",
            "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL",
            "JAR_DISPENSING_POSITION_PHOTOCELL",
            "JAR_DETECTION_MICROSWITCH_1",
            "JAR_DETECTION_MICROSWITCH_2",
        )

        for bit, name in enumerate(names):
            with self.subTest(name=name):
                self.assertTrue(
                    self.head.check_jar_photocells_status(1 << bit, name)
                )
                self.assertFalse(
                    self.head.check_jar_photocells_status(0, name)
                )

        with self.assertRaises(ValueError):
            self.head.check_jar_photocells_status(0, "UNKNOWN_SENSOR")


class TestMachineHeadRunLifecycle(unittest.TestCase):
    """Il websocket e il watchdog devono vivere e terminare insieme."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.head = machine_head_module.MachineHead.__new__(
            machine_head_module.MachineHead
        )

    def tearDown(self):
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self.loop.close()

    def test_cancelling_run_cancels_websocket_and_watchdog(self):
        watchdog_started = asyncio.Event()
        websocket_started = asyncio.Event()
        stopped = {"watchdog": False, "websocket": False}

        async def watchdog():
            watchdog_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped["watchdog"] = True

        async def websocket_loop():
            websocket_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped["websocket"] = True

        self.head._MachineHead__watch_dog_task = watchdog
        self.head._MachineHead__run_ws_loop = websocket_loop
        run_task = self.loop.create_task(self.head.run())
        self.loop.run_until_complete(asyncio.gather(
            watchdog_started.wait(), websocket_started.wait()
        ))

        run_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            self.loop.run_until_complete(run_task)

        self.assertEqual(stopped, {"watchdog": True, "websocket": True})

    def test_watchdog_failure_terminates_run_and_cancels_websocket(self):
        websocket_cancelled = []

        async def failing_watchdog():
            await asyncio.sleep(0)
            raise RuntimeError("watchdog failure")

        async def websocket_loop():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                websocket_cancelled.append(True)
                raise

        self.head._MachineHead__watch_dog_task = failing_watchdog
        self.head._MachineHead__run_ws_loop = websocket_loop

        async def observe_without_forcing_cancellation():
            task = asyncio.ensure_future(self.head.run())
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=0.1)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except BaseException as exc:
                    return False, exc
                return False, None
            except BaseException as exc:  # conserva anche CancelledError 3.8+
                return True, exc
            return True, None

        completed, error = self.loop.run_until_complete(
            observe_without_forcing_cancellation()
        )

        self.assertTrue(completed, "run() ha continuato senza watchdog")
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(str(error), "watchdog failure")
        self.assertEqual(websocket_cancelled, [True])

    def test_watchdog_normal_return_is_treated_as_a_failure(self):
        websocket_cancelled = []

        async def terminating_watchdog():
            return None

        async def websocket_loop():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                websocket_cancelled.append(True)
                raise

        self.head._MachineHead__watch_dog_task = terminating_watchdog
        self.head._MachineHead__run_ws_loop = websocket_loop

        with self.assertRaisesRegex(
                RuntimeError, "watchdog task terminated unexpectedly"
        ):
            self.loop.run_until_complete(self.head.run())

        self.assertEqual(websocket_cancelled, [True])

    def test_websocket_failure_terminates_run_and_cancels_watchdog(self):
        watchdog_cancelled = []

        async def watchdog():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                watchdog_cancelled.append(True)
                raise

        async def failing_websocket_loop():
            await asyncio.sleep(0)
            raise OSError("websocket failure")

        self.head._MachineHead__watch_dog_task = watchdog
        self.head._MachineHead__run_ws_loop = failing_websocket_loop

        with self.assertRaisesRegex(OSError, "websocket failure"):
            self.loop.run_until_complete(self.head.run())

        self.assertEqual(watchdog_cancelled, [True])


if __name__ == "__main__":
    unittest.main()
