# coding: utf-8

"""Caratterizzazione delle race di MachineHead.send_command reale.

MOTIVO DEL TEST
---------------
``BaseApplication._send_attention_led_command`` avvia ``send_command`` tramite
``asyncio.ensure_future`` e non attende il risultato. La gestione a token
``_attention_led_requests`` evita invii duplicati mentre piu' richieste LED
sono contemporaneamente attive, ma non serializza le transizioni successive
del conteggio richieste::

    non vuoto -> vuoto -> non vuoto -> vuoto
                     0             1         0

Se la testa non ha ancora risposto al primo comando, per esempio per risposta
``status_code=254``, risposta persa, bus cache in timeout o firmware lento, le
tre transizioni producono tre coroutine concorrenti con Action 0, 1 e 0. Tutte
attendono sul medesimo ``MachineHead.last_answer``; una sola risposta positiva
con lo stesso nome comando puo' quindi risvegliarle tutte.

RIPRODUCIBILITA'
----------------
Sulla macchina la race non si presenta in ogni condizione: con firmware e
comunicazione sani la risposta normalmente arriva prima della transizione
successiva. E' pero' realisticamente raggiungibile nei flussi di refill,
freeze/unfreeze, retry o cancellazione che cambiano nuovamente lo stato LED
entro i 30 secondi di attesa di ``send_command``.

Nel test la stessa finestra viene resa deterministica: tre chiamate reali a
``MachineHead.send_command`` vengono portate tutte nello stato di attesa prima
di iniettare una sola risposta attraverso il vero ``__process_ws_msg``. Non
dipende quindi dalla velocita' del computer o da sleep temporizzati.

Questi test non propongono ancora una strategia di correlazione: riproducono
il comportamento corrente chiamando il codice produttivo con una app fake e
un websocket controllabile.
"""

import asyncio
import json
import unittest
from unittest import mock

import alfa_CR6_backend.machine_head as machine_head_module


class _ControlledWebSocket:
    """Registra gli invii; le risposte vengono iniettate separatamente."""

    def __init__(self):
        self.sent = []

    async def send(self, payload):
        self.sent.append(json.loads(payload)["msg_out_dict"])


class _FakeApp:

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {0: "A"}

    def __init__(self):
        self.exceptions = []

    def handle_exception(self, exc):
        self.exceptions.append(exc)

    @staticmethod
    async def wait_for_condition(condition, **_kwargs):
        # Mantiene il contratto di polling usato da send_command senza copiare
        # alcuna logica di correlazione. Il limite rende deterministico e
        # immediato anche lo scenario senza risposta.
        for _ in range(1000):
            if condition():
                return True
            await asyncio.sleep(0)
        return None


class TestRealMachineHeadSendCommandRace(unittest.TestCase):

    COMMAND = "SET_ATTENTION_REQUEST_STATUS"

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.app = _FakeApp()
        self.app_patch = mock.patch.object(
            machine_head_module, "get_application_instance",
            return_value=self.app,
        )
        self.app_patch.start()
        self.head = machine_head_module.MachineHead(
            0, "127.0.0.1", 11001, 8081
        )
        self.websocket = _ControlledWebSocket()
        self.head.websocket = self.websocket

    def tearDown(self):
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self.loop.close()
        self.app_patch.stop()

    def _run(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    async def _wait_for_sent_count(self, expected):
        for _ in range(1000):
            if len(self.websocket.sent) >= expected:
                return
            await asyncio.sleep(0)
        self.fail("solo {} comandi inviati, attesi {}".format(
            len(self.websocket.sent), expected
        ))

    async def _inject_answer(
            self, command=None, status_code=0, ref_id=None, error="no error"
    ):
        answer = {
            "status_code": status_code,
            "error": error,
            "command": command or self.COMMAND + "_END",
        }
        if ref_id is not None:
            answer["ref_id"] = ref_id
        await self.head._MachineHead__process_ws_msg(json.dumps({
            "type": "answer",
            "value": answer,
        }))

    def test_one_success_wakes_all_concurrent_same_command_requests(self):
        """Una sola conferma viene condivisa dai tre Action 0, 1 e 0.

        La sequenza rappresenta tre transizioni LED avvenute mentre le
        risposte precedenti sono ancora pendenti; ``_wait_for_sent_count``
        garantisce che questa precondizione sia soddisfatta prima di
        consegnare la sola conferma positiva.
        """

        async def scenario():
            tasks = [
                asyncio.ensure_future(self.head.send_command(
                    self.COMMAND, {"Action": action}
                ))
                for action in (0, 1, 0)
            ]
            await self._wait_for_sent_count(3)

            # Rappresenta la sola conferma osservata per il comando Action=1.
            await self._inject_answer(ref_id=371661)
            return await asyncio.gather(*tasks)

        results = self._run(scenario())

        self.assertEqual(results, [True, True, True])
        self.assertEqual(
            [message["params"]["Action"] for message in self.websocket.sent],
            [0, 1, 0],
        )
        self.assertEqual(self.head.last_answer["ref_id"], 371661)
        self.assertEqual(self.app.exceptions, [])

    def test_unrelated_answer_does_not_complete_real_send_command(self):
        async def scenario():
            task = asyncio.ensure_future(
                self.head.send_command(self.COMMAND, {"Action": 0})
            )
            await self._wait_for_sent_count(1)

            await self._inject_answer(command="RESET_END", ref_id=100)
            await asyncio.sleep(0)
            completed_on_unrelated_answer = task.done()

            await self._inject_answer(ref_id=101)
            return completed_on_unrelated_answer, await task

        completed_on_unrelated_answer, result = self._run(scenario())

        self.assertFalse(completed_on_unrelated_answer)
        self.assertTrue(result)
        self.assertEqual(self.head.last_answer["ref_id"], 101)

    def test_negative_answer_keeps_waiting_until_a_success_arrives(self):
        """Documenta che lo status 254 non conclude subito la richiesta."""

        async def scenario():
            task = asyncio.ensure_future(
                self.head.send_command(self.COMMAND, {"Action": 0})
            )
            await self._wait_for_sent_count(1)

            await self._inject_answer(
                command=self.COMMAND,
                status_code=254,
                ref_id=849126,
                error="time expired in waiting for reply in bus cache",
            )
            await asyncio.sleep(0)
            completed_on_negative_answer = task.done()

            await self._inject_answer(ref_id=371661)
            return completed_on_negative_answer, await task

        completed_on_negative_answer, result = self._run(scenario())

        self.assertFalse(completed_on_negative_answer)
        self.assertTrue(result)
        self.assertEqual(self.head.last_answer["ref_id"], 371661)

    def test_single_real_command_returns_true_on_its_answer(self):
        async def scenario():
            task = asyncio.ensure_future(
                self.head.send_command("RESET", {"mode": 0})
            )
            await self._wait_for_sent_count(1)
            await self._inject_answer(
                command="RESET_END", ref_id=999
            )
            return await task

        result = self._run(scenario())

        self.assertTrue(result)
        self.assertEqual(self.websocket.sent, [{
            "command": "RESET", "params": {"mode": 0},
        }])
        self.assertEqual(self.head.last_answer["ref_id"], 999)

    def test_scale_command_accepts_answer_without_end_suffix(self):
        async def scenario():
            task = asyncio.ensure_future(self.head.send_command(
                "STABLE_WEIGHT", {}, channel="scale"
            ))
            await self._wait_for_sent_count(1)
            await self._inject_answer(command="STABLE_WEIGHT", ref_id=1000)
            return await task

        self.assertTrue(self._run(scenario()))

    def test_machine_command_still_requires_end_suffix(self):
        async def scenario():
            task = asyncio.ensure_future(
                self.head.send_command("CAN_MOVEMENT", {})
            )
            await self._wait_for_sent_count(1)

            await self._inject_answer(command="CAN_MOVEMENT", ref_id=1001)
            await asyncio.sleep(0)
            completed_without_suffix = task.done()

            await self._inject_answer(command="CAN_MOVEMENT_END", ref_id=1002)
            return completed_without_suffix, await task

        completed_without_suffix, result = self._run(scenario())

        self.assertFalse(completed_without_suffix)
        self.assertTrue(result)

    def test_real_command_without_answer_times_out(self):
        result = self._run(
            self.head.send_command(self.COMMAND, {"Action": 0})
        )

        self.assertIsNone(result)
        self.assertEqual(len(self.websocket.sent), 1)
        self.assertIsNone(self.head.last_answer)
        self.assertEqual(self.app.exceptions, [])


if __name__ == "__main__":
    unittest.main()
