# coding: utf-8

"""Regressioni per la scala dei soli tempi fisici dell'emulatore CR6."""

import asyncio
import json
import unittest
from unittest import mock

import alfa_CR6_test.emulator as emulator


class TestEmulatorTimeScale(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_default_time_scale_preserves_real_emulator_timing(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="[]")):
            head = emulator.MachineHeadMockup(0)

        self.assertEqual(head.time_scale, 1.0)

    def test_non_positive_scale_is_rejected(self):
        for value in (0, -1, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                emulator.MachineHeadMockup(0, time_scale=value)

    def test_physical_sleep_is_scaled(self):
        head = emulator.MachineHeadMockup.__new__(emulator.MachineHeadMockup)
        head.time_scale = 0.01

        with mock.patch.object(
            emulator.asyncio, "sleep", new=mock.AsyncMock()
        ) as sleep_mock:
            self.loop.run_until_complete(head._machine_sleep(4))

        sleep_mock.assert_awaited_once_with(0.04)

    def test_move_uses_scaled_physical_sleep_and_keeps_transition(self):
        head = emulator.MachineHeadMockup.__new__(emulator.MachineHeadMockup)
        head.time_scale = 0.25
        head.letter = "A"
        head.status = {"jar_photocells_status": 0}
        status_updates = []

        async def update_status(params=None):
            status_updates.append(params)
            head.status.update(params or {})

        head.update_status = update_status

        with mock.patch.object(
            emulator.asyncio, "sleep", new=mock.AsyncMock()
        ) as sleep_mock:
            self.loop.run_until_complete(
                head.do_move(
                    emulator.INPUT_ROLLER_MASK, "set", duration=2,
                    tgt_level="JAR_POSITIONING"
                )
            )

        sleep_mock.assert_awaited_once_with(0.5)
        self.assertEqual(status_updates, [{
            "status_level": "JAR_POSITIONING",
            "jar_photocells_status": emulator.INPUT_ROLLER_MASK,
        }])

    def test_dispense_replays_observed_steps_before_engaging_circuit(self):
        pigment = [{
            "name": "STBLUE 137",
            "pipes": [{"name": "C16"}],
        }]
        with mock.patch(
                "builtins.open",
                mock.mock_open(read_data=json.dumps(pigment))):
            head = emulator.MachineHeadMockup(0, time_scale=0.001)

        head.status["circuit_engaged"] = 0
        observed = []

        async def record_status():
            observed.append((
                head.status["status_level"],
                head.status["cycle_step"],
                head.status["circuit_engaged"],
            ))

        head.dump_status = record_status
        self.loop.run_until_complete(head.handle_command({
            "command": "DISPENSE_FORMULA",
            "params": {
                "ingredients": {"STBLUE 137": 0.0096},
            },
        }))

        self.assertEqual(observed, [
            ("DISPENSING", 1, 0),
            ("DISPENSING", 4, 0),
            ("DISPENSING", 9, 0),
            ("DISPENSING", 10, 0),
            ("DISPENSING", 10, 23),
            ("DISPENSING", 10, 0),
            ("DISPENSING", 14, 0),
            ("DISPENSING", 17, 0),
            ("DISPENSING", 23, 0),
            ("STANDBY", 0, 0),
        ])

    def test_physical_call_later_is_scaled(self):
        head = emulator.MachineHeadMockup.__new__(emulator.MachineHeadMockup)
        head.time_scale = 0.1
        callback = mock.Mock()
        loop_stub = mock.Mock()
        handle = object()
        loop_stub.call_later.return_value = handle

        with mock.patch.object(
            emulator.asyncio, "get_event_loop", return_value=loop_stub
        ):
            result = head._machine_call_later(3, callback, "arg")

        self.assertIs(result, handle)
        loop_stub.call_later.assert_called_once()
        delay, scheduled_callback, callback_arg = loop_stub.call_later.call_args.args
        self.assertAlmostEqual(delay, 0.3)
        self.assertIs(scheduled_callback, callback)
        self.assertEqual(callback_arg, "arg")

    def test_websocket_heartbeat_is_not_scaled(self):
        head = emulator.MachineHeadMockupWsSocket.__new__(
            emulator.MachineHeadMockupWsSocket
        )
        head.time_scale = 0.01
        head.timer_step = 1
        head.ws_clients = []
        sleep_values = []

        async def stop_after_first_sleep(delay):
            sleep_values.append(delay)
            raise asyncio.CancelledError()

        with mock.patch.object(emulator.asyncio, "sleep", stop_after_first_sleep):
            with self.assertRaises(asyncio.CancelledError):
                self.loop.run_until_complete(head._time_notifier())

        self.assertEqual(sleep_values, [1])

    def test_cli_default_and_override(self):
        self.assertEqual(emulator.parse_options([]).time_scale, 1.0)
        self.assertEqual(
            emulator.parse_options(["--time-scale", "0.02"]).time_scale,
            0.02,
        )
        self.assertEqual(
            emulator.parse_options([
                "--machine-variant", "CRX80"
            ]).machine_variant,
            "CRX80",
        )

    def test_factory_propagates_scale_to_all_six_heads(self):
        fake_heads = []

        class FakeWsHead:

            def __init__(self, index, time_scale):
                self.index = index
                self.time_scale = time_scale
                fake_heads.append(self)

            def command_watcher(self):
                return (self.index, self.time_scale)

        with mock.patch.object(
            emulator, "MachineHeadMockupWsSocket", FakeWsHead
        ):
            tasks = emulator.create_and_run_tasks(time_scale=0.05)

        self.assertEqual(
            tasks, [(index, 0.05) for index in range(6)]
        )
        self.assertEqual(len(fake_heads), 6)

    def test_factory_selects_physical_head_indices_for_each_variant(self):
        class FakeWsHead:

            def __init__(self, index, time_scale):
                self.index = index
                self.time_scale = time_scale

            def command_watcher(self):
                return self.index

        expected = {
            "CR4": [0, 1, 4, 5],
            "CRX60": [0, 2, 4],
            "CRX80": [0, 2, 4, 6],
        }
        with mock.patch.object(
                emulator, "MachineHeadMockupWsSocket", FakeWsHead):
            for variant, indices in expected.items():
                with self.subTest(variant=variant):
                    self.assertEqual(
                        emulator.create_and_run_tasks(
                            time_scale=0.05,
                            machine_variant=variant,
                        ),
                        indices,
                    )

    def test_crx80_g_head_emulates_linear_output_sensor(self):
        with mock.patch("builtins.open", mock.mock_open(read_data="[]")):
            head = emulator.MachineHeadMockup(6, time_scale=0.05)

        self.assertEqual(head.letter, "G")
        head.dump_status = mock.AsyncMock()
        head.status["jar_photocells_status"] = (
            emulator.DISPENSING_POSITION_MASK
        )
        head.do_move_by_crx_outputs(output_number=1, output_action=2)
        self.loop.run_until_complete(asyncio.sleep(0))

        self.assertTrue(
            head.status["jar_photocells_status"]
            & emulator.LOAD_LIFTER_ROLLER_MASK
        )


if __name__ == "__main__":
    unittest.main()
