#!/usr/bin/env python3
# coding: utf-8

"""Collect Chromium DevTools performance traces from the CR6 QtWebEngine.

Start CR6 with ``QTWEBENGINE_REMOTE_DEBUGGING=<port>``, then run this script
before touching a service-page button. Each matching navigation produces one
compact log line and one JSON payload containing navigation, paint, scripting,
style, layout, paint and compositor timings.
"""

import argparse
import asyncio
import gzip
import json
import statistics
import urllib.request

import websockets


TRACE_CATEGORIES = ",".join((
    "devtools.timeline",
    "disabled-by-default-devtools.timeline",
    "blink.user_timing",
    "loading",
))

TRACE_GROUPS = {
    "parse": {"ParseHTML"},
    "script": {
        "EvaluateScript",
        "FunctionCall",
        "RunMicrotasks",
        "TimerFire",
        "EventDispatch",
    },
    "style": {
        "RecalculateStyles",
        "UpdateLayoutTree",
        "ParseAuthorStyleSheet",
    },
    "layout": {"Layout"},
    "paint": {"Paint"},
    "composite": {"CompositeLayers"},
}


def _fetch_json(url):
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _round_ms(value):
    if value is None:
        return None
    return round(value, 2)


def _interval_union_ms(intervals):
    if not intervals:
        return 0.0
    merged = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start for start, end in merged) / 1000.0


def _trace_breakdown(events):
    intervals_by_thread = {}
    stacks = {}
    for event in sorted(events, key=lambda item: item.get("ts", 0)):
        name = event.get("name")
        group = next(
            (key for key, names in TRACE_GROUPS.items() if name in names),
            None)
        if group is None:
            continue
        thread = (event.get("pid"), event.get("tid"))
        phase = event.get("ph")
        if phase == "X" and event.get("dur"):
            intervals_by_thread.setdefault(thread, {}).setdefault(
                group, []).append(
                    (event["ts"], event["ts"] + event["dur"]))
        elif phase == "B":
            stacks.setdefault((thread, name), []).append(
                event.get("ts", 0))
        elif phase == "E":
            starts = stacks.get((thread, name))
            if starts:
                start = starts.pop()
                end = event.get("ts", start)
                if end > start:
                    intervals_by_thread.setdefault(
                        thread, {}).setdefault(
                            group, []).append((start, end))

    if not intervals_by_thread:
        return {group: 0.0 for group in TRACE_GROUPS}

    def activity(grouped):
        all_intervals = [
            interval
            for intervals in grouped.values()
            for interval in intervals
        ]
        return _interval_union_ms(all_intervals)

    # Prefer the renderer main thread that parsed the new document. Tracing starts
    # before the operator touches the screen; cropping at the first ParseHTML keeps
    # old-page/background work out of the measured navigation.
    candidates = [
        grouped
        for grouped in intervals_by_thread.values()
        if grouped.get("parse")
    ]
    grouped = max(candidates or intervals_by_thread.values(), key=activity)
    parse_start = min(
        (start for start, _ in grouped.get("parse", [])),
        default=None)

    def measured_intervals(group):
        intervals = grouped.get(group, [])
        if parse_start is None:
            return intervals
        return [
            (max(start, parse_start), end)
            for start, end in intervals
            if end > parse_start
        ]

    return {
        group: _round_ms(_interval_union_ms(measured_intervals(group)))
        for group in TRACE_GROUPS
    }


class DevToolsConnection:

    def __init__(self, websocket):
        self.websocket = websocket
        self.next_id = 1
        self.pending = {}
        self.events = asyncio.Queue()
        self.reader_task = None

    async def start(self):
        self.reader_task = asyncio.ensure_future(self._reader())

    async def close(self):
        if self.reader_task:
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
            except Exception:  # Chromium 69 may close without a close frame.
                pass
        await self.websocket.close()

    async def _reader(self):
        async for raw in self.websocket:
            message = json.loads(raw)
            message_id = message.get("id")
            if message_id in self.pending:
                future = self.pending.pop(message_id)
                if "error" in message:
                    future.set_exception(RuntimeError(message["error"]))
                else:
                    future.set_result(message.get("result") or {})
            else:
                await self.events.put(message)

    async def command(self, method, params=None):
        message_id = self.next_id
        self.next_id += 1
        future = asyncio.get_event_loop().create_future()
        self.pending[message_id] = future
        await self.websocket.send(json.dumps({
            "id": message_id,
            "method": method,
            "params": params or {},
        }))
        return await future


async def _performance_metrics(connection):
    result = await connection.command("Performance.getMetrics")
    return {
        metric["name"]: metric["value"]
        for metric in result.get("metrics") or []
    }


def _metric_delta(before, after, name):
    if name not in before or name not in after:
        return None
    return _round_ms((after[name] - before[name]) * 1000.0)


async def _page_timing(connection):
    expression = """
        new Promise(function (resolve) {
            function collect() {
                var n = performance.getEntriesByType("navigation")[0] || {};
                var paint = {};
                performance.getEntriesByType("paint").forEach(function (p) {
                    paint[p.name] = Math.round(p.startTime);
                });
                resolve({
                    responseEnd: Math.round(n.responseEnd || 0),
                    domInteractive: Math.round(n.domInteractive || 0),
                    domContentLoaded: Math.round(n.domContentLoadedEventEnd || 0),
                    loadEvent: Math.round(n.loadEventEnd || 0),
                    firstPaint: paint["first-paint"] || null,
                    firstContentfulPaint: paint["first-contentful-paint"] || null,
                    now: Math.round(performance.now())
                });
            }
            requestAnimationFrame(function () {
                requestAnimationFrame(collect);
            });
        })
    """
    result = await connection.command("Runtime.evaluate", {
        "expression": expression,
        "awaitPromise": True,
        "returnByValue": True,
    })
    return (
        result.get("result", {}).get("value") or {})


async def _navigation_state(connection):
    result = await connection.command("Runtime.evaluate", {
        "expression": """
            (function () {
                var timing = performance.timing || {};
                return {
                    navigationStart: timing.navigationStart || 0,
                    loadEventEnd: timing.loadEventEnd || 0,
                    url: location.href,
                    readyState: document.readyState
                };
            })()
        """,
        "returnByValue": True,
    })
    return result.get("result", {}).get("value") or {}


async def _start_trace(connection):
    await connection.command("Tracing.start", {
        "categories": TRACE_CATEGORIES,
        "options": "record-as-much-as-possible",
        "transferMode": "ReportEvents",
    })


async def _end_trace(connection):
    await connection.command("Tracing.end")
    events = []
    while True:
        message = await connection.events.get()
        method = message.get("method")
        if method == "Tracing.dataCollected":
            events.extend(message.get("params", {}).get("value") or [])
        elif method == "Tracing.tracingComplete":
            return events


async def _wait_for_event(connection, method, timeout=5):
    while True:
        message = await asyncio.wait_for(
            connection.events.get(), timeout=timeout)
        if message.get("method") == method:
            return message


def _median(values):
    values = [value for value in values if value is not None]
    return _round_ms(statistics.median(values)) if values else None


def _summary(results):
    fields = (
        "response_end_ms",
        "dom_interactive_ms",
        "load_event_ms",
        "first_contentful_paint_ms",
        "two_frames_complete_ms",
        "script_duration_ms",
        "style_duration_ms",
        "layout_duration_ms",
        "trace_parse_ms",
        "trace_paint_ms",
        "trace_composite_ms",
    )
    warm = results[1:] if len(results) > 1 else results
    return {
        "cold": {
            field: results[0].get(field)
            for field in fields
        },
        "warm_median": {
            field: _median([result.get(field) for result in warm])
            for field in fields
        },
        "warm_samples": len(warm),
    }


async def collect(options):
    deadline = asyncio.get_event_loop().time() + options.wait_target_seconds
    pages = []
    wait_announced = False
    while not pages:
        targets = _fetch_json(
            options.endpoint.rstrip("/") + "/json/list")
        pages = [
            target for target in targets
            if target.get("type") == "page"
        ]
        if pages:
            break
        if asyncio.get_event_loop().time() >= deadline:
            raise RuntimeError("no QtWebEngine page target found")
        if not wait_announced:
            print(
                "webengine_trace waiting for QtWebEngine to be opened",
                flush=True)
            wait_announced = True
        await asyncio.sleep(0.5)

    target = next(
        (page for page in pages
         if options.target_url_contains in page.get("url", "")),
        pages[0])
    print(
        "webengine_trace target id={} url={} title={}".format(
            target.get("id"), target.get("url"), target.get("title")),
        flush=True)

    websocket = await websockets.connect(
        target["webSocketDebuggerUrl"], max_size=None)
    connection = DevToolsConnection(websocket)
    await connection.start()
    await connection.command("Page.enable")
    await connection.command("Runtime.enable")
    await connection.command("Performance.enable")
    await connection.command("Network.enable")

    sample = 0
    results = []
    try:
        while sample < options.samples:
            if sample == 0 and options.clear_cache_first:
                await connection.command("Network.clearBrowserCache")
                print(
                    "webengine_trace browser cache cleared; sample 1 is cold",
                    flush=True)

            previous_navigation = await _navigation_state(connection)
            previous_start = previous_navigation.get("navigationStart")
            baseline = await _performance_metrics(connection)
            await _start_trace(connection)
            if options.auto_reload:
                print(
                    "webengine_trace running sample={} mode={}".format(
                        sample + 1,
                        "cold" if sample == 0 and options.clear_cache_first
                        else "warm"),
                    flush=True)
                while not connection.events.empty():
                    connection.events.get_nowait()
                await connection.command("Page.reload", {
                    "ignoreCache": (
                        sample == 0 and options.clear_cache_first),
                })
                await _wait_for_event(
                    connection, "Page.loadEventFired")
                state = await _navigation_state(connection)
                matched_url = state.get("url") or target.get("url")
            else:
                print(
                    "webengine_trace ready sample={} touch the service-page button".format(
                        sample + 1),
                    flush=True)

            if not options.auto_reload:
                matched_url = None
                while matched_url is None:
                    try:
                        state = await _navigation_state(connection)
                    except RuntimeError:
                        # During a cross-document navigation Chromium can briefly
                        # destroy the execution context between polling calls.
                        await asyncio.sleep(0.02)
                        continue
                    navigation_start = state.get("navigationStart")
                    url = state.get("url") or ""
                    if (navigation_start
                            and navigation_start != previous_start
                            and options.url_contains in url):
                        matched_url = url
                        break
                    await asyncio.sleep(0.02)

                while True:
                    try:
                        state = await _navigation_state(connection)
                    except RuntimeError:
                        await asyncio.sleep(0.02)
                        continue
                    if (state.get("readyState") == "complete"
                            and state.get("loadEventEnd", 0)
                            > state.get("navigationStart", 0)):
                        break
                    await asyncio.sleep(0.02)

            timing = await _page_timing(connection)
            after = await _performance_metrics(connection)
            trace_events = await _end_trace(connection)
            trace = _trace_breakdown(trace_events)
            if options.raw_trace_prefix:
                path = "{}.sample-{}.json.gz".format(
                    options.raw_trace_prefix, sample + 1)
                with gzip.open(path, "wt", encoding="utf-8") as stream:
                    json.dump({"traceEvents": trace_events}, stream)

            result = {
                "sample": sample + 1,
                "url": matched_url,
                "response_end_ms": timing.get("responseEnd"),
                "dom_interactive_ms": timing.get("domInteractive"),
                "dom_content_loaded_ms": timing.get("domContentLoaded"),
                "load_event_ms": timing.get("loadEvent"),
                "first_paint_ms": timing.get("firstPaint"),
                "first_contentful_paint_ms": timing.get(
                    "firstContentfulPaint"),
                "two_frames_complete_ms": timing.get("now"),
                "script_duration_ms": _metric_delta(
                    baseline, after, "ScriptDuration"),
                "layout_duration_ms": _metric_delta(
                    baseline, after, "LayoutDuration"),
                "style_duration_ms": _metric_delta(
                    baseline, after, "RecalcStyleDuration"),
                "task_duration_ms": _metric_delta(
                    baseline, after, "TaskDuration"),
                "trace_parse_ms": trace["parse"],
                "trace_script_ms": trace["script"],
                "trace_style_ms": trace["style"],
                "trace_layout_ms": trace["layout"],
                "trace_paint_ms": trace["paint"],
                "trace_composite_ms": trace["composite"],
            }
            compact = (
                "webengine_trace sample={sample} response_ms={response_end_ms} "
                "dom_interactive_ms={dom_interactive_ms} fcp_ms={first_contentful_paint_ms} "
                "load_ms={load_event_ms} frames_done_ms={two_frames_complete_ms} "
                "script_ms={script_duration_ms} style_ms={style_duration_ms} "
                "layout_ms={layout_duration_ms} paint_ms={trace_paint_ms} "
                "composite_ms={trace_composite_ms}").format(**result)
            print(compact, flush=True)
            payload = "WEBENGINE_TRACE_JSON " + json.dumps(
                result, sort_keys=True)
            print(payload, flush=True)
            if options.log_file:
                with open(options.log_file, "a", encoding="utf-8") as stream:
                    stream.write(compact + "\n")
                    stream.write(payload + "\n")
            results.append(result)
            sample += 1
            if options.auto_reload and options.reload_pause_seconds:
                await asyncio.sleep(options.reload_pause_seconds)
        summary_line = (
            "WEBENGINE_TRACE_SUMMARY_JSON "
            + json.dumps(_summary(results), sort_keys=True))
        print(summary_line, flush=True)
        if options.log_file:
            with open(options.log_file, "a", encoding="utf-8") as stream:
                stream.write(summary_line + "\n")
    finally:
        await connection.close()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint", default="http://127.0.0.1:9222")
    parser.add_argument("--target-url-contains", default="")
    parser.add_argument("--url-contains", default="service_page")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--log-file")
    parser.add_argument(
        "--clear-cache-first", action="store_true",
        help="clear Chromium's HTTP cache before sample 1")
    parser.add_argument(
        "--raw-trace-prefix",
        help="optionally save each complete trace as PREFIX.sample-N.json.gz")
    parser.add_argument(
        "--wait-target-seconds", type=float, default=180,
        help="wait for the lazy-created QtWebEngine target")
    parser.add_argument(
        "--auto-reload", action="store_true",
        help="reload the selected target instead of waiting for operator input")
    parser.add_argument(
        "--reload-pause-seconds", type=float, default=1,
        help="pause between automatic reload samples")
    return parser.parse_args()


def main():
    options = parse_args()
    asyncio.get_event_loop().run_until_complete(collect(options))


if __name__ == "__main__":
    main()
