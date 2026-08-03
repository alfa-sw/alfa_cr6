# coding: utf-8

"""Test di sincronizzazione e trasferimento carosello senza motori o PLC."""

import asyncio
import types
import unittest
from unittest import mock

import alfa_CR6_backend.carousel_motor as carousel_module
from alfa_CR6_backend.carousel_motor import CarouselMotor
from alfa_CR6_test.hardware_fakes import FakeJar, FakeMachineHead, VirtualClock


class _MainWindow:

    def __init__(self):
        self.alerts = []

    def open_alert_dialog(self, *args, **kwargs):
        self.alerts.append((args, kwargs))


class TestCarouselWaitForCondition(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.carousel = CarouselMotor.__new__(CarouselMotor)
        self.carousel.main_window = _MainWindow()
        self.carousel.exceptions = []
        self.carousel.handle_exception = self.carousel.exceptions.append

    def tearDown(self):
        self.loop.close()

    def _run(self, coro, clock):
        with mock.patch.object(carousel_module.time, "time", clock.time), \
                mock.patch.object(carousel_module.asyncio, "sleep", clock.sleep):
            return self.loop.run_until_complete(coro)

    def test_requires_consecutive_stable_samples_and_calls_callback_once(self):
        samples = iter((True, True, False, True, True, True))
        state = {"value": False}
        callback_calls = []

        def advance(_):
            state["value"] = next(samples, True)

        clock = VirtualClock(on_sleep=advance)
        # La prima valutazione avviene prima del primo sleep.
        advance(0)

        result = self._run(
            self.carousel.wait_for_condition(
                lambda: state["value"], timeout=1, stability_count=3,
                step=0.01, callback=lambda: callback_calls.append(True)
            ),
            clock,
        )

        self.assertTrue(result)
        self.assertEqual(callback_calls, [True])
        self.assertEqual(clock.sleep_calls, 5)
        self.assertEqual(self.carousel.exceptions, [])

    def test_break_condition_aborts_without_operator_alert(self):
        clock = VirtualClock()

        result = self._run(
            self.carousel.wait_for_condition(
                lambda: False, timeout=10, show_alert=True,
                break_condition=lambda: True
            ),
            clock,
        )

        self.assertFalse(result)
        self.assertEqual(clock.sleep_calls, 0)
        self.assertEqual(self.carousel.main_window.alerts, [])

    def test_timeout_can_raise_operator_alert(self):
        clock = VirtualClock()

        result = self._run(
            self.carousel.wait_for_condition(
                lambda: False, timeout=0.025, show_alert=True,
                extra_info="sensor A", step=0.01
            ),
            clock,
        )

        self.assertIsNone(result)
        self.assertEqual(len(self.carousel.main_window.alerts), 1)
        self.assertIn("sensor A", self.carousel.main_window.alerts[0][0][0])


class TestCarouselTransfers(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.carousel = CarouselMotor.__new__(CarouselMotor)
        self.head_a = FakeMachineHead("A")
        self.head_b = FakeMachineHead("B")
        self.carousel.machine_head_dict = {0: self.head_a, 1: self.head_b}
        self.carousel.get_machine_head_by_letter = lambda name: {
            "A": self.head_a, "B": self.head_b
        }[name]
        self.carousel._test_runners = {}
        self.carousel.get_jar_runners = lambda: self.carousel._test_runners
        self.position_updates = []
        self.carousel.update_jar_position = (
            lambda **kwargs: self.position_updates.append(kwargs)
        )

    def tearDown(self):
        self.loop.close()

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    def _install_availability_check(self, available=True):
        async def wait_for_available(_self, jar, letter, extra_check=None):
            self.assertEqual(letter, "B")
            if not available:
                return False
            return bool(extra_check is None or extra_check())

        self.carousel.wait_for_dispense_position_available = types.MethodType(
            wait_for_available, self.carousel
        )

    def test_positions_already_engaged_ignores_current_jar(self):
        current = FakeJar(position="A")
        other = FakeJar(position="B")
        self.carousel._test_runners = {
            "current": {"jar": current},
            "other": {"jar": other},
        }

        self.assertTrue(
            CarouselMotor.positions_already_engaged(
                self.carousel, ["A", "B"], jar=current
            )
        )
        self.assertFalse(
            CarouselMotor.positions_already_engaged(
                self.carousel, ["A"], jar=current
            )
        )

    def test_successful_transfer_starts_then_stops_both_rollers(self):
        jar = FakeJar(position="A")
        self.head_b.queue_wait_results(True)
        self._install_availability_check()

        result = self._run(
            CarouselMotor.move_from_to(self.carousel, jar, "A", "B")
        )

        self.assertTrue(result)
        self.assertEqual(
            [(n, action) for n, action, _timeout, _silent in self.head_a.command_log],
            [(0, 1), (0, 0)],
        )
        self.assertEqual(
            [(n, action) for n, action, _timeout, _silent in self.head_b.command_log],
            [(0, 2), (0, 0)],
        )
        self.assertEqual(
            self.head_b.wait_log,
            [("JAR_DISPENSING_POSITION_PHOTOCELL", True, 45, True)],
        )
        self.assertEqual(self.position_updates[0]["pos"], "B")
        self.assertIs(self.position_updates[0]["machine_head"], self.head_b)

    def test_sensor_timeout_still_stops_both_rollers(self):
        jar = FakeJar(position="A")
        self.head_b.queue_wait_results(False)
        self._install_availability_check()

        result = self._run(
            CarouselMotor.move_from_to(self.carousel, jar, "A", "B")
        )

        self.assertFalse(result)
        self.assertEqual(self.head_a.status["crx_outputs_status"], 0)
        self.assertEqual(self.head_b.status["crx_outputs_status"], 0)
        self.assertEqual(self.position_updates, [])

    def test_panel_interlock_prevents_any_motor_command(self):
        jar = FakeJar(position="A")
        self.head_b.status["panel_table_status"] = True
        self._install_availability_check()

        result = self._run(
            CarouselMotor.move_from_to(
                self.carousel, jar, "A", "B",
                check_lower_heads_panel_table_status=True
            )
        )

        self.assertFalse(result)
        self.assertEqual(self.head_a.command_log, [])
        self.assertEqual(self.head_b.command_log, [])
        self.assertEqual(self.position_updates, [])

    def test_alarm_923_interlock_prevents_any_motor_command(self):
        jar = FakeJar(position="A")
        self.head_a.alarm_923 = True
        self._install_availability_check()

        result = self._run(
            CarouselMotor.move_from_to(self.carousel, jar, "A", "B")
        )

        self.assertFalse(result)
        self.assertEqual(self.head_a.command_log, [])
        self.assertEqual(self.head_b.command_log, [])


if __name__ == "__main__":
    unittest.main()
