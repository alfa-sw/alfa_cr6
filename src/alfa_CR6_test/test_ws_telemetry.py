# coding: utf-8

# pylint: disable=missing-docstring

"""
Test end-to-end della telemetria e delle mitigazioni websocket di MachineHead.

CONTESTO (indagine "sent 1000 (OK); no close frame received"):
  quel messaggio e' lo str() di ConnectionClosed e implica che il CR6 ha
  inviato lui il close frame 1000 e che la testa non ha mai risposto.
  Comportamento atteso dopo le mitigazioni:

  - un messaggio difettoso NON butta giu' la connessione: viene registrato
    WS_MSG_EXCP (con last_recv_msg) e il loop continua a processare;
  - all'uscita dal contesto (WS_CTX_EXIT: exit_trigger, close_duration,
    stato handshake) self.websocket viene azzerato → i send_command nella
    finestra di riconnessione falliscono in modo silenzioso (ret None);
  - un send_command che becca comunque il socket morto (race oltre il guard)
    produce WS_SEND_FAIL ma NON arriva a handle_exception (niente modal).
"""

import asyncio
import json
import logging
import unittest

import websockets  # pylint: disable=import-error

import alfa_CR6_backend.machine_head as machine_head_module

TEST_PORT = 18931

# websockets >= 10 espone i close frame (close_rcvd/close_sent) e li cita nello
# str() di ConnectionClosed ("received 1011...", "sent 1000..."); su 8.1 (venv
# del banco; in prod docker gira 13.1) quegli attributi non esistono, quindi i
# campi telemetrici corrispondenti sono strutturalmente None e i messaggi hanno
# il formato "code = 1011 ...". Le asserzioni si adattano di conseguenza.
WS_HAS_CLOSE_FRAMES = int(websockets.__version__.split(".")[0]) >= 10


def close_frame_code(info):
    """Codice del close frame telemetrico, o None dove ws 8.1 non lo espone."""
    return info["code"] if info is not None else None


class FakeApp:

    MACHINE_HEAD_INDEX_TO_NAME_MAP = {0: "A_TEST"}

    def __init__(self):
        self.docs = []
        self.exceptions = []

    def insert_db_document(self, name, type, json_properties):  # pylint: disable=redefined-builtin,unused-argument
        self.docs.append((type, json.loads(json_properties)))

    def handle_exception(self, e):
        self.exceptions.append(e)

    async def wait_for_condition(self, condition=None, **kwargs):  # pylint: disable=unused-argument
        # come la vera: polla la condition fino al timeout (qui tagliato a 1s)
        for _ in range(20):
            if condition is not None and condition():
                return True
            await asyncio.sleep(0.05)
        return False


async def _handler(websocket, path):  # pylint: disable=unused-argument
    # payload malformato: nel client deve esplodere json.loads nel processing
    await websocket.send("{this is not json")
    # poi un messaggio valido: il loop deve essere sopravvissuto e processarlo
    await websocket.send(json.dumps({"type": "time", "value": 12345}))
    await websocket.wait_closed()


class TestWsTelemetry(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.fake_app = FakeApp()
        self._orig_get_app = machine_head_module.get_application_instance
        machine_head_module.get_application_instance = lambda: self.fake_app

    def tearDown(self):
        machine_head_module.get_application_instance = self._orig_get_app
        self.loop.close()

    def test_recovery_ctx_exit_and_send_fail(self):

        async def scenario():
            server = await websockets.serve(_handler, "127.0.0.1", TEST_PORT)
            try:
                head = machine_head_module.MachineHead(0, "127.0.0.1", TEST_PORT, 8080)
                run_task = asyncio.ensure_future(head.run())

                # il messaggio difettoso non deve chiudere la connessione:
                # il messaggio "time" successivo deve essere processato
                for _ in range(30):
                    if head.time_stamp == 12345:
                        break
                    await asyncio.sleep(0.1)
                self.assertEqual(head.time_stamp, 12345)
                self.assertIsNotNone(head.websocket)
                doc_types = [t for t, _ in self.fake_app.docs]
                self.assertIn("WS_MSG_EXCP", doc_types)
                self.assertNotIn("WS_CTX_EXIT", doc_types)

                # uscita dal contesto via cancel: WS_CTX_EXIT + socket azzerato
                run_task.cancel()
                try:
                    await run_task
                except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
                    pass
                self.assertIsNone(head.websocket)

                # send_command nella finestra di riconnessione: fast-fail silenzioso
                ret = await head.send_command("RESET", {"mode": 0})
                self.assertIsNone(ret)
                self.assertNotIn("WS_SEND_FAIL", [t for t, _ in self.fake_app.docs])
                self.assertEqual(self.fake_app.exceptions, [])

                # race oltre il guard: socket morto assegnato, send_command deve
                # produrre WS_SEND_FAIL senza passare da handle_exception
                stale = await websockets.connect(f"ws://127.0.0.1:{TEST_PORT}/x")
                await stale.close()
                head.websocket = stale
                ret = await head.send_command("RESET", {"mode": 0})
                self.assertIsNone(ret)
            finally:
                server.close()
                await server.wait_closed()

        self.loop.run_until_complete(scenario())

        docs = dict(self.fake_app.docs)

        excp = docs["WS_MSG_EXCP"]
        self.assertEqual(excp["phase"], "message processing (recovered)")
        self.assertEqual(excp["exception_type"], "JSONDecodeError")
        self.assertIn("{this is not json", excp["last_recv_msg"])

        ctx = docs["WS_CTX_EXIT"]
        self.assertEqual(ctx["exit_trigger"], "CancelledError")
        self.assertLess(ctx["close_duration"], 6)
        self.assertEqual(close_frame_code(ctx["websocket_close_sent"]),
                         1000 if WS_HAS_CLOSE_FRAMES else None)

        send_fail = docs["WS_SEND_FAIL"]
        self.assertEqual(send_fail["phase"], "send_command")
        self.assertEqual(send_fail["cmd_name"], "RESET")
        self.assertTrue("sent 1000 (OK)" in send_fail["error"]        # ws >= 10
                        or "code = 1000 (OK)" in send_fail["error"],  # ws 8.1
                        send_fail["error"])

        # in nessun caso l'operatore vede il modal (handle_exception mai chiamata)
        self.assertEqual(self.fake_app.exceptions, [])


class _LogCapture(logging.Handler):

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def root_messages(self):
        # solo i log del codice applicativo (root logger), non quelli di asyncio/websockets
        return [r.getMessage() for r in self.records if r.name == "root"]


class TestRunLoopClosePaths(unittest.TestCase):
    """I tre percorsi di chiusura visti dal message loop di run():

    - received 1001/1006/1011 -> ramo except ConnectionClosed: logging.error +
      WS_CTX_EXIT + WS_CLOSED su db, reconnect, MAI handle_exception;
    - comando nella finestra di riconnessione -> None silenzioso, zero log;
    - race oltre il guard -> logging.error + WS_SEND_FAIL, niente modal.
    """

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.fake_app = FakeApp()
        self._orig_get_app = machine_head_module.get_application_instance
        machine_head_module.get_application_instance = lambda: self.fake_app
        self.log_capture = _LogCapture()
        logging.getLogger().addHandler(self.log_capture)

    def tearDown(self):
        logging.getLogger().removeHandler(self.log_capture)
        machine_head_module.get_application_instance = self._orig_get_app
        self.loop.close()

    def _doc_types(self):
        return [t for t, _ in self.fake_app.docs]

    def _last_doc(self, doc_type):
        return [d for t, d in self.fake_app.docs if t == doc_type][-1]

    async def _wait_until(self, predicate, timeout=10):
        for _ in range(int(timeout / 0.1)):
            if predicate():
                return True
            await asyncio.sleep(0.1)
        return False

    def _run_close_path(self, handler, port, expect_reconnect=False):

        async def scenario():
            server = await websockets.serve(handler, "127.0.0.1", port)
            try:
                head = machine_head_module.MachineHead(0, "127.0.0.1", port, 8080)
                run_task = asyncio.ensure_future(head.run())

                ok = await self._wait_until(lambda: "WS_CLOSED" in self._doc_types())
                self.assertTrue(ok, f"WS_CLOSED not seen, docs:{self._doc_types()}")

                if expect_reconnect:
                    # run() dorme 5s nel ramo ConnectionClosed, poi riconnette
                    ok = await self._wait_until(
                        lambda: self._doc_types().count("WS_CONNECTED") >= 2, timeout=10)
                    self.assertTrue(ok, "no reconnection observed")

                run_task.cancel()
                try:
                    await run_task
                except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
                    pass
            finally:
                server.close()
                await server.wait_closed()

        self.loop.run_until_complete(scenario())

        # mai un dialog: handle_exception non chiamata in nessun percorso del loop
        self.assertEqual(self.fake_app.exceptions, [])
        self.assertIn("WS_CTX_EXIT", self._doc_types())
        return self._last_doc("WS_CLOSED")

    def test_received_1001_going_away(self):
        # il peer fa un restart pulito (SIGTERM gestito): close frame 1001

        async def handler(websocket, path):  # pylint: disable=unused-argument
            await websocket.close(1001)

        ws_closed = self._run_close_path(handler, 18941, expect_reconnect=True)
        self.assertEqual(ws_closed["close_code"], 1001)
        self.assertEqual(close_frame_code(ws_closed["close_rcvd"]),
                         1001 if WS_HAS_CLOSE_FRAMES else None)
        self.assertTrue(any("1001 (going away)" in m for m in self.log_capture.root_messages()))

    def test_received_1006_abnormal_closure(self):
        # il peer crasha: TCP abortito, nessun close frame

        async def handler(websocket, path):  # pylint: disable=unused-argument
            websocket.transport.abort()

        ws_closed = self._run_close_path(handler, 18942)
        self.assertEqual(ws_closed["close_code"], 1006)
        self.assertIsNone(ws_closed["close_rcvd"])
        self.assertTrue(any("no close frame received or sent" in m      # ws >= 10
                            or "connection closed abnormally" in m      # ws 8.1
                            for m in self.log_capture.root_messages()))

    def test_received_1011_internal_error(self):
        # il peer chiude con 1011 (es. keepalive ping timeout lato server)

        async def handler(websocket, path):  # pylint: disable=unused-argument
            await websocket.close(1011, "keepalive ping timeout")

        ws_closed = self._run_close_path(handler, 18943)
        self.assertEqual(ws_closed["close_code"], 1011)
        self.assertEqual(close_frame_code(ws_closed["close_rcvd"]),
                         1011 if WS_HAS_CLOSE_FRAMES else None)
        self.assertTrue(any("received 1011" in m       # ws >= 10
                            or "code = 1011" in m      # ws 8.1
                            for m in self.log_capture.root_messages()))

    def test_send_command_in_reconnect_window_is_silent(self):
        # dopo l'uscita dal contesto self.websocket e' None: il comando
        # ritorna None senza log, senza documenti, senza dialog

        async def handler(websocket, path):  # pylint: disable=unused-argument
            await websocket.wait_closed()

        async def scenario():
            server = await websockets.serve(handler, "127.0.0.1", 18944)
            try:
                head = machine_head_module.MachineHead(0, "127.0.0.1", 18944, 8080)
                run_task = asyncio.ensure_future(head.run())
                ok = await self._wait_until(lambda: head.websocket is not None, timeout=5)
                self.assertTrue(ok)

                run_task.cancel()
                try:
                    await run_task
                except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
                    pass
                self.assertIsNone(head.websocket)

                docs_before = len(self.fake_app.docs)
                self.log_capture.records.clear()
                ret = await head.send_command("RESET", {"mode": 0})

                self.assertIsNone(ret)
                self.assertEqual(self.log_capture.root_messages(), [])
                self.assertEqual(len(self.fake_app.docs), docs_before)
                self.assertEqual(self.fake_app.exceptions, [])
            finally:
                server.close()
                await server.wait_closed()

        self.loop.run_until_complete(scenario())

    async def _connect_head(self, port, handler):
        server = await websockets.serve(handler, "127.0.0.1", port)
        head = machine_head_module.MachineHead(0, "127.0.0.1", port, 8080)
        run_task = asyncio.ensure_future(head.run())
        ok = await self._wait_until(lambda: head.websocket is not None, timeout=5)
        self.assertTrue(ok, "head did not connect")
        return server, head, run_task

    @staticmethod
    async def _teardown(server, run_task):
        run_task.cancel()
        try:
            await run_task
        except (asyncio.CancelledError, Exception):  # pylint: disable=broad-except
            pass
        server.close()
        await server.wait_closed()

    def test_command_answered_returns_true(self):
        # controprova del percorso answer: il peer risponde -> ret True

        async def handler(websocket, path):  # pylint: disable=unused-argument
            async for message in websocket:
                cmd = json.loads(message)["msg_out_dict"]["command"]
                answer = {"status_code": 0, "command": cmd + "_END"}
                await websocket.send(json.dumps({"type": "answer", "value": answer}))

        async def scenario():
            server, head, run_task = await self._connect_head(18946, handler)
            try:
                ret = await head.send_command("RESET", {"mode": 0})
                self.assertTrue(ret)
                self.assertEqual(head.last_answer["command"], "RESET_END")
            finally:
                await self._teardown(server, run_task)

        self.loop.run_until_complete(scenario())
        self.assertEqual(self.fake_app.exceptions, [])

    def test_command_sent_but_peer_restarts_before_answer(self):
        # la send() riesce, il peer viene riavviato (close 1001) prima di
        # rispondere: l'answer non arriva mai -> ret False, niente eccezioni,
        # niente dialog; run() vede il 1001 e va in riconnessione

        async def handler(websocket, path):  # pylint: disable=unused-argument
            async for _ in websocket:
                await websocket.close(1001)     # restart prima dell'answer

        async def scenario():
            server, head, run_task = await self._connect_head(18947, handler)
            try:
                ret = await head.send_command("RESET", {"mode": 0})
                self.assertFalse(ret)
                self.assertIsNone(head.last_answer)

                # il loop ha gestito il 1001: contesto chiuso e socket azzerato
                ok = await self._wait_until(lambda: "WS_CLOSED" in self._doc_types())
                self.assertTrue(ok)
                self.assertIsNone(head.websocket)
            finally:
                await self._teardown(server, run_task)

        self.loop.run_until_complete(scenario())

        self.assertEqual(self._last_doc("WS_CLOSED")["close_code"], 1001)
        self.assertEqual(self.fake_app.exceptions, [])

    def test_send_command_race_past_guard_logs_and_documents(self):
        # socket morto oltre il guard: logging.error + WS_SEND_FAIL, niente modal

        async def handler(websocket, path):  # pylint: disable=unused-argument
            await websocket.wait_closed()

        async def scenario():
            server = await websockets.serve(handler, "127.0.0.1", 18945)
            try:
                head = machine_head_module.MachineHead(0, "127.0.0.1", 18945, 8080)
                stale = await websockets.connect("ws://127.0.0.1:18945/x")
                await stale.close()
                head.websocket = stale

                self.log_capture.records.clear()
                ret = await head.send_command("RESET", {"mode": 0})
                self.assertIsNone(ret)
            finally:
                server.close()
                await server.wait_closed()

        self.loop.run_until_complete(scenario())

        self.assertIn("WS_SEND_FAIL", self._doc_types())
        send_fail = self._last_doc("WS_SEND_FAIL")
        self.assertEqual(send_fail["cmd_name"], "RESET")
        self.assertTrue(any("closed websocket" in m for m in self.log_capture.root_messages()))
        self.assertEqual(self.fake_app.exceptions, [])


if __name__ == "__main__":
    unittest.main()
