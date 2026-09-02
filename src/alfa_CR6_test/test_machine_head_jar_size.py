# coding: utf-8

"""Test della lettura taglia barattolo senza una testa CR6 reale.

La testa espone due microswitch nel campo ``jar_photocells_status``. Questi
test riproducono sia i quattro stati elettrici sia il rimbalzo dei contatti
durante la stabilizzazione. Il tempo e' virtuale: la suite non apre socket e
non introduce le attese da 100 ms usate in produzione.

Esecuzione:
    PYTHONPATH=src /opt/alfa_cr6/venv/bin/python3 -m unittest \
        alfa_CR6_test.test_machine_head_jar_size -v
"""

import asyncio
import unittest
from unittest import mock

import alfa_CR6_backend.machine_head as machine_head_module


class _FakeApp:

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {0: "A_TEST"}


class _VirtualSampler:
    """Avanza il clock e applica una nuova lettura a ogni sleep."""

    def __init__(self, head, samples=()):
        self.head = head
        self.samples = iter(samples)
        self.now = 0.0
        self.sleep_calls = 0

    async def sleep(self, delay):
        self.now += delay
        self.sleep_calls += 1
        try:
            self.head.jar_size_detect = next(self.samples)
        except StopIteration:
            pass


class TestJarSizeMicroswitchDecode(unittest.TestCase):
    """Verifica la stessa decodifica effettuata sulla telemetria hardware."""

    def setUp(self):
        self.get_app_patch = mock.patch.object(
            machine_head_module, "get_application_instance", return_value=_FakeApp()
        )
        self.get_app_patch.start()
        self.head = machine_head_module.MachineHead(
            0, "127.0.0.1", 11001, 8081
        )
        # Evita il refresh REST pianificato soltanto alla prima telemetria.
        self.head.status = {
            "status_level": "STANDBY",
            "jar_photocells_status": 0,
            "crx_outputs_status": 0,
        }
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()
        self.get_app_patch.stop()

    def _update_sensor_mask(self, mask):
        status = {
            "status_level": "STANDBY",
            "photocells_status": 0,
            "jar_photocells_status": mask,
            "crx_outputs_status": 0,
        }
        self.loop.run_until_complete(self.head.update_status(status))

    def test_all_microswitch_combinations_map_to_four_package_indexes(self):
        cases = (
            (0x000, 0),
            (0x200, 1),
            (0x400, 2),
            (0x600, 3),
        )

        for sensor_mask, expected_size in cases:
            with self.subTest(sensor_mask=hex(sensor_mask)):
                self._update_sensor_mask(sensor_mask)
                self.assertEqual(self.head.jar_size_detect, expected_size)

    def test_microswitch_flags_are_exposed_individually(self):
        self._update_sensor_mask(0x600)

        self.assertEqual(
            self.head.jar_photocells_status["JAR_DETECTION_MICROSWITCH_1"], 1
        )
        self.assertEqual(
            self.head.jar_photocells_status["JAR_DETECTION_MICROSWITCH_2"], 1
        )

        self._update_sensor_mask(0)

        self.assertEqual(
            self.head.jar_photocells_status["JAR_DETECTION_MICROSWITCH_1"], 0
        )
        self.assertEqual(
            self.head.jar_photocells_status["JAR_DETECTION_MICROSWITCH_2"], 0
        )

    def test_other_photocells_do_not_change_detected_size(self):
        non_size_photocells = 0x001 | 0x010 | 0x100
        # 0x100 causerebbe la callback di transizione; lo rendiamo gia' attivo
        # nello stato precedente per concentrarci sulla decodifica dei bit 9/10.
        self.head.status["jar_photocells_status"] = 0x100

        self._update_sensor_mask(non_size_photocells | 0x400)

        self.assertEqual(self.head.jar_size_detect, 2)


class TestGetStabilizedJarSize(unittest.TestCase):
    """Simula letture stabili, contact bounce e timeout con clock virtuale."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.head = machine_head_module.MachineHead.__new__(
            machine_head_module.MachineHead
        )

    def tearDown(self):
        self.loop.close()

    def _run_with_sampler(self, sampler, **kwargs):
        with mock.patch.object(
            machine_head_module.time, "time", side_effect=lambda: sampler.now
        ), mock.patch.object(machine_head_module.asyncio, "sleep", sampler.sleep):
            return self.loop.run_until_complete(
                self.head.get_stabilized_jar_size(**kwargs)
            )

    def test_each_valid_size_is_returned_after_consecutive_equal_samples(self):
        for jar_size in range(4):
            with self.subTest(jar_size=jar_size):
                self.head.jar_size_detect = jar_size
                sampler = _VirtualSampler(self.head)

                result = self._run_with_sampler(
                    sampler, time_out_sec=1.0, max_cntr=3
                )

                self.assertEqual(result, jar_size)
                self.assertEqual(sampler.sleep_calls, 3)
                self.assertAlmostEqual(sampler.now, 0.3)

    def test_contact_bounce_restarts_consecutive_sample_counter(self):
        self.head.jar_size_detect = 0
        sampler = _VirtualSampler(self.head, samples=(1, 0, 1, 1, 1, 1))

        result = self._run_with_sampler(
            sampler, time_out_sec=2.0, max_cntr=3
        )

        self.assertEqual(result, 1)
        # Senza il reset del contatore sarebbero bastati tre sleep: i tre
        # cambi iniziali obbligano invece a ricominciare la stabilizzazione.
        self.assertEqual(sampler.sleep_calls, 6)

    def test_continuously_changing_signal_returns_none_on_timeout(self):
        self.head.jar_size_detect = 0
        sampler = _VirtualSampler(self.head, samples=(1, 0, 1, 0, 1))

        result = self._run_with_sampler(
            sampler, time_out_sec=0.25, max_cntr=5
        )

        self.assertIsNone(result)
        self.assertEqual(sampler.sleep_calls, 3)
        self.assertGreater(sampler.now, 0.25)

    def test_signal_lost_during_sampling_is_not_reported_as_a_size(self):
        self.head.jar_size_detect = 2
        sampler = _VirtualSampler(self.head, samples=(None, None, None))

        result = self._run_with_sampler(
            sampler, time_out_sec=1.0, max_cntr=2
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
