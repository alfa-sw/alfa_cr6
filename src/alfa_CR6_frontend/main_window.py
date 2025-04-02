# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import logging
import traceback
import json
import os

from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QIcon, QMovie
from PyQt5.QtWidgets import QApplication, QMainWindow

from alfa_CR6_backend.globals import (
    get_res, tr_, KEYBOARD_PATH, import_settings, set_language, LANGUAGE_MAP, DEFAULT_DEBUG_PAGE_PWD)
from alfa_CR6_backend.base_application import BarCodeReader
from alfa_CR6_frontend.dialogs import (
    ModalMessageBox,
    EditDialog,
    InputDialog,
    AliasDialog,
    RecoveryInfoDialog,
    RefillDialog)

from alfa_CR6_frontend.pages import (
    OrderPage,
    HelpPage)

from alfa_CR6_frontend.action_page import ActionPage
from alfa_CR6_frontend.browser_page import BrowserPage
from alfa_CR6_frontend.home_page import (HomePageSixHeads, HomePageFourHeads)


from alfa_CR6_frontend.keyboard import Keyboard

ACTION_PAGE_LIST = [
    {"title": tr_("action 01 (head 1 or A)"),
     "buttons": [
         {"text": tr_("Start input roller"), "action_args": ("single_move", "A", [1, 1])},
         {"text": tr_("Stop  input roller"), "action_args": ("single_move", "A", [1, 0])},
         {"text": tr_("Start input roller to photocell"), "action_args": ("single_move", "A", [1, 2])},
         {"text": tr_("move 00 01 ('feed')"), "action_args": ("move_00_01",)},
         {"text": tr_("move 01 02 ('IN -> A')"), "action_args": ("move_01_02",)}, ],
     "labels_args": [
         ("A", "JAR_INPUT_ROLLER_PHOTOCELL", tr_("INPUT ROLLER PHOTOCELL")),
         ("A", "JAR_DETECTION_MICROSWITCH_1", tr_("MICROSWITCH 1")),
         ("A", "JAR_DETECTION_MICROSWITCH_2", tr_("MICROSWITCH 2")), ], },
    {"title": tr_("action 02 (head 1 or A)"),
     "buttons": [
         {"text": tr_("Start dispensing roller"), "action_args": ("single_move", "A", [0, 1])},
         {"text": tr_("Stop dispensing roller"), "action_args": ("single_move", "A", [0, 0])},
         {"text": tr_("Start dispensing roller to photocell"), "action_args": ("single_move", "A", [0, 2])}, ],
     "labels_args": [
         ("A", "JAR_DISPENSING_POSITION_PHOTOCELL", tr_("DISPENSING POSITION PHOTOCELL")),
         ("A", "container_presence", tr_("CAN PRESENCE")),
         ("A", "THOR BRUSH_PHOTOCELL", tr_("BRUSH PHOTOCELL")),
         ("A", "THOR TABLE_PHOTOCELL", tr_("ROTATING TABLE PHOTOCELL")),
         ("A", "THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL", tr_("PUMP MOTOR HOME PHOTOCELL")),
         ("A", "THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL", tr_("PUMP MOTOR INGR PHOTOCELL")),
         ("A", "THOR VALVE_OPEN_PHOTOCELL", tr_("VALVE PHOTOCELL LEFT")),
         ("A", "THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL", tr_("VALVE PHOTOCELL RIGHT")),
         ("A", "panel_table_status", tr_("PANEL TABLE STATUS")),], },
    {"title": tr_("action 03 (head 3 or B)"),
     "buttons": [
         {"text": tr_("Start dispensing roller"), "action_args": ("single_move", "B", [0, 1])},
         {"text": tr_("Stop dispensing roller"), "action_args": ("single_move", "B", [0, 0])},
         {"text": tr_("Start dispensing roller to photocell"), "action_args": ("single_move", "B", [0, 2])}, ],
     "labels_args": [
         ("B", "JAR_DISPENSING_POSITION_PHOTOCELL", tr_("DISPENSING POSITION PHOTOCELL")),
         ("B", "container_presence", tr_("CAN PRESENCE")),
         ("B", "THOR BRUSH_PHOTOCELL", tr_("BRUSH PHOTOCELL")),
         ("B", "THOR TABLE_PHOTOCELL", tr_("ROTATING TABLE PHOTOCELL")),
         ("B", "THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL", tr_("PUMP MOTOR HOME PHOTOCELL")),
         ("B", "THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL", tr_("PUMP MOTOR INGR PHOTOCELL")),
         ("B", "THOR VALVE_OPEN_PHOTOCELL", tr_("VALVE PHOTOCELL LEFT")),
         ("B", "THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL", tr_("VALVE PHOTOCELL RIGHT")),
         ("B", "panel_table_status", tr_("PANEL TABLE STATUS")),], },
    {"title": tr_("action 04 (head 5, 6 or C, D)"),
     "buttons": [
         {"text": tr_("Start dispensing roller"), "action_args": ("single_move", "C", [0, 1])},
         {"text": tr_("Stop dispensing roller"), "action_args": ("single_move", "C", [0, 0])},
         {"text": tr_("Start dispensing roller to photocell"), "action_args": ("single_move", "C", [0, 2])},
         {"text": tr_("move 04 05 ('C -> UP')"), "action_args": ("move_04_05",)},
         {"text": tr_("move 05 06 ('UP -> DOWN')"), "action_args": ("move_05_06",)},
         {"text": tr_("move 06 07 ('DOWN -> D')"), "action_args": ("move_06_07",)}, ],
     "labels_args": [
         ("C", "JAR_DISPENSING_POSITION_PHOTOCELL", tr_("DISPENSING POSITION PHOTOCELL")),
         ("C", "container_presence", tr_("CAN PRESENCE")),
         ("C", "THOR BRUSH_PHOTOCELL", tr_("BRUSH PHOTOCELL")),
         ("C", "THOR TABLE_PHOTOCELL", tr_("ROTATING TABLE PHOTOCELL")),
         ("C", "THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL", tr_("PUMP MOTOR HOME PHOTOCELL")),
         ("C", "THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL", tr_("PUMP MOTOR INGR PHOTOCELL")),
         ("C", "THOR VALVE_OPEN_PHOTOCELL", tr_("VALVE PHOTOCELL LEFT")),
         ("C", "THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL", tr_("VALVE PHOTOCELL RIGHT")),
         ("C", "panel_table_status", tr_("PANEL TABLE STATUS")),], },
    {"title": tr_("action 05 (head 5, 6 or C, D)"),
     "buttons": [
         {"text": tr_("Start lifter roller CW"), "action_args": ("single_move", "C", [1, 1])},
         {"text": tr_("Start lifter roller CCW"), "action_args": ("single_move", "C", [1, 4])},
         {"text": tr_("Stop  lifter roller"), "action_args": ("single_move", "C", [1, 0])},
         {"text": tr_("Start lifter up"), "action_args": ("single_move", "D", [1, 2])},
         {"text": tr_("Start lifter down"), "action_args": ("single_move", "D", [1, 5])},
         {"text": tr_("Stop  lifter"), "action_args": ("single_move", "D", [1, 0])},
         {"text": tr_("move 04 05 ('C -> UP')"), "action_args": ("move_04_05",)},
         {"text": tr_("move 05 06 ('UP -> DOWN')"), "action_args": ("move_05_06",)},
         {"text": tr_("move 06 07 ('DOWN -> D')"), "action_args": ("move_06_07",)}, ],
     "labels_args": [
         ("C", "JAR_LOAD_LIFTER_ROLLER_PHOTOCELL", tr_("LIFTER ROLLER PHOTOCELL")),
         ("D", "LOAD_LIFTER_UP_PHOTOCELL", tr_("LIFTER UP PHOTOCELL")),
         ("D", "LOAD_LIFTER_DOWN_PHOTOCELL", tr_("LIFTER DOWN PHOTOCELL")), ], },
    {"title": tr_("action 06 (head 6 or D)"),
     "buttons": [
         {"text": tr_("Start dispensing roller"), "action_args": ("single_move", "D", [0, 1])},
         {"text": tr_("Stop dispensing roller"), "action_args": ("single_move", "D", [0, 0])},
         {"text": tr_("Start dispensing roller to photocell"), "action_args": ("single_move", "D", [0, 2])}, ],
     "labels_args": [
         ("D", "JAR_DISPENSING_POSITION_PHOTOCELL", tr_("DISPENSING POSITION PHOTOCELL")),
         ("D", "container_presence", tr_("CAN PRESENCE")),
         ("D", "THOR BRUSH_PHOTOCELL", tr_("BRUSH PHOTOCELL")),
         ("D", "THOR TABLE_PHOTOCELL", tr_("ROTATING TABLE PHOTOCELL")),
         ("D", "THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL", tr_("PUMP MOTOR HOME PHOTOCELL")),
         ("D", "THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL", tr_("PUMP MOTOR INGR PHOTOCELL")),
         ("D", "THOR VALVE_OPEN_PHOTOCELL", tr_("VALVE PHOTOCELL LEFT")),
         ("D", "THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL", tr_("VALVE PHOTOCELL RIGHT")),
         ("D", "panel_table_status", tr_("PANEL TABLE STATUS")),], },
    {"title": tr_("action 07 (head 4 or E)"),
     "buttons": [
         {"text": tr_("Start dispensing roller"), "action_args": ("single_move", "E", [0, 1])},
         {"text": tr_("Stop dispensing roller"), "action_args": ("single_move", "E", [0, 0])},
         {"text": tr_("Start dispensing roller to photocell"), "action_args": ("single_move", "E", [0, 2])}, ],
     "labels_args": [
         ("E", "JAR_DISPENSING_POSITION_PHOTOCELL", tr_("DISPENSING POSITION PHOTOCELL")),
         ("E", "container_presence", tr_("CAN PRESENCE")),
         ("E", "THOR BRUSH_PHOTOCELL", tr_("BRUSH PHOTOCELL")),
         ("E", "THOR TABLE_PHOTOCELL", tr_("ROTATING TABLE PHOTOCELL")),
         ("E", "THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL", tr_("PUMP MOTOR HOME PHOTOCELL")),
         ("E", "THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL", tr_("PUMP MOTOR INGR PHOTOCELL")),
         ("E", "THOR VALVE_OPEN_PHOTOCELL", tr_("VALVE PHOTOCELL LEFT")),
         ("E", "THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL", tr_("VALVE PHOTOCELL RIGHT")),
         ("E", "panel_table_status", tr_("PANEL TABLE STATUS")),], },
    {"title": tr_("action 08 (head 2 or F)"),
     "buttons": [
         {"text": tr_("Start dispensing roller"), "action_args": ("single_move", "F", [0, 1])},
         {"text": tr_("Stop dispensing roller"), "action_args": ("single_move", "F", [0, 0])},
         {"text": tr_("Start dispensing roller to photocell"), "action_args": ("single_move", "F", [0, 2])},
         {"text": tr_("move 09 10 ('F -> DOWN')"), "action_args": ("move_09_10",)}, ],
     "labels_args": [
         ("F", "JAR_DISPENSING_POSITION_PHOTOCELL", tr_("DISPENSING POSITION PHOTOCELL")),
         ("F", "container_presence", tr_("CAN PRESENCE")),
         ("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL", tr_("LIFTER DOWN PHOTOCELL")),
         ("F", "THOR BRUSH_PHOTOCELL", tr_("BRUSH PHOTOCELL")),
         ("F", "THOR TABLE_PHOTOCELL", tr_("ROTATING TABLE PHOTOCELL")),
         ("F", "THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL", tr_("PUMP MOTOR HOME PHOTOCELL")),
         ("F", "THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL", tr_("PUMP MOTOR INGR PHOTOCELL")),
         ("F", "THOR VALVE_OPEN_PHOTOCELL", tr_("VALVE PHOTOCELL LEFT")),
         ("F", "THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL", tr_("VALVE PHOTOCELL RIGHT")),
         ("F", "panel_table_status", tr_("PANEL TABLE STATUS")),], },
    {"title": tr_("action 09 (head 2 or F)"),
     "buttons": [
         {"text": tr_("Start lifter roller CW"), "action_args": ("single_move", "F", [1, 1])},
         {"text": tr_("Start lifter roller CCW"), "action_args": ("single_move", "F", [1, 4])},
         {"text": tr_("Stop  lifter roller"), "action_args": ("single_move", "F", [1, 0])},
         {"text": tr_("Start lifter up"), "action_args": ("single_move", "F", [3, 2])},
         {"text": tr_("Start lifter down"), "action_args": ("single_move", "F", [3, 5])},
         {"text": tr_("Stop  lifter"), "action_args": ("single_move", "F", [3, 0])},
         {"text": tr_("move 09 10 ('F -> DOWN')"), "action_args": ("move_09_10",)},
         {"text": tr_("move 10 11 ('DOWN -> UP')"), "action_args": ("move_10_11",)},
         {"text": tr_("move 11 12 ('UP -> OUT')"), "action_args": ("move_11_12",)}, ],
     "labels_args": [
         ("F", "JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL", tr_("LIFTER ROLLER PHOTOCELL")),
         ("F", "UNLOAD_LIFTER_UP_PHOTOCELL", tr_("LIFTER UP PHOTOCELL")),
         ("F", "UNLOAD_LIFTER_DOWN_PHOTOCELL", tr_("LIFTER DOWN PHOTOCELL")), ], },
    {"title": tr_("action 10 (head 2 or F)"),
     "buttons": [
         {"text": tr_("Start output roller CCW"), "action_args": ("single_move", "F", [2, 4])},
         {"text": tr_("Stop  output roller"), "action_args": ("single_move", "F", [2, 0])},
         {"text": tr_("Start output roller CCW to photocell dark"), "action_args": ("single_move", "F", [2, 5])},
         {"text": tr_("Start output roller CCW to photocell light"), "action_args": ("single_move", "F", [2, 6])},
         {"text": tr_("move 11 12 ('UP -> OUT')"), "action_args": ("move_11_12",)},
         {"text": tr_("move 12 00 ('deliver')"), "action_args": ("move_12_00",)}, ],
     "labels_args": [
         ("F", "JAR_OUTPUT_ROLLER_PHOTOCELL", tr_("OUTPUT ROLLER PHOTOCELL")), ], }, ]


class MainWindow(QMainWindow):  # pylint:  disable=too-many-instance-attributes

    def __init__(self, parent=None):

        from alfa_CR6_frontend.debug_page import DebugPage  # pylint: disable=import-outside-toplevel

        self.action_frame_map = {}

        super().__init__(parent)

        if os.getenv("IN_DOCKER", False) in ['1', 'true']:
            loadUi(get_res("UI", "main_window_snowball.ui"), self)
        else:
            loadUi(get_res("UI", "main_window.ui"), self)

        self.settings = import_settings()

        self.setStyleSheet("""
                QWidget {font-size: 24px; font-family:Dejavu;}
                QPushButton {background-color: #F3F3F3F3; border: 1px solid #999999; border-radius: 4px;}
                QPushButton:pressed {background-color: #AAAAAA;}
                QScrollBar:vertical {width: 40px;}
                QScrollBar:horizontal {width: 36px;}
            """)

        self.menu_btn_group.buttonClicked.connect(self.on_menu_btn_group_clicked)

        self.menu_line_edit.returnPressed.connect(self.on_menu_line_edit_return_pressed)

        self.keyboard = Keyboard(self, keyboard_path=KEYBOARD_PATH)
        self.keyboard.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.keyboard.setGeometry(
            0,
            self.menu_frame.y() - self.keyboard.height(),
            self.menu_frame.width(),
            256)
        self.keyboard.hide()

        self.debug_page = DebugPage(self)
        self.stacked_widget.addWidget(self.debug_page.main_frame)

        self.help_page = HelpPage(parent=self)
        self.order_page = OrderPage(parent=self)

        self.browser_page = BrowserPage(parent=self)

        if QApplication.instance().n_of_active_heads == 6:
            self.home_page = HomePageSixHeads(parent=self)
            home_btn_pixmap = QPixmap(get_res("IMAGE", "sinottico_6_small.png"))

        elif QApplication.instance().n_of_active_heads == 4:
            self.home_page = HomePageFourHeads(parent=self)
            home_btn_pixmap = QPixmap(get_res("IMAGE", "sinottico_4_small.png"))

        self.home_btn.setIcon(QIcon(home_btn_pixmap))
        self.home_btn.setIconSize(QSize(280, 72))

        browser_btn_pixmap = QPixmap(get_res("IMAGE", "browser_btn.png"))
        self.browser_btn.setIcon(QIcon(browser_btn_pixmap))
        self.browser_btn.setIconSize(QSize(140, 60))
        self.browser_btn.setStyleSheet("""QPushButton {background-color: #FFFFFF; border: 1px solid #999999; border-radius: 4px;}""")

        self.stacked_widget.setCurrentWidget(self.home_page)

        self.__init_action_pages()

        self.__init_dialogs()
        self.__init_icons()

        self.home_page.recovery_btn.hide()
        self.set_warning_icon()

        self.showFullScreen()

        # ~ self.refill_1_lbl.mouseReleaseEvent = lambda event: self.show_reserve(0)
        # ~ self.refill_2_lbl.mouseReleaseEvent = lambda event: self.show_reserve(1)
        # ~ self.refill_3_lbl.mouseReleaseEvent = lambda event: self.show_reserve(2)
        # ~ self.refill_4_lbl.mouseReleaseEvent = lambda event: self.show_reserve(3)
        # ~ self.refill_5_lbl.mouseReleaseEvent = lambda event: self.show_reserve(4)
        # ~ self.refill_6_lbl.mouseReleaseEvent = lambda event: self.show_reserve(5)

        self._set_manual_barcode_btn()

    def __init_icons(self):

        self.gray_icon = QPixmap(get_res("IMAGE", "gray.png"))
        self.green_icon = QPixmap(get_res("IMAGE", "green.png"))
        self.red_icon = QPixmap(get_res("IMAGE", "red.png"))

        self.jar_icon_map = {
            k: QPixmap(get_res("IMAGE", p))
            for k, p in (
                ("no", ""),
                ("green", "jar-green.png"),
                ("red", "jar-red.png"),
                ("blue", "jat-blue.png"),
            )
        }
        self.tank_icon_map = {
            k: QPixmap(get_res("IMAGE", p))
            for k, p in (
                ("green", "tank_green.png"),
                ("gray", "tank_gray.png"),
            )
        }

    def __init_dialogs(self):

        self.input_dialog = InputDialog(self)
        self.edit_dialog = EditDialog(self)
        self.alias_dialog = AliasDialog(self)
        self.refill_dialog = RefillDialog(self)

    def __init_action_pages(self):

        action_page_list_ = ACTION_PAGE_LIST

        action_button_list_ = [
            self.home_page.action_01_btn,
            self.home_page.action_02_btn,
            self.home_page.action_03_btn,
            self.home_page.action_04_btn,
            self.home_page.action_05_btn,
            self.home_page.action_06_btn,
            self.home_page.action_07_btn,
            self.home_page.action_08_btn,
            self.home_page.action_09_btn,
            self.home_page.action_10_btn,
        ]

        if self.home_page.action_03_btn:
            action_page_list_[1]["buttons"].append(
                {"text": tr_("move 02 03 ('A -> B')"), "action_args": ("move_02_03",)})
            action_page_list_[2]["buttons"].append(
                {"text": tr_("move 03 04 ('B -> C')"), "action_args": ("move_03_04",)})
        else:
            action_page_list_[1]["buttons"].append(
                {"text": tr_("move 02 04 ('A -> C')"), "action_args": ("move_02_04",)})

        if self.home_page.action_07_btn:
            action_page_list_[5]["buttons"].append(
                {"text": tr_("move 07 08 ('D -> E')"), "action_args": ("move_07_08",)})
            action_page_list_[6]["buttons"].append(
                {"text": tr_("move 08 09 ('E -> F')"), "action_args": ("move_08_09",)})
        else:
            action_page_list_[5]["buttons"].append(
                {"text": tr_("move 07 09 ('D -> F')"), "action_args": ("move_07_09",)})

        action_frame_map = {}
        for i, btn in enumerate(action_button_list_):
            if btn:
                action_item = action_page_list_[i]
                action_item["buttons"].append({"text": tr_("back to home page"), "action_args": ("open_home_page",)})
                w = ActionPage(action_item, parent=self)
                action_frame_map[btn] = w

        self.action_frame_map = action_frame_map

    def _set_manual_barcode_btn(self):
        manual_barcode_btn = getattr(self.settings, "MANUAL_BARCODE_INPUT", False)
        self.manual_barcode_btn.setEnabled(manual_barcode_btn)

    def set_warning_icon(self):

        self.home_page.fw_align_ko_lbl.hide()

        if os.getenv("IN_DOCKER", False) in ['1', 'true']:
            file_path = '/tmp/share/data_from_app.json'
            if not os.path.exists(file_path):
                logging.error("data_from_app.json is missing!")
                return

            with open(file_path, 'r') as file:
                data = json.load(file)
                status = data.get('status', '')

                if not status:
                    logging.error("The key 'status' is empty or missing")

                if status != "app_running" :
                    self.home_page.fw_align_ko_lbl.show()
                    self.warning_movie = QMovie(get_res("IMAGE", "warning_blinking.gif"))
                    self.home_page.fw_align_ko_lbl.setMovie(self.warning_movie)
                    self.warning_movie.start()

    def get_stacked_widget(self):
        return self.stacked_widget

    def on_menu_line_edit_return_pressed(self):

        logging.warning("")

        def ok_cb_(lang_):
            logging.warning(f"lang_:{ lang_ }")
            set_language(lang_)

        txt_ = self.menu_line_edit.text()
        if LANGUAGE_MAP.get(txt_):
            lang_ = LANGUAGE_MAP[txt_]
            msg_ = tr_("confirm changing language to: {}? \n (WARN: application will be restarted)").format(lang_)
            self.open_input_dialog(message=msg_, ok_cb=ok_cb_, ok_cb_args=[lang_, ])
        elif 'alarm' in txt_:
            # ~ self.open_alert_dialog('TEST ALERT MESSAGE', title="ALERT", callback=None, args=None)
            args, fmt = ('sample', ), "TEST ALERT MESSAGE: {}"
            self.open_alert_dialog(args, fmt=fmt, title="ALERT")

    def on_menu_btn_group_clicked(self, btn):  # pylint: disable=too-many-branches

        btn_name = btn.objectName()

        try:

            if "keyboard" in btn_name:
                self.toggle_keyboard()

            elif "browser" in btn_name:
                if hasattr(self.settings, 'CHROMIUM_WRAPPER') and self.settings.CHROMIUM_WRAPPER:
                    chromium_wrapper = QApplication.instance().chromium_wrapper
                    if chromium_wrapper:
                        if "browser" in btn_name:
                            chromium_wrapper.window_remap(1)
                        else:
                            chromium_wrapper.window_remap(0)
                else:
                    self.toggle_keyboard(on_off=False)
                    self.browser_page.open_page()

            elif "home" in btn_name:
                self.toggle_keyboard(on_off=False)
                self.home_page.open_page()

            elif "order" in btn_name:
                self.toggle_keyboard(on_off=False)
                self.order_page.open_page()

            elif "debug_page" in btn_name:

                if self.stacked_widget.currentWidget() != self.debug_page.main_frame:
                    self.toggle_keyboard(on_off=True)

                    def ok_cb_():
                        debug_page_pwd = DEFAULT_DEBUG_PAGE_PWD
                        if hasattr(self.settings, 'DEBUG_PAGE_PWD') and self.settings.DEBUG_PAGE_PWD:
                            debug_page_pwd = self.settings.DEBUG_PAGE_PWD

                        pwd_ = self.input_dialog.content_container.toPlainText()
                        if pwd_ == debug_page_pwd:
                            self.stacked_widget.setCurrentWidget(self.debug_page.main_frame)
                            self.toggle_keyboard(on_off=False)

                    msg_ = tr_("please, enter service password")
                    self.open_input_dialog(message=msg_,  content="", ok_cb=ok_cb_)


            elif "help" in btn_name:
                self.toggle_keyboard(on_off=False)
                # ~ self.help_page.open_page()
                self.browser_page.open_page(url="http://127.0.0.1:8090/manual_index")

            elif "change_workspace" in btn_name:
                if os.system("/opt/snowball_client.py display change_workspace_wm") != 0:
                    raise RuntimeError("command execution failure")

            elif "manual_barcode" in btn_name:

                import asyncio

                def on_ok_callback():
                    self.toggle_keyboard(on_off=False)
                    head_A = QApplication.instance().get_machine_head_by_letter("A")
                    sensor = head_A.status["jar_photocells_status"] & 0x001 and 1
                    manual_barcode = self.input_dialog.get_content_text()

                    if not sensor:
                        message = tr_("Missing Jar on JAR_INPUT_ROLLER_PHOTOCELL")
                        self.open_alert_dialog(args=message, show_cancel_btn=False)
                        return

                    if not manual_barcode:
                        message = tr_("Empty Barcode")
                        self.open_alert_dialog(args="Empty Barcode ...", show_cancel_btn=False)
                        return

                    barcode_reader = BarCodeReader(QApplication.instance().on_barcode_read, "", True, True)
                    loop = asyncio.get_event_loop()
                    t = barcode_reader.manual_read(manual_barcode)
                    asyncio.ensure_future(t, loop=loop)

                self.toggle_keyboard(on_off=True)
                self.open_input_dialog(
                    icon_name="SP_MessageBoxQuestion",
                    message="MANUAL BARCODE INPUT:",
                    content="",
                    ok_cb=on_ok_callback,
                    ok_on_enter=True,
                    content_editable=True
                )

        except Exception as e:  # pylint: disable=broad-except
            QApplication.instance().handle_exception(e)

    def toggle_keyboard(self, on_off=None):

        if on_off is None:
            on_off = not self.keyboard.isVisible()

        ls = [
            self.order_page.jar_table_view,
            self.order_page.order_table_view,
            self.order_page.file_table_view, ]

        if not hasattr(self.settings, 'CHROMIUM_WRAPPER') or not self.settings.CHROMIUM_WRAPPER:
            if self.browser_page.webengine_view:
                ls.append(self.browser_page.webengine_view)

        if on_off and not self.keyboard.isVisible():
            self.keyboard.show()
            for l in ls:
                l.resize(l.width(), l.height() - self.keyboard.height())
        elif not on_off and self.keyboard.isVisible():
            self.keyboard.hide()
            for l in ls:
                l.resize(l.width(), l.height() + self.keyboard.height())

    def __update_action_pages(self):

        for action_frame in self.action_frame_map.values():
            if action_frame.isVisible():
                action_frame.show_values_in_labels()

    def update_status_data(self, head_index, _=None):

        try:
            self.debug_page.update_status()

            self.home_page.update_service_btns__presences_and_lifters(head_index)
            self.home_page.update_tank_pixmaps()
            self.home_page.update_jar_pixmaps()
            self.__update_action_pages()

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def show_carousel_recovery_mode(self, toggle):
        self.home_page.update_lbl_recovery(toggle)
        self.home_page.feed_jar_btn.setEnabled(not toggle)

        if toggle:
            self.home_page.recovery_btn.show()
        else:
            self.home_page.recovery_btn.hide()

    def show_reserve(self, head_index, flag=None):

        self.home_page.show_reserve(head_index, flag=flag)

    def show_carousel_frozen(self, flag):
        if flag:
            self.home_page.freeze_carousel_btn.setText(tr_("Carousel Paused"))
            self.home_page.freeze_carousel_btn.setIcon(QIcon(self.red_icon))
            self.home_page.freeze_carousel_btn.setStyleSheet(
                "background-color: #00FFFFFF; color: #990000"
            )
        else:
            self.home_page.freeze_carousel_btn.setText(tr_("Carousel OK"))
            self.home_page.freeze_carousel_btn.setIcon(QIcon(self.green_icon))
            self.home_page.freeze_carousel_btn.setStyleSheet(
                "background-color: #00FFFFFF; color: #004400"
            )

        try:
            self.__update_action_pages()
            self.home_page.update_jar_pixmaps()
            self.home_page.update_tank_pixmaps()
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def open_alias_dialog(self):

        self.alias_dialog.show_dialog(self.settings.DATA_PATH)

    def open_edit_dialog(self, order_nr):

        self.edit_dialog.show_dialog(order_nr)
        self.toggle_keyboard(on_off=True)

        logging.warning(str(order_nr))

    def open_input_dialog(  # pylint: disable=too-many-arguments
            self, icon_name=None, message=None, content=None,
            ok_cb=None, ok_cb_args=None, ok_on_enter=False,
            choices=None, bg_image=None, to_html=None, wide=None,
            content_editable=True
    ):

        self.input_dialog.show_dialog(
            icon_name=icon_name,
            message=message,
            content=content,
            ok_cb=ok_cb,
            ok_cb_args=ok_cb_args,
            ok_on_enter=ok_on_enter,
            choices=choices,
            bg_image=bg_image,
            to_html=to_html,
            wide=wide,
            content_editable=content_editable)

        logging.warning(str(message))

    def open_alert_dialog(  # pylint: disable=too-many-arguments
            self, args, title="ALERT", fmt=None,
            callback=None, cb_args=None, hp_callback=None,
            visibility=1, show_cancel_btn=True
    ):

        if fmt is not None:
            msg = tr_(fmt).format(*args)
            msg_ = fmt.format(*args)
        else:
            msg = str(args)
            msg_ = ''
        json_properties_ = json.dumps({'fmt': fmt, 'args': args, 'msg_': msg_, 'msg': msg}, indent=2, ensure_ascii=False)

        logging.warning(f"dialog visibility:{visibility} msg:{msg}")

        if visibility > 0:

            _msgbox = ModalMessageBox(
                parent=self, msg=msg, title=title,
                ok_callback=callback, ok_callback_args=cb_args,
                hp_callback=hp_callback
            )
            if not show_cancel_btn:
                _msgbox.enable_buttons(True, False, False)

            if visibility > 1:
                _msgbox.setStyleSheet("""QMessageBox {border: 10px solid #FF3333; background-color: #FFFF33;}""")
                txt_ = _msgbox.text() + "\n___________________________________________\n"
                _msgbox.setText(txt_)

        QApplication.instance().insert_db_event(
            name='UI_DIALOG',
            level=f"{title}",
            severity='',
            source="MainWindow.open_alert_dialog",
            json_properties=json_properties_,
            description=f"{msg_ or msg}")

    def open_frozen_dialog( # pylint: disable=too-many-arguments
            self, msg, title="ALERT", force_explicit_restart=False,
            ok_callback=None, hp_callback=None, visibility=1,
            show_cancel_btn=True
    ):

        logging.info(msg)
        msg_ = tr_("carousel is paused.")
        msg_ += f'\n------------------------------\n"{msg}"\n------------------------------\n'
        if force_explicit_restart:
            # ~ self.open_alert_dialog(msg_, title=title)
            callback = ok_callback
            cb_args = []
        else:
            msg_ += tr_("hit 'OK' to unfreeze it")
            callback = QApplication.instance().freeze_carousel
            cb_args = [False, ]

        self.open_alert_dialog(
            msg_, title=title, callback=callback, cb_args=cb_args,
            hp_callback=hp_callback, visibility=visibility,
            show_cancel_btn=show_cancel_btn
        )

    def open_recovery_dialog(self, recovery_items, lbl_text=None):
        app_frozen = QApplication.instance().carousel_frozen
        _msgbox = RecoveryInfoDialog(
            parent=self,
            recovery_items=recovery_items,
            lbl_text=lbl_text,
            app_frozen=app_frozen
        ) 

    def show_barcode(self, barcode, is_ok=False):

        css = "color: #000000" if is_ok else "color: #990000"
        self.menu_line_edit.setStyleSheet(css)
        self.menu_line_edit.setText(f"{barcode}")

    def open_refill_dialog(  # pylint: disable=too-many-arguments
            self, icon_name=None, message=None,
            ok_cb=None, ok_cb_args=None, ok_on_enter=False,
            choices=None, unit=None
    ):
        self.refill_dialog.show_dialog(
            icon_name=icon_name,
            message=message,
            ok_cb=ok_cb,
            ok_cb_args=ok_cb_args,
            ok_on_enter=ok_on_enter,
            choices=choices,
            unit=unit)

    def hide_input_dialog(self):
        self.input_dialog.hide_dialog()
