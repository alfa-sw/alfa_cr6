# coding: utf-8

"""Concurrent movement errors: real Qt labels, timers and carousel cleanup.

No controllers are contacted. Only physical moves and operator input are
simulated; the sequence, pause waits, task cancellation and UI are production
code. Timer ticks are emitted explicitly to keep the tests deterministic.
"""

import asyncio
from functools import partial
import os
from pathlib import Path
import types
import unittest
from unittest import mock

from PyQt5.QtCore import QCoreApplication, QEvent, QTimer
from PyQt5.QtWidgets import QApplication, QFrame
from PyQt5.uic import loadUi

from alfa_CR6_backend.carousel_motor import CarouselMotor
import alfa_CR6_frontend.home_page as home_module
from alfa_CR6_frontend.main_window import MainWindow


class _StepBlinkTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.pages = []
        self.app = types.SimpleNamespace(
            get_jar_runners=lambda: {}, machine_head_dict={})
        patcher = mock.patch.object(
            home_module.QApplication, 'instance', return_value=self.app)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        for page in self.pages:
            page.close()
            page.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def page(self, page_class=home_module.HomePageSixHeads):
        page = page_class.__new__(page_class)
        QFrame.__init__(page)
        self.pages.append(page)
        loadUi(str(Path(home_module.__file__).parent / 'ui' / page.ui_file_name), page)
        page._init_step_blink()
        # Actual transit labels, initially hidden by the normal renderer.
        page.jar_pixmap_map = [
            (getattr(page, 'STEP_{}_label'.format(step)),
             (('A', 'PHOTOCELL'),), step, (('FROM',), ('TO',)))
            for step in ('01_02', '02_03', '07_08')
            if getattr(page, 'STEP_{}_label'.format(step), None) is not None
        ]
        page.update_jar_pixmaps()
        return page

    def assertOrange(self, label, expected=True):
        self.assertEqual('jar-orange.png' in label.styleSheet(), expected)


class TestHomeStepBlink(_StepBlinkTestCase):

    def test_overlapping_errors_survive_refresh_and_stop_independently(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                page = self.page()
                first = page.start_step_blink('01_02')
                second = page.start_step_blink('07_08')
                timer = page._step_blink_timer
                self.assertEqual(timer.interval(), 500)
                page.update_jar_pixmaps()
                self.assertOrange(page.STEP_01_02_label)
                self.assertOrange(page.STEP_07_08_label)
                timer.timeout.emit()
                page.update_jar_pixmaps()
                self.assertOrange(page.STEP_01_02_label, False)
                self.assertOrange(page.STEP_07_08_label, False)
                timer.timeout.emit()

                stopped, remaining = (
                    (page.STEP_07_08_label, page.STEP_01_02_label) if reverse
                    else (page.STEP_01_02_label, page.STEP_07_08_label))
                page.stop_step_blink(second if reverse else first)
                self.assertOrange(stopped, False)
                self.assertIsNone(stopped._alfa_visual_key)
                page.update_jar_pixmaps()
                self.assertEqual(stopped._alfa_visual_key, ('hidden',))
                self.assertOrange(remaining)
                self.assertTrue(timer.isActive())
                page.stop_step_blink(first if reverse else second)
                page.update_jar_pixmaps()
                self.assertOrange(stopped, False)
                self.assertOrange(remaining, False)
                self.assertFalse(timer.isActive())
                timer.timeout.emit()  # A late tick cannot resurrect an icon.
                self.assertOrange(remaining, False)

    def test_same_position_stays_active_until_last_request_is_released(self):
        page = self.page()
        first = page.start_step_blink('07_08')
        second = page.start_step_blink('07_08')
        page.stop_step_blink(first)
        page.stop_step_blink(first)
        page.stop_step_blink(None)
        page.stop_step_blink(object())
        self.assertOrange(page.STEP_07_08_label)
        page.stop_step_blink(second)
        self.assertOrange(page.STEP_07_08_label, False)

    def test_rapid_retry_reuses_one_timer_and_old_cleanup_is_harmless(self):
        page = self.page()
        timer = page._step_blink_timer
        with mock.patch.object(home_module.QTimer, 'singleShot') as single_shot:
            old = page.start_step_blink('07_08')
            page.stop_step_blink(old)
            current = page.start_step_blink('07_08')
            page.stop_step_blink(old)
            self.assertOrange(page.STEP_07_08_label)
            self.assertEqual(page.findChildren(QTimer), [timer])
            timer.timeout.emit()
            self.assertOrange(page.STEP_07_08_label, False)
            timer.timeout.emit()
            self.assertOrange(page.STEP_07_08_label)
            page.stop_step_blink(current)
            single_shot.assert_not_called()
        self.assertFalse(timer.isActive())

    def test_three_errors_share_phase_without_restarting_timer(self):
        page = self.page()
        tokens = [page.start_step_blink('01_02')]
        timer = page._step_blink_timer
        timer.timeout.emit()
        tokens.extend(page.start_step_blink(step) for step in ('02_03', '07_08'))
        labels = (page.STEP_01_02_label, page.STEP_02_03_label, page.STEP_07_08_label)
        for label in labels:
            self.assertOrange(label, False)
        timer.timeout.emit()
        for label in labels:
            self.assertOrange(label)
        for token in tokens:
            page.stop_step_blink(token)
        page.update_jar_pixmaps()
        for label in labels:
            self.assertOrange(label, False)
        self.assertFalse(timer.isActive())

    def test_absent_transit_labels_do_not_affect_existing_request_on_any_variant(self):
        for variant in (
                home_module.HomePageSixHeads, home_module.HomePageFourHeads,
                home_module.HomePageCRX40Heads, home_module.HomePageCRX60Heads,
                home_module.HomePageCRX80Heads):
            with self.subTest(variant=variant.__name__):
                page = self.page(variant)
                token = page.start_step_blink('01_02')
                missing = page.start_step_blink('10_11')
                self.assertIsNone(missing)
                page.stop_step_blink(missing)
                self.assertOrange(page.STEP_01_02_label)
                if variant is home_module.HomePageSixHeads:
                    self.assertIsNone(page.start_step_blink('05_06'))
                page.stop_step_blink(token)


class TestCarouselStepBlink(_StepBlinkTestCase):

    def setUp(self):
        super().setUp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.tasks = []
        self.moves_ready = {}
        self.release_moves = asyncio.Event()
        self.failures = {}
        self.page_ui = self.page()
        self.carousel = CarouselMotor.__new__(CarouselMotor)
        app = self.carousel
        app.carousel_frozen = False
        app.busy_head_A = False
        app.machine_variant = 'CR6'
        app._BaseApplication__jar_runners = {}
        app.request_attention_led = mock.Mock(return_value=False)
        app.freeze_carousel = lambda flag: setattr(app, 'carousel_frozen', flag)
        app.update_jar_position = mock.Mock()
        app.db_session = mock.Mock()
        app.ws_server = mock.Mock()
        app.restore_machine_helper = None
        app.handle_exception = mock.Mock(side_effect=AssertionError('Unexpected exception'))
        self.heads = {
            letter: types.SimpleNamespace(status={}, jar_photocells_status={})
            for letter in 'ABCDEF'
        }
        app.get_machine_head_by_letter = self.heads.get
        window = types.SimpleNamespace(home_page=self.page_ui, open_frozen_dialog=mock.Mock())
        window.start_step_blink = partial(MainWindow.start_step_blink, window)
        window.stop_step_blink = partial(MainWindow.stop_step_blink, window)
        app.main_window = window

        # Replace physical moves while preserving names used by the sequence.
        for name in (
                'move_01_02', 'move_02_03', 'move_03_04', 'move_04_05',
                'move_05_06', 'move_06_07', 'move_07_08', 'move_08_09',
                'move_09_10', 'move_10_11', 'move_11_12', 'dispense_step',
                'wait_for_jar_delivery'):
            self._stub_move(name)

    def _stub_move(self, name):
        async def move(_app, *args):
            jar = args[-1]
            if self.failures.get(jar.barcode) == name:
                del self.failures[jar.barcode]
                self.moves_ready[jar.barcode].set()
                await self.release_moves.wait()
                return False
            return True
        move.__qualname__ = 'CarouselMotor.' + name
        setattr(self.carousel, name, types.MethodType(move, self.carousel))

    def tearDown(self):
        for task in self.tasks:
            task.cancel()
        self.loop.run_until_complete(asyncio.gather(*self.tasks, return_exceptions=True))
        self.loop.close()
        asyncio.set_event_loop(None)
        super().tearDown()

    async def _overlap(self, first='move_02_03', second='move_07_08'):
        runners = self.carousel._BaseApplication__jar_runners
        for code, step in (('1', first), ('2', second)):
            self.failures[code] = step
            self.moves_ready[code] = asyncio.Event()
            jar = types.SimpleNamespace(
                barcode=code, position='A' if code == '1' else 'D',
                status='PROGRESS', machine_head=None, order=mock.Mock())
            task = asyncio.create_task(self.carousel.execute_carousel_steps(6, jar))
            runners[code] = {'jar': jar, 'task': task}
            self.tasks.append(task)
        await asyncio.gather(*(event.wait() for event in self.moves_ready.values()))
        # Both transfers are already in progress before the first pause.
        self.release_moves.set()
        while not all(runner.get('frozen') for runner in runners.values()):
            await asyncio.sleep(0)
        self.assertEqual(self.carousel.main_window.open_frozen_dialog.call_count, 1)

    def run_scenario(self, scenario):
        self.loop.run_until_complete(asyncio.wait_for(scenario, timeout=3))

    def test_ok_then_successful_retries_clear_both_icons(self):
        async def scenario():
            await self._overlap()
            self.assertOrange(self.page_ui.STEP_02_03_label)
            self.assertOrange(self.page_ui.STEP_07_08_label)
            self.carousel.freeze_carousel(False)
            self.assertEqual(await asyncio.gather(*self.tasks), [True, True])
            self.page_ui.update_jar_pixmaps()
            self.assertOrange(self.page_ui.STEP_02_03_label, False)
            self.assertOrange(self.page_ui.STEP_07_08_label, False)
            self.assertFalse(self.page_ui._step_blink_timer.isActive())
        self.run_scenario(scenario())

    def test_debug_cancellation_releases_only_the_cancelled_jar(self):
        async def scenario():
            await self._overlap()
            self.carousel.delete_jar_runner('2')
            await asyncio.gather(self.tasks[1], return_exceptions=True)
            self.assertTrue(self.tasks[1].cancelled())
            self.assertOrange(self.page_ui.STEP_02_03_label)
            self.assertOrange(self.page_ui.STEP_07_08_label, False)
            self.assertTrue(self.carousel.carousel_frozen)
            self.carousel.delete_jar_runner('1')
            await asyncio.gather(self.tasks[0], return_exceptions=True)
            self.assertFalse(self.page_ui._step_blink_timer.isActive())
        self.run_scenario(scenario())

    def test_entering_jar_cancellation_keeps_other_error_visible(self):
        async def scenario():
            await self._overlap(first='move_01_02')
            self.carousel.delete_entering_jar()
            await asyncio.gather(self.tasks[0], return_exceptions=True)
            self.assertTrue(self.tasks[0].cancelled())
            self.assertOrange(self.page_ui.STEP_01_02_label, False)
            self.assertOrange(self.page_ui.STEP_07_08_label)
        self.run_scenario(scenario())

    def _cancel_error_without_blink(self, step):
        async def scenario():
            await self._overlap(second=step)
            self.assertEqual(len(self.page_ui._step_blinks), 1)
            self.carousel.delete_jar_runner('2')
            await asyncio.gather(self.tasks[1], return_exceptions=True)
            self.assertOrange(self.page_ui.STEP_02_03_label)
            self.assertTrue(self.page_ui._step_blink_timer.isActive())
        self.run_scenario(scenario())

    def test_cancelled_move_without_label_cannot_stop_another_error(self):
        self._cancel_error_without_blink('move_05_06')

    def test_cancelled_too_many_jars_alarm_cannot_stop_another_error(self):
        self.heads['D'].status = {
            'status_level': 'ALARM', 'error_code': 1211}
        self._cancel_error_without_blink('move_07_08')


if __name__ == '__main__':
    unittest.main()
