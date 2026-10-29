# coding: utf-8

"""Calcoli applicativi e lifecycle teste senza QApplication o hardware."""

import asyncio
import copy
import json
import os
import tempfile
import types
import unittest
from unittest import mock

import alfa_CR6_backend.base_application as app_module
import alfa_CR6_backend.models as models_module
import alfa_CR6_backend.order_parser as parser_module
from alfa_CR6_backend.base_application import BaseApplication, RestoreMachineHelper
from alfa_CR6_backend.models import Jar, Order, init_models
from alfa_CR6_backend.settings_manager import SettingsManager


class _PigmentHead:

    def __init__(self, name, pigment_name, specific_weight, available_weight):
        self.name = name
        self.pigment_name = pigment_name
        self.specific_weight = specific_weight
        self.available_weight = available_weight
        self.pigment_list = [{"name": pigment_name, "head": name}]

    def get_specific_weight(self, pigment_name):
        if pigment_name == self.pigment_name:
            return self.specific_weight
        return -1

    def get_available_weight(self, pigment_name):
        if pigment_name == self.pigment_name:
            return self.available_weight
        return 0

    def get_machine_pigments(self):
        return [self.pigment_name]

    def get_pigment_list(self):
        return [(self.pigment_name, "C01")]


class TestApplicationHardwareFree(unittest.TestCase):

    def setUp(self):
        self.app = BaseApplication.__new__(BaseApplication)

    def test_formula_is_distributed_across_heads_by_real_availability(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=6)
        head_b = _PigmentHead("B", "RED", specific_weight=1.0, available_weight=10)
        self.app.machine_head_dict = {0: head_a, 1: head_b}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=[], pigment_name="RED",
            requested_quantity_gr=10, remaining_volume=0,
            dispense_not_successful=False,
        )

        self.assertEqual(missing_gr, 0)
        self.assertEqual(total_ml, 7.0)
        self.assertEqual(volume_map, {"RED": {"A": 3.0, "B": 4.0}})

    def test_successful_retry_skips_heads_already_visited(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=20)
        head_b = _PigmentHead("B", "RED", specific_weight=1.0, available_weight=20)
        self.app.machine_head_dict = {0: head_a, 1: head_b}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=["A"], pigment_name="RED",
            requested_quantity_gr=5, remaining_volume=0,
            dispense_not_successful=False,
        )

        self.assertEqual((missing_gr, total_ml), (0, 5.0))
        self.assertEqual(volume_map, {"RED": {"B": 5.0}})

    def test_failed_dispense_can_reuse_a_visited_head(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=20)
        self.app.machine_head_dict = {0: head_a}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=["A"], pigment_name="RED",
            requested_quantity_gr=4, remaining_volume=0,
            dispense_not_successful=True,
        )

        self.assertEqual((missing_gr, total_ml), (0, 2.0))
        self.assertEqual(volume_map, {"RED": {"A": 2.0}})

    def test_insufficient_quantity_remains_explicit(self):
        head_a = _PigmentHead("A", "RED", specific_weight=2.0, available_weight=4)
        self.app.machine_head_dict = {0: head_a}
        volume_map = {"RED": {}}

        missing_gr, total_ml = self.app._build_ingredient_volume_map_helper(
            volume_map, visited_head_names=[], pigment_name="RED",
            requested_quantity_gr=10, remaining_volume=0,
            dispense_not_successful=False,
        )

        self.assertEqual(missing_gr, 6)
        self.assertEqual(total_ml, 2.0)
        self.assertEqual(volume_map, {"RED": {"A": 2.0}})

    def test_available_pigments_and_low_level_locations_span_all_heads(self):
        head_a = _PigmentHead("A", "RED", 1.0, 1)
        head_b = _PigmentHead("B", "BLUE", 1.0, 1)
        self.app.machine_head_dict = {0: head_a, 1: None, 2: head_b}

        self.assertEqual(
            set(self.app.get_available_pigments()), {"RED", "BLUE"}
        )
        self.assertEqual(
            self.app.build_insufficient_pigments_infos({"RED": 3, "BLUE": 2}),
            [("RED", "A"), ("BLUE", "B")],
        )


class TestDuplicateOrderIngredients(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.addCleanup(models_module.set_global_session, models_module.global_session)
        self.session = init_models('sqlite:///:memory:')
        self.addCleanup(self.session.bind.dispose)
        self.addCleanup(self.session.close)
        self.app = BaseApplication.__new__(BaseApplication)
        self.app.settings = types.SimpleNamespace(
            MERGE_DUPLICATE_ORDER_INGREDIENTS=True,
            DATA_PATH=self.temp_dir.name,
        )
        self.app.db_session = self.session
        self.app.machine_head_dict = {}
        self.app.handle_exception = mock.Mock()
        translation = mock.patch.object(app_module, 'tr_', side_effect=lambda text: text)
        translation.start()
        self.addCleanup(translation.stop)

    @staticmethod
    def _properties(*weights):
        return {
            'meta': {'quality': '90', 'file name': 'line90.json'},
            'extra_lines_to_print': ['BASF Line 90'],
            'ingredients': [
                {'pigment_name': name, 'weight(g)': weight, 'description': name}
                for name, weight in weights
            ],
        }

    def _create(self, properties):
        order = self.app._do_create_order(
            properties, 'BASF Line 90', 2, file_name='line90.json')
        self.assertIsNotNone(order)
        self.app.handle_exception.assert_not_called()
        self.session.expire_all()
        return self.session.query(Order).one()

    def test_repeated_toners_are_persisted_once_with_total_and_first_metadata(self):
        properties = self._properties(
            ('A926', 10.5), ('M4', 20.0), ('A926', 3.2),
            ('M4', 1.25), ('A926', 0.3))
        properties['ingredients'][2]['description'] = 'Later description'
        original = copy.deepcopy(properties)

        order = self._create(properties)
        stored = json.loads(order.json_properties)

        self.assertEqual(stored['ingredients'], [
            {'pigment_name': 'A926', 'weight(g)': 14.0, 'description': 'A926'},
            {'pigment_name': 'M4', 'weight(g)': 21.25, 'description': 'M4'},
        ])
        self.assertEqual(stored['meta'], properties['meta'])
        self.assertEqual(stored['extra_lines_to_print'], properties['extra_lines_to_print'])
        self.assertEqual(order.file_name, 'line90.json')
        self.assertEqual(self.session.query(Jar).count(), 2)
        self.assertEqual(properties, original)

    def test_decimal_totals_keep_precision_without_binary_addition_artifacts(self):
        order = self._create(self._properties(
            ('A926', 0.1), ('M4', 0.00001), ('A926', 0.2), ('M4', 0.00002)))

        self.assertEqual(
            [i['weight(g)'] for i in json.loads(order.json_properties)['ingredients']],
            [0.3, 0.00003])

    def test_unknown_toners_use_the_total_in_order_and_jar(self):
        order = self._create(self._properties(('MANUAL', 2.5), ('MANUAL', 3.2)))

        self.assertEqual(json.loads(order.json_properties)['unknown_pigments'], {'MANUAL': 5.7})
        jar = order.jars[0]
        self.app.update_jar_properties(jar)
        self.assertEqual(jar.unknown_pigments, {'MANUAL': 5.7})

    def test_available_toner_uses_total_for_dispensing_and_remaining_quantity(self):
        self.app.machine_head_dict = {0: _PigmentHead('A', 'A926', 2.0, 100)}
        order = self._create(self._properties(('A926', 10.5), ('A926', 3.5)))
        jar = order.jars[0]

        self.app.update_jar_properties(jar)
        # The machine command uses millilitres: 14 g / 2 g/ml = 7 ml.
        self.assertEqual(jar.get_ingredients_for_machine(self.app.machine_head_dict[0]), {'A926': 7.0})

        jar.json_properties = json.dumps({'dispensed_quantities_gr': {'A926': 4.0}})
        self.app.update_jar_properties(jar)
        self.assertEqual(jar.get_ingredients_for_machine(self.app.machine_head_dict[0]), {'A926': 5.0})

    def test_availability_is_checked_against_the_total(self):
        self.app.machine_head_dict = {0: _PigmentHead('A', 'A926', 1.0, 10)}
        order = self._create(self._properties(('A926', 8.0), ('A926', 6.0)))
        jar = order.jars[0]

        self.app.update_jar_properties(jar)

        self.assertEqual(jar.insufficient_pigments, {'A926': 14.0})
        self.assertEqual(jar.get_ingredients_for_machine(self.app.machine_head_dict[0]), {})

    def test_unique_toners_and_empty_recipe_are_preserved(self):
        for properties in (self._properties(('A926', 10.12345), ('M4', 0)), {}):
            with self.subTest(properties=properties):
                order = self._create(properties)
                stored = json.loads(order.json_properties)
                stored.pop('unknown_pigments')
                self.assertEqual(stored, properties)
                self.session.query(Jar).delete()
                self.session.query(Order).delete()
                self.session.commit()

    def test_disabled_or_missing_option_keeps_duplicate_rejection(self):
        properties = self._properties(('A926', 10.5), ('A926', 3.5))
        for settings in (types.SimpleNamespace(MERGE_DUPLICATE_ORDER_INGREDIENTS=False),
                         types.SimpleNamespace()):
            with self.subTest(settings=settings):
                self.app.settings = settings
                self.app.handle_exception.reset_mock()

                order = self.app._do_create_order(properties, 'BASF Line 90', 1)

                self.assertIsNone(order)
                self.assertEqual(self.session.query(Order).count(), 0)
                self.assertEqual(self.session.query(Jar).count(), 0)
                self.app.handle_exception.assert_called_once()
                error = self.app.handle_exception.call_args[0][0]
                self.assertIsInstance(error, AssertionError)
                self.assertEqual(str(error), 'duplicated name in ingredient list')

    def test_basf_json_is_merged_after_aliases_without_changing_source_file(self):
        source = {
            'header': 'SW CRx formula file', 'version': '1.0.0',
            'system': 'Refinity', 'batchId': 1234, 'operatorId': '',
            'jobId': '', 'formulaNumber': '',
            'meta': {
                'brand': 'BASF', 'region': '', 'colorCode': 'TEST',
                'variantCode': '', 'colorName': 'Test', 'secondName': '',
                'year': '', 'remark': '', 'quality': '90', 'undercoat': '',
                'pictograms': '', 'dateModified': '', 'quantity': 1.0,
                'quantityUom': 'l', 'cumulative': 0.0, 'extraInfo': [],
            },
            'ingredients': [
                {'code': 'A926', 'weight(g)': 10.5, 'description': 'First'},
                {'code': 'M4', 'weight(g)': 20.0, 'description': 'Other'},
                {'code': 'ALIAS_A926', 'weight(g)': 3.2, 'description': 'Alias'},
                {'code': 'A926', 'weight(g)': 0.3, 'description': 'Repeated'},
            ],
        }
        path = os.path.join(self.temp_dir.name, 'line90.json')
        original = json.dumps(source).encode('utf-8')
        with open(path, 'wb') as stream:
            stream.write(original)
        with open(os.path.join(self.temp_dir.name, 'pigment_alias.json'), 'w') as stream:
            json.dump({'A926': ['ALIAS_A926']}, stream)

        with mock.patch.object(parser_module, 'get_application_instance', return_value=self.app):
            orders = self.app.create_orders_from_file(path, n_of_jars=1)

        self.assertEqual(len(orders), 1)
        self.assertIsNotNone(orders[0])
        self.app.handle_exception.assert_not_called()
        self.assertEqual(json.loads(orders[0].json_properties)['ingredients'], [
            {'pigment_name': 'A926', 'weight(g)': 14.0, 'description': 'First'},
            {'pigment_name': 'M4', 'weight(g)': 20.0, 'description': 'Other'},
        ])
        with open(path, 'rb') as stream:
            self.assertEqual(stream.read(), original)

    def test_setting_is_editable_boolean_and_defaults_to_disabled(self):
        key = 'MERGE_DUPLICATE_ORDER_INGREDIENTS'
        self.assertIs(SettingsManager.DEFAULTS[key], False)
        for value in (True, False):
            self.assertEqual(SettingsManager._validate_updates({key: value}), {key: value})
        with mock.patch.dict('sys.modules', {'app_settings': types.ModuleType('app_settings')}):
            self.assertIs(SettingsManager.get_editable_settings()[key], False)


class TestRestoreMachineHelperRawPersistence(unittest.TestCase):

    VALID_BARCODE = "260804001001"
    HIDDEN_BARCODE = "260804001002"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "running_jars.json")
        self.parent = types.SimpleNamespace(
            delete_jar_runner=mock.Mock()
        )
        # Evita il singleton globale: ogni test usa un file isolato.
        self.helper = object.__new__(RestoreMachineHelper)
        self.helper.json_file_path = self.path
        self.helper.parent = self.parent
        self.initial_data = {
            self.VALID_BARCODE: {
                "pos": "A", "jar_status": "PROGRESS",
                "dispensation": None,
            },
            self.HIDDEN_BARCODE: {
                "pos": "_", "jar_status": "ERROR",
                "dispensation": "dispensation_failure",
            },
        }
        self.helper.write_data(self.initial_data)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _read_raw_file(self):
        with open(self.path, "r") as stream:
            return json.load(stream)

    def test_public_read_remains_filtered(self):
        data = self.helper.read_data()

        self.assertEqual(list(data), [self.VALID_BARCODE])
        self.assertNotIn(self.HIDDEN_BARCODE, data)

    def test_position_update_preserves_hidden_records(self):
        self.helper.update_jar_data_position(self.VALID_BARCODE, "B")

        data = self._read_raw_file()
        self.assertEqual(data[self.VALID_BARCODE]["pos"], "B")
        self.assertEqual(data[self.HIDDEN_BARCODE], self.initial_data[self.HIDDEN_BARCODE])

    def test_store_preserves_hidden_records(self):
        jar = types.SimpleNamespace(
            barcode="260804001003", status="PROGRESS"
        )

        self.helper.store_jar_data(jar, "IN", dispensation=None)

        data = self._read_raw_file()
        self.assertEqual(data[self.HIDDEN_BARCODE], self.initial_data[self.HIDDEN_BARCODE])
        self.assertEqual(data[jar.barcode], {
            "pos": "IN", "jar_status": "PROGRESS", "dispensation": None,
        })

    def test_runner_deletion_preserves_unrelated_hidden_records(self):
        self.helper.recovery_task_deletion(self.VALID_BARCODE)

        data = self._read_raw_file()
        self.parent.delete_jar_runner.assert_called_once_with(self.VALID_BARCODE)
        self.assertNotIn(self.VALID_BARCODE, data)
        self.assertEqual(data[self.HIDDEN_BARCODE], self.initial_data[self.HIDDEN_BARCODE])

    def test_runner_deletion_can_remove_a_hidden_record(self):
        self.helper.recovery_task_deletion(self.HIDDEN_BARCODE)

        data = self._read_raw_file()
        self.parent.delete_jar_runner.assert_called_once_with(self.HIDDEN_BARCODE)
        self.assertNotIn(self.HIDDEN_BARCODE, data)
        self.assertIn(self.VALID_BARCODE, data)


class TestCarouselPauseMessages(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.app = types.SimpleNamespace(
            carousel_frozen=True,
            main_window=types.SimpleNamespace(open_frozen_dialog=mock.Mock()),
            request_attention_led=mock.Mock(return_value=True),
            release_attention_led=mock.Mock(),
            _BaseApplication__jar_runners={},
        )
        self.app.freeze_carousel = mock.Mock(
            side_effect=lambda flag: setattr(self.app, 'carousel_frozen', flag))

    def tearDown(self):
        tasks = asyncio.all_tasks(self.loop)
        for task in tasks:
            task.cancel()
        self.loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        self.loop.close()
        asyncio.set_event_loop(None)

    def test_transfer_failure_during_alarm_has_its_own_message_and_keeps_pause(self):
        async def scenario():
            source, destination = object(), object()
            task = asyncio.create_task(BaseApplication.wait_for_carousel_not_frozen(
                self.app, True, message_args=('BC1', 'A -> B', '1'),
                message_fmt='barcode:{} error in {}. I will retry. ({})',
                error_head=source, dest_head=destination))
            await asyncio.sleep(0)

            dialog = self.app.main_window.open_frozen_dialog
            dialog.assert_called_once()
            self.assertEqual(dialog.call_args.args[0], ('BC1', 'A -> B', '1'))
            self.assertTrue(dialog.call_args.kwargs['force_explicit_restart'])
            self.app.freeze_carousel.assert_not_called()
            self.assertTrue(self.app.carousel_frozen)
            self.assertFalse(task.done())

            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.assertTrue(self.app.carousel_frozen)
            released = self.app.release_attention_led.call_args_list
            self.assertEqual([call.args[0] for call in released], [source, destination])

        self.loop.run_until_complete(scenario())

    def test_first_failure_keeps_normal_resume_dialog(self):
        async def scenario():
            self.app.carousel_frozen = False
            task = asyncio.create_task(BaseApplication.wait_for_carousel_not_frozen(
                self.app, True, message_fmt='transfer failed'))
            await asyncio.sleep(0)

            self.app.freeze_carousel.assert_called_once_with(True)
            self.assertFalse(self.app.main_window.open_frozen_dialog.call_args.kwargs.get(
                'force_explicit_restart', False))
            self.app.carousel_frozen = False
            await task
            self.assertEqual(self.app.release_attention_led.call_count, 2)

        self.loop.run_until_complete(scenario())

    def test_waiting_for_an_existing_pause_does_not_open_another_dialog(self):
        async def scenario():
            task = asyncio.create_task(BaseApplication.wait_for_carousel_not_frozen(
                self.app, message_fmt='not a new failure'))
            await asyncio.sleep(0)
            self.app.main_window.open_frozen_dialog.assert_not_called()
            self.app.request_attention_led.assert_not_called()
            self.app.carousel_frozen = False
            await task

        self.loop.run_until_complete(scenario())

    def test_overlapping_failures_keep_distinct_messages(self):
        async def scenario():
            self.app.carousel_frozen = False
            tasks = []
            for barcode, route in [('BC1', 'A -> B'), ('BC2', 'D -> E')]:
                tasks.append(asyncio.create_task(
                    BaseApplication.wait_for_carousel_not_frozen(
                        self.app, True, message_args=(barcode, route),
                        message_fmt='barcode:{} error in {}')))
                await asyncio.sleep(0)

            calls = self.app.main_window.open_frozen_dialog.call_args_list
            self.assertEqual([call.args[0] for call in calls], [
                ('BC1', 'A -> B'), ('BC2', 'D -> E')])
            self.assertTrue(calls[1].kwargs['force_explicit_restart'])
            tasks[1].cancel()
            await asyncio.gather(tasks[1], return_exceptions=True)
            self.assertFalse(tasks[0].done())
            self.assertTrue(self.app.carousel_frozen)
            self.app.carousel_frozen = False
            await tasks[0]

        self.loop.run_until_complete(scenario())


class TestMachineTaskSupervision(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self.loop.close()

    def test_machine_task_restarts_after_unexpected_failure(self):
        second_run_started = asyncio.Event()

        class FailingOnceMachineHead:

            def __init__(self, *_args, **_kwargs):
                self.run_calls = 0

            async def run(self):
                self.run_calls += 1
                if self.run_calls == 1:
                    raise RuntimeError("watchdog failure")
                second_run_started.set()
                await asyncio.Event().wait()

        machine = FailingOnceMachineHead()
        app = types.SimpleNamespace(
            machine_head_dict={}, on_head_msg_received=mock.AsyncMock()
        )

        async def no_retry_delay(_seconds):
            return None

        with mock.patch.object(app_module, "MachineHead", return_value=machine), \
                mock.patch.object(app_module.asyncio, "sleep", no_retry_delay):
            task = self.loop.create_task(
                BaseApplication._BaseApplication__create_machine_task(
                    app, 0, "127.0.0.1", 11001, 8081
                )
            )
            self.loop.run_until_complete(asyncio.wait_for(
                second_run_started.wait(), timeout=0.1
            ))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                self.loop.run_until_complete(task)

        self.assertIs(app.machine_head_dict[0], machine)
        self.assertEqual(machine.run_calls, 2)


if __name__ == "__main__":
    unittest.main()
