# coding: utf-8

"""Concurrent movement errors: real Qt labels, timers and carousel cleanup.

No controllers are contacted. Only physical moves and operator input are
simulated; the sequence, pause waits, task cancellation and UI are production
code. Timer ticks are emitted explicitly to keep the tests deterministic.
The alarm/timeout scenarios also exercise the real transfer and photocell wait
with virtual time, simulated motor commands and an injected head status.
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
from alfa_CR6_backend.base_application import BaseApplication
import alfa_CR6_backend.carousel_motor as carousel_module
import alfa_CR6_backend.machine_head as head_module
import alfa_CR6_frontend.home_page as home_module
from alfa_CR6_frontend.main_window import MainWindow
from alfa_CR6_test.hardware_fakes import FakeMachineHead, VirtualClock


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

    def test_first_draw_failure_leaves_no_request_or_running_timer(self):
        page = self.page()
        label = page.STEP_07_08_label
        with mock.patch.object(label, 'setStyleSheet', side_effect=RuntimeError('draw failed')):
            with self.assertRaisesRegex(RuntimeError, 'draw failed'):
                page.start_step_blink('07_08')

        self.assertEqual(page._step_blinks, {})
        self.assertFalse(page._step_blink_timer.isActive())
        self.assertOrange(label, False)

        token = page.start_step_blink('07_08')
        self.assertOrange(label)
        self.assertTrue(page._step_blink_timer.isActive())
        page.stop_step_blink(token)
        self.assertFalse(page._step_blink_timer.isActive())

    def test_draw_failure_preserves_existing_blink(self):
        page = self.page()
        existing_label = page.STEP_01_02_label
        failed_label = page.STEP_07_08_label
        token = page.start_step_blink('01_02')
        timer = page._step_blink_timer
        with mock.patch.object(failed_label, 'setStyleSheet', side_effect=RuntimeError('draw failed')):
            with self.assertRaisesRegex(RuntimeError, 'draw failed'):
                page.start_step_blink('07_08')

        self.assertEqual(page._step_blinks, {token: existing_label})
        self.assertTrue(timer.isActive())
        self.assertOrange(existing_label)
        self.assertOrange(failed_label, False)
        timer.timeout.emit()
        self.assertOrange(existing_label, False)
        timer.timeout.emit()
        self.assertOrange(existing_label)
        self.assertOrange(failed_label, False)
        page.stop_step_blink(token)
        self.assertFalse(timer.isActive())

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
        dialogs = self.carousel.main_window.open_frozen_dialog.call_args_list
        self.assertEqual(len(dialogs), 2)
        self.assertEqual([call.args[0][0] for call in dialogs], ['1', '2'])
        self.assertTrue(dialogs[1].kwargs['force_explicit_restart'])

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
            dialog = self.carousel.main_window.open_frozen_dialog.call_args_list[0]
            self.assertEqual(dialog.kwargs['message_fmt'],
                             'barcode:{} error in {}. Remove all Cans from input roller and from HEAD A!')
            self.assertFalse(dialog.kwargs['show_cancel_btn'])
            self.assertEqual(dialog.kwargs['visibility'], 2)
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

    def _alarm_during_transfer(self, arrival_before_timeout=False, cancel=False):
        app = self.carousel
        app.settings = types.SimpleNamespace(TROUBLESHOOTING=False)
        app._head_safety_states = {1: 'STANDBY'}
        app._BaseApplication__modal_freeze_msgbox = None
        app.ws_server = None
        app.insert_db_event = mock.Mock()
        app.main_window.debug_page = None
        app.main_window.show_carousel_frozen = mock.Mock()
        app.main_window.set_carousel_freeze_control_enabled = mock.Mock()
        app.main_window.open_alert_dialog = mock.Mock()
        app.freeze_carousel = types.MethodType(BaseApplication.freeze_carousel, app)
        self.heads = {letter: FakeMachineHead(letter) for letter in 'ABCDEF'}
        app.get_machine_head_by_letter = self.heads.get
        app.machine_head_dict = {
            index: self.heads[letter]
            for index, letter in app.MACHINE_HEAD_INDEX_TO_NAME_MAP.items()
            if letter in self.heads}
        source, destination = self.heads['A'], self.heads['B']
        destination.app = app
        # Restore the production transfer; other sequence steps stay simulated.
        app.move_02_03 = types.MethodType(CarouselMotor.move_02_03, app)
        clock = VirtualClock()
        arrival_waits = []
        real_sleep = asyncio.sleep

        async def virtual_sleep(_delay):
            # Only the scenario advances time; tasks still yield to each other.
            await real_sleep(0)

        async def wait_for_arrival(head, bit_name, **kwargs):
            arrival_waits.append((clock.time(), kwargs['timeout']))
            return await head_module.MachineHead.wait_for_jar_photocells_status(
                head, bit_name, **kwargs)

        destination.wait_for_jar_photocells_status = types.MethodType(
            wait_for_arrival, destination)

        async def scenario():
            alarm_head = head_module.MachineHead(1, 'unused', 0, 0)
            alarm_head.status = {'status_level': 'STANDBY'}
            self.heads['F'] = alarm_head
            app.machine_head_dict[1] = alarm_head
            jar = types.SimpleNamespace(
                barcode='3', position='A', status='PROGRESS',
                machine_head=None, order=mock.Mock())
            task = asyncio.create_task(app.execute_carousel_steps(6, jar))
            self.tasks.append(task)
            runner = {'jar': jar, 'task': task}
            app._BaseApplication__jar_runners['3'] = runner
            while not arrival_waits:
                if task.done():
                    await task
                    self.fail('Sequence ended before the transfer wait')
                await real_sleep(0)
            started, timeout = arrival_waits[0]
            self.assertEqual(timeout, 45)
            self.assertEqual(source.command_log[0][1], 1)
            self.assertEqual(destination.command_log[0][1], 2)

            clock.now = started + 10
            await alarm_head.update_status({
                'status_level': 'ALARM', 'error_code': 1065,
                'error_message': 'C2_TINTING_VALVE_1_POS0_READ_LIGHT_ERROR',
                'photocells_status': 0, 'jar_photocells_status': 0,
                'crx_outputs_status': 0})
            self.assertTrue(app.carousel_frozen)
            self.assertEqual(self.page_ui._step_blinks, {})
            self.assertFalse(task.done())
            app.main_window.open_frozen_dialog.assert_called_once()
            self.assertTrue(app.main_window.open_frozen_dialog.call_args.kwargs[
                'force_explicit_restart'])

            if arrival_before_timeout:
                clock.now = started + 20
                destination.jar_photocells_status['JAR_DISPENSING_POSITION_PHOTOCELL'] = True
            else:
                clock.now = started + 44
                for _ in range(3):
                    await real_sleep(0)
                self.assertEqual(self.page_ui._step_blinks, {})
                self.assertFalse(runner.get('frozen'))
                clock.now = started + 46

            while not runner.get('frozen'):
                if task.done():
                    await task
                    self.fail('Sequence ended before observing the pause')
                await real_sleep(0)
            self.assertFalse(task.done())
            self.assertTrue(app.carousel_frozen)
            if arrival_before_timeout:
                app.main_window.open_frozen_dialog.assert_called_once()
            else:
                dialogs = app.main_window.open_frozen_dialog.call_args_list
                self.assertEqual(len(dialogs), 2)
                movement_dialog = dialogs[1]
                self.assertEqual(movement_dialog.args[0], (
                    '3', '\nmove_02_03 (A)\n', '1'))
                self.assertEqual(movement_dialog.kwargs['message_fmt'], [
                    'barcode:{} error in {}. I will retry.', '({})'])
                self.assertTrue(movement_dialog.kwargs['force_explicit_restart'])
            app.main_window.open_alert_dialog.assert_not_called()
            self.assertEqual(source.command_log[-1][1], 0)
            self.assertEqual(destination.command_log[-1][1], 0)
            self.page_ui.update_jar_pixmaps()
            self.assertOrange(self.page_ui.STEP_02_03_label, not arrival_before_timeout)
            if arrival_before_timeout:
                self.assertEqual(self.page_ui._step_blinks, {})
                app.update_jar_position.assert_any_call(jar=jar, machine_head=destination, pos='B')
                self.assertFalse(any(
                    call.args and call.args[0] == 'Movement failed: barcode:%s step:%s'
                    for call in movement_log.warning.call_args_list))
            else:
                movement_log.warning.assert_any_call(
                    'Movement failed: barcode:%s step:%s', '3', 'move_02_03 (A)')
                self.assertEqual(len(self.page_ui._step_blinks), 1)

            if cancel:
                app.ws_server = types.SimpleNamespace(refresh_can_list=mock.Mock())
                app.delete_jar_runner('3')
                await asyncio.gather(task, return_exceptions=True)
                self.assertTrue(task.cancelled())
                self.assertTrue(app.carousel_frozen)
                self.assertEqual(alarm_head.status['status_level'], 'ALARM')
            else:
                if not arrival_before_timeout:
                    original_output = destination.crx_outputs_management

                    async def output_with_arrival(output_number, output_action, **kwargs):
                        result = await original_output(output_number, output_action, **kwargs)
                        if output_action == 2:
                            destination.jar_photocells_status['JAR_DISPENSING_POSITION_PHOTOCELL'] = True
                        return result

                    destination.crx_outputs_management = output_with_arrival
                await alarm_head.update_status({
                    'status_level': 'STANDBY', 'error_code': 0,
                    'photocells_status': 0, 'jar_photocells_status': 0,
                    'crx_outputs_status': 0})
                self.assertTrue(app.carousel_frozen)
                self.assertTrue(app.freeze_carousel(False))
                self.assertTrue(await task)
                self.assertEqual(len(arrival_waits), 1 if arrival_before_timeout else 2)
            self.page_ui.update_jar_pixmaps()
            self.assertEqual(self.page_ui._step_blinks, {})
            self.assertOrange(self.page_ui.STEP_02_03_label, False)
            self.assertFalse(self.page_ui._step_blink_timer.isActive())

        with mock.patch.object(carousel_module, 'time', clock), \
                mock.patch.object(carousel_module.asyncio, 'sleep', virtual_sleep), \
                mock.patch.object(carousel_module, 'logging', wraps=carousel_module.logging) as movement_log, \
                mock.patch.object(head_module, 'get_application_instance', return_value=app):
            self.run_scenario(scenario())

    def test_transfer_timeout_during_other_alarm_blinks_until_explicit_resume(self):
        self._alarm_during_transfer()

    def test_arrival_during_other_alarm_completes_transfer_without_blink(self):
        self._alarm_during_transfer(arrival_before_timeout=True)

    def test_cancel_after_transfer_timeout_preserves_other_alarm_pause(self):
        self._alarm_during_transfer(cancel=True)


if __name__ == '__main__':
    unittest.main()
