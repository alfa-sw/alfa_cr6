# coding: utf-8

"""E2E hardware-free: creazione ordine, barcode, carosello e dispensazione.

Il test attraversa il percorso produttivo a partire da ``_do_create_order`` e
da una lettura del vero ``BarCodeReader``. La lettura avvia il vero jar task,
che usa lookup SQLite, validazione del volume, ``execute_carousel_steps``,
``dispense_step`` e ``MachineHead.do_dispense`` sulle matrici CR4, CR6, CRX60
e CRX80.

Il confine sostituito e' soltanto quello fisico: un websocket in-process passa
i comandi del vero ``MachineHead.send_command`` a ``MachineHeadMockup``. Le
transizioni di fotocellule, rulli, lifter e stato DISPENSING/STANDBY sono quindi
quelle dell'emulatore di progetto, accelerate con ``time_scale=0.05``. Anche
il REST tintometro e' deterministico e in memoria.

Il ritiro finale dal rullo di uscita di CR4/CR6 rappresenta l'unica azione
dell'operatore simulata esplicitamente; CRX60/80 usano il percorso lineare.
"""

import asyncio
import copy
import json
import os
import tempfile
import threading
import types
import unittest
from unittest import mock

import alfa_CR6_backend.machine_head as machine_head_module
import alfa_CR6_backend.models as models_module
import alfa_CR6_test.emulator as emulator_module
from alfa_CR6_backend.base_application import (
    BarCodeReader,
    BaseApplication,
    RestoreMachineHelper,
)
from alfa_CR6_backend.carousel_motor import CarouselMotor
from alfa_CR6_backend.machine_head import MachineHead
from alfa_CR6_backend.models import Jar, compile_barcode, init_models
from alfa_CR6_test.emulator import (
    DISPENSING_POSITION_MASK,
    INPUT_ROLLER_MASK,
    LOAD_LIFTER_ROLLER_MASK,
    OUTPUT_ROLLER_MASK,
    UNLOAD_LIFTER_ROLLER_MASK,
    MachineHeadMockup,
)


class _Page:

    def __init__(self):
        self.update_calls = 0

    def update_status(self):
        self.update_calls += 1

    def update_jar_pixmaps(self):
        self.update_calls += 1


class _MainWindow:

    def __init__(self):
        self.alerts = []
        self.barcodes = []
        self.status_updates = []
        self.frozen_dialogs = []
        self.recovery_mode_updates = []
        self.on_frozen_dialog = None
        self.home_page = _Page()
        self.debug_page = _Page()

    def open_alert_dialog(self, *args, **kwargs):
        self.alerts.append((args, kwargs))

    def show_barcode(self, barcode, is_ok):
        self.barcodes.append((barcode, is_ok))

    def update_status_data(self, index, status):
        self.status_updates.append((index, copy.deepcopy(status)))

    def open_frozen_dialog(self, *args, **kwargs):
        self.frozen_dialogs.append((args, kwargs))
        if self.on_frozen_dialog:
            self.on_frozen_dialog()

    def show_carousel_recovery_mode(self, flag):
        self.recovery_mode_updates.append(flag)

    @staticmethod
    def show_reserve(_index, _flag):
        return None

    @staticmethod
    def show_carousel_frozen(_flag):
        return None

    @staticmethod
    def start_step_blink(_step):
        return None

    @staticmethod
    def stop_step_blink():
        return None


class _WsServer:

    def __init__(self):
        self.refresh_calls = 0

    def refresh_can_list(self):
        self.refresh_calls += 1

    @staticmethod
    async def broadcast_msg(_channel, _message):
        return True


class _RedisPublisher:

    def __init__(self):
        self.messages = []

    def publish_messages(self, message):
        self.messages.append(copy.deepcopy(message))


class _InProcessPhysics(MachineHeadMockup):
    """Emulatore fisico che inoltra ogni stato al vero MachineHead."""

    def __init__(self, index, time_scale):
        self.receiver = None
        self._pickup_scheduled = False
        self.fail_next_dispense = False
        super().__init__(index, time_scale=time_scale)

    async def handle_command(self, msg_out_dict):
        command = msg_out_dict["command"]
        if (
                self.fail_next_dispense
                and command == "DISPENSE_FORMULA"):
            self.fail_next_dispense = False
            await self.do_move(duration=0.5, tgt_level="DISPENSING")
            await self._machine_sleep(1.0)
            await self.update_status({
                "status_level": "ALARM",
                "error_code": 9901,
                "error_message": "E2E_EMULATED_DISPENSE_FAILURE",
            })
            return
        await super().handle_command(msg_out_dict)

    async def dump_status(self):
        if self.receiver is not None:
            await self.receiver.update_status(copy.deepcopy(self.status))

        # Il flusso reale termina quando l'operatore preleva la latta. Lascia
        # visibile il fronte ON abbastanza a lungo per move_11_12, poi simula
        # il prelievo e il conseguente fronte OFF atteso da wait_for_delivery.
        output_occupied = bool(
            self.letter == "F"
            and self.status.get("jar_photocells_status", 0)
            & OUTPUT_ROLLER_MASK
        )
        if output_occupied and not self._pickup_scheduled:
            self._pickup_scheduled = True
            asyncio.get_event_loop().call_later(
                0.1, lambda: asyncio.ensure_future(self._simulate_pickup())
            )

    async def _simulate_pickup(self):
        await self.update_status({
            "jar_photocells_status": (
                self.status["jar_photocells_status"]
                & ~OUTPUT_ROLLER_MASK
            )
        })


class _InProcessWebSocket:
    """Trasporto controllato; mantiene reale MachineHead.send_command()."""

    def __init__(self, head, physics):
        self.head = head
        self.physics = physics
        self.sent = []
        self._last_command_task = None
        self.fault_policy = []
        self.fault_events = []
        self.connection_generation = 1
        self._forced_wait_timeouts = []

    def _consume_fault(self, outgoing):
        for index, fault in enumerate(self.fault_policy):
            if fault.get("command") != outgoing["command"]:
                continue
            expected_params = fault.get("params", {})
            actual_params = outgoing.get("params", {})
            if any(
                    actual_params.get(key) != value
                    for key, value in expected_params.items()):
                continue
            return self.fault_policy.pop(index)
        return None

    def consume_forced_wait_timeout(self, timeout):
        for index, expected in enumerate(self._forced_wait_timeouts):
            if abs(float(timeout) - expected) < 0.001:
                self._forced_wait_timeouts.pop(index)
                return True
        return False

    async def _deliver_answer(
            self, outgoing, status_code=0, error="no error"):
        answer = {
            "status_code": status_code,
            "error": error,
            "reply_to": None,
            "ref_id": len(self.sent),
            "command": outgoing["command"] + "_END",
        }
        await self.head._MachineHead__process_ws_msg(json.dumps({
            "type": "answer",
            "value": answer,
        }))

    async def _record_fault(self, behavior, outgoing, restart=False):
        previous_generation = self.connection_generation
        if restart:
            self.connection_generation += 1
        self.fault_events.append({
            "behavior": behavior,
            "command": copy.deepcopy(outgoing),
            "from_generation": previous_generation,
            "to_generation": self.connection_generation,
        })
        await asyncio.sleep(0)

    async def _queue_controller_execution(self, outgoing):
        previous_task = self._last_command_task

        async def execute_in_controller_order():
            # Il websocket conferma subito la ricezione, mentre il controller
            # fisico serializza i comandi della stessa testa. Avviare una task
            # indipendente per ogni comando permetteva invece a ON/OFF e macro
            # di sovrapporsi in un ordine impossibile sulla macchina reale.
            if previous_task is not None:
                await previous_task
            await self.physics.handle_command(outgoing)

        self._last_command_task = asyncio.ensure_future(
            execute_in_controller_order()
        )
        # Pubblica lo stato iniziale prima che il chiamante inizi ad attendere
        # la relativa transizione.
        await asyncio.sleep(0)

    async def send(self, payload):
        message = json.loads(payload)
        outgoing = copy.deepcopy(message["msg_out_dict"])
        self.sent.append(outgoing)
        fault = self._consume_fault(outgoing)
        behavior = fault and fault.get("behavior")

        if behavior == "disconnect_after_ack":
            await self._deliver_answer(outgoing)
            # La macro e' stata accettata dal trasporto ma il nuovo canale non
            # riceve la transizione DISPENSING. Accelera soltanto quel timeout
            # software; i tempi fisici degli altri comandi restano reali.
            self._forced_wait_timeouts.append(41.0)
            await self._record_fault(behavior, outgoing, restart=True)
            return

        if behavior == "restart_with_pending_request":
            # Il frame e' partito, ma la connessione cade prima dell'answer.
            # Il comando e la successiva attesa dell'uscita falliscono in modo
            # deterministico; il retry usera' la nuova generazione sana.
            self._forced_wait_timeouts.extend((30.0, 7.3))
            await self._record_fault(behavior, outgoing, restart=True)
            return

        if behavior == "restart_with_pending_stop":
            # Il bit dell'uscita resta attivo: il primo stop non raggiunge il
            # controller e deve essere ritentato dal watchdog sulla nuova
            # connessione.
            self._forced_wait_timeouts.extend((30.0, 7.3))
            await self._record_fault(behavior, outgoing, restart=True)
            return

        if behavior == "negative_answer":
            await self._deliver_answer(
                outgoing,
                status_code=fault.get("status_code", 254),
                error=fault.get("error", "controller rejected command"),
            )
            self._forced_wait_timeouts.extend((30.0, 7.3))
            await self._record_fault(behavior, outgoing)
            return

        if behavior == "restart_after_execution_before_answer":
            # Il controller esegue il frame e pubblica la nuova telemetria, ma
            # la risposta si perde. L'uscita osservata deve poter confermare
            # il comando senza ripeterlo.
            await self._queue_controller_execution(outgoing)
            self._forced_wait_timeouts.append(30.0)
            await self._record_fault(behavior, outgoing, restart=True)
            return

        if behavior:
            raise AssertionError(
                "unsupported E2E protocol fault: {}".format(behavior)
            )

        await self._deliver_answer(outgoing)
        await self._queue_controller_execution(outgoing)


class _E2EMachineHead(MachineHead):

    def __init__(self, index, app, physics, pigment):
        with mock.patch.object(
                machine_head_module, "get_application_instance",
                return_value=app):
            super().__init__(index, "127.0.0.1", 11001 + index, 8081 + index)
        # update_status legge la precedente maschera delle uscite per rilevare
        # i fronti. Sulla macchina esiste gia' un payload iniziale; nel test
        # evitiamo quindi il solo stato transitorio completamente vuoto.
        self.status = {"crx_outputs_status": 0}
        self._rest_pigments = [copy.deepcopy(pigment)]
        self.fail_next_transfer = False
        self.output_timeout_overrides = {}
        self.websocket = _InProcessWebSocket(self, physics)
        physics.receiver = self

    async def crx_outputs_management(
            self, output_number, output_action, timeout=30, silent=True):
        if (
                self.fail_next_transfer
                and output_number == 0
                and output_action == 1):
            self.fail_next_transfer = False
            raise RuntimeError(
                "E2E emulated movement controller failure on head {}".format(
                    self.name
                )
            )
        if output_action and output_number in self.output_timeout_overrides:
            timeout = self.output_timeout_overrides[output_number]
        return await super().crx_outputs_management(
            output_number, output_action, timeout=timeout, silent=silent
        )

    async def call_api_rest(  # pylint: disable=too-many-arguments
            self, path, method, data, timeout=40, expected_ret_type="json"):
        del method, timeout, expected_ret_type
        if path == "apiV1/config":
            return {"objects": []}
        if path == "apiV1/pigment":
            return {"objects": copy.deepcopy(self._rest_pigments)}
        if path == "apiV1/package":
            return {"objects": [{"name": "500 ml", "size": 500}]}
        if path == "apiV1/ad_hoc":
            return {
                "result": "OK",
                "pipe_formula": copy.deepcopy(
                    data.get("params", {}).get("ingredients", {})
                ),
            }
        raise AssertionError("REST E2E non previsto: {}".format(path))


class _OrderBarcodeDispenseE2EMixin:

    VARIANT_SPECS = {
        "CR6": {
            "variant": "CR6",
            "in_docker": False,
            "heads": ((0, "A"), (1, "F"), (2, "B"),
                      (3, "E"), (4, "C"), (5, "D")),
            "carousel_order": ("A", "B", "C", "D", "E", "F"),
            "minimum_movements": 21,
        },
        "CR4": {
            "variant": "CR4",
            "in_docker": False,
            "heads": ((0, "A"), (1, "F"), (4, "C"), (5, "D")),
            "carousel_order": ("A", "C", "D", "F"),
            "minimum_movements": 16,
        },
        "CRX60": {
            "variant": "CRX60",
            "in_docker": True,
            "heads": ((0, "A"), (2, "B"), (4, "C")),
            "carousel_order": ("A", "B", "C"),
            "minimum_movements": 8,
        },
        "CRX80": {
            "variant": "CRX80",
            "in_docker": True,
            "heads": ((0, "A"), (2, "B"), (4, "C"), (6, "G")),
            "carousel_order": ("A", "B", "C", "G"),
            "minimum_movements": 10,
        },
    }
    PHASE_TIMEOUT = 30
    # Sotto 0.05 i fronti brevi di uscita o circuito possono sovrapporsi ai
    # tre campioni stabili (10 ms ciascuno) del polling produttivo.
    TIME_SCALE = 0.05

    def setUp(self):
        self.spec = self.VARIANT_SPECS[self.VARIANT]
        self.head_names = tuple(name for _index, name in self.spec["heads"])
        self.environment_patch = mock.patch.dict(os.environ, {
            "MACHINE_VARIANT": self.spec["variant"],
            "IN_DOCKER": "1" if self.spec["in_docker"] else "0",
        })
        self.environment_patch.start()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.temp_dir = tempfile.TemporaryDirectory(prefix="alfa_e2e_")
        self.db_path = os.path.join(self.temp_dir.name, "e2e.sqlite")
        self.session = init_models("sqlite:///" + self.db_path)
        self.exceptions = []
        self.physics = []

        self.app = CarouselMotor.__new__(CarouselMotor)
        self.app.settings = types.SimpleNamespace(
            TMP_PATH=self.temp_dir.name,
            TROUBLESHOOTING=False,
        )
        self.app.db_session = self.session
        self.app.machine_head_dict = {}
        self.app.main_window = _MainWindow()
        self.app.ws_server = _WsServer()
        self.app.redis_publisher = _RedisPublisher()
        self.app.restore_machine_helper = None
        self.app.ready_to_read_a_barcode = True
        self.app.running_recovery_mode = False
        self.app.barcode_read_blocked_on_refill = False
        self.app.carousel_frozen = False
        self.app.busy_head_A = False
        self.app.double_can_alert = False
        self.app.timer_01_02 = 0
        self.app.machine_variant = self.spec["variant"]
        self.app.in_docker = self.spec["in_docker"]
        self.app.n_of_active_heads = len(self.spec["heads"])
        self.app.MOVE_DEST_LED_HEAD_MAP = dict(
            CarouselMotor.MOVE_DEST_LED_HEAD_MAP
        )
        if self.spec["variant"] == "CRX80":
            self.app.MOVE_DEST_LED_HEAD_MAP["move_04_05"] = "G"
        self.app.id_bc_shuttle = "DISABLED"
        # La taglia puo' arrivare dal secondo lettore anche su CR6; evita di
        # introdurre nel test il debounce dei microswitch, gia' coperto a parte.
        self.app.shuttle_size_from_barcode_scanner = 500
        self.app._shuttle_size_ready_evt = asyncio.Event()
        self.app._crx_ja_block_sequence_active = False
        self.app._crx_pending_barcode = None
        self.app._database_cleanup_cancel_event = threading.Event()
        self.app._database_cleanup_future = None
        self.app._attention_led_requests = {}
        self.app._refill_alarm_tokens = set()
        self.app._BaseApplication__jar_runners = {}
        self.app._BaseApplication__tasks_to_freeze = 0
        self.app._BaseApplication__modal_freeze_msgbox = None
        self.app.handle_exception = self.exceptions.append

        self.emulator_data_patch = mock.patch.object(
            emulator_module, "DATA_ROOT", self.temp_dir.name + os.sep
        )
        self.emulator_data_patch.start()
        self.models_app_patch = mock.patch.object(
            models_module, "get_application_instance", return_value=self.app
        )
        self.models_app_patch.start()

        for index, name in self.spec["heads"]:
            pigment = self._pigment_for(name)
            with open(
                    os.path.join(self.temp_dir.name, name + "_pigment_list.json"),
                    "w", encoding="utf-8") as stream:
                json.dump([pigment], stream)

            physics = _InProcessPhysics(index, self.TIME_SCALE)
            physics.status["panel_table_status"] = False
            if name == "A":
                physics.status["jar_photocells_status"] |= INPUT_ROLLER_MASK
            head = _E2EMachineHead(index, self.app, physics, pigment)
            self.physics.append(physics)
            self.app.machine_head_dict[index] = head

        async def fault_aware_wait_for_condition(
                app, condition, timeout, show_alert=True, extra_info="",
                stability_count=3, step=0.01, callback=None,
                break_condition=None):
            for head in app.machine_head_dict.values():
                if head.websocket.consume_forced_wait_timeout(timeout):
                    await asyncio.sleep(0)
                    return None
            return await CarouselMotor.wait_for_condition(
                app, condition, timeout, show_alert=show_alert,
                extra_info=extra_info, stability_count=stability_count,
                step=step, callback=callback,
                break_condition=break_condition,
            )

        self.app.wait_for_condition = types.MethodType(
            fault_aware_wait_for_condition, self.app
        )

        self.loop.run_until_complete(self._publish_initial_states())

    def tearDown(self):
        pending = [task for task in asyncio.all_tasks(self.loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        self.session.close()
        self.models_app_patch.stop()
        self.emulator_data_patch.stop()
        self.environment_patch.stop()
        self.loop.close()
        self.temp_dir.cleanup()

    @staticmethod
    def _pigment_for(head_name):
        return {
            "name": "PIG_{}".format(head_name),
            "type": "colorant",
            "specific_weight": 1.0,
            "pipes": [{
                # B01 ha circuit_id 0, valore usato anche per "disimpegnato".
                # B02 consente di verificare i fronti 1 -> 0 della telemetria.
                "name": "B02",
                "enabled": True,
                "sync": True,
                "current_level": 500.0,
                "minimum_level": 0.0,
                "reserve_level": 25.0,
                "effective_specific_weight": 1.0,
            }],
        }

    async def _publish_initial_states(self):
        for physics in self.physics:
            await physics.dump_status()
        for head in self.app.machine_head_dict.values():
            await head.update_tintometer_data()

    def _run(self, coroutine):
        return self.loop.run_until_complete(coroutine)

    def _create_order_and_jar(self):
        properties = {
            "meta": {"file name": "e2e-hardware-free"},
            "ingredients": [
                {"pigment_name": "PIG_{}".format(name), "weight(g)": 5.0}
                for name in self.head_names
            ],
        }
        order = BaseApplication._do_create_order(
            self.app, properties, "E2E ordine-barcode-dispensazione", 1
        )
        if order is None:
            self.fail("fase ordine: _do_create_order non ha creato l'ordine")

        jar = self.session.query(Jar).filter(Jar.order_id == order.id).one()
        return order, jar

    async def _scan_and_wait(self, barcode):
        reader = BarCodeReader(
            self.app.on_barcode_read,
            identification_string="E2E",
            exception_handler=self.exceptions.append,
            manual_input=True,
        )
        await reader.manual_read(barcode)

        runners = self.app._BaseApplication__jar_runners
        if barcode not in runners:
            self.fail("fase barcode: la lettura non ha creato il jar runner")

        try:
            await asyncio.wait_for(
                asyncio.shield(runners[barcode]["task"]),
                timeout=self.PHASE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            runner_task = runners[barcode]["task"]
            commands = {
                head.name: [entry["command"] for entry in head.websocket.sent]
                for head in self.app.machine_head_dict.values()
            }
            statuses = {
                head.name: {
                    "status_level": head.status.get("status_level"),
                    "crx_outputs_status": head.status.get(
                        "crx_outputs_status", 0
                    ),
                    "inner_outputs": copy.deepcopy(
                        head._MachineHead__crx_inner_status
                    ),
                }
                for head in self.app.machine_head_dict.values()
            }
            self.fail(
                "fase carosello/dispensazione in timeout; "
                "comandi={}, stati={}, stack={}".format(
                    commands,
                    statuses,
                    [frame.f_code.co_name for frame in runner_task.get_stack()],
                )
            )

        self.app._BaseApplication__check_jars_to_freeze()

        return reader

    async def _run_e2e(self):
        order, jar = self._create_order_and_jar()
        reader = await self._scan_and_wait(jar.barcode)
        self.session.refresh(jar)
        self.session.refresh(order)
        return order, jar, reader, jar.barcode

    def _assert_complete_variant(self):
        order, jar, reader, barcode = self._run(self._run_e2e())

        properties = json.loads(jar.json_properties)
        macro_heads = []
        movement_commands = 0
        for head in self.app.machine_head_dict.values():
            commands = head.websocket.sent
            if any(item["command"] == "DISPENSE_FORMULA" for item in commands):
                macro_heads.append(head.name)
            movement_commands += sum(
                item["command"] == "CRX_OUTPUTS_MANAGEMENT"
                for item in commands
            )

        self.assertEqual(reader.last_read_event_buffer, barcode)
        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "_")
        self.assertEqual(order.status, "DONE")
        self.assertEqual(
            properties["visited_head_names"],
            list(self.spec["carousel_order"]),
        )
        self.assertEqual(
            set(properties["dispensed_quantities_gr"]),
            {"PIG_{}".format(name) for name in self.head_names},
        )
        self.assertEqual(properties["ingredient_volume_map"], {})
        self.assertEqual(properties["remaining_volume"], 0)
        self.assertEqual(
            set(properties["effective_engaged_circuits"]),
            set(self.head_names),
        )
        for name in self.head_names:
            engaged = properties["effective_engaged_circuits"][name]
            self.assertEqual(
                list(engaged.values()),
                [["B02", "PIG_{}".format(name)]],
            )
        self.assertEqual(set(macro_heads), set(self.head_names))
        self.assertGreaterEqual(
            movement_commands, self.spec["minimum_movements"]
        )
        self.assertTrue(any(
            message.get("status") == "DONE"
            for message in self.app.redis_publisher.messages
        ))
        self.assertEqual(self.app.main_window.alerts, [])
        self.assertEqual(self.exceptions, [])

    def test_complete_order_barcode_and_dispense(self):
        self._assert_complete_variant()

    def test_missing_barcode_does_not_start_machine(self):
        order, jar = self._create_order_and_jar()
        missing_barcode = compile_barcode(order.order_nr + 1000, 1)

        reader = self._run(self._scan_and_wait(missing_barcode))

        self.session.refresh(jar)
        self.session.refresh(order)
        sent_commands = [
            command
            for head in self.app.machine_head_dict.values()
            for command in head.websocket.sent
        ]
        self.assertEqual(reader.last_read_event_buffer, missing_barcode)
        self.assertEqual(jar.status, "NEW")
        self.assertEqual(order.status, "NEW")
        self.assertEqual(sent_commands, [])
        self.assertTrue(any(
            "not found" in kwargs.get("fmt", "")
            for _args, kwargs in self.app.main_window.alerts
        ))
        self.assertEqual(self.exceptions, [])

    def test_movement_controller_error_marks_order_error(self):
        head_a = self.app.get_machine_head_by_letter("A")
        head_a.fail_next_transfer = True

        order, jar, _reader, _barcode = self._run(self._run_e2e())

        properties = json.loads(jar.json_properties)
        macro_heads = {
            head.name
            for head in self.app.machine_head_dict.values()
            if any(
                command["command"] == "DISPENSE_FORMULA"
                for command in head.websocket.sent
            )
        }
        self.assertEqual(jar.status, "ERROR")
        self.assertEqual(jar.position, "A")
        self.assertEqual(order.status, "ERROR")
        self.assertEqual(properties["visited_head_names"], ["A"])
        self.assertEqual(macro_heads, {"A"})
        self.assertTrue(any(
            isinstance(exc, RuntimeError)
            and "movement controller failure" in str(exc)
            for exc in self.exceptions
        ))

    def test_dispense_alarm_marks_order_error_and_ejects_jar(self):
        physics_a = next(item for item in self.physics if item.letter == "A")
        physics_a.fail_next_dispense = True
        self.app.main_window.on_frozen_dialog = (
            lambda: self.loop.call_later(
                0.01, self.app.freeze_carousel, False
            )
        )

        order, jar, _reader, _barcode = self._run(self._run_e2e())

        properties = json.loads(jar.json_properties)
        macro_heads = {
            head.name
            for head in self.app.machine_head_dict.values()
            if any(
                command["command"] == "DISPENSE_FORMULA"
                for command in head.websocket.sent
            )
        }
        outcomes = dict(properties["dispensation_outcomes"])
        self.assertEqual(jar.status, "ERROR")
        self.assertEqual(jar.position, "_")
        self.assertEqual(order.status, "ERROR")
        self.assertEqual(macro_heads, {"A"})
        self.assertIn("failure during dispensation", outcomes["A"])
        self.assertGreaterEqual(len(self.app.main_window.frozen_dialogs), 1)

    @staticmethod
    def _new_restore_helper(app, json_file_path):
        helper = object.__new__(RestoreMachineHelper)
        helper.json_file_path = json_file_path
        helper.parent = app
        return helper

    async def _run_recovery_after_shutdown(
            self, dispensation_state="done", dispense_before_shutdown=True,
            physical_position="current"):
        order, jar = self._create_order_and_jar()
        jar_id = jar.id
        helper_path = os.path.join(self.temp_dir.name, "running_jars.json")
        helper = self._new_restore_helper(self.app, helper_path)
        helper.write_data({})
        self.app.restore_machine_helper = helper
        self.app.update_jar_properties(jar)

        head_a = self.app.get_machine_head_by_letter("A")
        physics_a = next(item for item in self.physics if item.letter == "A")
        a_sensor_mask = (
            physics_a.status["jar_photocells_status"]
            & ~INPUT_ROLLER_MASK
        ) | DISPENSING_POSITION_MASK
        await physics_a.update_status({
            "status_level": "STANDBY",
            "container_presence": True,
            "jar_photocells_status": a_sensor_mask,
        })
        self.app.update_jar_position(
            jar=jar, machine_head=head_a, status="PROGRESS", pos="A"
        )
        self.app._BaseApplication__jar_runners[jar.barcode] = {
            "jar": jar,
            "task": asyncio.current_task(),
            "frozen": False,
            "running_engaged_circuits": [],
        }
        if dispense_before_shutdown:
            dispensed = await self.app.dispense_step("A", jar)
            self.assertTrue(dispensed)

        # Permette di riprodurre i soli dati durable disponibili nei diversi
        # punti di interruzione. In particolare ``None`` rappresenta sia il
        # crash prima dell'invio sia quello dopo l'ACK ma prima di DISPENSING:
        # al riavvio i due casi sono intenzionalmente indistinguibili.
        helper.store_jar_data(
            jar, "A", dispensation=dispensation_state
        )
        persisted_before_shutdown = dict(helper.read_data())[jar.barcode]
        self.assertEqual(persisted_before_shutdown["pos"], "A")
        self.assertEqual(
            persisted_before_shutdown["dispensation"], dispensation_state
        )

        if physical_position not in ("current", "next", "missing", "ambiguous"):
            raise ValueError(
                "unsupported recovery physical position: {}".format(
                    physical_position
                )
            )
        next_head_name = self.spec["carousel_order"][1]
        physics_next = next(
            item for item in self.physics if item.letter == next_head_name
        )
        for physics, occupied in (
                (physics_a, physical_position in ("current", "ambiguous")),
                (physics_next, physical_position in ("next", "ambiguous"))):
            sensor_mask = physics.status["jar_photocells_status"]
            if occupied:
                sensor_mask |= DISPENSING_POSITION_MASK
            else:
                sensor_mask &= ~DISPENSING_POSITION_MASK
            await physics.update_status({
                "container_presence": occupied,
                "jar_photocells_status": sensor_mask,
            })

        # Confine di spegnimento: vengono persi runner e sessione, mentre DB,
        # running_jars.json e fotocellule della macchina restano persistenti.
        self.app._BaseApplication__jar_runners = {}
        for head in self.app.machine_head_dict.values():
            head._current_runner = None
        self.session.close()
        self.session = init_models("sqlite:///" + self.db_path)
        self.app.db_session = self.session
        restarted_helper = self._new_restore_helper(self.app, helper_path)
        self.app.restore_machine_helper = restarted_helper
        self.app.running_recovery_mode = False
        self.app.ready_to_read_a_barcode = False

        async def accelerated_recovery_actions(
                app, j_code, recovery_jar, actions, movement_params,
                deduced_position, sleeptime=1):
            del sleeptime
            return await CarouselMotor.run_recovery_actions(
                app, j_code, recovery_jar, actions, movement_params,
                deduced_position, sleeptime=0
            )

        self.app.run_recovery_actions = types.MethodType(
            accelerated_recovery_actions, self.app
        )
        recovery_task = asyncio.create_task(self.app.machine_recovery())

        async def reap_completed_runners():
            while not recovery_task.done():
                self.app._BaseApplication__check_jars_to_freeze()
                await asyncio.sleep(0.01)

        reaper_task = asyncio.create_task(reap_completed_runners())
        try:
            await asyncio.wait_for(
                asyncio.shield(recovery_task), timeout=self.PHASE_TIMEOUT
            )
        finally:
            reaper_task.cancel()
            await asyncio.gather(reaper_task, return_exceptions=True)

        controller_tasks = [
            head.websocket._last_command_task
            for head in self.app.machine_head_dict.values()
            if head.websocket._last_command_task is not None
        ]
        if controller_tasks:
            await asyncio.gather(*controller_tasks, return_exceptions=True)

        recovered_jar = self.session.query(Jar).filter(Jar.id == jar_id).one()
        self.session.refresh(recovered_jar)
        self.session.refresh(recovered_jar.order)
        with open(helper_path, "r", encoding="utf-8") as stream:
            raw_recovery_data = json.load(stream)
        return recovered_jar.order, recovered_jar, raw_recovery_data

    def _dispense_command_count(self, head_name):
        head = self.app.get_machine_head_by_letter(head_name)
        return sum(
            command["command"] == "DISPENSE_FORMULA"
            for command in head.websocket.sent
        )

    def _movement_command_count(self):
        return sum(
            command["command"] == "CRX_OUTPUTS_MANAGEMENT"
            for head in self.app.machine_head_dict.values()
            for command in head.websocket.sent
        )

    def _assert_runtime_invariants(self, allow_ambiguous_physics=False):
        async def wait_for_auto_stopped_outputs():
            return await CarouselMotor.wait_for_condition(
                self.app,
                lambda: all(
                    physics.status.get("crx_outputs_status", 0) == 0
                    for physics in self.physics
                ),
                timeout=0.5, show_alert=False, stability_count=1, step=0.01,
            )

        self.assertTrue(
            self._run(wait_for_auto_stopped_outputs()),
            "l'emulatore non ha auto-arrestato tutte le uscite",
        )

        occupancy_mask = (
            INPUT_ROLLER_MASK
            | LOAD_LIFTER_ROLLER_MASK
            | OUTPUT_ROLLER_MASK
            | UNLOAD_LIFTER_ROLLER_MASK
            | DISPENSING_POSITION_MASK
        )
        occupied_positions = 0
        for physics in self.physics:
            self.assertEqual(physics.status.get("crx_outputs_status", 0), 0)
            occupied_mask = (
                physics.status.get("jar_photocells_status", 0)
                & occupancy_mask
            )
            occupied_positions += bin(occupied_mask).count("1")
        if not allow_ambiguous_physics:
            self.assertLessEqual(occupied_positions, 1)

        for head in self.app.machine_head_dict.values():
            self.assertLessEqual(self._dispense_command_count(head.name), 1)
            command_task = head.websocket._last_command_task
            self.assertTrue(command_task is None or command_task.done())

        self.assertEqual(self.app._BaseApplication__jar_runners, {})
        self.assertEqual(self.exceptions, [])

    def _assert_recovery_invariants(
            self, raw_recovery_data, recovery_completed=True,
            allow_ambiguous_physics=False):
        self._assert_runtime_invariants(
            allow_ambiguous_physics=allow_ambiguous_physics
        )
        self.assertFalse(self.app.running_recovery_mode)
        self.assertEqual(
            self.app.ready_to_read_a_barcode, recovery_completed
        )

        jars_by_barcode = {
            db_jar.barcode: db_jar
            for db_jar in self.session.query(Jar).all()
        }
        for barcode, recovery_data in raw_recovery_data.items():
            self.assertIn(barcode, jars_by_barcode)
            db_jar = jars_by_barcode[barcode]
            if recovery_completed:
                self.assertNotIn(db_jar.status, ("DONE", "ERROR"))
            else:
                self.assertEqual(db_jar.status, "ERROR")
            self.assertEqual(recovery_data.get("pos"), db_jar.position)
        for barcode, db_jar in jars_by_barcode.items():
            if db_jar.status == "DONE" or (
                    recovery_completed and db_jar.status == "ERROR"):
                self.assertNotIn(barcode, raw_recovery_data)

    def _assert_failed_closed_recovery(
            self, dispensation_state, dispense_before_shutdown,
            expected_a_dispenses):
        order, jar, raw_recovery_data = self._run(
            self._run_recovery_after_shutdown(
                dispensation_state=dispensation_state,
                dispense_before_shutdown=dispense_before_shutdown,
            )
        )

        self.assertEqual(jar.status, "ERROR")
        self.assertEqual(jar.position, "OUT")
        self.assertEqual(order.status, "ERROR")
        self.assertEqual(
            self._dispense_command_count("A"), expected_a_dispenses
        )
        self.assertEqual(raw_recovery_data, {})
        self._assert_recovery_invariants(raw_recovery_data)

    def _assert_recovery_blocked_by_physical_state(
            self, physical_position, expected_alert_text):
        order, jar, raw_recovery_data = self._run(
            self._run_recovery_after_shutdown(
                dispensation_state="done",
                dispense_before_shutdown=True,
                physical_position=physical_position,
            )
        )

        self.assertEqual(jar.status, "ERROR")
        self.assertEqual(jar.position, "A")
        self.assertEqual(order.status, "ERROR")
        self.assertEqual(self._dispense_command_count("A"), 1)
        self.assertEqual(self._movement_command_count(), 0)
        self.assertIn(jar.barcode, raw_recovery_data)
        self.assertTrue(any(
            expected_alert_text in kwargs.get("fmt", "")
            for _args, kwargs in self.app.main_window.alerts
        ))
        self._assert_recovery_invariants(
            raw_recovery_data,
            recovery_completed=False,
            allow_ambiguous_physics=physical_position == "ambiguous",
        )

    def test_recovery_after_shutdown_resumes_without_redispensing(self):
        order, jar, raw_recovery_data = self._run(
            self._run_recovery_after_shutdown()
        )

        properties = json.loads(jar.json_properties)
        self.assertEqual(jar.status, "DONE")
        expected_position = "_" if self.spec["in_docker"] else "OUT"
        self.assertEqual(jar.position, expected_position)
        self.assertEqual(order.status, "DONE")
        self.assertEqual(
            properties["visited_head_names"],
            list(self.spec["carousel_order"]),
        )
        self.assertEqual(
            properties["visited_head_names"].count("A"), 1
        )
        self.assertEqual(raw_recovery_data, {})
        self._assert_recovery_invariants(raw_recovery_data)


class TestCR4OrderBarcodeDispenseE2E(
        _OrderBarcodeDispenseE2EMixin, unittest.TestCase):
    VARIANT = "CR4"


class TestCR6OrderBarcodeDispenseE2E(
        _OrderBarcodeDispenseE2EMixin, unittest.TestCase):
    VARIANT = "CR6"

    def test_recovery_without_durable_dispense_marker_fails_closed(self):
        self._assert_failed_closed_recovery(
            dispensation_state=None,
            dispense_before_shutdown=False,
            expected_a_dispenses=0,
        )

    def test_recovery_during_dispense_fails_closed_without_repeating_it(self):
        self._assert_failed_closed_recovery(
            dispensation_state="ongoing",
            dispense_before_shutdown=True,
            expected_a_dispenses=1,
        )

    def test_recovery_after_dispense_failure_does_not_repeat_it(self):
        self._assert_failed_closed_recovery(
            dispensation_state="dispensation_failure",
            dispense_before_shutdown=True,
            expected_a_dispenses=1,
        )

    def test_recovery_deduces_jar_on_next_head(self):
        order, jar, raw_recovery_data = self._run(
            self._run_recovery_after_shutdown(
                dispensation_state="done",
                dispense_before_shutdown=True,
                physical_position="next",
            )
        )

        properties = json.loads(jar.json_properties)
        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "OUT")
        self.assertEqual(order.status, "DONE")
        self.assertEqual(
            properties["visited_head_names"],
            list(self.spec["carousel_order"]),
        )
        self.assertEqual(self._dispense_command_count("A"), 1)
        self.assertEqual(self._dispense_command_count("B"), 1)
        self.assertEqual(raw_recovery_data, {})
        self._assert_recovery_invariants(raw_recovery_data)

    def test_recovery_blocks_when_jar_is_missing_from_both_heads(self):
        self._assert_recovery_blocked_by_physical_state(
            physical_position="missing",
            expected_alert_text="Jar not detected",
        )

    def test_recovery_blocks_on_ambiguous_double_occupancy(self):
        self._assert_recovery_blocked_by_physical_state(
            physical_position="ambiguous",
            expected_alert_text="Ambiguous jar position",
        )

    def test_disconnect_after_macro_ack_fails_order_without_hanging(self):
        head_a = self.app.get_machine_head_by_letter("A")
        head_a.websocket.fault_policy.append({
            "command": "DISPENSE_FORMULA",
            "behavior": "disconnect_after_ack",
        })
        self.app.main_window.on_frozen_dialog = (
            lambda: self.loop.call_later(
                0.01, self.app.freeze_carousel, False
            )
        )

        order, jar, _reader, _barcode = self._run(self._run_e2e())

        properties = json.loads(jar.json_properties)
        outcomes = dict(properties["dispensation_outcomes"])
        self.assertEqual(jar.status, "ERROR")
        self.assertEqual(jar.position, "_")
        self.assertEqual(order.status, "ERROR")
        self.assertIn(
            "failure waiting for dispensation to start", outcomes["A"]
        )
        self.assertEqual(self._dispense_command_count("A"), 1)
        self.assertEqual(head_a.websocket.connection_generation, 2)
        self.assertEqual(
            [event["behavior"] for event in head_a.websocket.fault_events],
            ["disconnect_after_ack"],
        )
        self.assertGreaterEqual(len(self.app.main_window.frozen_dialogs), 1)
        self.assertTrue(self.app.ready_to_read_a_barcode)
        self._assert_runtime_invariants()

    def test_restart_with_pending_movement_retries_on_new_connection(self):
        head_a = self.app.get_machine_head_by_letter("A")
        head_a.websocket.fault_policy.append({
            "command": "CRX_OUTPUTS_MANAGEMENT",
            "params": {"Output_Number": 0, "Output_Action": 1},
            "behavior": "restart_with_pending_request",
        })
        self.app.main_window.on_frozen_dialog = (
            lambda: self.loop.call_later(
                0.01, self.app.freeze_carousel, False
            )
        )

        order, jar, _reader, _barcode = self._run(self._run_e2e())

        properties = json.loads(jar.json_properties)
        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "_")
        self.assertEqual(order.status, "DONE")
        self.assertEqual(
            properties["visited_head_names"],
            list(self.spec["carousel_order"]),
        )
        self.assertEqual(self._dispense_command_count("A"), 1)
        self.assertEqual(head_a.websocket.connection_generation, 2)
        self.assertEqual(
            [event["behavior"] for event in head_a.websocket.fault_events],
            ["restart_with_pending_request"],
        )
        self.assertGreaterEqual(len(self.app.main_window.frozen_dialogs), 1)
        self.assertTrue(self.app.ready_to_read_a_barcode)
        self._assert_runtime_invariants()

    def test_destination_movement_nack_stops_and_retries_safely(self):
        head_b = self.app.get_machine_head_by_letter("B")
        head_b.websocket.fault_policy.append({
            "command": "CRX_OUTPUTS_MANAGEMENT",
            "params": {"Output_Number": 0, "Output_Action": 2},
            "behavior": "negative_answer",
            "status_code": 254,
            "error": "time expired in waiting for reply in bus cache",
        })
        self.app.main_window.on_frozen_dialog = (
            lambda: self.loop.call_later(
                0.01, self.app.freeze_carousel, False
            )
        )

        order, jar, _reader, _barcode = self._run(self._run_e2e())

        destination_starts = [
            command for command in head_b.websocket.sent
            if command["command"] == "CRX_OUTPUTS_MANAGEMENT"
            and command["params"] == {
                "Output_Number": 0, "Output_Action": 2
            }
        ]
        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "_")
        self.assertEqual(order.status, "DONE")
        self.assertEqual(len(destination_starts), 2)
        self.assertEqual(self._dispense_command_count("A"), 1)
        self.assertEqual(head_b.websocket.connection_generation, 1)
        self.assertEqual(
            [event["behavior"] for event in head_b.websocket.fault_events],
            ["negative_answer"],
        )
        self.assertGreaterEqual(len(self.app.main_window.frozen_dialogs), 1)
        self.assertTrue(self.app.ready_to_read_a_barcode)
        self._assert_runtime_invariants()

    def test_lost_movement_answer_uses_telemetry_without_retry(self):
        head_a = self.app.get_machine_head_by_letter("A")
        head_a.websocket.fault_policy.append({
            "command": "CRX_OUTPUTS_MANAGEMENT",
            "params": {"Output_Number": 0, "Output_Action": 1},
            "behavior": "restart_after_execution_before_answer",
        })

        order, jar, _reader, _barcode = self._run(self._run_e2e())

        source_starts = [
            command for command in head_a.websocket.sent
            if command["command"] == "CRX_OUTPUTS_MANAGEMENT"
            and command["params"] == {
                "Output_Number": 0, "Output_Action": 1
            }
        ]
        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "_")
        self.assertEqual(order.status, "DONE")
        self.assertEqual(len(source_starts), 1)
        self.assertEqual(self._dispense_command_count("A"), 1)
        self.assertEqual(head_a.websocket.connection_generation, 2)
        self.assertEqual(
            [event["behavior"] for event in head_a.websocket.fault_events],
            ["restart_after_execution_before_answer"],
        )
        self.assertEqual(self.app.main_window.frozen_dialogs, [])
        self.assertTrue(self.app.ready_to_read_a_barcode)
        self._assert_runtime_invariants()

    def test_lost_stop_is_retried_by_real_watchdog(self):
        head_b = self.app.get_machine_head_by_letter("B")
        head_b.output_timeout_overrides[0] = 0.05
        head_b.websocket.fault_policy.append({
            "command": "CRX_OUTPUTS_MANAGEMENT",
            "params": {"Output_Number": 0, "Output_Action": 0},
            "behavior": "restart_with_pending_stop",
        })

        async def run_with_watchdog_after_fault():
            e2e_task = asyncio.ensure_future(self._run_e2e())
            while not head_b.websocket.fault_events:
                if e2e_task.done():
                    return await e2e_task
                await asyncio.sleep(0)

            watchdog_task = asyncio.ensure_future(
                head_b._MachineHead__watch_dog_task()
            )
            try:
                return await e2e_task
            finally:
                if watchdog_task.done() and not watchdog_task.cancelled():
                    exception = watchdog_task.exception()
                    if exception is not None:
                        self.exceptions.append(exception)
                watchdog_task.cancel()
                await asyncio.gather(
                    watchdog_task, return_exceptions=True
                )

        order, jar, _reader, _barcode = self._run(
            run_with_watchdog_after_fault()
        )

        output_actions = [
            command["params"]["Output_Action"]
            for command in head_b.websocket.sent
            if command["command"] == "CRX_OUTPUTS_MANAGEMENT"
            and command["params"]["Output_Number"] == 0
        ]
        inner = head_b._MachineHead__crx_inner_status[0]
        self.assertEqual(jar.status, "DONE")
        self.assertEqual(jar.position, "_")
        self.assertEqual(order.status, "DONE")
        self.assertEqual(output_actions, [2, 0, 0, 1, 0])
        self.assertEqual(self._dispense_command_count("A"), 1)
        self.assertEqual(self._dispense_command_count("B"), 1)
        self.assertEqual(head_b.websocket.connection_generation, 2)
        self.assertEqual(
            [event["behavior"] for event in head_b.websocket.fault_events],
            ["restart_with_pending_stop"],
        )
        self.assertEqual(
            {key: inner[key] for key in ("value", "timeout", "t0")},
            {"value": 0, "timeout": 0, "t0": 0},
        )
        self.assertEqual(self.app.main_window.frozen_dialogs, [])
        self.assertTrue(self.app.ready_to_read_a_barcode)
        self._assert_runtime_invariants()


class TestCRX60OrderBarcodeDispenseE2E(
        _OrderBarcodeDispenseE2EMixin, unittest.TestCase):
    VARIANT = "CRX60"


class TestCRX80OrderBarcodeDispenseE2E(
        _OrderBarcodeDispenseE2EMixin, unittest.TestCase):
    VARIANT = "CRX80"


if __name__ == "__main__":
    unittest.main()
