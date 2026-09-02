# coding: utf-8

"""Componenti deterministici condivisi dai test che sostituiscono la CR6."""

from collections import deque


class VirtualClock:
    """Clock asincrono senza attese reali, con hook a ogni campionamento."""

    def __init__(self, on_sleep=None):
        self.now = 0.0
        self.sleep_calls = 0
        self.on_sleep = on_sleep

    def time(self):
        return self.now

    async def sleep(self, delay):
        self.now += delay
        self.sleep_calls += 1
        if self.on_sleep:
            self.on_sleep(self.sleep_calls)


class FakeMachineHead:
    """Doppio di una testa: sensori impostabili e attuatori registrati."""

    def __init__(self, name, wait_results=()):
        self.name = name
        self.status = {
            "status_level": "STANDBY",
            "crx_outputs_status": 0,
            "panel_table_status": False,
        }
        self.photocells_status = {}
        self.jar_photocells_status = {}
        self.command_log = []
        self.wait_log = []
        self._wait_results = deque(wait_results)
        self.alarm_923 = False
        self.pigment_list = []

    def queue_wait_results(self, *results):
        self._wait_results.extend(results)

    def check_alarm_923(self):
        return self.alarm_923

    async def crx_outputs_management(
            self, output_number, output_action, timeout=30, silent=True
    ):
        self.command_log.append((output_number, output_action, timeout, silent))
        mask = 1 << output_number
        if output_action:
            self.status["crx_outputs_status"] |= mask
        else:
            self.status["crx_outputs_status"] &= ~mask
        return True

    async def wait_for_jar_photocells_status(
            self, bit_name, on=True, timeout=None, show_alert=True
    ):
        self.wait_log.append((bit_name, on, timeout, show_alert))
        if self._wait_results:
            result = self._wait_results.popleft()
        else:
            result = bool(self.jar_photocells_status.get(bit_name, False))
            result = result if on else not result
        return result


class FakeJar:
    """Jar minimale che conserva tutte le transizioni richieste dal flusso."""

    def __init__(self, position=None, status="NEW"):
        self.position = position
        self.status = status
        self.machine_head = None
        self.transitions = []

    def update_live(self, machine_head=None, status=None, pos=None, t0=None):
        if machine_head is not None:
            self.machine_head = machine_head
        if status is not None:
            self.status = status
        if pos is not None:
            self.position = pos
        self.transitions.append({
            "machine_head": machine_head,
            "status": status,
            "pos": pos,
            "t0": t0,
        })
