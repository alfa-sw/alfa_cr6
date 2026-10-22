# coding: utf-8

"""AUTORECOVERY interlock: real application/head logic, no hardware or network."""

import asyncio
import copy
import json
import types
import unittest
from unittest import mock

import alfa_CR6_backend.base_application as app_module
import alfa_CR6_backend.carousel_motor as carousel_module
import alfa_CR6_backend.machine_head as head_module
from alfa_CR6_backend.carousel_motor import CarouselMotor
from alfa_CR6_test.hardware_fakes import VirtualClock


class TestAutorecoveryInterlock(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.app = CarouselMotor.__new__(CarouselMotor)
        self.app.settings = types.SimpleNamespace(TROUBLESHOOTING=False)
        # A, F and B are all expected, even before MachineHead creation.
        self.app._head_safety_states = {0: None, 1: None, 2: None}
        self.app.machine_head_dict = {}
        self.app.carousel_frozen = True
        self.app.ws_server = None
        self.app._BaseApplication__modal_freeze_msgbox = None
        self.app._BaseApplication__jar_runners = {}
        self.app.main_window = types.SimpleNamespace(
            debug_page=None,
            show_carousel_frozen=mock.Mock(),
            set_carousel_freeze_control_enabled=mock.Mock(),
            open_frozen_dialog=mock.Mock(),
            open_alert_dialog=mock.Mock(),
        )
        self.app.insert_db_event = mock.Mock()
        self.app.insert_db_document = mock.Mock()
        self.app.handle_exception = mock.Mock()
        self.app_patch = mock.patch.object(
            head_module, "get_application_instance", return_value=self.app)
        self.app_patch.start()
        self.translation_patch = mock.patch.object(
            app_module, "tr_", side_effect=lambda text: text)
        self.translation_patch.start()

    def tearDown(self):
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True))
        for head in self.app.machine_head_dict.values():
            head.invalidate_safety_status()
        self.loop.close()
        self.translation_patch.stop()
        self.app_patch.stop()

    def _run(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    def _head(self, index):
        if index not in self.app.machine_head_dict:
            head = head_module.MachineHead(index, "127.0.0.1", 11001, 8080)
            head.update_tintometer_data = mock.AsyncMock()
            self.app.machine_head_dict[index] = head
        return self.app.machine_head_dict[index]

    async def _status(self, index, level, **extra):
        status = {
            "status_level": level, "photocells_status": 0,
            "jar_photocells_status": 0, "crx_outputs_status": 0,
        }
        status.update(extra)
        await self._head(index).update_status(status)

    async def _ready(self):
        for index in self.app._head_safety_states:
            await self._status(index, "STANDBY")
        self.assertTrue(self.app.freeze_carousel(False))

    def _assert_home_enabled(self, expected):
        args = self.app.main_window.set_carousel_freeze_control_enabled.call_args.args
        self.assertEqual(args[0], expected)
        self.assertEqual(bool(args[1]), not expected)

    def test_startup_includes_heads_that_have_not_been_created(self):
        self.app._update_carousel_freeze_control()
        self.assertFalse(self.app.freeze_carousel(False))
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(False)
        self._run(self._status(0, "STANDBY"))
        self.assertFalse(self.app.freeze_carousel(False))
        self.assertIn("F, B", self.app.get_carousel_unlock_block_reason())

    def test_verification_after_restart_never_resumes_automatically(self):
        for index in (0, 1, 2):
            self._run(self._status(index, "STANDBY"))
        self._assert_home_enabled(True)
        self.assertTrue(self.app.carousel_frozen)
        self.assertTrue(self.app.freeze_carousel(False))
        self.assertFalse(self.app.carousel_frozen)

    def test_multiple_heads_must_all_leave_autorecovery(self):
        for first_end, last_end in (
                ("STANDBY", "STANDBY"), ("STANDBY", "ALARM"),
                ("ALARM", "STANDBY"), ("ALARM", "ALARM")):
            with self.subTest(first_end=first_end, last_end=last_end):
                self._run(self._ready())
                self._run(self._status(0, "AUTORECOVERY"))
                self._run(self._status(1, "AUTORECOVERY"))
                self.assertEqual(self._head(0).status["status_level"], "AUTORECOVERY")
                self.assertIn("A, F", self.app.get_carousel_unlock_block_reason())
                self._run(self._status(0, first_end))
                self._assert_home_enabled(False)
                self.assertFalse(self.app.freeze_carousel(False))
                self._run(self._status(1, last_end))
                self._assert_home_enabled(True)
                self.assertTrue(self.app.carousel_frozen)
                # The existing home confirmation calls this callback: only an
                # explicit operator action can now resume the carousel.
                self.assertTrue(self.app.toggle_freeze_carousel())
                self.assertFalse(self.app.carousel_frozen)

    def test_last_head_can_leave_for_alarm_without_automatic_restart(self):
        self._run(self._ready())
        self._run(self._status(2, "AUTORECOVERY"))
        self._run(self._status(2, "ALARM", error_code=123))
        self._assert_home_enabled(True)
        self.assertTrue(self.app.carousel_frozen)
        self.assertTrue(
            self.app.main_window.open_frozen_dialog.call_args.kwargs[
                "force_explicit_restart"])
        self.assertTrue(self.app.toggle_freeze_carousel())
        self.assertFalse(self.app.carousel_frozen)

    def test_confirmation_opened_before_autorecovery_cannot_unlock(self):
        self._run(self._ready())
        self.app.freeze_carousel(True)
        confirm = self.app.toggle_freeze_carousel
        self._run(self._status(1, "AUTORECOVERY"))
        self.assertFalse(confirm())
        self.assertTrue(self.app.carousel_frozen)

    def test_jar_recovery_cannot_bypass_the_interlock(self):
        self._run(self._ready())
        self._run(self._status(1, "AUTORECOVERY"))
        self.app.n_of_active_heads = 6
        self.app.running_recovery_mode = False
        self.app.restore_machine_helper = types.SimpleNamespace(
            async_read_data=mock.AsyncMock(return_value={"barcode": {"pos": "A"}}))
        self.app.db_session = mock.Mock()
        self._run(self.app.machine_recovery())
        self.assertTrue(self.app.carousel_frozen)
        self.app.db_session.query.assert_not_called()

    def test_debug_override_survives_repeated_status_but_not_a_new_hazard(self):
        self._run(self._ready())
        self._run(self._status(0, "AUTORECOVERY"))
        self.assertTrue(self.app.freeze_carousel(False, force=True))
        self._assert_home_enabled(False)
        self._run(self._status(0, "AUTORECOVERY", autorecovery_component=2))
        self.assertFalse(self.app.carousel_frozen)
        self._run(self._status(1, "AUTORECOVERY"))
        self.assertTrue(self.app.carousel_frozen)

    def test_missing_and_unknown_states_do_not_release_recovery(self):
        self._run(self._ready())
        for status in ({}, {"status_level": None}, {"status_level": "UNKNOWN"},
                       {"status_level": 13}, {"status_level": []},
                       {"status_level": "POWER_OFF"},
                       {"status_level": "STANDBY", "expired": True}):
            with self.subTest(status=status):
                self._run(self._status(0, "AUTORECOVERY"))
                self._run(self._head(0).update_status(status))
                self.assertFalse(self.app.freeze_carousel(False))
                self.assertTrue(self.app.carousel_frozen)
                self._assert_home_enabled(False)

    def test_empty_or_malformed_status_message_invalidates_previous_standby(self):
        self._run(self._ready())
        for value in (None, [], {}, ["invalid"]):
            with self.subTest(value=value):
                self._run(self._status(0, "STANDBY"))
                message = json.dumps({"type": "device:machine:status", "value": value})
                try:
                    self._run(self._head(0)._MachineHead__process_ws_msg(message))
                except (TypeError, ValueError):
                    pass
                self.assertFalse(self.app.freeze_carousel(False))

    def test_empty_or_unreadable_frame_cannot_keep_an_unlock_available(self):
        self._run(self._ready())
        for message in ("", "{invalid json"):
            with self.subTest(message=message):
                self._run(self._status(0, "STANDBY"))
                try:
                    self._run(self._head(0)._MachineHead__process_ws_msg(message))
                except ValueError:
                    pass
                self.assertFalse(self.app.freeze_carousel(False))

    def test_receive_timeout_blocks_unlock_until_a_new_machine_status(self):
        self._run(self._ready())
        head = self._head(0)

        async def receive_timeout(awaitable, **_kwargs):
            awaitable.close()
            raise asyncio.TimeoutError()

        head.websocket = types.SimpleNamespace(recv=mock.AsyncMock())
        with mock.patch.object(head_module.asyncio, "wait_for", receive_timeout):
            with self.assertRaises(asyncio.TimeoutError):
                self._run(head.handle_ws_recv())
        self.assertTrue(self.app.carousel_frozen)
        self._run(head._MachineHead__process_ws_msg(json.dumps({
            "type": "time", "value": 12345})))
        self._run(self._status(1, "STANDBY"))
        self.assertFalse(self.app.freeze_carousel(False))
        self._run(self._status(0, "STANDBY"))
        self._assert_home_enabled(True)
        self.assertTrue(self.app.carousel_frozen)

    def test_unchanged_status_remains_valid_while_transport_is_alive(self):
        self._run(self._ready())
        for _ in range(10):
            self._run(self._head(0)._MachineHead__process_ws_msg(json.dumps({
                "type": "time", "value": 12345})))
        self.assertFalse(self.app.carousel_frozen)
        self.assertEqual(self.app.get_carousel_unlock_block_reason(), "")

    def test_reconnect_requires_new_status_from_disconnected_head(self):
        self._run(self._ready())
        self._run(self._status(0, "AUTORECOVERY"))
        self._head(0).invalidate_safety_status()
        self._run(self._status(1, "STANDBY"))
        self._run(self._status(2, "STANDBY"))
        self.assertFalse(self.app.freeze_carousel(False))
        self._run(self._status(0, "STANDBY"))
        self._assert_home_enabled(True)
        self.assertTrue(self.app.carousel_frozen)

    def test_websocket_loss_invalidates_before_close_handshake_finishes(self):
        async def scenario():
            await self._ready()
            head = self._head(0)
            closing = asyncio.Event()

            async def close():
                closing.set()
                await asyncio.Future()

            websocket = types.SimpleNamespace(
                recv=mock.AsyncMock(side_effect=[
                    json.dumps({"type": "device:machine:status", "value": {
                        "status_level": "STANDBY"}}),
                    OSError("connection lost"),
                ]),
                close=close,
            )
            with mock.patch.object(head_module.websockets, "connect",
                                   new=mock.AsyncMock(return_value=websocket)):
                task = asyncio.create_task(head._MachineHead__run_ws_loop())
                await asyncio.wait_for(closing.wait(), 1)
                self.assertIsNone(self.app._head_safety_states[0])
                self.assertFalse(self.app.freeze_carousel(False))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

        self._run(scenario())

    def test_queued_command_and_jar_wait_for_explicit_operator_restart(self):
        async def scenario():
            await self._ready()
            await self._status(1, "AUTORECOVERY")
            head = self._head(0)
            head.websocket = types.SimpleNamespace(send=mock.AsyncMock())
            jar = {"status": "PROGRESS", "position": "A", "dispensed": {"RED": 1.5}}
            snapshot = copy.deepcopy(jar)
            task = asyncio.create_task(head.send_command(
                "DISPENSE_FORMULA", {"ingredients": {"RED": 2}}, type_="macro"))
            runner = {"task": task, "jar": jar, "frozen": False}
            self.app._BaseApplication__jar_runners["barcode"] = runner
            await asyncio.sleep(0)
            self.assertTrue(runner["frozen"])
            head.websocket.send.assert_not_awaited()
            await self._status(1, "STANDBY")
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertEqual(jar, snapshot)
            self.assertIs(self.app._BaseApplication__jar_runners["barcode"], runner)
            self.assertTrue(self.app.freeze_carousel(False))
            self.assertTrue(await asyncio.wait_for(task, 1))
            head.websocket.send.assert_awaited_once()
            self.assertFalse(runner["frozen"])
            self.assertEqual(jar, snapshot)

        self._run(scenario())

    def test_pending_dispense_does_not_touch_jar_or_request_formula(self):
        async def scenario():
            await self._ready()
            await self._status(1, "AUTORECOVERY")
            head = self._head(0)
            head.call_api_rest = mock.AsyncMock()
            jar = mock.Mock()
            task = asyncio.create_task(head.do_dispense(jar))
            await asyncio.sleep(0)
            jar.update_live.assert_not_called()
            jar.get_ingredients_for_machine.assert_not_called()
            head.call_api_rest.assert_not_awaited()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self._run(scenario())

    def test_every_start_command_waits_at_the_transport_boundary(self):
        async def scenario():
            await self._ready()
            await self._status(1, "AUTORECOVERY")
            head = self._head(0)
            head.websocket = types.SimpleNamespace(send=mock.AsyncMock())
            commands = (
                ("CRX_OUTPUTS_MANAGEMENT", {"Output_Number": 0, "Output_Action": 2}),
                ("CAN_MOVEMENT", {"Lifter": 1}),
                ("DISPENSE_FORMULA", {"ingredients": {"RED": 2}}),
                ("PURGE", {"items": [{"name": "RED", "qtity": 2}]}),
            )
            for command, params in commands:
                with self.subTest(command=command):
                    task = asyncio.create_task(head.send_command(command, params))
                    await asyncio.sleep(0)
                    head.websocket.send.assert_not_awaited()
                    self.assertFalse(task.done())
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

        self._run(scenario())

    def test_starts_wait_but_stops_aborts_leds_and_scale_can_pass(self):
        async def scenario():
            await self._ready()
            await self._status(1, "AUTORECOVERY")
            head = self._head(0)
            head.websocket = types.SimpleNamespace(send=mock.AsyncMock())
            commands = (
                ("CRX_OUTPUTS_MANAGEMENT", {"Output_Number": 0, "Output_Action": 0}, "machine"),
                ("CAN_MOVEMENT", {"Lifter": 0}, "machine"),
                ("ABORT", {}, "machine"),
                ("SET_ATTENTION_REQUEST_STATUS", {"Action": 1}, "machine"),
                ("SEND_IMMEDIATE", {}, "scale"),
            )
            with mock.patch.object(self.app, "wait_for_condition", new=mock.AsyncMock(return_value=False)), \
                    mock.patch.object(self.app, "wait_for_carousel_not_frozen", new=mock.AsyncMock()) as wait:
                for command, params, channel in commands:
                    await head.send_command(command, params, channel=channel)
                wait.assert_not_awaited()
            self.assertEqual(head.websocket.send.await_count, len(commands))

        self._run(scenario())

    def test_freeze_arriving_during_output_lock_wait_prevents_start(self):
        async def scenario():
            await self._ready()
            head = self._head(0)
            head.websocket = types.SimpleNamespace(send=mock.AsyncMock())
            output = head._MachineHead__crx_inner_status[0]
            output["locked"] = True
            task = asyncio.create_task(head.crx_outputs_management(0, 1))
            await asyncio.sleep(0)
            await self._status(1, "AUTORECOVERY")
            output["locked"] = False
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.assertEqual(output["t0"], 0)
            head.websocket.send.assert_not_awaited()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self._run(scenario())

    def test_operator_wait_does_not_consume_precondition_timeout(self):
        self._run(self._ready())
        clock = VirtualClock()
        condition = mock.Mock(side_effect=[False, True])

        def freeze_on_first_sample(_count):
            self.app.update_head_safety(1, "AUTORECOVERY")

        clock.on_sleep = freeze_on_first_sample

        async def operator_wait():
            # More than the operation timeout elapses while no work is started.
            clock.now += 1000
            self.app.update_head_safety(1, "STANDBY")
            self.assertTrue(self.app.carousel_frozen)
            self.app.freeze_carousel(False)

        with mock.patch.object(carousel_module.time, "time", clock.time), \
                mock.patch.object(carousel_module.asyncio, "sleep", clock.sleep), \
                mock.patch.object(self.app, "wait_for_carousel_not_frozen", operator_wait):
            result = self._run(self.app.wait_for_condition(
                condition, timeout=1, stability_count=1, step=0.1,
                pause_on_freeze=True))

        self.assertTrue(result)
        self.assertGreater(clock.now, 1000)
        self.app.main_window.open_alert_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
