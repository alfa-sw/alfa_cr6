# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-few-public-methods
# pylint: disable=multiple-statements
# pylint: disable=logging-fstring-interpolation, consider-using-f-string
# pylint: disable=too-many-lines

import os
import copy
import logging
import traceback
import asyncio
import json
import time

from PyQt5.QtCore import Qt, QTimer

from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QApplication

from alfa_CR6_backend.globals import (import_settings, get_res, tr_, DEFAULT_DEBUG_PAGE_PWD)
from alfa_CR6_backend.dymo_printer import async_dymo_print_pigment_labels, async_dymo_print_low_pigment_labels

from alfa_CR6_frontend.pages import BaseStackedPage
from alfa_CR6_frontend.debug_page import simulate_read_barcode


g_settings = import_settings()

LINER_REMINDER_MESSAGE = "Please ensure a PPS liner is placed inside the shuttle"


class PrintException(Exception):
    def __init__(self, message, payload):
        super().__init__(message)
        self.payload = payload


class PrintLabelHelper:

    def __init__(self, parent=None, printables=[]):
        self.parent = parent
        self.printables = printables

    async def print_labels(self):
        fake_print = os.getenv("FAKE_DYMO_PRINT", False) in ["1", "true"]

        try:
            ret = await async_dymo_print_pigment_labels(self.printables, fake=fake_print)
            logging.debug("print_labels ret: %s", ret)

            if ret['result'] != 'OK':
                raise PrintException("Printing failed", ret)

        except PrintException as pexc:
            error_message = pexc.payload
            logging.error(f"PrintException: {error_message}")
            QApplication.instance().main_window.open_input_dialog(
                icon_name="SP_MessageBoxCritical",
                message=error_message,
                content=None)
            return

        msg_ = tr_("OK")
        QApplication.instance().main_window.open_input_dialog(
            icon_name="SP_MessageBoxQuestion",
            message=msg_,
            content=None)

    def run(self):

        if not self.printables:
            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxCritical",
                message="Missing printables ...")
            return

        t = self.print_labels()
        asyncio.ensure_future(t)


class LowPigmentsPrintHelper:

    def __init__(self, parent=None):
        self.parent = parent

    @staticmethod
    def collect_low_pigment_heads():
        # All heads currently in 'Low Pigments' state, with their low pipes.
        app = QApplication.instance()
        per_head = []
        for m in app.machine_head_dict.values():
            if m and m.low_level_pipes:
                per_head.append({'head_name': m.name, 'low_pipes': list(m.low_level_pipes)})
        return per_head

    async def print_labels(self):
        fake_print = os.getenv("FAKE_DYMO_PRINT", False) in ["1", "true"]

        per_head = self.collect_low_pigment_heads()
        if not per_head:
            # Defensive only: the reserve label is shown (hence clickable) just
            # while a head has low_level_pipes, so reaching here with nothing to
            # print would require all heads to clear between click and run.
            logging.warning("print Low Pigments label: no head in low-level state, nothing to print")
            return

        try:
            ret = await async_dymo_print_low_pigment_labels(per_head, fake=fake_print)
            logging.debug("print_low_pigment_labels ret: %s", ret)

            if ret['result'] != 'OK':
                raise PrintException("Printing failed", ret)

        except PrintException as pexc:
            error_message = pexc.payload
            logging.error(f"PrintException: {error_message}")
            QApplication.instance().main_window.open_input_dialog(
                icon_name="SP_MessageBoxCritical",
                message=error_message,
                content=None)
            return

        msg_ = tr_("OK")
        QApplication.instance().main_window.open_input_dialog(
            icon_name="SP_MessageBoxQuestion",
            message=msg_,
            content=None)

    def run(self):
        t = self.print_labels()
        asyncio.ensure_future(t)


class RefillProcedureHelper:

    def __init__(self, parent, head_index):

        self.parent = parent
        self.machine_ = QApplication.instance().machine_head_dict[head_index]

        self.refill_choices = self._get_refill_choices()

        self.units_ = "CC"
        if self.machine_.machine_config:
            self.units_ = self.machine_.machine_config.get('UNITS', {}).get('service_page_unit')

        self.fl_oz_unit = self.machine_.machine_config.get('UNITS', {}).get('fl_oz_unit', 1)

        t = self.machine_.update_tintometer_data()
        asyncio.ensure_future(t)

    @staticmethod
    def _get_refill_choices():
        choices = []
        if os.getenv("IN_DOCKER", False) in ['1', 'true']:
            choices = g_settings.USER_SETTINGS.get('POPUP_REFILL_CHOICES', [])
        else:
            choices = g_settings.POPUP_REFILL_CHOICES

        logging.warning(f"choices: {choices}")
        return sorted(choices, reverse=True)

    def __qtity_from_ml(self, val, pigment_name):

        _convert_factor = {
            "CC": 1.,
            "GR": self.machine_.get_specific_weight(pigment_name),
            "FL OZ": 1. / self.fl_oz_unit,
        }.get(self.units_, 1)
        logging.warning(f"_convert_factor({type(_convert_factor)}):{_convert_factor}.")
        return round(_convert_factor * float(val), 2)

    def __qtity_to_ml(self, val, pigment_name):

        _convert_factor = {
            "CC": 1.,
            "GR": 1. / self.machine_.get_specific_weight(pigment_name),
            "FL OZ": 1. * self.fl_oz_unit,
        }.get(self.units_, 1)
        # ~ logging.warning(f"_convert_factor({type(_convert_factor)}):{_convert_factor}.")
        return _convert_factor * float(val)

    def _cb_confirm_reset(self):

        t = self.machine_.send_command(
            cmd_name="RESET",
            params={"mode": 0},
            type_="command",
            channel="machine")
        asyncio.ensure_future(t)

    async def __update_level_task(self, pigment_, pipe_, qtity_ml_, updated_spec_weight=None,
                                  qr_code_info=None):

        def _cb_on_refill(answer):
            logging.warning(f"answer:{answer}.")
            try:
                msg_ = ""
                for k, v in answer.items():
                    _ = " ".join(
                        [f"{_k}, {self.__qtity_from_ml(_v, pigment_['name'])} ({self.units_.lower()})" for _k, _v in v.items()])
                    msg_ += f"{tr_(k)}: {_}"
                    msg_ += tr_(". RESET head: {} ?").format(self.machine_.name)
                logging.warning(f"msg_:{msg_}.")
                self.parent.main_window.open_input_dialog(
                    icon_name="SP_MessageBoxInformation",
                    message=msg_,
                    ok_cb=self._cb_confirm_reset)
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        # ~ data = {'action': 'adjust_pipe_levels', 'params': {pipe_['name']: qtity_ml_}}
        # ~ answer = await self.machine_.call_api_rest("apiV1/ad_hoc", "POST", data, timeout=8)
        # ~ _cb_on_refill(answer)
        params_ = {'items': [{'name': pipe_['name'], 'qtity': qtity_ml_}]}
        if updated_spec_weight:
            params_['items'][0]['specific_weight'] = updated_spec_weight
        if qr_code_info:
            params_['items'][0]['QR_code_info'] = qr_code_info
        await self.machine_.send_command(cmd_name="REFILL", params=params_, type_="macro", callback_on_macro_answer=_cb_on_refill)

        await self.machine_.update_tintometer_data()
        self.parent.main_window.browser_page.reload_page()

        margs = (pipe_['name'], qtity_ml_)
        rfll_msg = "Refilled pipe {} with {} ML".format(*margs)
        alert_infos = {'fmt': rfll_msg, 'args': margs, 'msg_': rfll_msg, 'msg': rfll_msg}
        json_properties_ = json.dumps(
            alert_infos,
            indent=2,
            ensure_ascii=False
        )
        QApplication.instance().insert_db_event(
            name='UI_DIALOG',
            level="INFO",
            severity='',
            source="RefillProcedureHelper",
            json_properties=json_properties_,
            description=rfll_msg
        )

    def _cb_confirm_quantity(self, pigment_, pipe_, qtity_ml_, updated_spec_weight=None,
                             qr_code_info=None):

        t = self.__update_level_task(pigment_, pipe_, qtity_ml_, updated_spec_weight,
                                     qr_code_info=qr_code_info)
        asyncio.ensure_future(t)

    def _cb_input_quantity(self, pigment_, pipe_, updated_spec_weight=None, from_qrcode=False,
                           lot_specific_weight=None, current_specific_weight=None,
                           qr_code_info=None):

        self.parent.main_window.toggle_keyboard(on_off=False)

        qtity_units_ = self.parent.main_window.refill_dialog.get_content_text()
        qtity_units_ = round(float(qtity_units_), 2)
        qtity_ml_ = self.__qtity_to_ml(qtity_units_, pigment_['name'])

        logging.warning("maximum_level:{}, current_level:{}, qtity_ml_:{}, qtity_units_:{}".format(
            pipe_['maximum_level'], pipe_['current_level'], qtity_ml_, qtity_units_))

        def _recompute_spec_weight(refill_ml):
            if lot_specific_weight is None or current_specific_weight is None:
                return updated_spec_weight
            tot_vol = refill_ml + pipe_['current_level']
            if tot_vol <= 0:
                return updated_spec_weight
            tot_weight = lot_specific_weight * refill_ml + current_specific_weight * pipe_['current_level']
            return tot_weight / tot_vol

        def _qr_info_with(spec_weight):
            if qr_code_info is None:
                return None
            info = dict(qr_code_info)
            info["specific_weight"] = spec_weight
            return info

        if pipe_['maximum_level'] >= (pipe_['current_level'] + qtity_ml_) * 0.98:
            spec_weight_ = _recompute_spec_weight(qtity_ml_)
            msg_ = """please, confirm refilling pipe: {} <br>with {} ({}) of product: {}?."""
            msg_ = tr_(msg_).format(pipe_['name'], qtity_units_, self.units_.lower(), pigment_['name'])

            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=msg_,
                content=None,
                ok_cb=self._cb_confirm_quantity,
                ok_cb_args=(pigment_, pipe_, qtity_ml_, spec_weight_, _qr_info_with(spec_weight_)))
        elif from_qrcode:
            cap_ml_ = pipe_['maximum_level'] - pipe_['current_level']
            cap_units_ = round(self.__qtity_from_ml(cap_ml_, pigment_['name']), 2)
            cap_spec_weight = _recompute_spec_weight(cap_ml_)

            msg_ = ("QR proposes {} ({}) which exceeds maximum level for pipe: {}.<br>"
                    "Refill will be capped to {} ({}). Confirm?")
            msg_ = tr_(msg_).format(
                qtity_units_, self.units_.lower(), pipe_['name'],
                cap_units_, self.units_.lower())
            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxWarning",
                message=msg_,
                content=None,
                ok_cb=self._cb_confirm_quantity,
                ok_cb_args=(pigment_, pipe_, cap_ml_, cap_spec_weight, _qr_info_with(cap_spec_weight)))
        else:
            msg_ = """refilling with {} ({}) would exceed maximum level! Aborting."""
            msg_ = tr_(msg_).format(qtity_units_, self.units_.lower())
            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxCritical",
                message=msg_)

    def _cb_verify_barcode(self, pigment_, pipe_, _default_qtity_units, barcode_):

        barcode_check = self.parent.main_window.input_dialog.get_content_text()
        barcode_check = barcode_check.strip()
        logging.warning(f"{self.machine_.name} barcode_check:{barcode_check}.")

        current_level_ = pipe_['current_level']
        current_level_ = self.__qtity_from_ml(current_level_, pigment_['name'])
        current_level_ = round(current_level_, 2)
        _default_qtity_units = str(_default_qtity_units).strip()
        msg_ = """please, input quantity (in {}) of product: {}<br> for refilling pipe: {} (current level:{}),<br> leave as is for total refill or select from the list."""
        msg_ = tr_(msg_).format(self.units_.lower(), pigment_['name'], pipe_['name'], current_level_)
        margin_ml_ = pipe_['maximum_level'] - pipe_['current_level']
        margin_units_ = self.__qtity_from_ml(margin_ml_, pigment_['name'])

        if barcode_check == barcode_:
            self.parent.main_window.hide_input_dialog()
            self.parent.main_window.toggle_keyboard(on_off=True)
            info_flup = f"{margin_units_} {self.units_}"
            choices_ = [{
                "label": tr_("FILL UP"),
                "value": round(margin_units_, 2)
            }] + list(self.refill_choices)

            self.parent.main_window.open_refill_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=msg_,
                unit=self.units_,
                ok_cb=self._cb_input_quantity,
                ok_cb_args=(pigment_, pipe_),
                choices=choices_)
        else:
            def _cb_reset_refill_block():
                QApplication.instance().barcode_read_blocked_on_refill = False

            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxCritical",
                message=tr_("barcode mismatch <br/>{} != {}").format(barcode_, barcode_check),
                content=None,
                ok_cb=_cb_reset_refill_block)

    async def _rotate_circuit_task(
            self, pigment_, pipe_, _default_qtity_units, barcode_,
            skip_verify=False, qrcode_refill_infos={}
    ):

        def __get_pipe_index_from_name(p_name):

            pipe_addresses = {"B%02d" % (i + 1): i for i in range(0, 8)}
            pipe_addresses.update({"C%02d" % (i - 7): i for i in range(8, 32)})
            return pipe_addresses[p_name]

        pipe_index = __get_pipe_index_from_name(pipe_['name'])
        pars_ = {'Id_color_circuit': pipe_index, 'Refilling_angle': 0, 'Direction': 0}

        t = self.machine_.send_command(cmd_name='DIAG_ROTATING_TABLE_POSITIONING',
                                       params=pars_, type_='command', channel='machine')
        asyncio.ensure_future(t)

        if not skip_verify:
            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=tr_("please, verify barcode {} on canister.").format(barcode_),
                content="",
                ok_cb=self._cb_verify_barcode,
                ok_cb_args=(pigment_, pipe_, _default_qtity_units, barcode_),
                ok_on_enter=1)

        else:
            current_level_ = pipe_['current_level']
            current_level_ = self.__qtity_from_ml(current_level_, pigment_['name'])
            current_level_ = round(current_level_, 2)
            msg_ = """please, input quantity (in {}) of product: {}<br> for refilling pipe: {} (current level:{}),<br> leave as is for total refill or select from the list."""
            msg_ = tr_(msg_).format(self.units_.lower(), pigment_['name'], pipe_['name'], current_level_)

            self.parent.main_window.hide_input_dialog()
            self.parent.main_window.toggle_keyboard(on_off=True)
            margin_ml_ = pipe_['maximum_level'] - pipe_['current_level']
            margin_units_ = self.__qtity_from_ml(margin_ml_, pigment_['name'])

            choices_ = [{
                "label": tr_("FILL UP"),
                "value": round(margin_units_, 2)
            }]
            # Keep QR-proposed qty as an additional choice if present
            qr_qty = qrcode_refill_infos.get("qty")
            if qr_qty is not None:
                choices_.append(qr_qty)

            self.parent.main_window.open_refill_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=msg_,
                unit=self.units_,
                ok_cb=self._cb_input_quantity,
                ok_cb_args=(pigment_, pipe_,
                            qrcode_refill_infos.get("new_specific_weight"), True,
                            qrcode_refill_infos.get("lot_specific_weight"),
                            qrcode_refill_infos.get("current_specific_weight"),
                            qrcode_refill_infos.get("qr_code_info")),
                choices=choices_)

    def _cb_input_barcode(self, barcode_):

        try:
            # ~ logging.warning(f"{m.name}.pigment_list:\n\t{json.dumps(m.pigment_list, indent=2)}")
            found_pigments = []
            for p in self.machine_.pigment_list:
                pigment_customer_id = p.get('customer_id')
                if pigment_customer_id and barcode_ == pigment_customer_id:
                    found_pigments.append(p)

            if found_pigments:

                def _pipe_current_level(pigment):
                    return pigment['pipes'] and pigment['pipes'][0].get('current_level', 0)

                found_pigments.sort(key=_pipe_current_level)
                pigment_ = found_pigments[0]

                pipes_ = pigment_['pipes'][:]
                pipes_.sort(key=lambda p: p['current_level'] - p['maximum_level'])

                if len(pipes_) > 1:

                    choices = {}
                    for p in pipes_:
                        try:
                            curr = round(float(p.get('current_level', 0)), 2)
                            mx = round(float(p.get('maximum_level', 0)), 2)
                            label = f"{p.get('name', '?')} (level {curr}/{mx})"
                        except Exception:
                            label = str(p.get('name', '?'))
                        choices[label] = p

                    def _on_pipe_selected(pigment=pigment_, barcode=barcode_):
                        sel_pipe = self.parent.main_window.input_dialog.get_selected_choice()
                        pipe_sel = sel_pipe or pipes_[0]
                        _default_qtity_ml = pipe_sel['maximum_level'] - pipe_sel['current_level']
                        _default_qtity_units = self.__qtity_from_ml(_default_qtity_ml, pigment['name'])
                        _default_qtity_units = round(_default_qtity_units, 2)
                        t = self._rotate_circuit_task(pigment, pipe_sel, _default_qtity_units, barcode)
                        asyncio.ensure_future(t)

                    self.parent.main_window.open_input_dialog(
                        icon_name="SP_MessageBoxQuestion",
                        message=tr_("Multiple circuits found for {}").format(pigment_['name']),
                        content= tr_('Choose circuit to refill:'),
                        choices=choices,
                        ok_cb=_on_pipe_selected,
                        ok_on_enter=False,
                        content_editable=False,
                        use_combo_for_choice=True
                    )

                else:
                    pipe_ = pipes_[0]

                    _default_qtity_ml = pipe_['maximum_level'] - pipe_['current_level']
                    _default_qtity_units = self.__qtity_from_ml(_default_qtity_ml, pigment_['name'])
                    _default_qtity_units = round(_default_qtity_units, 2)

                    t = self._rotate_circuit_task(pigment_, pipe_, _default_qtity_units, barcode_)
                    asyncio.ensure_future(t)

            else:
                h_idx = int(self.machine_.index) + 1

                def _cb_reset_refill_block():
                    QApplication.instance().barcode_read_blocked_on_refill = False

                QApplication.instance().main_window.hide_input_dialog()
                QApplication.instance().main_window.open_alert_dialog(
                    (barcode_, str(h_idx), self.machine_.name),
                    fmt="The code entered '{}' does not match any toner on HEAD {} ({})",
                    callback=_cb_reset_refill_block,
                    show_cancel_btn=False
                )

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def _cb_input(self):

        input = self.parent.main_window.input_dialog.get_content_text()
        input = input.strip()

        debug_input = os.getenv("DEBUG_INPUT")
        if debug_input is not None and debug_input != "":
            input = debug_input

        if not input:
            return

        if input.count("|") >= 10:
            t = self._check_and_decode_KCC_qrcode_string(input)
            asyncio.ensure_future(t)
        else:
            self._cb_input_barcode(input)

    async def _check_and_decode_KCC_qrcode_string(self, input):
        """
        Delegates QR decoding and validation to the head's device endpoint
        (apiV1/ad_hoc, action=check_and_decode_KCC_qrcode_string), which is the
        single source of truth for KCC lot data and specific weight calculation.
        """

        try:
            data = {
                "action": "check_and_decode_KCC_qrcode_string",
                "params": {"qrcode_string": input},
            }
            device_resp = await self.machine_.call_api_rest(
                "apiV1/ad_hoc", "POST", data, timeout=10)

            # The device endpoint wraps the JSON payload in flask Markup, so the
            # response comes back as a JSON-encoded string and needs a second parse.
            if isinstance(device_resp, str):
                import json as _json  # pylint: disable=import-outside-toplevel
                device_resp = _json.loads(device_resp)

            if not device_resp or device_resp.get("result") != "OK":
                err_msg = (device_resp or {}).get("error", "unknown error")
                args, fmt = (err_msg,), "KCC QR decode failed: {}"
                self.parent.main_window.open_alert_dialog(args, fmt=fmt, title="ERROR")
                return

            pigment_name = device_resp["pigment_name"]
            pipe_name = device_resp["pipe_name"]
            product_quantity = device_resp["product_quantity"]
            lot_specific_weight = device_resp["lot_specific_weight"]
            current_specific_weight = device_resp["current_specific_weight"]
            new_specific_weight = device_resp["specific_weight"]

            _pipe = None
            _pigment = None
            for p in self.machine_.pigment_list:
                if p.get("name") == pigment_name:
                    _pigment = p.copy()
                    pipes = _pigment.pop("pipes", None) or []
                    for pipe in pipes:
                        if pipe.get("name") == pipe_name:
                            _pipe = pipe
                            break
                    if not _pipe and pipes:
                        _pipe = pipes[0]
                    break

            if not _pipe:
                args, fmt = (pigment_name,), "pipe with pigment:{} not found."
                self.parent.main_window.open_alert_dialog(args, fmt=fmt, title="ERROR")
                return

            _default_qtity_ml = _pipe["maximum_level"] - _pipe["current_level"]
            _default_qtity_units = round(self.__qtity_from_ml(_default_qtity_ml, _pigment["name"]), 2)

            qrcode_refill = {
                "qty": product_quantity,
                "new_specific_weight": new_specific_weight,
                "lot_specific_weight": lot_specific_weight,
                "current_specific_weight": current_specific_weight,
                "qr_code_info": device_resp,
            }

            t = self._rotate_circuit_task(
                _pigment, _pipe, _default_qtity_units, input,
                skip_verify=True, qrcode_refill_infos=qrcode_refill)
            asyncio.ensure_future(t)

        except Exception as e:
            logging.error(traceback.format_exc())
            # decode_KCC_qrcode  # leftover from commit 610dc1f2, raises NameError
            self.parent.main_window.open_alert_dialog(
                args=(),
                fmt="DECODE KCC QRCODE EXCEPTION",
                title="ERROR",
                traceback=traceback.format_exc())

    def run(self):

        self.parent.main_window.open_input_dialog(
            icon_name="SP_MessageBoxQuestion",
            message=tr_("please, input barcode for refill"),
            content="",
            ok_cb=self._cb_input,
            ok_on_enter=1)


class HomePage(BaseStackedPage):

    # in-transit labels: shown when adjacent photocells are simultaneously occupied
    # subclasses declare = None for labels missing from their UI file
    STEP_01_02_label = None

    _blink_step_label = None
    _blink_state = False

    _belt_blink_timer = None
    _belt_blink_state = False
    STEP_02_03_label = None
    STEP_02_04_label = None  # four-heads only (skips HEAD B)
    STEP_03_04_label = None
    STEP_04_05_label = None
    STEP_06_07_label = None
    STEP_07_08_label = None
    STEP_07_09_label = None  # four-heads only (skips HEAD E)
    STEP_08_09_label = None
    STEP_09_10_label = None
    STEP_11_12_label = None

    def __init__(self, *args, **kwargs):  # pylint:disable=too-many-branches, too-many-statements

        super().__init__(*args, **kwargs)

        self.jar_pixmap_map = [
            (self.STEP_01_label,    (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),), "IN_A",),
            (self.STEP_01_02_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"), ("A", "JAR_DISPENSING_POSITION_PHOTOCELL")), "IN_A", (("IN_A",), ("A",)),),
            (self.STEP_02_label,    (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "A",),
            (self.STEP_02_03_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("B", "JAR_DISPENSING_POSITION_PHOTOCELL")), "A", (("A",), ("B",)),),
            (self.STEP_02_04_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("C", "JAR_DISPENSING_POSITION_PHOTOCELL")), "A", (("A",), ("C",)),),
            (self.STEP_03_label,    (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "B",),
            (self.STEP_03_04_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("C", "JAR_DISPENSING_POSITION_PHOTOCELL")), "B", (("B",), ("C",)),),
            (self.STEP_04_label,    (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "C",),
            (self.STEP_04_05_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL")), "C", (("C",), ("LIFTR_UP", "LIFTR_DOWN")),),
            (self.STEP_05_label,    (("D", "LOAD_LIFTER_UP_PHOTOCELL"), ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTR_UP",),
            (self.STEP_06_label,    (("D", "LOAD_LIFTER_DOWN_PHOTOCELL"), ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTR_DOWN",),
            (self.STEP_06_07_label, (("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"), ("D", "JAR_DISPENSING_POSITION_PHOTOCELL")), "LIFTR_DOWN", (("LIFTR_UP", "LIFTR_DOWN"), ("D",)),),
            (self.STEP_07_label,    (("D", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "D",),
            (self.STEP_07_08_label, (("D", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("E", "JAR_DISPENSING_POSITION_PHOTOCELL")), "D", (("D",), ("E",)),),
            (self.STEP_07_09_label, (("D", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("F", "JAR_DISPENSING_POSITION_PHOTOCELL")), "D", (("D",), ("F",)),),
            (self.STEP_08_label,    (("E", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "E",),
            (self.STEP_08_09_label, (("E", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("F", "JAR_DISPENSING_POSITION_PHOTOCELL")), "E", (("E",), ("F",)),),
            (self.STEP_09_label,    (("F", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "F",),
            (self.STEP_09_10_label, (("F", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL")), "F", (("F",), ("LIFTL_DOWN", "LIFTL_UP")),),
            (self.STEP_10_label,    (("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"), ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTL_DOWN",),
            (self.STEP_11_label,    (("F", "UNLOAD_LIFTER_UP_PHOTOCELL"), ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTL_UP",),
            (self.STEP_11_12_label, (("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"), ("F", "JAR_OUTPUT_ROLLER_PHOTOCELL")), "LIFTL_UP", (("LIFTL_UP", "LIFTL_DOWN"), ("OUT",)),),
            (self.STEP_12_label,    (("F", "JAR_OUTPUT_ROLLER_PHOTOCELL"),), "OUT",),
        ]

        self.running_jars_lbl.setStyleSheet("font-size: 15px")

        for b in self.action_btn_group.buttons():
            b.setStyleSheet(
                """QPushButton { background-color: #00FFFFFF; border: 0px;}"""
            )

            # Prevent stray ENTER (e.g. trailing newline from a barcode gun whose
            # device isn't grabbed by evdev) from "clicking" the focused action
            # button — observed firing move_00_01 unintentionally.
            b.setAutoDefault(False)
            b.setDefault(False)
            b.setFocusPolicy(Qt.NoFocus)

            if "recovery_btn" in b.objectName():
                b.setStyleSheet(
                    """QPushButton { background-color: #00FFFFFF; color: #47AE4B; border: 2px solid #000000; font-size: 20px; text-align: center;}"""
                )

        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)
        self.action_btn_group.buttonClicked.connect(self.on_action_btn_group_clicked)

        self.reserve_movie = QMovie(get_res("IMAGE", "riserva.gif"))
        self.expiry_movie = QMovie(get_res("IMAGE", "expiry.gif"))

        self._blinking_belt_indexes = set()
        for lbl in self._belt_label_map():
            if lbl:
                lbl.setVisible(False)

        if self.STEP_01_label:
            self.STEP_01_label.mouseReleaseEvent = lambda event: self.step_label_clicked("IN")
        if self.STEP_02_label:
            self.STEP_02_label.mouseReleaseEvent = lambda event: self.step_label_clicked("A")
        if self.STEP_03_label:
            self.STEP_03_label.mouseReleaseEvent = lambda event: self.step_label_clicked("B")
        if self.STEP_04_label:
            self.STEP_04_label.mouseReleaseEvent = lambda event: self.step_label_clicked("C")
        if self.STEP_05_label:
            self.STEP_05_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTR_UP")
        if self.STEP_06_label:
            self.STEP_06_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTR_DOWN")
        if self.STEP_07_label:
            self.STEP_07_label.mouseReleaseEvent = lambda event: self.step_label_clicked("D")
        if self.STEP_08_label:
            self.STEP_08_label.mouseReleaseEvent = lambda event: self.step_label_clicked("E")
        if self.STEP_09_label:
            self.STEP_09_label.mouseReleaseEvent = lambda event: self.step_label_clicked("F")
        if self.STEP_10_label:
            self.STEP_10_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTL_DOWN")
        if self.STEP_11_label:
            self.STEP_11_label.mouseReleaseEvent = lambda event: self.step_label_clicked("LIFTL_UP")
        if self.STEP_12_label:
            self.STEP_12_label.mouseReleaseEvent = lambda event: self.step_label_clicked("OUT")

        if self.reserve_1_label:
            self.reserve_1_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(0)
        if self.reserve_2_label:
            self.reserve_2_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(1)
        if self.reserve_3_label:
            self.reserve_3_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(2)
        if self.reserve_4_label:
            self.reserve_4_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(3)
        if self.reserve_5_label:
            self.reserve_5_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(4)
        if self.reserve_6_label:
            self.reserve_6_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(5)
        if self.reserve_7_label:
            self.reserve_7_label.mouseReleaseEvent = lambda event: self.reserve_label_clicked(6)

        if self.expiry_1_label:
            self.expiry_1_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(0)
        if self.expiry_2_label:
            self.expiry_2_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(1)
        if self.expiry_3_label:
            self.expiry_3_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(2)
        if self.expiry_4_label:
            self.expiry_4_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(3)
        if self.expiry_5_label:
            self.expiry_5_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(4)
        if self.expiry_6_label:
            self.expiry_6_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(5)
        if self.expiry_7_label:
            self.expiry_7_label.mouseReleaseEvent = lambda event: self.expiry_label_clicked(6)

        if self.refill_1_lbl:
            self.refill_1_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(0)
        if self.refill_2_lbl:
            self.refill_2_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(1)
        if self.refill_3_lbl:
            self.refill_3_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(2)
        if self.refill_4_lbl:
            self.refill_4_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(3)
        if self.refill_5_lbl:
            self.refill_5_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(4)
        if self.refill_6_lbl:
            self.refill_6_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(5)
        if self.refill_7_lbl:
            self.refill_7_lbl.mouseReleaseEvent = lambda event: self.refill_lbl_clicked(6)

        # self.printer_helper = PrinterHelper()
        # self.printer_helper.all_prints_finished.connect(self.on_all_prints_finished)
        # self.printer_helper.print_error.connect(self.on_print_error)

        self.lbl_recovery.hide()
        self.recovery_btn.setText(tr_("START \nRECOVERY"))
        self.recovery_info_btn.hide()

    def open_page(self):

        self.parent().setCurrentWidget(self)

    def on_service_btn_group_clicked(self, btn):

        # timestamp del CLICK: misura la latenza reale click -> pagina caricata
        # (passato a open_page, loggato in browser_page.__on_load_finish)
        _clicked_at = time.monotonic()
        btn_name = btn.objectName()

        try:
            service_page_query = "?light_service_page=1"
            service_page_urls = [f"http://127.0.0.1:8080/service_page/{service_page_query}", ]
            for i in QApplication.instance().settings.MACHINE_HEAD_IPADD_PORTS_LIST:
                if i:
                    url = "http://{}:{}/service_page/{}".format(i[0], i[2], service_page_query)
                else:
                    url = None
                service_page_urls.append(url)

            service_btns = [
                self.service_0_btn,
                self.service_1_btn,
                self.service_2_btn,
                self.service_3_btn,
                self.service_4_btn,
                self.service_5_btn,
                self.service_6_btn,
                self.service_7_btn,
            ]

            map_ = dict(zip(service_btns, service_page_urls))

            head_index = service_btns.index(btn) - 1
            logging.debug("btn_name:%s, map_[btn]:%s, map_:%s, head_index:%s", btn_name, map_[btn], map_, head_index)

            self.main_window.browser_page.open_page(map_[btn], head_index=head_index, requested_at=_clicked_at)

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def on_action_btn_group_clicked(self, btn):

        btn_name = btn.objectName()
        try:
            if "feed" in btn_name:
                self._on_feed_jar_clicked()

            elif "deliver" in btn_name:
                QApplication.instance().run_a_coroutine_helper("move_12_00")
            elif "freeze_carousel" in btn_name:
                msg_ = (
                    tr_("confirm unfreezing carousel?")
                    if QApplication.instance().carousel_frozen
                    else tr_("confirm freezing carousel?")
                )
                self.main_window.open_input_dialog(
                    icon_name=None,
                    message=msg_,
                    content=None,
                    ok_cb=QApplication.instance().toggle_freeze_carousel,
                )
            elif "action_" in btn_name:
                # ~ Mettere l'accesso a tutti i comandi manuali presenti nel sinottico sotto password.

                self.main_window.toggle_keyboard(on_off=True)

                def ok_cb_():
                    debug_page_pwd = DEFAULT_DEBUG_PAGE_PWD
                    if hasattr(g_settings, 'DEBUG_PAGE_PWD') and g_settings.DEBUG_PAGE_PWD:
                        debug_page_pwd = g_settings.DEBUG_PAGE_PWD

                    pwd_ = self.main_window.input_dialog.content_container.toPlainText()
                    if pwd_ == debug_page_pwd:

                        self.main_window.action_frame_map[btn].show_values_in_labels()
                        self.parent().setCurrentWidget(self.main_window.action_frame_map[btn])
                        self.main_window.toggle_keyboard(on_off=False)

                msg_ = tr_("please, enter service password")
                self.main_window.open_input_dialog(message=msg_,  content="", ok_cb=ok_cb_)

            elif "recovery" in btn_name:
                QApplication.instance().run_a_coroutine_helper("machine_recovery")

            for i, m in QApplication.instance().machine_head_dict.items():
                if m:
                    self.main_window.update_status_data(i)

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def _on_feed_jar_clicked(self):
        self._start_feed_jar()

        if getattr(g_settings, 'REMINDER_LINER', False):
            self.main_window.open_alert_dialog(
                (),
                fmt=LINER_REMINDER_MESSAGE,
                title="REMINDER",
                show_cancel_btn=True,
                show_ok_btn=False,
            )

    @staticmethod
    def _start_feed_jar():
        if (hasattr(g_settings, 'SIMULATE_READ_BARCODE')
                and getattr(g_settings, 'SIMULATE_READ_BARCODE')):
            allowed_jar_statuses = g_settings.SIMULATE_READ_BARCODE.get(
                "allowed_jar_statuses", ("NEW", "DONE"))
            simulate_read_barcode(allowed_jar_statuses)
        else:
            QApplication.instance().run_a_coroutine_helper("move_00_01")

    def update_expired_products(self, head_index):

        map_ = [
            self.expiry_1_label,
            self.expiry_2_label,
            self.expiry_3_label,
            self.expiry_4_label,
            self.expiry_5_label,
            self.expiry_6_label,
            self.expiry_7_label,
        ]

        m = QApplication.instance().machine_head_dict.get(head_index)
        try:
            if m and map_[head_index]:

                # ~ logging.warning(f"head_index:{head_index}, m.expired_products:{m.expired_products}")

                if m.expired_products:
                    map_[head_index].setMovie(self.expiry_movie)
                    self.expiry_movie.start()
                    map_[head_index].show()
                else:
                    map_[head_index].setText("")
                    map_[head_index].hide()

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def _belt_label_map(self):
        return [
            self.belt_label_1,
            self.belt_label_2,
            self.belt_label_3,
            self.belt_label_4,
            self.belt_label_5,
            self.belt_label_6,
            self.belt_label_7,
        ]

    def update_table_belt_health(self, head_index):

        map_ = self._belt_label_map()
        m = QApplication.instance().machine_head_dict.get(head_index)
        try:
            lbl = map_[head_index]
            if not (m and lbl):
                return

            msg = m.table_belt_health_msg if isinstance(m.table_belt_health_msg, dict) else {}
            status = msg.get('status')

            if status and status != 'ok':
                self._blinking_belt_indexes.add(head_index)
                lbl.setVisible(True)
                self._start_belt_blink()
            else:
                self._blinking_belt_indexes.discard(head_index)
                lbl.setVisible(False)
                if not self._blinking_belt_indexes:
                    self._stop_belt_blink()

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def _start_belt_blink(self):
        if self._belt_blink_timer is None:
            self._belt_blink_timer = QTimer(self)
            self._belt_blink_timer.timeout.connect(self._do_belt_blink)
        if not self._belt_blink_timer.isActive():
            self._belt_blink_state = True
            self._belt_blink_timer.start(500)

    def _stop_belt_blink(self):
        if self._belt_blink_timer is not None:
            self._belt_blink_timer.stop()
            self._belt_blink_timer.deleteLater()
            self._belt_blink_timer = None
        self._belt_blink_state = False

    def _do_belt_blink(self):
        if not self._blinking_belt_indexes:
            self._stop_belt_blink()
            return
        self._belt_blink_state = not self._belt_blink_state
        visible = self._belt_blink_state
        map_ = self._belt_label_map()
        for idx in self._blinking_belt_indexes:
            lbl = map_[idx]
            if lbl:
                lbl.setVisible(visible)

    def update_service_btns__presences_and_lifters(self, head_index):

        status = QApplication.instance().machine_head_dict[head_index].status

        map_ = [
            self.service_1_btn,
            self.service_2_btn,
            self.service_3_btn,
            self.service_4_btn,
            self.service_5_btn,
            self.service_6_btn,
            self.service_7_btn,
        ]
        if map_[head_index]:
            map_[head_index].setText(tr_(f"{status.get('status_level', 'NONE')}"))

        map_ = [
            self.container_presence_1_label,
            self.container_presence_2_label,
            self.container_presence_3_label,
            self.container_presence_4_label,
            self.container_presence_5_label,
            self.container_presence_6_label,
            self.container_presence_7_label,
        ]

        if map_[head_index]:
            if status.get("container_presence"):
                map_[head_index].setPixmap(self.main_window.green_icon)
            else:
                map_[head_index].setPixmap(self.main_window.gray_icon)

            # ~ lifter positions
            self.__set_pixmap_by_photocells(self.load_lifter_up_label,
                                            (("D", "LOAD_LIFTER_UP_PHOTOCELL"),), icon=self.main_window.green_icon)
            self.__set_pixmap_by_photocells(self.load_lifter_down_label,
                                            (("D", "LOAD_LIFTER_DOWN_PHOTOCELL"),), icon=self.main_window.green_icon)
            self.__set_pixmap_by_photocells(self.unload_lifter_up_label,
                                            (("F", "UNLOAD_LIFTER_UP_PHOTOCELL"),), icon=self.main_window.green_icon)
            self.__set_pixmap_by_photocells(self.unload_lifter_down_label,
                                            (("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"),), icon=self.main_window.green_icon)

    def update_tank_pixmaps(self):
        map_ = [
            self.refill_1_lbl,
            self.refill_2_lbl,
            self.refill_3_lbl,
            self.refill_4_lbl,
            self.refill_5_lbl,
            self.refill_6_lbl,
            self.refill_7_lbl,
        ]

        for head_index, m in QApplication.instance().machine_head_dict.items():
            if m and map_[head_index]:
                status = m.status
                crx_outputs_status = m.status.get('crx_outputs_status', 0x1)
                if (not crx_outputs_status and
                        status.get('status_level', '') in ("STANDBY", "DIAGNOSTIC", ) and
                        QApplication.instance().carousel_frozen):

                    map_[head_index].setPixmap(self.main_window.tank_icon_map['green'])
                else:
                    map_[head_index].setPixmap(self.main_window.tank_icon_map['gray'])

                map_[head_index].setText("")

    def update_jar_pixmaps(self):

        runners = QApplication.instance().get_jar_runners()

        # Indici costruiti UNA sola volta per aggiornamento, cosi'
        # __set_pixmap_by_photocells fa lookup O(1) invece di ricostruire la lista
        # dei jar e scandire le teste per ogni etichetta:
        #   position_to_jar: posizione -> jar in lavorazione in quella posizione
        #   letter_to_head : lettera testa ("A".."F") -> oggetto MachineHead
        position_to_jar = {}
        for j in runners.values():
            jar = j.get('jar')
            if jar is not None and jar.position:
                # se due jar avessero la stessa posizione, vince il primo
                position_to_jar.setdefault(jar.position, jar)
        letter_to_head = {
            m.name[0]: m
            for m in QApplication.instance().machine_head_dict.values()
            if m
        }

        list_ = []
        for k, j in runners.items():
            if j['jar'].position:
                if j['jar'].status == 'ERROR':
                    _color = "#990000"
                else:
                    _color = "#005500"
                _ = f"""<span style="color:{_color};background-color:#EEEEEE;">{k} ({j['jar'].position[0]})</span>"""
                list_.append(f"{_ : >4}")
        self.running_jars_lbl.setText("\n".join(list_))

        for entry in self.jar_pixmap_map:
            lbl, head_letters_bit_names, position = entry[:3]
            adjacent_positions = entry[3] if len(entry) > 3 else None
            if lbl and lbl is not self._blink_step_label:
                self.__set_pixmap_by_photocells(lbl, head_letters_bit_names, position,
                                                adjacent_positions=adjacent_positions,
                                                position_to_jar=position_to_jar,
                                                letter_to_head=letter_to_head)

    def start_step_blink(self, step_key):
        lbl = getattr(self, f"STEP_{step_key}_label", None)
        if lbl:
            self._blink_step_label = lbl
            self._blink_state = False
            self._do_blink()

    def stop_step_blink(self):
        lbl = self._blink_step_label
        self._blink_step_label = None
        if lbl:
            lbl.setStyleSheet("QLabel {}")
            lbl.setText("")
            # Il lampeggio ha impostato lo stile direttamente, scavalcando la
            # cache visuale: azzera la chiave-cache cosi' la label viene
            # ridisegnata al prossimo aggiornamento (altrimenti verrebbe saltata).
            lbl._alfa_visual_key = None

    def _do_blink(self):
        if not self._blink_step_label:
            return
        self._blink_state = not self._blink_state
        if self._blink_state:
            _url = get_res("IMAGE", "jar-orange.png")
            self._blink_step_label.setStyleSheet(
                f'color:#000000; border-image:url("{_url}"); font-size: 15px')
        else:
            self._blink_step_label.setStyleSheet("QLabel {}")
            self._blink_step_label.setText("")
        QTimer.singleShot(500, self._do_blink)

    @staticmethod
    def _apply_label_visual(lbl, key, apply_fn):
        # Applica stile/immagine a una label solo se sono cambiati rispetto
        # all'ultima volta. 'key' descrive lo stato visuale desiderato; se coincide
        # con quello gia' applicato (memorizzato in lbl._alfa_visual_key) non si fa
        # nulla, evitando setStyleSheet/setText/setPixmap ripetuti e costosi.
        # 'apply_fn' deve produrre esattamente il visual descritto da 'key'.
        if getattr(lbl, "_alfa_visual_key", None) == key:
            return
        apply_fn()
        lbl._alfa_visual_key = key

    @staticmethod
    def __set_pixmap_by_photocells(  # pylint: disable=too-many-locals
            lbl, head_letters_bit_names, position=None, icon=None, adjacent_positions=None,
            position_to_jar=None, letter_to_head=None):

        # Se position_to_jar/letter_to_head sono forniti (li passa
        # update_jar_pixmaps, che li costruisce una volta sola), i lookup sono
        # O(1). I chiamanti che non li passano (es. i lifter in
        # update_service_btns) usano i metodi originali: poche label, costo
        # trascurabile.
        if lbl:
            def _get_bit(head_letter, bit_name):
                if letter_to_head is not None:
                    m = letter_to_head.get(head_letter)
                else:
                    m = QApplication.instance().get_machine_head_by_letter(head_letter)
                ret = m.jar_photocells_status.get(bit_name) if m else None
                return ret

            try:

                false_condition = [
                    1 for h, b in head_letters_bit_names if not _get_bit(h, b)
                ]

                if icon is None:
                    hide = bool(false_condition)
                    if not hide and adjacent_positions:
                        # Adjacent photocells alone are ambiguous: they may belong
                        # to different jars while jar_runners is still empty or
                        # only partially populated. Keep middle labels hidden in
                        # normal rendering and reserve them for explicit blink/error
                        # states handled elsewhere.
                        hide = True

                    if hide:
                        HomePage._apply_label_visual(
                            lbl, ("hidden",),
                            lambda: (lbl.setStyleSheet("QLabel {}"), lbl.setText("")))
                    else:
                        _text = ""
                        _status = ""
                        if position_to_jar is not None:
                            jar = position_to_jar.get(position)
                            if jar is not None:
                                _status = jar.status
                                _bc = str(jar.barcode)
                                _text = _bc[-6:-3] + "\n" + _bc[-3:]
                        else:
                            for j in QApplication.instance().get_jar_runners().values():
                                pos = j["jar"].position
                                if pos == position:
                                    _status = j["jar"].status
                                    _bc = str(j["jar"].barcode)
                                    _text = _bc[-6:-3] + "\n" + _bc[-3:]
                                    break

                        if _status == "ERROR":
                            _img_name = "jar-red.png"
                        elif _text:
                            _img_name = "jar-green.png"
                        else:
                            _img_name = "jar-gray.png"

                        def _apply_jar():
                            _img_url = get_res("IMAGE", _img_name)
                            lbl.setStyleSheet(
                                'color:#000000; border-image:url("{0}"); font-size: 15px'.format(_img_url))
                            lbl.setText(_text)

                        # La chiave usa il NOME dell'immagine (non il path risolto):
                        # cosi' quando nulla e' cambiato non si chiama nemmeno get_res().
                        HomePage._apply_label_visual(lbl, ("jar", _img_name, _text), _apply_jar)
                else:
                    size = (0, 0) if false_condition else (32, 32)

                    def _apply_icon():
                        pixmap = icon.scaled(*size, Qt.KeepAspectRatio)
                        lbl.setPixmap(pixmap)

                    HomePage._apply_label_visual(lbl, ("icon", id(icon), size), _apply_icon)

                lbl.show()

            except Exception as e:  # pylint: disable=broad-except
                QApplication.instance().handle_exception(e)

    def show_reserve(self, head_index, flag=None):

        map_ = [
            self.reserve_1_label,
            self.reserve_2_label,
            self.reserve_3_label,
            self.reserve_4_label,
            self.reserve_5_label,
            self.reserve_6_label,
            self.reserve_7_label,
        ]

        if map_[head_index]:
            if flag is None:
                flag = not map_[head_index].isVisible()

            _label = map_[head_index]
            # ~ logging.warning(f"head_index:{head_index}, flag:{flag}, _label:{_label}.")

            if flag:
                _label.setMovie(self.reserve_movie)
                self.reserve_movie.start()
                _label.show()
            else:
                _label.setText("")
                _label.hide()

    def step_label_clicked(self, position):

        logging.warning(f"position:{position}")

        app = QApplication.instance()

        try:

            moving_heads = [m for m in app.machine_head_dict.values() if m and m.status.get('status_level')
                            not in ['STANDBY', 'DIAGNOSTIC']]

            logging.warning(f"moving_heads:{moving_heads}")

            jar = None
            for j in app.get_jar_runners().values():
                if j and j['jar'] and j['jar'].position and (j['jar'].position == position):
                    logging.warning(f"j['jar']:{j['jar']}")
                    logging.warning(f"j['jar'].machine_head:{j['jar'].machine_head}")
                    jar = j['jar']
                    break

            if jar:

                txt_ = f"{jar.barcode} " + ' '.join(jar.extra_lines_to_print)
                QApplication.instance().main_window.menu_line_edit.setText(txt_)

                if app.carousel_frozen and not moving_heads:
                    if jar:
                        def _remove_jar():
                            logging.warning(f"removing:{jar.barcode}")
                            try:
                                app.delete_jar_runner(jar.barcode)
                                self.update_jar_pixmaps()
                            except Exception:   # pylint: disable=broad-except
                                logging.error(traceback.format_exc())
                        msg_ = tr_("confirm removing {}?").format(jar.barcode)
                        self.main_window.open_input_dialog(message=msg_, content="", ok_cb=_remove_jar)

        except Exception:   # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    @staticmethod
    def reserve_label_clicked(head_index):

        logging.warning(f"head_index:{head_index}")

        m = QApplication.instance().machine_head_dict[head_index]
        if m.low_level_pipes:
            QApplication.instance().main_window.open_alert_dialog(
                (m.name, m.low_level_pipes),
                fmt="{} Please, Check Pipe Levels: low_level_pipes:{}",
                print_callback=lambda: LowPigmentsPrintHelper().run(),
            )

    @staticmethod
    def expiry_label_clicked(head_index):

        logging.warning(f"head_index:{head_index}")

        m = QApplication.instance().machine_head_dict[head_index]
        if m.expired_products:           # pylint: disable=too-many-nested-blocks

            try:
                # ~ txt_ = [{tr_(k): p['QR_code_info'].get(k) for k in keys_} for p in m.expired_products if p.get('QR_code_info')]

                # ~ keys_ = ('pipe_name', 'pigment_name', 'production_date', 'lot_number')
                keys_ = ('pipe_name', 'pigment_name')
                info_ = []
                for p in m.expired_products:
                    for expired_info in ["QR_code_info", "production_date_expired"]:
                        if p.get(expired_info):
                            curr_info = p[expired_info]
                            item = []
                            for k in keys_:
                                try:
                                    if curr_info and curr_info.get(k):
                                        # ~ item[tr_(k)] = QR_code_info[k]
                                        item.append(curr_info[k])
                                except Exception:   # pylint: disable=broad-except
                                    logging.error(traceback.format_exc())
                            info_.append(item)
                            # break

                QApplication.instance().main_window.open_alert_dialog((m.name, info_), fmt="{} expired produtcs:{}")

            except Exception as e:  # pylint: disable=broad-except
                QApplication.instance().handle_exception(e)

    @staticmethod
    def refill_lbl_is_active(head_index):

        # ~ if head_index is not None and hasattr(g_settings, 'USE_PIGMENT_ID_AS_BARCODE') and (
        # ~ g_settings.USE_PIGMENT_ID_AS_BARCODE and QApplication.instance().carousel_frozen):

        flag = head_index is not None
        flag = flag and hasattr(g_settings, 'USE_PIGMENT_ID_AS_BARCODE')
        flag = flag and g_settings.USE_PIGMENT_ID_AS_BARCODE
        flag = flag and QApplication.instance().carousel_frozen
        return flag

    def refill_lbl_clicked(self, head_index):

        if self.refill_lbl_is_active(head_index):
            QApplication.instance().barcode_read_blocked_on_refill = True
            logging.warning(f"impostato a barcode_read_blocked_on_refill=True")
            rph = RefillProcedureHelper(parent=self, head_index=head_index)
            rph.run()

    def print_label_clicked(self, head_index):

        machine_ = QApplication.instance().machine_head_dict[head_index]

        def _cb_pipe_confirmed(selected_):
            logging.warning(f"selected_:{selected_}")

            labels = [selected_]
            if selected_.get("pigment_name") == "Print All":
                printables = copy.deepcopy(pipes_)
                printables.pop("Print All")
                sorted_printables = {k: printables[k] for k in sorted(printables)}
                labels = list(sorted_printables.values())
            logging.debug("labels -> %s", labels)

            print_helper = PrintLabelHelper(parent=self, printables=labels)
            print_helper.run()

        def _cb_pipe_selected():
            selected_ = QApplication.instance().main_window.input_dialog.get_selected_choice()
            logging.warning(f"selected_:{selected_}")
            barcode_txt = selected_.get('barcode_txt', '')
            pigment_name = selected_.get('pigment_name', '')
            pipe_name = selected_.get('pipe_name', '')

            msg_ = """please, confirm printing label<br>{} {} {}."""
            msg_ = tr_(msg_).format(pipe_name, pigment_name, barcode_txt)

            QApplication.instance().main_window.open_input_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=msg_,
                content=None,
                ok_cb=_cb_pipe_confirmed,
                ok_cb_args=(selected_,))

        pipes_ = {"Print All": {'pigment_name': 'Print All'}}
        for p in machine_.pigment_list:
            for pipe_ in p.get('pipes'):
                k = f"{pipe_['name']} {p['name']}"
                v = {
                    'pigment_name': p['name'],
                    'pipe_name': pipe_['name'],
                    'barcode_txt': p.get('customer_id') or '',
                    'rgb': p['rgb']
                }
                pipes_[k] = v

        logging.warning(f"self:{self}, pipes_:{pipes_}")

        if pipes_:
            keys_ = list(pipes_.keys())
            keys_.sort()
            selected_ = keys_[0]

            QApplication.instance().main_window.open_input_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=tr_("please, choose a circuit to print the corresponding label."),
                content=selected_,
                ok_cb=_cb_pipe_selected,
                choices=pipes_)

    def update_lbl_recovery(self, toggle_lbl_recovery=False):
        
        if toggle_lbl_recovery:
            self.lbl_recovery.setText(tr_("RECOVERY MODE ON"))
            self.lbl_recovery.setStyleSheet(
                "QLabel { font-weight: bold; background-color: yellow; font-size: 40px; }")
            self.lbl_recovery.setAlignment(Qt.AlignCenter)
            self.lbl_recovery.show()
            self.recovery_info_btn.show()

            try:
                self.recovery_info_btn.clicked.disconnect(self._on_recovery_info_clicked)
            except TypeError:
                pass
            
            self.recovery_info_btn.clicked.connect(self._on_recovery_info_clicked)

        else:
            self.lbl_recovery.hide()
            self.recovery_info_btn.hide()

            try:
                self.recovery_info_btn.clicked.disconnect(self._on_recovery_info_clicked)
            except TypeError:
                pass

    def _on_recovery_info_clicked(self):
        recovery_text = tr_("If you prefer to unload manually some or all jars,\npress DELETE for each one to remove permanently\nthem from the machine recovery logic")
        recovery_text += tr_("\nAutomation paused is required!")
        jars = QApplication.instance().get_restorable_jars_for_recovery_mode()
        top_label = tr_("Below is the list of pending orders:")
        bottom = [
            "Orders in green will be completed during Recovery Mode.",
            "Orders in red cannot be completed and will automatically move towards the machine exit.",
            "If some orders have already been physically removed from the machine, press Delete to remove them also from the automation memory.",
            "Automation paused is required!"
        ]
        self.main_window.open_recovery_dialog(jars, lbl_text=top_label, bottom_lbl_text=bottom)

class HomePageSixHeads(HomePage):

    ui_file_name = "home_page_six_heads.ui"
    help_file_name = 'home_six_heads.html'

    STEP_02_04_label = None  # four-heads only
    STEP_07_09_label = None  # four-heads only

    service_7_btn = None
    refill_7_lbl = None
    expiry_7_label = None
    reserve_7_label = None
    container_presence_7_label = None

    belt_label_7 = None


class HomePageFourHeads(HomePage):

    ui_file_name = "home_page_four_heads.ui"
    help_file_name = 'home_four_heads.html'

    action_03_btn = None
    action_07_btn = None

    STEP_03_label = None
    STEP_08_label = None

    STEP_02_03_label = None  # six-heads only (HEAD B not present)
    STEP_03_04_label = None  # six-heads only
    STEP_07_08_label = None  # six-heads only (HEAD E not present)
    STEP_08_09_label = None  # six-heads only

    refill_3_lbl = None
    refill_4_lbl = None

    expiry_3_label = None
    expiry_4_label = None

    reserve_3_label = None
    reserve_4_label = None

    service_3_btn = None
    service_4_btn = None

    container_presence_3_label = None
    container_presence_4_label = None

    service_7_btn = None
    refill_7_lbl = None
    expiry_7_label = None
    reserve_7_label = None
    container_presence_7_label = None

    belt_label_3 = None
    belt_label_4 = None
    belt_label_7 = None

class HomePageCRX60Heads(HomePage):

    ui_file_name = "home_page_three_heads.ui"
    help_file_name = ''

    action_02_btn = None
    action_04_btn = None
    action_06_btn = None
    action_07_btn = None
    action_08_btn = None
    action_09_btn = None
    action_10_btn = None

    STEP_06_label = None
    STEP_07_label = None
    STEP_08_label = None
    STEP_09_label = None
    STEP_10_label = None
    STEP_11_label = None
    STEP_12_label = None

    refill_2_lbl = None
    refill_4_lbl = None
    refill_6_lbl = None

    expiry_2_label = None
    expiry_4_label = None
    expiry_6_label = None

    reserve_2_label = None
    reserve_4_label = None
    reserve_6_label = None

    service_2_btn = None
    service_4_btn = None
    service_6_btn = None

    container_presence_2_label = None
    container_presence_4_label = None
    container_presence_6_label = None

    service_7_btn = None
    refill_7_lbl = None
    expiry_7_label = None
    reserve_7_label = None
    container_presence_7_label = None

    belt_label_2 = None
    belt_label_4 = None
    belt_label_6 = None
    belt_label_7 = None

    unload_lifter_down_label = None
    unload_lifter_up_label = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.jar_pixmap_map = [
            (self.STEP_01_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),), "IN_A",),
            (self.STEP_01_02_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"), ("A", "JAR_DISPENSING_POSITION_PHOTOCELL")), "IN_A", (("IN_A",), ("A",)),),
            (self.STEP_02_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "A",),
            (self.STEP_03_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "B",),
            (self.STEP_04_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "C",),
            (self.STEP_05_label, (("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "OUT",),
        ]

class HomePageCRX80Heads(HomePage):

    ui_file_name = "home_page_four_linear_heads.ui"
    help_file_name = ''

    action_07_btn = None
    action_08_btn = None
    action_09_btn = None
    action_10_btn = None

    STEP_07_label = None
    STEP_08_label = None
    STEP_09_label = None
    STEP_10_label = None
    STEP_11_label = None
    STEP_12_label = None

    refill_2_lbl = None
    refill_4_lbl = None
    refill_6_lbl = None

    expiry_2_label = None
    expiry_4_label = None
    expiry_6_label = None

    reserve_2_label = None
    reserve_4_label = None
    reserve_6_label = None

    service_2_btn = None
    service_4_btn = None
    service_6_btn = None

    container_presence_2_label = None
    container_presence_4_label = None
    container_presence_6_label = None

    belt_label_2 = None
    belt_label_4 = None
    belt_label_6 = None

    unload_lifter_down_label = None
    unload_lifter_up_label = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.jar_pixmap_map = [
            (self.STEP_01_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),), "IN_A",),
            (self.STEP_01_02_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"), ("A", "JAR_DISPENSING_POSITION_PHOTOCELL")), "IN_A", (("IN_A",), ("A",)),),
            (self.STEP_02_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "A",),
            (self.STEP_02_03_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("B", "JAR_DISPENSING_POSITION_PHOTOCELL")), "A", (("A",), ("B",)),),
            (self.STEP_03_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "B",),
            (self.STEP_03_04_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("C", "JAR_DISPENSING_POSITION_PHOTOCELL")), "B", (("B",), ("C",)),),
            (self.STEP_04_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "C",),
            (self.STEP_04_05_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("G", "JAR_DISPENSING_POSITION_PHOTOCELL")), "C", (("C",), ("G",)),),
            (self.STEP_05_label, (("G", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "G",),
            (self.STEP_05_06_label, (("G", "JAR_DISPENSING_POSITION_PHOTOCELL"), ("G", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL")), "G", (("G",), ("OUT",)),),
            (self.STEP_06_label, (("G", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "OUT",),
        ]


class HomePageCRX40Heads(HomePage):

    ui_file_name = "home_page_two_heads.ui"
    help_file_name = ''

    action_02_btn = None
    action_03_btn = None
    action_04_btn = None
    action_06_btn = None
    action_07_btn = None
    action_08_btn = None
    action_09_btn = None
    action_10_btn = None

    STEP_03_label = None
    STEP_06_label = None
    STEP_07_label = None
    STEP_08_label = None
    STEP_09_label = None
    STEP_10_label = None
    STEP_11_label = None
    STEP_12_label = None

    refill_2_lbl = None
    refill_3_lbl = None
    refill_4_lbl = None
    refill_6_lbl = None

    expiry_2_label = None
    expiry_3_label = None
    expiry_4_label = None
    expiry_6_label = None

    reserve_2_label = None
    reserve_3_label = None
    reserve_4_label = None
    reserve_6_label = None

    service_2_btn = None
    service_3_btn = None
    service_4_btn = None
    service_6_btn = None

    container_presence_2_label = None
    container_presence_3_label = None
    container_presence_4_label = None
    container_presence_6_label = None

    service_7_btn = None
    refill_7_lbl = None
    expiry_7_label = None
    reserve_7_label = None
    container_presence_7_label = None

    belt_label_2 = None
    belt_label_3 = None
    belt_label_4 = None
    belt_label_6 = None
    belt_label_7 = None

    unload_lifter_down_label = None
    unload_lifter_up_label = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.jar_pixmap_map = [
            (self.STEP_01_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),), "IN_A",),
            (self.STEP_01_02_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"), ("A", "JAR_DISPENSING_POSITION_PHOTOCELL")), "IN_A", (("IN_A",), ("A",)),),
            (self.STEP_02_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "A",),
            (self.STEP_04_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "C",),
            (self.STEP_05_label, (("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "OUT",),
        ]
