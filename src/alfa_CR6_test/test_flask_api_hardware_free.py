# coding: utf-8

"""API HTTP verificata con Flask test client e Redis/DB sostituiti da fake."""

import json
import types
import unittest
from unittest import mock

from flask import Flask

import alfa_CR6_flask.api as api_module


class _Redis:

    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)


class _Query:

    def filter(self, *_args):
        return self

    def all(self):
        return []


class _Session:

    @staticmethod
    def query(*_args):
        return _Query()


class TestFlaskApiHardwareFree(unittest.TestCase):

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.redis = _Redis()
        self.redis_patch = mock.patch.object(
            api_module, "REDIS_BUS", self.redis
        )
        self.redis_patch.start()
        api_module.init_restful_api(
            self.app, types.SimpleNamespace(session=_Session())
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.redis_patch.stop()

    def test_head_status_returns_controller_payload(self):
        payload = {"status_level": "STANDBY", "error_code": 0}
        self.redis.values["device:machine:status@52"] = json.dumps(payload).encode()

        response = self.client.get("/api/v1/head_status/2")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"], payload)

    def test_head_status_missing_is_a_structured_404(self):
        response = self.client.get("/api/v1/head_status/4")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json(), {
            "status": "error",
            "message": "Head 4 not available",
            "data": None,
        })

    def test_head_status_is_read_only(self):
        for method in (self.client.post, self.client.put,
                       self.client.patch, self.client.delete):
            with self.subTest(method=method.__name__):
                response = method("/api/v1/head_status/1")
                self.assertEqual(response.status_code, 405)
                self.assertEqual(
                    response.get_json(), {"message": "Method Not Allowed"}
                )

    def test_filtered_orders_requires_at_least_one_filter(self):
        response = self.client.get("/api/v1/filtered_orders")

        self.assertEqual(response.status_code, 400)
        self.assertIn("filter parameters are required", response.get_json()["error"])

    def test_filtered_orders_rejects_bad_time_window(self):
        response = self.client.get(
            "/api/v1/filtered_orders?last_hours_interval=not-a-number"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("must be an integer", response.get_json()["error"])

    def test_filtered_orders_rejects_unknown_model_field(self):
        response = self.client.get(
            "/api/v1/filtered_orders?field_that_does_not_exist=x"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("not a valid filter", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
