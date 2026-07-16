# coding: utf-8

"""Unit tests for BrowserPage's cooperative WebSocket lifecycle.

These tests use a fake QWebEnginePage and a fake WebSocket state machine: no
Chromium renderer or real network socket is required.
"""

import unittest

from PyQt5.QtCore import QUrl

from alfa_CR6_frontend.browser_page import BrowserPage


class FakeWebSocket:

    OPEN = "open"
    CLOSED = "closed"

    def __init__(self):
        self.state = self.OPEN
        self.suspended = False
        self.close_count = 0
        self.open_count = 0

    def suspend(self):
        if self.suspended:
            return
        self.suspended = True
        if self.state == self.OPEN:
            self.state = self.CLOSED
            self.close_count += 1

    def resume(self):
        if not self.suspended:
            return
        self.suspended = False
        if self.state == self.CLOSED:
            self.state = self.OPEN
            self.open_count += 1


class FakeWebEnginePage:

    def __init__(self, websocket, hooks_available=True, defer_callback=False):
        self.websocket = websocket
        self.hooks_available = hooks_available
        self.defer_callback = defer_callback
        self.pending_callback = None
        self.scripts = []

    def runJavaScript(self, script, callback=None):  # pylint: disable=invalid-name
        self.scripts.append(script)
        result = False
        if "alfaSuspendWS" in script:
            if self.hooks_available:
                self.websocket.suspend()
                result = True
        elif "alfaResumeWS" in script:
            if self.hooks_available:
                self.websocket.resume()
                result = True
        if callback:
            if self.defer_callback:
                self.pending_callback = lambda: callback(result)
            else:
                callback(result)

    def finish_javascript(self):
        callback = self.pending_callback
        self.pending_callback = None
        callback()


class FakeWebEngineView:

    def __init__(self, url, page):
        self._url = QUrl(url)
        self._page = page

    def page(self):
        return self._page

    def url(self):
        return self._url

    def setUrl(self, url):  # pylint: disable=invalid-name
        self._url = QUrl(url)


class FakeLabel:

    def __init__(self):
        self.text = ""

    def setText(self, text):  # pylint: disable=invalid-name
        self.text = text


class BrowserPageHarness:
    """Minimal object exposing the BrowserPage methods under test."""

    _should_blank_without_ws_hook = BrowserPage._should_blank_without_ws_hook
    _blank_internal_page_without_hook = BrowserPage._blank_internal_page_without_hook
    blank_webengine_view = BrowserPage.blank_webengine_view
    _suspend_page_ws = BrowserPage._suspend_page_ws
    _resume_page_ws = BrowserPage._resume_page_ws
    _BrowserPage__on_load_finish = BrowserPage._BrowserPage__on_load_finish

    def __init__(self, url, hooks_available=True, visible=True, defer_callback=False):
        self.websocket = FakeWebSocket()
        self.webengine_page = FakeWebEnginePage(
            self.websocket,
            hooks_available=hooks_available,
            defer_callback=defer_callback)
        self.webengine_view = FakeWebEngineView(url, self.webengine_page)
        self.q_url = QUrl(url)
        self.visible = visible
        self.url_lbl = FakeLabel()
        self.loaded = "loaded:"
        self._BrowserPage__load_started_at = None
        self._BrowserPage__load_started_url = url
        self._BrowserPage__load_requested_url = url
        self._BrowserPage__open_requested_at = None

    def isVisible(self):  # pylint: disable=invalid-name
        return self.visible

    def _BrowserPage__log_page_performance(self, _url, *_timings):
        pass


class BrowserPageWebSocketLifecycleTest(unittest.TestCase):

    def test_suspend_suspend_resume_resume_is_idempotent(self):
        browser = BrowserPageHarness(
            "http://127.0.0.1:8080/service_page/?light_service_page=1")

        browser._suspend_page_ws()
        browser._suspend_page_ws()
        self.assertEqual(browser.websocket.state, FakeWebSocket.CLOSED)
        self.assertEqual(browser.websocket.close_count, 1)

        browser._resume_page_ws()
        browser._resume_page_ws()
        self.assertEqual(browser.websocket.state, FakeWebSocket.OPEN)
        self.assertEqual(browser.websocket.open_count, 1)

    def test_load_finished_while_hidden_suspends_websocket(self):
        browser = BrowserPageHarness(
            "http://127.0.0.1:8080/service_page/?light_service_page=1",
            visible=False)

        browser._BrowserPage__on_load_finish(True)

        self.assertEqual(browser.websocket.state, FakeWebSocket.CLOSED)
        self.assertEqual(browser.websocket.close_count, 1)

    def test_internal_page_without_hook_falls_back_to_about_blank(self):
        browser = BrowserPageHarness(
            "http://127.0.0.1:8090/settings",
            hooks_available=False,
            visible=False)

        browser._suspend_page_ws()

        self.assertEqual(browser.webengine_view.url().toString(), "about:blank")
        self.assertEqual(browser.q_url.toString(), "about:blank")

    def test_external_page_without_hook_stays_resident(self):
        browser = BrowserPageHarness(
            "https://customer.example/session",
            hooks_available=False,
            visible=False)

        browser._suspend_page_ws()

        self.assertEqual(
            browser.webengine_view.url().toString(),
            "https://customer.example/session")

    def test_delayed_missing_hook_does_not_blank_page_that_became_visible(self):
        url = "http://127.0.0.1:8090/settings"
        browser = BrowserPageHarness(
            url,
            hooks_available=False,
            visible=False,
            defer_callback=True)

        browser._suspend_page_ws()
        browser.visible = True
        browser.webengine_page.finish_javascript()

        self.assertEqual(browser.webengine_view.url().toString(), url)

    def test_delayed_missing_hook_does_not_blank_changed_view_or_url(self):
        url = "http://127.0.0.1:8090/settings"

        for changed_context in ("url", "view"):
            with self.subTest(changed_context=changed_context):
                browser = BrowserPageHarness(
                    url,
                    hooks_available=False,
                    visible=False,
                    defer_callback=True)
                browser._suspend_page_ws()

                if changed_context == "url":
                    browser.webengine_view.setUrl(QUrl(
                        "http://127.0.0.1:8090/admin"))
                else:
                    browser.webengine_view = FakeWebEngineView(
                        "http://127.0.0.1:8090/admin",
                        FakeWebEnginePage(browser.websocket, hooks_available=False))

                browser.webengine_page.finish_javascript()

                self.assertNotEqual(
                    browser.webengine_view.url().toString(),
                    "about:blank")


if __name__ == "__main__":
    unittest.main()
