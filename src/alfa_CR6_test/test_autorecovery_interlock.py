# coding: utf-8

"""AUTORECOVERY interlock: real application/head logic, no hardware or network."""

import asyncio
import copy
import itertools
import json
import types
import unittest
from unittest import mock

import alfa_CR6_backend.base_application as app_module
import alfa_CR6_backend.carousel_motor as carousel_module
import alfa_CR6_backend.machine_head as head_module
import alfa_CR6_backend.models as models_module
from alfa_CR6_backend.carousel_motor import CarouselMotor
from alfa_CR6_backend.lang.it import D as ITALIAN
from alfa_CR6_test.hardware_fakes import VirtualClock


class TestAutorecoveryInterlock(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.app = CarouselMotor.__new__(CarouselMotor)
        self.app.settings = types.SimpleNamespace(TROUBLESHOOTING=False)
        # A, F and B are all expected, even before MachineHead creation.
        self.app._head_safety_states = {0: None, 1: None, 2: None}
        self.app._autorecovery_pending_heads = set()
        self.app._autorecovery_can_resume = False
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

    def test_single_success_resumes_without_an_operator_action(self):
        self._run(self._ready())
        for _ in range(2):
            self._run(self._status(0, "AUTORECOVERY"))
            self.assertTrue(self.app.carousel_frozen)
            self._assert_home_enabled(False)
            self._run(self._status(0, "STANDBY"))
            self.assertFalse(self.app.carousel_frozen)
            self._assert_home_enabled(True)
        self.app.main_window.open_frozen_dialog.assert_not_called()

    def test_multiple_heads_resume_only_if_all_recoveries_succeed(self):
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
                failed = "ALARM" in (first_end, last_end)
                self.assertEqual(self.app.carousel_frozen, failed)
                if failed:
                    # Mixed outcomes still require the home confirmation.
                    self.assertTrue(self.app.toggle_freeze_carousel())
                self.assertFalse(self.app.carousel_frozen)

    def test_three_successful_heads_wait_for_the_last_in_any_completion_order(self):
        for order in itertools.permutations((0, 1, 2)):
            with self.subTest(order=order):
                self._run(self._ready())
                for index in (0, 1, 2):
                    self._run(self._status(index, "AUTORECOVERY"))
                for index in order[:-1]:
                    self._run(self._status(index, "STANDBY"))
                    self.assertTrue(self.app.carousel_frozen)
                    self._assert_home_enabled(False)
                self._run(self._status(order[-1], "STANDBY"))
                self.assertFalse(self.app.carousel_frozen)
                self._assert_home_enabled(True)

    def test_cleared_alarm_is_remembered_until_other_recoveries_finish(self):
        self._run(self._ready())
        for index in (0, 1, 2):
            self._run(self._status(index, "AUTORECOVERY"))
        self._run(self._status(0, "ALARM"))
        self._run(self._status(0, "STANDBY"))
        self._run(self._status(1, "STANDBY"))
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(False)
        self._run(self._status(2, "STANDBY"))
        self._assert_home_enabled(True)
        self.assertTrue(self.app.carousel_frozen)
        self.assertTrue(self.app.toggle_freeze_carousel())
        # An explicit restart permits a later, clean group to resume normally.
        self._run(self._status(0, "AUTORECOVERY"))
        self._run(self._status(0, "STANDBY"))
        self.assertFalse(self.app.carousel_frozen)

    def test_reentering_recovery_waits_for_the_new_attempt_too(self):
        self._run(self._ready())
        self._run(self._status(0, "AUTORECOVERY"))
        self._run(self._status(1, "AUTORECOVERY"))
        self._run(self._status(0, "STANDBY"))
        self._run(self._status(0, "AUTORECOVERY"))
        self._run(self._status(1, "STANDBY"))
        self.assertTrue(self.app.carousel_frozen)
        self._run(self._status(0, "STANDBY"))
        self.assertFalse(self.app.carousel_frozen)

    def test_intermediate_reset_does_not_count_as_success(self):
        self._run(self._ready())
        self._run(self._status(0, "AUTORECOVERY"))
        self._run(self._status(1, "AUTORECOVERY"))
        self._run(self._status(0, "RESET"))
        self._run(self._status(1, "STANDBY"))
        self.assertTrue(self.app.carousel_frozen)
        self._run(self._status(0, "STANDBY"))
        self.assertFalse(self.app.carousel_frozen)

    def test_success_preserves_manual_pause_before_or_during_recovery(self):
        for pause_before in (True, False):
            with self.subTest(pause_before=pause_before):
                self._run(self._ready())
                if pause_before:
                    self.app.freeze_carousel(True)
                self._run(self._status(0, "AUTORECOVERY"))
                if not pause_before:
                    self.app.freeze_carousel(True)
                self._run(self._status(0, "STANDBY"))
                self.assertTrue(self.app.carousel_frozen)
                self._assert_home_enabled(True)

    def test_success_preserves_an_alarm_from_a_head_not_in_recovery(self):
        self._run(self._ready())
        self._run(self._status(0, "AUTORECOVERY"))
        self._run(self._status(2, "ALARM"))
        self._run(self._status(2, "STANDBY"))
        self._run(self._status(0, "STANDBY"))
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(True)

    def test_startup_during_recovery_does_not_authorize_automatic_resume(self):
        self._run(self._status(0, "AUTORECOVERY"))
        self._run(self._status(1, "STANDBY"))
        self._run(self._status(2, "STANDBY"))
        self._run(self._status(0, "STANDBY"))
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(True)

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
        self._assert_home_enabled(False)
        self.assertTrue(self.app.freeze_carousel(False, force=True))
        self.assertFalse(self.app.carousel_frozen)
        self._assert_home_enabled(True)
        self._run(self._status(0, "AUTORECOVERY", autorecovery_component=2))
        self.assertFalse(self.app.carousel_frozen)
        self._assert_home_enabled(True)
        self._run(self._status(1, "AUTORECOVERY"))
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(False)
        self.assertFalse(self.app.toggle_freeze_carousel())

    def test_home_can_pause_after_debug_unlock(self):
        self._run(self._ready())
        self._run(self._status(0, "AUTORECOVERY"))
        self.assertTrue(self.app.freeze_carousel(False, force=True))
        self.assertTrue(self.app.toggle_freeze_carousel())
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(False)
        self.assertFalse(self.app.toggle_freeze_carousel())

    def test_missing_and_unknown_states_do_not_release_recovery(self):
        for status in ({}, {"status_level": None}, {"status_level": "UNKNOWN"},
                       {"status_level": 13}, {"status_level": []},
                       {"status_level": "POWER_OFF"},
                       {"status_level": "STANDBY", "expired": True}):
            with self.subTest(status=status):
                self._run(self._ready())
                self._run(self._status(0, "AUTORECOVERY"))
                self._run(self._head(0).update_status(status))
                self.assertFalse(self.app.freeze_carousel(False))
                self.assertTrue(self.app.carousel_frozen)
                self._assert_home_enabled(False)
                self._run(self._status(0, "STANDBY"))
                self.assertTrue(self.app.carousel_frozen)
                self._assert_home_enabled(True)

    def test_communication_loss_on_another_head_prevents_automatic_resume(self):
        self._run(self._ready())
        self._run(self._status(0, "AUTORECOVERY"))
        self._head(2).invalidate_safety_status()
        self._run(self._status(0, "STANDBY"))
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(False)
        self._run(self._status(2, "STANDBY"))
        self.assertTrue(self.app.carousel_frozen)
        self._assert_home_enabled(True)

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

    def test_queued_work_resumes_after_success_but_waits_for_operator_after_failure(self):
        async def scenario(failed):
            await self._ready()
            await self._status(1, "AUTORECOVERY")
            await self._status(2, "AUTORECOVERY")
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
            await self._status(1, "ALARM" if failed else "STANDBY")
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            head.websocket.send.assert_not_awaited()
            self.assertEqual(jar, snapshot)
            self.assertIs(self.app._BaseApplication__jar_runners["barcode"], runner)
            await self._status(2, "STANDBY")
            self.assertEqual(self.app.carousel_frozen, failed)
            if failed:
                await asyncio.sleep(0)
                self.assertFalse(task.done())
                head.websocket.send.assert_not_awaited()
                self.assertTrue(self.app.toggle_freeze_carousel())
            self.assertTrue(await asyncio.wait_for(task, 1))
            head.websocket.send.assert_awaited_once()
            self.assertFalse(runner["frozen"])
            self.assertEqual(jar, snapshot)

        for failed in (False, True):
            with self.subTest(failed=failed):
                self._run(scenario(failed))

    def test_movement_failure_during_recovery_requires_manual_restart(self):
        async def scenario():
            await self._ready()
            await self._status(0, "AUTORECOVERY")
            waiter = asyncio.create_task(self.app.wait_for_carousel_not_frozen(
                freeze=True, message_fmt="transfer failed"))
            await asyncio.sleep(0)
            self.assertTrue(self.app.main_window.open_frozen_dialog.call_args.kwargs[
                "force_explicit_restart"])
            await self._status(0, "STANDBY")
            self.assertTrue(self.app.carousel_frozen)
            self.assertFalse(waiter.done())
            self.assertTrue(self.app.toggle_freeze_carousel())
            await asyncio.wait_for(waiter, 1)

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

    async def _dispense_with_recovery(self, final_level=None, fast=False,
                                     recovery_index=0, purge=False, cancel=False,
                                     publish_dispensing=True, frames=None,
                                     queued_recovery=False):
        await self._ready()
        head = self._head(0)
        head.pigment_list = [{
            "name": "RED", "type": "colorant", "specific_weight": 1,
            "pipes": [{"name": "C01", "enabled": True,
                       "effective_specific_weight": 1}],
        }]
        order = models_module.Order(
            order_nr=261109001000, description="PURGE ALL" if purge else "",
            json_properties="{}")
        jar = models_module.Jar(
            order=order, index=1, status="PROGRESS", position="A",
            json_properties="{}")
        jar.get_ingredients_for_machine = mock.Mock(return_value={"RED": 1})
        jar.get_not_dispensed_ingredients = mock.Mock(return_value={})
        head.get_ingredients_for_purge_all = mock.AsyncMock(return_value={"RED": 1})
        head.call_api_rest = mock.AsyncMock(return_value={
            "result": "OK", "pipe_formula": {"RED": 1}})
        self.app.update_jar_properties = mock.Mock()
        self.app.main_window.debug_page = mock.Mock()
        runner = {"jar": jar}
        self.app._BaseApplication__jar_runners[jar.barcode] = runner
        restore = mock.Mock()
        clock = VirtualClock()
        injected = False
        cancellation_sent = False
        gate_calls = 0
        original_gate = self.app.wait_for_carousel_not_frozen

        async def gate(*args, **kwargs):
            nonlocal gate_calls
            gate_calls += 1
            if queued_recovery and gate_calls == 3:
                # This is send_command's gate, after do_dispense's two waits.
                self.app.freeze_carousel(True)
                head.websocket.send.assert_not_awaited()
                self.assertFalse(head._dispense_in_progress)
                await self._status(0, "AUTORECOVERY", autorecovery_error_code=1069)
                self.assertIsNone(head._dispense_autorecovery)
                await self._status(0, "STANDBY", container_presence=True,
                                   jar_photocells_status=0x100)
                self.assertTrue(self.app.freeze_carousel(False))
            return await original_gate(*args, **kwargs)

        async def recover():
            recovery_frames = frames if frames is not None else [
                {"autorecovery_error_code": 1065, "autorecovery_component": 5},
                {"autorecovery_error_code": 1065, "autorecovery_component": 1},
            ]
            for frame in recovery_frames:
                await self._status(recovery_index, "AUTORECOVERY",
                                   error_code=0, error_message="NO_ALARM", **frame)
            if final_level:
                await self._status(recovery_index, final_level,
                                   autorecovery_error_code=0, autorecovery_component=0)

        async def send(_payload):
            self.assertTrue(head._dispense_in_progress)
            self.assertIsNone(head._dispense_autorecovery)
            if publish_dispensing:
                await self._status(0, "DISPENSING", container_presence=True,
                                   jar_photocells_status=0x100)
            if fast:
                await recover()

        async def sleep(delay):
            nonlocal injected, cancellation_sent
            await clock.sleep(delay)
            self.assertLess(clock.now, 2, "Dispense did not finish promptly")
            if not fast and not injected and "running_engaged_circuits" in runner:
                if cancel and not cancellation_sent:
                    cancellation_sent = True
                    # delete_jar_runner removes the jar before cancelling its task.
                    jar.update_live(status="ERROR", pos="REMOVED")
                    raise asyncio.CancelledError()
                injected = True
                if not queued_recovery:
                    await recover()
                if recovery_index != 0 or queued_recovery:
                    await self._status(0, "STANDBY", container_presence=True,
                                       jar_photocells_status=0x100)

        head.websocket = types.SimpleNamespace(send=mock.AsyncMock(side_effect=send))
        await self._status(0, "STANDBY", container_presence=True,
                           jar_photocells_status=0x100)
        with mock.patch.object(carousel_module.time, "time", clock.time), \
                mock.patch.object(carousel_module.asyncio, "sleep", sleep), \
                mock.patch.object(self.app, "wait_for_carousel_not_frozen", gate), \
                mock.patch.object(models_module, "get_application_instance", return_value=self.app), \
                mock.patch.object(head_module, "tr_", side_effect=lambda text: ITALIAN.get(text, text)):
            if cancel:
                with self.assertRaises(asyncio.CancelledError):
                    await head.do_dispense(jar, restore)
            else:
                self.assertTrue(await head.do_dispense(jar, restore))
        self.app.handle_exception.assert_not_called()
        if queued_recovery:
            self.assertGreaterEqual(gate_calls, 3, "Transport gate was not exercised")
        return head, jar, restore

    def _assert_autorecovery_abort(self, head, jar):
        self.assertEqual(jar.status, "ERROR")
        self.assertEqual(jar.order.status, "ERROR")
        properties = json.loads(jar.json_properties)
        recovery = properties["dispensation_autorecovery"]["A"]
        code = recovery["autorecovery_error_code"]
        self.assertEqual(properties.get("dispensed_quantities_gr", {}), {})
        self.assertIn("AUTORECOVERY", properties["dispensation_outcomes"][0][1])
        self.assertIn("autorecovery_error_code:{}".format(code),
                      properties["dispensation_outcomes"][0][1])
        self.assertNotIn("NO_ALARM", properties["dispensation_outcomes"][0][1])
        self.app.update_jar_properties.assert_called_once_with(
            jar, dispense_not_successful=True)
        head.websocket.send.assert_awaited_once()
        self.app.main_window.open_alert_dialog.assert_called_once_with(
            ("A", jar.barcode, code or "sconosciuto"), title="Ordine abortito",
            fmt=["Head {} - BARCODE {}\nThe head entered AUTORECOVERY during dispensing.",
                 "\n", "Autorecovery code: {}"],
            ok_only=True)
        self.assertFalse(head._dispense_in_progress)
        self.assertIsNone(head._current_runner)

    def test_no_dispensing_frame_before_autorecovery_to_standby(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            final_level="STANDBY", fast=True, publish_dispensing=False))
        self._assert_autorecovery_abort(head, jar)
        self.assertFalse(self.app.carousel_frozen)
        self.app.main_window.open_frozen_dialog.assert_not_called()

    def test_no_dispensing_frame_before_autorecovery_to_alarm(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            final_level="ALARM", fast=True, publish_dispensing=False))
        self._assert_autorecovery_abort(head, jar)
        self.assertTrue(self.app.carousel_frozen)

    def test_same_head_autorecovery_while_macro_is_queued_does_not_abort_order(self):
        for purge in (False, True):
            with self.subTest(purge=purge):
                head, jar, _restore = self._run(self._dispense_with_recovery(
                    queued_recovery=True, purge=purge))
                self.assertEqual(jar.status, "PROGRESS")
                self.assertEqual(jar.order.status, "PROGRESS")
                self.assertEqual(json.loads(jar.json_properties).get("dispensed_quantities_gr", {}),
                                 {} if purge else {"RED": 1})
                self.assertIsNone(head._dispense_autorecovery)
                head.websocket.send.assert_awaited_once()
                self.app.main_window.open_alert_dialog.assert_not_called()
                self.app.main_window.open_frozen_dialog.assert_not_called()

    def test_purge_without_dispensing_frame_uses_autorecovery_popup(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            purge=True, fast=True, publish_dispensing=False, final_level="STANDBY"))
        self._assert_autorecovery_abort(head, jar)
        self.assertFalse(self.app.carousel_frozen)
        self.app.main_window.open_frozen_dialog.assert_not_called()

    def test_recovery_snapshot_keeps_first_cause_and_component(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(frames=[
            {"autorecovery_error_code": 1065, "autorecovery_component": 5},
            {"autorecovery_error_code": 1069, "autorecovery_component": 1},
            {"autorecovery_error_code": 0, "autorecovery_component": 0},
        ]))
        self._assert_autorecovery_abort(head, jar)
        self.assertEqual(json.loads(jar.json_properties)["dispensation_autorecovery"]["A"],
                         {"autorecovery_error_code": 1065, "autorecovery_component": 5})

    def test_recovery_snapshot_upgrades_only_unknown_code(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(frames=[
            {"autorecovery_error_code": 0, "autorecovery_component": 5},
            {"autorecovery_error_code": 1065, "autorecovery_component": 1},
            {"autorecovery_error_code": 1069, "autorecovery_component": 2},
        ]))
        self._assert_autorecovery_abort(head, jar)
        self.assertEqual(json.loads(jar.json_properties)["dispensation_autorecovery"]["A"],
                         {"autorecovery_error_code": 1065, "autorecovery_component": 5})

    def test_zero_code_is_still_an_autorecovery_event(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            fast=True, publish_dispensing=False, frames=[{"autorecovery_error_code": 0}]))
        self._assert_autorecovery_abort(head, jar)
        self.app.main_window.open_frozen_dialog.assert_not_called()

    def test_missing_code_is_still_an_autorecovery_event(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            fast=True, publish_dispensing=False, frames=[{}]))
        self._assert_autorecovery_abort(head, jar)
        self.app.main_window.open_frozen_dialog.assert_not_called()

    def test_dispense_recovery_marks_order_error_before_recovery_finishes(self):
        head, jar, restore = self._run(self._dispense_with_recovery())
        self._assert_autorecovery_abort(head, jar)
        restore.store_jar_data.assert_called_with(
            jar=jar, pos="A", dispensation="dispensation_failure")
        self.assertTrue(self.app.carousel_frozen)
        self.app.main_window.open_frozen_dialog.assert_not_called()
        self._run(self._status(0, "STANDBY"))
        self.assertFalse(self.app.carousel_frozen)
        self.assertEqual(jar.order.status, "ERROR")

    def test_fast_recovery_before_start_is_observed_cannot_mark_success(self):
        head, jar, restore = self._run(self._dispense_with_recovery(
            final_level="STANDBY", fast=True))
        self._assert_autorecovery_abort(head, jar)
        self.assertFalse(self.app.carousel_frozen)
        self.app.main_window.open_frozen_dialog.assert_not_called()
        restore.store_jar_data.assert_called_with(
            jar=jar, pos="A", dispensation="dispensation_failure")

    def test_recovery_to_standby_during_dispense_still_aborts_order(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            final_level="STANDBY"))
        self._assert_autorecovery_abort(head, jar)
        self.assertFalse(self.app.carousel_frozen)
        self.app.main_window.open_frozen_dialog.assert_not_called()

    def test_recovery_to_alarm_keeps_abort_notification_and_firmware_alarm(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            final_level="ALARM"))
        self._assert_autorecovery_abort(head, jar)
        self.assertTrue(self.app.carousel_frozen)
        self.app.main_window.open_frozen_dialog.assert_called_once()
        self.assertEqual(self.app.main_window.open_frozen_dialog.call_args.kwargs[
            "message_fmt"], "{} ALARM. {}: {}, {}: {}")

    def test_recovery_on_another_head_does_not_abort_this_dispense(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(
            final_level="STANDBY", recovery_index=1))
        self.assertEqual(jar.status, "PROGRESS")
        self.assertEqual(jar.order.status, "PROGRESS")
        self.assertEqual(json.loads(jar.json_properties)["dispensed_quantities_gr"],
                         {"RED": 1})
        self.app.main_window.open_alert_dialog.assert_not_called()
        self.app.main_window.open_frozen_dialog.assert_not_called()
        self.assertIsNone(head._dispense_autorecovery)

    def test_purge_recovery_also_marks_order_error(self):
        head, jar, _restore = self._run(self._dispense_with_recovery(purge=True))
        self._assert_autorecovery_abort(head, jar)
        payload = json.loads(head.websocket.send.call_args.args[0])
        self.assertEqual(payload["msg_out_dict"]["command"], "PURGE")

    def test_new_dispense_does_not_inherit_previous_autorecovery_failure(self):
        head, first_jar, _restore = self._run(self._dispense_with_recovery(
            final_level="STANDBY"))
        self._assert_autorecovery_abort(head, first_jar)
        self.app.main_window.open_alert_dialog.reset_mock()
        _head, next_jar, _restore = self._run(self._dispense_with_recovery(
            final_level="STANDBY", recovery_index=1))
        self.assertEqual(next_jar.status, "PROGRESS")
        self.assertEqual(next_jar.order.status, "PROGRESS")
        self.app.main_window.open_alert_dialog.assert_not_called()

    def test_recovery_while_cancelled_dispense_waits_for_standby_is_not_success(self):
        head, jar, restore = self._run(self._dispense_with_recovery(
            final_level="STANDBY", cancel=True))
        self._assert_autorecovery_abort(head, jar)
        self.assertNotIn("success", json.loads(jar.json_properties)[
            "dispensation_outcomes"][0][1])
        self.assertEqual(jar.position, "REMOVED")
        self.assertIsNone(jar.machine_head)
        self.assertFalse(any(call.kwargs["dispensation"] == "dispensation_failure"
                             for call in restore.store_jar_data.call_args_list))

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

    def test_recovery_wait_does_not_consume_precondition_timeout(self):
        self._run(self._ready())
        clock = VirtualClock()
        condition = mock.Mock(side_effect=[False, True])

        def freeze_on_first_sample(_count):
            self.app.update_head_safety(1, "AUTORECOVERY")

        clock.on_sleep = freeze_on_first_sample

        async def recovery_wait():
            # More than the operation timeout elapses while no work is started.
            clock.now += 1000
            self.app.update_head_safety(1, "STANDBY")
            self.assertFalse(self.app.carousel_frozen)

        with mock.patch.object(carousel_module.time, "time", clock.time), \
                mock.patch.object(carousel_module.asyncio, "sleep", clock.sleep), \
                mock.patch.object(self.app, "wait_for_carousel_not_frozen", recovery_wait):
            result = self._run(self.app.wait_for_condition(
                condition, timeout=1, stability_count=1, step=0.1,
                pause_on_freeze=True))

        self.assertTrue(result)
        self.assertGreater(clock.now, 1000)
        self.app.main_window.open_alert_dialog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
