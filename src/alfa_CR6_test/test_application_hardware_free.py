# coding: utf-8

"""Calcoli applicativi e lifecycle teste senza QApplication o hardware."""

import asyncio
import types
import unittest
from unittest import mock

import alfa_CR6_backend.base_application as app_module
from alfa_CR6_backend.base_application import BaseApplication


class _PigmentHead:

    def __init__(self, name, pigment_name, specific_weight, available_weight):
        self.name = name
        self.pigment_name = pigment_name
        self.specific_weight = specific_weight
        self.available_weight = available_weight
        self.pigment_list = [{"name": pigment_name, "head": name}]

    def get_specific_weight(self, pigment_name):
        if pigment_name == self.pigment_name:
            return self.specific_weight
        return -1

    def get_available_weight(self, pigment_name):
        if pigment_name == self.pigment_name:
            return self.available_weight
        return 0

    def get_machine_pigments(self):
        return [self.pigment_name]

    def get_pigment_list(self):
        return [(self.pigment_name, "C01")]


class TestApplicationHardwareFree(unittest.TestCase):

    def setUp(self):
        self.app = BaseApplication.__new__(BaseApplication)

    def test_formula_is_distributed_across_heads_by_real_availability(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=6)
        head_b = _PigmentHead("B", "RED", specific_weight=1.0, available_weight=10)
        self.app.machine_head_dict = {0: head_a, 1: head_b}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=[], pigment_name="RED",
            requested_quantity_gr=10, remaining_volume=0,
            dispense_not_successful=False,
        )

        self.assertEqual(missing_gr, 0)
        self.assertEqual(total_ml, 7.0)
        self.assertEqual(volume_map, {"RED": {"A": 3.0, "B": 4.0}})

    def test_successful_retry_skips_heads_already_visited(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=20)
        head_b = _PigmentHead("B", "RED", specific_weight=1.0, available_weight=20)
        self.app.machine_head_dict = {0: head_a, 1: head_b}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=["A"], pigment_name="RED",
            requested_quantity_gr=5, remaining_volume=0,
            dispense_not_successful=False,
        )

        self.assertEqual((missing_gr, total_ml), (0, 5.0))
        self.assertEqual(volume_map, {"RED": {"B": 5.0}})

    def test_failed_dispense_can_reuse_a_visited_head(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=20)
        self.app.machine_head_dict = {0: head_a}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=["A"], pigment_name="RED",
            requested_quantity_gr=4, remaining_volume=0,
            dispense_not_successful=True,
        )

        self.assertEqual((missing_gr, total_ml), (0, 2.0))
        self.assertEqual(volume_map, {"RED": {"A": 2.0}})

    def test_insufficient_quantity_remains_explicit(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=4)
        self.app.machine_head_dict = {0: head_a}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=[], pigment_name="RED",
            requested_quantity_gr=10, remaining_volume=0,
            dispense_not_successful=False,
        )

        self.assertEqual(missing_gr, 6)
        self.assertEqual(total_ml, 2.0)
        self.assertEqual(volume_map, {"RED": {"A": 2.0}})

    def test_available_pigments_and_low_level_locations_span_all_heads(self):
        head_a = _PigmentHead("A", "RED", 1.0, 1)
        head_b = _PigmentHead("B", "BLUE", 1.0, 1)
        self.app.machine_head_dict = {0: head_a, 1: None, 2: head_b}

        self.assertEqual(
            set(self.app.get_available_pigments()), {"RED", "BLUE"}
        )
        self.assertEqual(
            self.app.build_insufficient_pigments_infos({"RED": 3, "BLUE": 2}),
            [("RED", "A"), ("BLUE", "B")],
        )


class TestMachineTaskSupervision(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self.loop.close()

    def test_machine_task_restarts_after_unexpected_failure(self):
        second_run_started = asyncio.Event()

        class FailingOnceMachineHead:

            def __init__(self, *_args, **_kwargs):
                self.run_calls = 0

            async def run(self):
                self.run_calls += 1
                if self.run_calls == 1:
                    raise RuntimeError("watchdog failure")
                second_run_started.set()
                await asyncio.Event().wait()

        machine = FailingOnceMachineHead()
        app = types.SimpleNamespace(
            machine_head_dict={}, on_head_msg_received=mock.AsyncMock()
        )

        async def no_retry_delay(_seconds):
            return None

        with mock.patch.object(app_module, "MachineHead", return_value=machine), \
                mock.patch.object(app_module.asyncio, "sleep", no_retry_delay):
            task = self.loop.create_task(
                BaseApplication._BaseApplication__create_machine_task(
                    app, 0, "127.0.0.1", 11001, 8081
                )
            )
            self.loop.run_until_complete(asyncio.wait_for(
                second_run_started.wait(), timeout=0.1
            ))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                self.loop.run_until_complete(task)

        self.assertIs(app.machine_head_dict[0], machine)
        self.assertEqual(machine.run_calls, 2)


if __name__ == "__main__":
    unittest.main()
