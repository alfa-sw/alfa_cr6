# coding: utf-8

"""Test di sincronizzazione e trasferimento carosello senza motori o PLC.

Matrice di copertura del bug ``busy_head_A`` e dei cleanup confinanti:

+------------------------------------------+----------------------+-----------------------------------------------+
| Scenario                                 | Coperto              | Comportamento verificato                      |
+==========================================+======================+===============================================+
| Cancellazione durante ``IN -> A``        | Sì                   | Ferma i rulli, libera ``busy_head_A`` e       |
|                                          |                      | consente il passaggio dello shuttle.          |
+------------------------------------------+----------------------+-----------------------------------------------+
| Shuttle rimosso o fotocellula A non      | Sì, sensore simulato | Il timeout ferma i rulli e libera              |
| raggiunta                                |                      | ``busy_head_A``.                              |
+------------------------------------------+----------------------+-----------------------------------------------+
| Errore del controller durante l'avvio    | Sì                   | Il cleanup ferma entrambe le uscite e libera  |
| ``IN -> A``                              |                      | ``busy_head_A``.                              |
+------------------------------------------+----------------------+-----------------------------------------------+
| Cancellazione durante l'allarme          | Sì                   | Il ``finally`` esterno libera                 |
| double-can                               |                      | ``busy_head_A``.                              |
+------------------------------------------+----------------------+-----------------------------------------------+
| Cancellazione durante ``A -> B``         | Sì, cleanup          | Ferma i rulli sorgente e destinazione.        |
|                                          | preesistente         |                                               |
+------------------------------------------+----------------------+-----------------------------------------------+
| Errore durante un comando di stop        | Parziale             | Tenta comunque l'altro stop e libera il flag; |
|                                          |                      | lo stop fisico richiede hardware.             |
+------------------------------------------+----------------------+-----------------------------------------------+
| Diagnostica ``busy_head_A``              | Sì                   | Logga acquisizione e rilascio del flag,       |
|                                          |                      | includendo l'esito del movimento.             |
+------------------------------------------+----------------------+-----------------------------------------------+
| ``kill -9``, power loss o controller     | No                   | Un ``finally`` Python non può garantire       |
| irraggiungibile                          |                      | l'esecuzione o lo stop fisico.                |
+------------------------------------------+----------------------+-----------------------------------------------+
"""

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

    def _install_move_01_02_state(self, settings=None):
        self.carousel.busy_head_A = False
        self.carousel.machine_variant = "CRX60"
        self.carousel.settings = settings or types.SimpleNamespace()
        self.carousel.double_can_alert = False
        self.carousel.timer_01_02 = 0

        async def wait_for_available(_self, jar, letter, extra_check=None):
            self.assertEqual(letter, "A")
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

    def test_source_start_failure_stops_both_and_skips_destination_start(self):
        jar = FakeJar(position="A")
        self._install_availability_check()

        async def fail_source_start(
                output_number, output_action, timeout=30, silent=True):
            self.head_a.command_log.append(
                (output_number, output_action, timeout, silent)
            )
            return output_action == 0

        self.head_a.crx_outputs_management = fail_source_start

        result = self._run(
            CarouselMotor.move_from_to(self.carousel, jar, "A", "B")
        )

        self.assertFalse(result)
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_a.command_log],
            [(0, 1), (0, 0)],
        )
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_b.command_log],
            [(0, 0)],
        )
        self.assertEqual(self.position_updates, [])

    def test_destination_start_failure_stops_both_without_waiting_sensor(self):
        jar = FakeJar(position="A")
        self._install_availability_check()

        async def fail_destination_start(
                output_number, output_action, timeout=30, silent=True):
            self.head_b.command_log.append(
                (output_number, output_action, timeout, silent)
            )
            return output_action == 0

        self.head_b.crx_outputs_management = fail_destination_start

        result = self._run(
            CarouselMotor.move_from_to(self.carousel, jar, "A", "B")
        )

        self.assertFalse(result)
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_a.command_log],
            [(0, 1), (0, 0)],
        )
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_b.command_log],
            [(0, 2), (0, 0)],
        )
        self.assertEqual(self.head_b.wait_log, [])
        self.assertEqual(self.position_updates, [])

    def test_cancelled_move_01_02_releases_head_and_allows_next_can(self):
        first_jar = FakeJar(position="IN")
        second_jar = FakeJar(position="IN")
        self._install_move_01_02_state()

        first_wait_started = asyncio.Event()
        wait_calls = 0

        async def cancellable_photocell_wait(
                bit_name, on=True, timeout=None, show_alert=True):
            nonlocal wait_calls
            wait_calls += 1
            self.head_a.wait_log.append(
                (bit_name, on, timeout, show_alert)
            )
            if wait_calls == 1:
                first_wait_started.set()
                await asyncio.Event().wait()
            return True

        self.head_a.wait_for_jar_photocells_status = (
            cancellable_photocell_wait
        )

        async def cancel_first_then_move_second():
            first_task = asyncio.create_task(
                CarouselMotor.move_01_02(self.carousel, first_jar)
            )
            await first_wait_started.wait()
            self.assertTrue(self.carousel.busy_head_A)

            first_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first_task

            self.assertFalse(self.carousel.busy_head_A)
            self.assertEqual(
                self.head_a.status["crx_outputs_status"], 0
            )

            return await CarouselMotor.move_01_02(
                self.carousel, second_jar
            )

        with self.assertLogs(level="WARNING") as captured_logs:
            result = self._run(cancel_first_then_move_second())

        self.assertTrue(result)
        self.assertFalse(self.carousel.busy_head_A)
        self.assertEqual(wait_calls, 2)
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_a.command_log],
            [
                (1, 2), (0, 2), (1, 0), (0, 0),
                (1, 2), (0, 2), (1, 0), (0, 0),
            ],
        )
        self.assertEqual(second_jar.position, "IN")
        self.assertEqual(self.position_updates[-1]["pos"], "A")
        logs = "\n".join(captured_logs.output)
        self.assertIn(
            "busy_head_A=True: IN -> A started", logs
        )
        self.assertIn(
            "busy_head_A=False: IN -> A released; outcome=cancelled", logs
        )
        self.assertIn(
            "busy_head_A=False: IN -> A released; outcome=completed", logs
        )

    def test_move_01_02_sensor_timeout_releases_head_and_stops_outputs(self):
        jar = FakeJar(position="IN")
        self._install_move_01_02_state()
        self.head_a.queue_wait_results(False)

        result = self._run(
            CarouselMotor.move_01_02(self.carousel, jar)
        )

        self.assertFalse(result)
        self.assertFalse(self.carousel.busy_head_A)
        self.assertEqual(self.head_a.status["crx_outputs_status"], 0)
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_a.command_log],
            [(1, 2), (0, 2), (1, 0), (0, 0)],
        )

    def test_move_01_02_start_error_releases_head_and_stops_outputs(self):
        jar = FakeJar(position="IN")
        self._install_move_01_02_state()
        original_command = self.head_a.crx_outputs_management

        async def fail_input_start(
                output_number, output_action, timeout=30, silent=True):
            if (output_number, output_action) == (1, 2):
                self.head_a.command_log.append(
                    (output_number, output_action, timeout, silent)
                )
                raise RuntimeError("emulated input roller start failure")
            return await original_command(
                output_number, output_action, timeout, silent
            )

        self.head_a.crx_outputs_management = fail_input_start

        with self.assertRaisesRegex(RuntimeError, "start failure"):
            self._run(CarouselMotor.move_01_02(self.carousel, jar))

        self.assertFalse(self.carousel.busy_head_A)
        self.assertEqual(self.head_a.status["crx_outputs_status"], 0)
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_a.command_log],
            [(1, 2), (1, 0), (0, 0)],
        )

    def test_cancelled_double_can_alert_releases_busy_head_a(self):
        jar = FakeJar(position="IN")
        self._install_move_01_02_state(
            types.SimpleNamespace(MOVE_01_02_TIME_INTERVAL=999)
        )
        self.head_a.queue_wait_results(True)
        alert_started = asyncio.Event()

        async def wait_for_operator(*_args, **_kwargs):
            alert_started.set()
            await asyncio.Event().wait()

        self.carousel.wait_for_carousel_not_frozen = wait_for_operator

        async def cancel_during_alert():
            task = asyncio.create_task(
                CarouselMotor.move_01_02(self.carousel, jar)
            )
            await alert_started.wait()
            self.assertTrue(self.carousel.busy_head_A)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self._run(cancel_during_alert())

        self.assertFalse(self.carousel.busy_head_A)
        self.assertEqual(self.head_a.status["crx_outputs_status"], 0)

    def test_move_01_02_input_stop_error_still_stops_head_a_and_releases_flag(self):
        jar = FakeJar(position="IN")
        self._install_move_01_02_state()
        self.head_a.queue_wait_results(True)
        original_command = self.head_a.crx_outputs_management

        async def fail_input_stop(
                output_number, output_action, timeout=30, silent=True):
            if (output_number, output_action) == (1, 0):
                self.head_a.command_log.append(
                    (output_number, output_action, timeout, silent)
                )
                raise RuntimeError("emulated input roller stop failure")
            return await original_command(
                output_number, output_action, timeout, silent
            )

        self.head_a.crx_outputs_management = fail_input_stop

        with self.assertRaisesRegex(RuntimeError, "stop failure"):
            self._run(CarouselMotor.move_01_02(self.carousel, jar))

        self.assertFalse(self.carousel.busy_head_A)
        self.assertEqual(
            self.head_a.status["crx_outputs_status"] & 0x01, 0
        )
        self.assertEqual(
            [(number, action) for number, action, _timeout, _silent
             in self.head_a.command_log][-2:],
            [(1, 0), (0, 0)],
        )

    def test_cancelled_move_a_to_b_stops_both_heads(self):
        jar = FakeJar(position="A")
        self._install_availability_check()
        wait_started = asyncio.Event()

        async def cancellable_photocell_wait(
                bit_name, on=True, timeout=None, show_alert=True):
            self.head_b.wait_log.append(
                (bit_name, on, timeout, show_alert)
            )
            wait_started.set()
            await asyncio.Event().wait()

        self.head_b.wait_for_jar_photocells_status = (
            cancellable_photocell_wait
        )

        async def cancel_transfer():
            task = asyncio.create_task(
                CarouselMotor.move_from_to(
                    self.carousel, jar, "A", "B"
                )
            )
            await wait_started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self._run(cancel_transfer())

        self.assertEqual(self.head_a.status["crx_outputs_status"], 0)
        self.assertEqual(self.head_b.status["crx_outputs_status"], 0)

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
