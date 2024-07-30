# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-few-public-methods
# pylint: disable=multiple-statements
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import copy
import logging
import traceback
import asyncio

from PyQt5.QtCore import Qt

from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QApplication

from alfa_CR6_backend.globals import (import_settings, get_res, tr_, TMP_PIGMENT_IMAGE, DEFAULT_DEBUG_PAGE_PWD)
from alfa_CR6_backend.dymo_printer import dymo_print_pigment_label

from alfa_CR6_frontend.pages import BaseStackedPage
from alfa_CR6_frontend.debug_page import simulate_read_barcode


g_settings = import_settings()

import functools

class PrintException(Exception):
    def __init__(self, message, payload):
        super().__init__(message)
        self.payload = payload


class PrintLabelHelper:

    def __init__(self, parent=None, printables=[]):
        self.parent = parent
        self.printables = printables

    async def print_labels(self):
        loop = asyncio.get_running_loop()
        fake_print = os.getenv("FAKE_DYMO_PRINT", False) in ["1", "true"]

        for printable in self.printables:
            barcode_txt = printable.get('barcode_txt', '')
            pigment_name = printable.get('pigment_name', '')
            pipe_name = printable.get('pipe_name', '')
            fake = printable.get('fake', False)
            partial_func = functools.partial(
                dymo_print_pigment_label,
                barcode_txt,
                pigment_name,
                pipe_name,
                fake_print
            )

            try:
                # Esegui la funzione sincrona in un executor
                ret = await loop.run_in_executor(None, partial_func)
                logging.debug(f"ret: {ret}")

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
            content=None,
            bg_image=TMP_PIGMENT_IMAGE)

    def run(self):

        if not self.printables:
            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxCritical",
                message="Missing printables ...")
            return

        t = self.print_labels()
        asyncio.ensure_future(t)


class RefillProcedureHelper:

    refill_choices = ['100', '250', '500', '750', '1000', '1500', '2000', '2500', '3000']
    refill_choices_fl_oz = ['16', '32']

    def __init__(self, parent, head_index):

        self.parent = parent
        self.machine_ = QApplication.instance().machine_head_dict[head_index]

        self.units_ = "CC"
        if self.machine_.machine_config:
            self.units_ = self.machine_.machine_config.get('UNITS', {}).get('service_page_unit')

        self.fl_oz_unit = self.machine_.machine_config.get('UNITS', {}).get('fl_oz_unit', 1)

        t = self.machine_.update_tintometer_data()
        asyncio.ensure_future(t)

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

    def __get_refill_choices(self):

        if self.units_ == "FL OZ":
            return self.refill_choices_fl_oz

        return self.refill_choices

    def _cb_confirm_reset(self):

        t = self.machine_.send_command(
            cmd_name="RESET",
            params={"mode": 0},
            type_="command",
            channel="machine")
        asyncio.ensure_future(t)

    async def __update_level_task(self, pigment_, pipe_, qtity_ml_):

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
        await self.machine_.send_command(cmd_name="REFILL", params=params_, type_="macro", callback_on_macro_answer=_cb_on_refill)

        await self.machine_.update_tintometer_data()
        self.parent.main_window.browser_page.reload_page()

    def _cb_confirm_quantity(self, pigment_, pipe_, qtity_ml_):

        t = self.__update_level_task(pigment_, pipe_, qtity_ml_)
        asyncio.ensure_future(t)

    def _cb_input_quantity(self, pigment_, pipe_):

        self.parent.main_window.toggle_keyboard(on_off=False)

        qtity_units_ = self.parent.main_window.input_dialog.get_content_text()
        qtity_units_ = round(float(qtity_units_), 2)
        qtity_ml_ = self.__qtity_to_ml(qtity_units_, pigment_['name'])

        logging.warning("maximum_level:{}, current_level:{}, qtity_ml_:{}, qtity_units_:{}".format(
            pipe_['maximum_level'], pipe_['current_level'], qtity_ml_, qtity_units_))

        if pipe_['maximum_level'] >= (pipe_['current_level'] + qtity_ml_) * 0.98:
            msg_ = """please, confirm refilling pipe: {} <br>with {} ({}) of product: {}?."""
            msg_ = tr_(msg_).format(pipe_['name'], qtity_units_, self.units_.lower(), pigment_['name'])

            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=msg_,
                content=None,
                ok_cb=self._cb_confirm_quantity,
                ok_cb_args=(pigment_, pipe_, qtity_ml_))
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

        choices = {c: None for c in [_default_qtity_units, ] + self.__get_refill_choices() if float(c) <= margin_units_}

        if barcode_check == barcode_:
            self.parent.main_window.toggle_keyboard(on_off=True)
            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxQuestion",
                message=msg_,
                content=_default_qtity_units,
                ok_cb=self._cb_input_quantity,
                ok_cb_args=(pigment_, pipe_),
                choices=choices)
        else:

            self.parent.main_window.open_input_dialog(
                icon_name="SP_MessageBoxCritical",
                message=tr_("barcode mismatch <br/>{} != {}").format(barcode_, barcode_check),
                content=None)

    async def _rotate_circuit_task(self, pigment_, pipe_, _default_qtity_units, barcode_):

        def __get_pipe_index_from_name(p_name):

            pipe_addresses = {"B%02d" % (i + 1): i for i in range(0, 8)}
            pipe_addresses.update({"C%02d" % (i - 7): i for i in range(8, 32)})
            return pipe_addresses[p_name]

        pipe_index = __get_pipe_index_from_name(pipe_['name'])
        pars_ = {'Id_color_circuit': pipe_index, 'Refilling_angle': 0, 'Direction': 0}

        t = self.machine_.send_command(cmd_name='DIAG_ROTATING_TABLE_POSITIONING',
                                       params=pars_, type_='command', channel='machine')
        asyncio.ensure_future(t)

        self.parent.main_window.open_input_dialog(
            icon_name="SP_MessageBoxQuestion",
            message=tr_("please, verify barcode {} on canister.").format(barcode_),
            content="",
            ok_cb=self._cb_verify_barcode,
            ok_cb_args=(pigment_, pipe_, _default_qtity_units, barcode_),
            ok_on_enter=1)

    def _cb_input_barcode(self):

        barcode_ = self.parent.main_window.input_dialog.get_content_text()
        barcode_ = barcode_.strip()
        logging.warning(f"{self.machine_.name} barcode_:{barcode_}.")

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
                pipe_ = pipes_[0]

                _default_qtity_ml = pipe_['maximum_level'] - pipe_['current_level']
                _default_qtity_units = self.__qtity_from_ml(_default_qtity_ml, pigment_['name'])
                _default_qtity_units = round(_default_qtity_units, 2)

                t = self._rotate_circuit_task(pigment_, pipe_, _default_qtity_units, barcode_)
                asyncio.ensure_future(t)

            else:
                QApplication.instance().main_window.open_alert_dialog(
                    tr_("barcode not known:{}").format(barcode_))

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def run(self):

        self.parent.main_window.open_input_dialog(
            icon_name="SP_MessageBoxQuestion",
            message=tr_("please, input barcode for refill"),
            content="",
            ok_cb=self._cb_input_barcode,
            ok_on_enter=1)


class HomePage(BaseStackedPage):

    def __init__(self, *args, **kwargs):  # pylint:disable=too-many-branches, too-many-statements

        super().__init__(*args, **kwargs)

        self.running_jars_lbl.setStyleSheet("font-size: 15px")

        for b in self.action_btn_group.buttons():
            b.setStyleSheet(
                """QPushButton { background-color: #00FFFFFF; border: 0px;}"""
            )

        self.service_btn_group.buttonClicked.connect(self.on_service_btn_group_clicked)
        self.action_btn_group.buttonClicked.connect(self.on_action_btn_group_clicked)

        self.reserve_movie = QMovie(get_res("IMAGE", "riserva.gif"))
        self.expiry_movie = QMovie(get_res("IMAGE", "expiry.gif"))

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

        # self.printer_helper = PrinterHelper()
        # self.printer_helper.all_prints_finished.connect(self.on_all_prints_finished)
        # self.printer_helper.print_error.connect(self.on_print_error)

    def open_page(self):

        self.parent().setCurrentWidget(self)

    def on_service_btn_group_clicked(self, btn):

        btn_name = btn.objectName()

        try:
            service_page_urls = ["http://127.0.0.1:8080/service_page/", ]
            for i in QApplication.instance().settings.MACHINE_HEAD_IPADD_PORTS_LIST:
                if i:
                    url = "http://{}:{}/service_page/".format(i[0], i[2])
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
            ]

            map_ = dict(zip(service_btns, service_page_urls))

            head_index = service_btns.index(btn) - 1
            logging.debug(f"btn_name:{btn_name}, map_[btn]:{map_[btn]}, map_:{map_}, head_index:{head_index}")

            self.main_window.browser_page.open_page(map_[btn], head_index=head_index)

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def on_action_btn_group_clicked(self, btn):

        btn_name = btn.objectName()
        try:
            if "feed" in btn_name:
                if hasattr(g_settings, 'SIMULATE_READ_BARCODE') and getattr(g_settings, 'SIMULATE_READ_BARCODE'):
                    allowed_jar_statuses = g_settings.SIMULATE_READ_BARCODE.get("allowed_jar_statuses", ("NEW", "DONE"))
                    simulate_read_barcode(allowed_jar_statuses)
                else:
                    QApplication.instance().run_a_coroutine_helper("move_00_01")

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

    def update_expired_products(self, head_index):

        map_ = [
            self.expiry_1_label,
            self.expiry_2_label,
            self.expiry_3_label,
            self.expiry_4_label,
            self.expiry_5_label,
            self.expiry_6_label,
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

    def update_service_btns__presences_and_lifters(self, head_index):

        status = QApplication.instance().machine_head_dict[head_index].status

        map_ = [
            self.service_1_btn,
            self.service_2_btn,
            self.service_3_btn,
            self.service_4_btn,
            self.service_5_btn,
            self.service_6_btn,
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

        list_ = []
        for k, j in QApplication.instance().get_jar_runners().items():
            if j['jar'].position:
                if j['jar'].status == 'ERROR':
                    _color = "#990000"
                else:
                    _color = "#005500"
                _ = f"""<span style="color:{_color};background-color:#EEEEEE;">{k} ({j['jar'].position[0]})</span>"""
                list_.append(f"{_ : >4}")
        self.running_jars_lbl.setText("\n".join(list_))

        map_ = [
            (self.STEP_01_label, (("A", "JAR_INPUT_ROLLER_PHOTOCELL"),), "IN_A",),
            (self.STEP_02_label, (("A", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "A",),
            (self.STEP_03_label, (("B", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "B",),
            (self.STEP_04_label, (("C", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "C",),
            (self.STEP_05_label, (("D", "LOAD_LIFTER_UP_PHOTOCELL"), ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTR_UP",),
            (self.STEP_06_label, (("D", "LOAD_LIFTER_DOWN_PHOTOCELL"), ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTR_DOWN",),
            (self.STEP_07_label, (("D", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "D",),
            (self.STEP_08_label, (("E", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "E",),
            (self.STEP_09_label, (("F", "JAR_DISPENSING_POSITION_PHOTOCELL"),), "F",),
            (self.STEP_10_label, (("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL"), ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTL_DOWN",),
            (self.STEP_11_label, (("F", "UNLOAD_LIFTER_UP_PHOTOCELL"), ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL"),), "LIFTL_UP",),
            (self.STEP_12_label, (("F", "JAR_OUTPUT_ROLLER_PHOTOCELL"),), "OUT",),
        ]

        for lbl, head_letters_bit_names, position in map_:
            if lbl:
                self.__set_pixmap_by_photocells(lbl, head_letters_bit_names, position)

    @staticmethod
    def __set_pixmap_by_photocells(  # pylint: disable=too-many-locals
            lbl, head_letters_bit_names, position=None, icon=None):

        if lbl:
            def _get_bit(head_letter, bit_name):
                m = QApplication.instance().get_machine_head_by_letter(head_letter)
                ret = m.jar_photocells_status.get(bit_name) if m else None
                return ret

            try:

                false_condition = [
                    1 for h, b in head_letters_bit_names if not _get_bit(h, b)
                ]

                if icon is None:
                    if false_condition:
                        lbl.setStyleSheet("QLabel {{}}")
                        lbl.setText("")
                    else:
                        _text = ""
                        _status = ""
                        for j in QApplication.instance().get_jar_runners().values():
                            pos = j["jar"].position
                            if pos == position:
                                _status = j["jar"].status
                                _bc = str(j["jar"].barcode)
                                _text = _bc[-6:-3] + "\n" + _bc[-3:]
                                break

                        if _status == "ERROR":
                            _img_url = get_res("IMAGE", "jar-red.png")
                        else:
                            if _text:
                                _img_url = get_res("IMAGE", "jar-green.png")
                            else:
                                _img_url = get_res("IMAGE", "jar-gray.png")

                        lbl.setStyleSheet(
                            'color:#000000; border-image:url("{0}"); font-size: 15px'.format(_img_url))
                        lbl.setText(_text)
                else:
                    size = [0, 0] if false_condition else [32, 32]
                    pixmap = icon.scaled(*size, Qt.KeepAspectRatio)
                    lbl.setPixmap(pixmap)

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
                tr_("{} Please, Check Pipe Levels: low_level_pipes:{}").format(m.name, m.low_level_pipes))

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
            logging.debug(f"labels -> {labels}")

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
            self.lbl_recovery.setStyleSheet(
                "QLabel { font-weight: bold; background-color: yellow; font-size: 40px; }")
            self.lbl_recovery.setAlignment(Qt.AlignCenter)
            self.lbl_recovery.show()
        else:
            self.lbl_recovery.hide()

class HomePageSixHeads(HomePage):

    ui_file_name = "home_page_six_heads.ui"
    help_file_name = 'home_six_heads.html'


class HomePageFourHeads(HomePage):

    ui_file_name = "home_page_four_heads.ui"
    help_file_name = 'home_four_heads.html'

    action_03_btn = None
    action_07_btn = None

    STEP_03_label = None
    STEP_08_label = None

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
