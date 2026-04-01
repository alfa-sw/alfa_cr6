# coding: utf-8

# pylint: disable=missing-docstring

"""
Regression test per la race condition in MachineHead.send_command().

FONTE DEL BUG (log 2026-03-26):
  3 chiamate fire-and-forget a _send_attention_led_command() generano 3 coroutine
  concorrenti per la stessa testa. Tutte e 3 aspettano su self.last_answer che
  è un attributo di istanza CONDIVISO. Quando arriva un qualsiasi
  SET_ATTENTION_REQUEST_STATUS_END con status_code:0, TUTTE e 3 si svegliano
  e restituiscono True — indipendentemente dall'Action che avevano inviato.

  Log: 3× "send_command() A ret:True, answer:{ref_id: 371661, Action:1_END}"
       mentre le coroutine Action:0 (batch1 e batch3) erano anche loro in attesa.

CODICE COINVOLTO:
  - machine_head.py:555  send_command()         → condition() non controlla ref_id
  - machine_head.py:574  self.last_answer = None → reset condiviso
  - carousel_motor.py:115 wait_for_condition()  → await asyncio.sleep(step)
  - base_application.py:1589 asyncio.ensure_future() → fire-and-forget
"""

import asyncio
import json
import time
import unittest


# ---------------------------------------------------------------------------
# Infrastruttura minimale: riproduce fedelmente la logica del codice reale
# ---------------------------------------------------------------------------

class FakeWebSocket:
    """Stub di websockets.WebSocketClientProtocol usato in send_command()."""

    def __init__(self):
        self.sent = []  # lista di {"command": ..., "params": {...}}

    async def send(self, payload):
        msg = json.loads(payload)
        self.sent.append(msg["msg_out_dict"])  # {"command": ..., "params": ...}


class FakeHead:
    """
    Riproduce fedelmente la logica di:
      - MachineHead.send_command()         (machine_head.py:555-598)
      - CarouselMotor.wait_for_condition() (carousel_motor.py:115-157)

    L'unica semplificazione è stability_count=1 (default reale: 3)
    per mantenere il test veloce; il bug esiste con qualsiasi valore.
    """

    def __init__(self, name):
        self.name = name
        self.last_answer = None          # ← stato condiviso tra le coroutine
        self.websocket = FakeWebSocket()
        self.app = self

    # -- riproduzione di carousel_motor.py:115 --
    async def wait_for_condition(
            self, condition, timeout, show_alert=False, extra_info="",
            stability_count=1, step=0.01, callback=None, break_condition=None):
        ret = None
        t0 = time.time()
        counter = 0
        while time.time() - t0 < timeout:
            if break_condition and break_condition():
                ret = False
                break
            if condition and condition():
                counter += 1
                if counter >= stability_count:
                    if callback:
                        callback()
                    ret = True
                    break
            else:
                counter = 0
            await asyncio.sleep(step)
        return ret

    # -- riproduzione di machine_head.py:555 --
    async def send_command(self, cmd_name, params, type_="command"):
        ret = None
        msg = {
            "type": type_,
            "channel": "machine",
            "msg_out_dict": {"command": cmd_name, "params": params},
        }
        if self.websocket:
            self.last_answer = None                           # ← reset condiviso
            ret = await self.websocket.send(json.dumps(msg))  # ← invia al firmware

            if type_ == "command":
                def condition():
                    # BUG: controlla solo il nome del comando, NON il ref_id
                    if (self.last_answer is not None
                            and self.last_answer["status_code"] == 0
                            and self.last_answer["command"] == cmd_name + "_END"):
                        return True
                    return False

                ret = await self.app.wait_for_condition(
                    condition, timeout=5, show_alert=False)

        return ret


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

class TestSendCommandRaceCondition(unittest.TestCase):

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_three_concurrent_coroutines_all_wake_on_single_success(self):
        """
        DIMOSTRA IL BUG.

        Scenario riprodotto dal log 2026-03-26 (HEAD A):
          C1 = batch1  Action:0  (bus timeout, nessuna conferma firmware)
          C2 = batch2  Action:1  (SUCCESS confermato dal firmware → ref 371661)
          C3 = batch3  Action:0  (bus timeout, nessuna conferma firmware)

        Con il bug attuale, tutte e 3 restituiscono True quando arriva
        il SUCCESS di C2, anche se C1 e C3 avevano inviato Action:0.

        Conseguenza: il firmware ha l'LED ACCESO (ultimo comando confermato =
        Action:1), ma l'applicazione crede che anche i due Action:0 abbiano
        avuto successo. LED rimane acceso.
        """
        head = FakeHead("A")
        CMD = "SET_ATTENTION_REQUEST_STATUS"
        results = {}

        async def run():
            # le 3 coroutine sono schedulate quasi simultaneamente,
            # come accade con 3 chiamate fire-and-forget
            c1 = asyncio.ensure_future(head.send_command(CMD, {"Action": 0}))
            c2 = asyncio.ensure_future(head.send_command(CMD, {"Action": 1}))
            c3 = asyncio.ensure_future(head.send_command(CMD, {"Action": 0}))

            # attende che tutte e 3 siano entrate in wait_for_condition()
            await asyncio.sleep(0.05)

            # simula l'arrivo della risposta del firmware per Action:1 (ref 371661)
            # → corrisponde al SUCCESS osservato nel log a 10:30:09
            head.last_answer = {
                "ref_id": 371661,
                "params": {},
                "status_code": 0,
                "error": "no error",
                "command": CMD + "_END",
            }

            results["c1"] = await c1
            results["c2"] = await c2
            results["c3"] = await c3

        self._run(run())

        # --- assert che dimostrano il bug ---

        # Tutte e 3 restituiscono True, anche quelle che avevano inviato Action:0
        self.assertTrue(results["c1"],
                        "C1 (Action:0, batch1) restituisce True: BUG confermato")
        self.assertTrue(results["c2"],
                        "C2 (Action:1, batch2) restituisce True: comportamento atteso")
        self.assertTrue(results["c3"],
                        "C3 (Action:0, batch3) restituisce True: BUG confermato")

        # Verifica che i 3 comandi siano stati inviati al firmware nell'ordine
        # atteso (Action:0, Action:1, Action:0)
        sent_actions = [m["params"]["Action"] for m in head.websocket.sent]
        self.assertEqual(sent_actions, [0, 1, 0],
                         f"Comandi inviati al firmware: {sent_actions}")

        # Il last_answer è quello di Action:1: l'ultimo stato confermato
        # dal firmware è LED ACCESO — ma l'applicazione crede che anche i
        # due Action:0 abbiano avuto successo
        self.assertEqual(head.last_answer["ref_id"], 371661)

    def test_last_answer_reset_by_later_coroutine_wipes_previous_success(self):
        """
        DIMOSTRA il secondo aspetto del bug: self.last_answer = None all'avvio
        di ogni send_command() azzera la risposta precedente.

        Se C1 (Action:0) ha già ricevuto il suo SUCCESS e C2 (Action:1) parte
        subito dopo, C2 resetta last_answer=None. Ora C1 non vedrà più il suo
        SUCCESS (già consumato) e aspetterà fino al timeout, mentre C2 attende
        la propria risposta.

        Questo meccanismo spiega perché, nel log, i timeout di batch1 (30s
        wait_for_condition) si mescolano con i SUCCESS di batch2.
        """
        head = FakeHead("A")
        CMD = "SET_ATTENTION_REQUEST_STATUS"
        results = {}

        async def run():
            # C1 parte e aspetta; dopo 0.03s arriva il suo SUCCESS
            c1 = asyncio.ensure_future(head.send_command(CMD, {"Action": 0}))
            await asyncio.sleep(0.03)

            # arriva il SUCCESS per C1 (Action:0)
            head.last_answer = {
                "ref_id": 100,
                "params": {},
                "status_code": 0,
                "error": "no error",
                "command": CMD + "_END",
            }
            # piccola pausa: C1 potrebbe non aver ancora verificato la condizione
            await asyncio.sleep(0.005)

            # C2 parte e AZZERA last_answer prima che C1 la verifichi
            # (simula il caso in cui il reset arriva nei 5ms di "finestra")
            c2 = asyncio.ensure_future(head.send_command(CMD, {"Action": 1}))

            # C2 porta avanti la propria risposta
            await asyncio.sleep(0.03)
            head.last_answer = {
                "ref_id": 200,
                "params": {},
                "status_code": 0,
                "error": "no error",
                "command": CMD + "_END",
            }

            results["c1"] = await asyncio.wait_for(c1, timeout=2.0)
            results["c2"] = await asyncio.wait_for(c2, timeout=2.0)

        self._run(run())

        # C2 restituisce True (ha il suo SUCCESS)
        self.assertTrue(results["c2"])
        # C1: se il suo SUCCESS è stato sovrascritto da C2, restituisce True
        # su quello di C2 (race); se l'ha catturato in tempo, True comunque.
        # In entrambi i casi ret:True — il bug è che non possiamo sapere
        # su quale risposta si è svegliato.
        self.assertTrue(results["c1"],
                        "C1 si è svegliato su un SUCCESS (ma quale?): ref non verificabile")

        # Verifica: i 2 comandi sono stati inviati
        sent_actions = [m["params"]["Action"] for m in head.websocket.sent]
        self.assertIn(0, sent_actions)
        self.assertIn(1, sent_actions)

    def test_single_command_no_concurrent_coroutines_works_correctly(self):
        """
        Caso base (nessuna coroutine concorrente): send_command() funziona
        correttamente quando non ci sono race condition.
        """
        head = FakeHead("A")
        CMD = "SET_ATTENTION_REQUEST_STATUS"

        async def run():
            c = asyncio.ensure_future(head.send_command(CMD, {"Action": 0}))
            await asyncio.sleep(0.05)
            head.last_answer = {
                "ref_id": 999,
                "params": {},
                "status_code": 0,
                "error": "no error",
                "command": CMD + "_END",
            }
            return await c

        result = self._run(run())
        self.assertTrue(result)
        self.assertEqual(head.websocket.sent[0]["params"]["Action"], 0)

    def test_timeout_when_no_response_arrives(self):
        """
        Verifica che send_command() restituisca None (non True) quando
        il firmware non risponde entro il timeout.
        """
        head = FakeHead("A")
        CMD = "SET_ATTENTION_REQUEST_STATUS"

        # Usa un timeout cortissimo (0.05s) per non rallentare la suite
        async def fast_send_command():
            ret = None
            msg = {
                "type": "command",
                "channel": "machine",
                "msg_out_dict": {"command": CMD, "params": {"Action": 0}},
            }
            head.last_answer = None
            await head.websocket.send(json.dumps(msg))

            def condition():
                return (head.last_answer is not None
                        and head.last_answer["status_code"] == 0
                        and head.last_answer["command"] == CMD + "_END")

            ret = await head.wait_for_condition(condition, timeout=0.05)
            return ret

        result = self._run(fast_send_command())
        self.assertIsNone(result,
                          "Nessuna risposta → send_command() deve restituire None")

    def test_status_code_254_does_not_satisfy_condition(self):
        """
        Verifica che una risposta con status_code:254 (bus cache timeout)
        non soddisfi la condition, lasciando la coroutine in attesa.
        Il comportamento è corretto, ma la coroutine continua ad aspettare
        fino al proprio timeout di 30s (o fino a che non arriva un 254
        per un altro ref che confonde il check sul solo nome del comando).
        """
        head = FakeHead("A")
        CMD = "SET_ATTENTION_REQUEST_STATUS"

        async def run():
            c = asyncio.ensure_future(head.send_command(CMD, {"Action": 0}))
            await asyncio.sleep(0.03)

            # arriva il timeout del bus (status_code:254) — NON deve soddisfare
            head.last_answer = {
                "ref_id": 849126,
                "params": {},
                "status_code": 254,
                "error": "time expired in waiting for reply in bus cache",
                "command": CMD,   # senza _END
            }

            await asyncio.sleep(0.03)

            # ora arriva il SUCCESS vero
            head.last_answer = {
                "ref_id": 371661,
                "params": {},
                "status_code": 0,
                "error": "no error",
                "command": CMD + "_END",
            }

            return await c

        result = self._run(run())
        self.assertTrue(result,
                        "Dopo il 254 la coroutine deve restare in attesa e poi "
                        "risvegliarsi sul SUCCESS successivo")


if __name__ == "__main__":
    unittest.main()
