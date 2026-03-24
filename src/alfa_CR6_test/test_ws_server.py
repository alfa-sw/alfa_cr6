# coding: utf-8

import asyncio
import json
import sys
import types
import unittest
from unittest import mock

if 'websockets' not in sys.modules:
    websockets_stub = types.ModuleType('websockets')
    websockets_stub.exceptions = types.SimpleNamespace(ConnectionClosed=Exception)
    sys.modules['websockets'] = websockets_stub

if 'redis' not in sys.modules:
    sys.modules['redis'] = types.ModuleType('redis')

if 'arabic_reshaper' not in sys.modules:
    sys.modules['arabic_reshaper'] = types.ModuleType('arabic_reshaper')

if 'bidi' not in sys.modules:
    bidi_stub = types.ModuleType('bidi')
    bidi_algorithm_stub = types.ModuleType('bidi.algorithm')
    bidi_algorithm_stub.get_display = lambda value: value
    bidi_stub.algorithm = bidi_algorithm_stub
    sys.modules['bidi'] = bidi_stub
    sys.modules['bidi.algorithm'] = bidi_algorithm_stub

if 'barcode' not in sys.modules:
    barcode_stub = types.ModuleType('barcode')
    barcode_stub.EAN13 = object
    barcode_stub.Code128 = object
    barcode_writer_stub = types.ModuleType('barcode.writer')
    barcode_writer_stub.ImageWriter = object
    sys.modules['barcode'] = barcode_stub
    sys.modules['barcode.writer'] = barcode_writer_stub

from alfa_CR6_backend.ws_server import WsMessageHandler, WsServer


class FakeWebSocket:

    def __init__(self):
        self.messages = []

    async def send(self, payload):
        self.messages.append(payload)


class TestWsMessageHandler(unittest.TestCase):

    def setUp(self):
        WsMessageHandler.settings = object()
        self.websocket = FakeWebSocket()

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_handle_msg_unknown_command_returns_bad_request(self):
        self._run(WsMessageHandler.handle_msg(
            json.dumps({"command": "no_such_command", "params": {}}),
            self.websocket,
            object(),
        ))

        self.assertEqual(len(self.websocket.messages), 1)
        self.assertEqual(json.loads(self.websocket.messages[0]), {"type": "error", "code": "bad_request"})

    def test_handle_msg_invalid_json_returns_bad_request(self):
        self._run(WsMessageHandler.handle_msg('{not json}', self.websocket, object()))

        self.assertEqual(len(self.websocket.messages), 1)
        self.assertEqual(json.loads(self.websocket.messages[0]), {"type": "error", "code": "bad_request"})

    def test_handle_msg_debug_command_returns_bad_request(self):
        self._run(WsMessageHandler.handle_msg(
            json.dumps({"debug_command": "1 + 1"}),
            self.websocket,
            object(),
        ))

        self.assertEqual(len(self.websocket.messages), 1)
        self.assertEqual(json.loads(self.websocket.messages[0]), {"type": "error", "code": "bad_request"})

    def test_handle_msg_handler_exception_returns_internal_error(self):
        original = getattr(WsMessageHandler, 'exploding', None)

        async def exploding(_cls, _msg_dict, _websocket):
            raise RuntimeError('boom')

        WsMessageHandler.exploding = classmethod(exploding)
        try:
            self._run(WsMessageHandler.handle_msg(
                json.dumps({"command": "exploding", "params": {}}),
                self.websocket,
                object(),
            ))
        finally:
            if original is None:
                delattr(WsMessageHandler, 'exploding')
            else:
                WsMessageHandler.exploding = original

        self.assertEqual(len(self.websocket.messages), 1)
        self.assertEqual(json.loads(self.websocket.messages[0]), {"type": "error", "code": "internal_error"})

    def test_handle_msg_valid_command_preserves_success_flow(self):
        original = getattr(WsMessageHandler, 'fake_ok', None)

        async def fake_ok(_cls, _msg_dict, ws):
            await ws.send(json.dumps({"type": "ok", "value": 1}))
            return 'OK'

        WsMessageHandler.fake_ok = classmethod(fake_ok)
        try:
            self._run(WsMessageHandler.handle_msg(
                json.dumps({"command": "fake_ok", "params": {}}),
                self.websocket,
                object(),
            ))
        finally:
            if original is None:
                delattr(WsMessageHandler, 'fake_ok')
            else:
                WsMessageHandler.fake_ok = original

        self.assertEqual(len(self.websocket.messages), 1)
        self.assertEqual(json.loads(self.websocket.messages[0]), {"type": "ok", "value": 1})


class TestWsBroadcast(unittest.TestCase):

    def setUp(self):
        self.server = WsServer.__new__(WsServer)
        self.server.ws_clients = set()
        self.server.__version__ = 'test-version'

    @staticmethod
    def _run(coro):
        return asyncio.run(coro)

    def test_broadcast_delivers_to_all_clients(self):
        ws1, ws2, ws3 = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
        self.server.ws_clients = {ws1, ws2, ws3}
        self._run(self.server._broadcast_raw('hello'))
        for ws in (ws1, ws2, ws3):
            self.assertEqual(ws.messages, ['hello'])

    def test_broadcast_removes_failing_client(self):
        good = FakeWebSocket()
        bad = FakeWebSocket()

        async def fail_send(_payload):
            raise ConnectionError('gone')

        bad.send = fail_send
        self.server.ws_clients = {good, bad}
        self._run(self.server._broadcast_raw('hello'))
        self.assertEqual(good.messages, ['hello'])
        self.assertNotIn(bad, self.server.ws_clients)
        self.assertIn(good, self.server.ws_clients)

    def test_broadcast_keeps_healthy_clients_when_other_times_out(self):
        good = FakeWebSocket()
        slow = FakeWebSocket()

        async def timeout_send(_payload):
            raise asyncio.TimeoutError()

        slow.send = timeout_send
        self.server.ws_clients = {good, slow}
        self._run(self.server._broadcast_raw('hello'))
        self.assertEqual(good.messages, ['hello'])
        self.assertIn(good, self.server.ws_clients)
        self.assertNotIn(slow, self.server.ws_clients)

    def test_broadcast_removes_slow_client(self):
        slow = FakeWebSocket()

        async def hang(_payload):
            await asyncio.sleep(60)

        slow.send = hang
        self.server.ws_clients = {slow}

        async def fake_wait_for(awaitable, timeout):
            self.assertEqual(timeout, 5)
            awaitable.close()
            raise asyncio.TimeoutError()

        with mock.patch('alfa_CR6_backend.ws_server.asyncio.wait_for', new=fake_wait_for):
            self._run(self.server._broadcast_raw('hello'))
        self.assertNotIn(slow, self.server.ws_clients)

    def test_broadcast_no_clients_is_noop(self):
        self._run(self.server._broadcast_raw('hello'))
        self.assertEqual(self.server.ws_clients, set())

    def test_broadcast_msg_wraps_payload_with_metadata(self):
        websocket = FakeWebSocket()
        self.server.ws_clients = {websocket}
        self.server._format_to_html = lambda type_, msg: f'rendered:{type_}:{msg["value"]}'

        fake_app = types.SimpleNamespace(carousel_frozen=False)
        with mock.patch('alfa_CR6_backend.ws_server.get_application_instance', return_value=fake_app), \
                mock.patch('alfa_CR6_backend.ws_server.time.strftime', return_value='2026-03-24 10:11:12 (UTC)'):
            ret = self._run(self.server.broadcast_msg('status', {'value': 7}))

        self.assertTrue(ret)
        self.assertEqual(len(websocket.messages), 1)

        payload = json.loads(websocket.messages[0])
        self.assertEqual(payload['type'], 'status')
        self.assertEqual(payload['value'], 'rendered:status:7')
        self.assertEqual(
            payload['server_time'],
            '2026-03-24 10:11:12 (UTC) - ver.:test-version - paused: False.',
        )

    def test_broadcast_msg_without_clients_returns_true_without_formatting(self):
        self.server._format_to_html = mock.Mock(side_effect=AssertionError('formatting should be skipped'))

        with mock.patch(
            'alfa_CR6_backend.ws_server.get_application_instance',
            side_effect=AssertionError('application lookup should be skipped'),
        ):
            ret = self._run(self.server.broadcast_msg('status', {'value': 7}))

        self.assertTrue(ret)


if __name__ == '__main__':
    unittest.main()
