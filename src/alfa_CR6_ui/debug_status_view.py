# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=bad-continuation


import os
# ~ import sys
# ~ import time
import logging
import traceback
import asyncio
# ~ import json

from PyQt5.QtWidgets import QApplication, QFrame, QTextBrowser, QTextEdit, QButtonGroup, QPushButton   # pylint: disable=no-name-in-module


class DebugStatusView():

    def __init__(self):

        app = QApplication.instance()

        self.main_frame = QFrame(parent=app.main_window.main_window_stack)
        # ~ self.main_frame.setGeometry(0, 0, 1800, 1000)

        self.buttons_frame = QFrame(parent=self.main_frame)
        self.buttons_frame.setGeometry(20, 680, 1800, 160)
        self.buttons_frame.setStyleSheet("background-color: rgb(220, 220, 220)")
        self.button_group = QButtonGroup(parent=self.buttons_frame)
        for i, n in enumerate([
            ('01-02', 'IN -> A'),
            ('02-03', 'A -> B'),
            ('03-04', 'B -> C'),
            ('04-05', 'C -> UP'),
            ('05-06', 'UP -> DOWN'),
            ('06-07', 'DOWN -> D'),
            ('07-08', 'D -> E'),
            ('08-09', 'E -> F'),
            ('09-10', 'F -> DOWN'),
            ('10-11', 'DOWN -> UP'),
            ('11-12', 'UP -> OUT'),
            ('StopAll', 'A -> B'),
        ]):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 144, 0, 140, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate([
            'feed',
            'deliver',
            'complete',
            'read BC',
            '*',
            '*',
            '*',
            '*',
            '*',
            '*',
            '*',
            '*',
        ]):

            b = QPushButton(n, parent=self.buttons_frame)
            b.setGeometry(20 + i * 144, 70, 140, 60)
            self.button_group.addButton(b)

        self.text_browser = QTextBrowser(parent=self.main_frame)
        self.text_browser.setGeometry(20, 0, 1800, 680)
        self.text_browser.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.text_browser.setStyleSheet("background-color: rgb(230, 230, 230)")

        self.text_edit = QTextEdit(parent=self.main_frame)
        self.text_edit.setGeometry(20, 840, 1800, 680)
        self.text_edit.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.text_edit.setStyleSheet("background-color: rgb(230, 230, 230)")

        app.main_window.sinottico.main_view_stack.addWidget(self.main_frame)
        app.main_window.sinottico.main_view_stack.setCurrentWidget(self.main_frame)

        self.text_browser.anchorClicked.connect(self.on_text_browser_anchor_clicked)
        self.button_group.buttonClicked.connect(self.on_button_group_clicked)
        app.onHeadStatusChanged.connect(self.show_status)

        app.onCmdAnswer.connect(self.on_machine_cmd_answer)

    def on_machine_cmd_answer(self, index, answer):       # pylint: disable=no-self-use

        logging.warning(f"index:{ index }, answer:{ answer }")
        self.text_edit.append(f"index:{ index }, answer:{ answer }")

    def on_text_browser_anchor_clicked(self, url):       # pylint: disable=no-self-use

        logging.warning(f"url:{url.url()}")
        os.system("chromium-browser {} &".format(url.url()))

    def on_button_group_clicked(self, btn):             # pylint: disable=no-self-use
        logging.warning(f"{btn}")

        # ~ if 'reset_tasks' in btn.text():
        # ~ app = QApplication.instance()
        # ~ app.reset_tasks()
        # ~ else:

        if 'read BC' in btn.text():
            app = QApplication.instance()
            t = app._CR6_application__on_barcode_read(0, 23456, skip_checks=True)
            asyncio.ensure_future(t)
            logging.warning(f"t:{t}")

        elif 'complete' in btn.text():

            async def coro():

                for i in [
                    '01-02',
                    '02-03',
                    '03-04',
                    '04-05',
                    '05-06',
                    '06-07',
                    '07-08',
                    '08-09',
                    '09-10',
                    '10-11',
                    '11-12',
                ]:
                    await self.move_task(i)
                    await asyncio.sleep(1)

            try:
                t = coro()
                asyncio.ensure_future(t)
            except BaseException:
                logging.error(traceback.format_exc())

        else:
            try:
                t = self.move_task(btn.text())
                asyncio.ensure_future(t)
            except BaseException:
                logging.error(traceback.format_exc())

    def show_status(self, _):

        app = QApplication.instance()

        named_map = {m.name: m for m in app.machine_head_dict.values()}
        keys_ = named_map.keys()

        html_ = """
            <table>
            <tr>
            <td>
            <br/># 'photocells_status' mask bit coding:
            <br/># bit0: THOR PUMP HOME_PHOTOCELL - MIXER HOME PHOTOCELL
            <br/># bit1: THOR PUMP COUPLING_PHOTOCELL - MIXER JAR PHOTOCELL
            <br/># bit2: THOR VALVE_PHOTOCELL - MIXER DOOR OPEN PHOTOCELL
            <br/># bit3: THOR TABLE_PHOTOCELL -
            <br/># bit4: THOR VALVE_OPEN_PHOTOCELL
            <br/># bit5: THOR AUTOCAP_CLOSE_PHOTOCELL
            <br/># bit6: THOR AUTOCAP_OPEN_PHOTOCELL
            <br/># bit7: THOR BRUSH_PHOTOCELL
            </td>
            <td>
            <br/># 'jar photocells_status' mask bit coding:
            <br/># bit0: JAR_INPUT_ROLLER_PHOTOCELL
            <br/># bit1: JAR_LOAD_LIFTER_ROLLER_PHOTOCELL
            <br/># bit2: JAR_OUTPUT_ROLLER_PHOTOCELL
            <br/># bit3: LOAD_LIFTER_DOWN_PHOTOCELL
            <br/># bit4: LOAD_LIFTER_UP_PHOTOCELL
            <br/># bit5: UNLOAD_LIFTER_DOWN_PHOTOCELL
            <br/># bit6: UNLOAD_LIFTER_UP_PHOTOCELL
            <br/># bit7: JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL
            <br/># bit8: JAR_DISPENSING_POSITION_PHOTOCELL
            <br/># bit9: JAR_DETECTION_MICROSWITCH_1
            <br/># bit10:JAR_DETECTION_MICROSWITCH_2
            </td>
            </tr>
            </table>
        """

        # ~ html_ += '<h3>CURRENT STATUS:</h3>'
        html_ += '<hr></hr>'
        html_ += '<table width="100%" aligbcellpadding="80px" cellspacing="80px">'
        html_ += "<tr><th>index</th><th>name</th><th>add</th><th>level</th><th>last update</th>"
        html_ += "<th>photocells_status</th><th>jar_photocells_status</th></tr>"

        for k in sorted(keys_):
            html_ += '<tr>'
            m = named_map[k]

            photoc_ = m.status.get('photocells_status', -1)
            jar_ph_ = m.status.get('jar_photocells_status', -1)

            html_ += '  <td align="center">{}</td>'.format(m.index)
            html_ += '  <td align="center">{}</td>'.format(m.name)
            html_ += '  <td align="center"><a href="http://{0}:8080/admin"> {0} </a></td>'.format(m.ip_add)
            html_ += '  <td align="center">{}</td>'.format(m.status.get('status_level'))
            html_ += '  <td align="center">{}</td>'.format(m.status.get('last_update'))
            html_ += '  <td align="center">        {0:04b} {1:04b} 0x{2:04X} {2:05d}</td>'.format(
                0xF & (photoc_ >> 4), 0xF & (photoc_ >> 0), photoc_)
            html_ += '  <td align="center">{0:04b} {1:04b} {2:04b} 0x{3:04X} {3:05d}</td>'.format(
                0xF & (jar_ph_ >> 8), 0xF & (jar_ph_ >> 4), 0xF & (jar_ph_ >> 0), jar_ph_)
            html_ += '</tr>'
        html_ += '<table>'

        self.text_browser.setHtml(html_)

    async def move_task(self, cmd_string):

        app = QApplication.instance()

        try:

            logging.warning(f"cmd_string:{cmd_string}")
            if 'feed' in cmd_string:  # ' -> IN'
                await app.feed_to_IN()

            if '01-02' in cmd_string:  # 'IN -> A'
                await app.move_IN_A()

            if '02-03' in cmd_string:  # 'A -> B'

                await app.move_A_B()

            if '03-04' in cmd_string:  # 'B -> C'

                await app.move_B_C()

            if '04-05' in cmd_string:  # 'C -> UP'

                await app.move_C_UP()

            if '05-06' in cmd_string:  # 'UP -> DOWN'

                await app.move_UP_DOWN_LEFT()

            if '06-07' in cmd_string:  # 'DOWN -> D'

                await app.move_DOWN_D()

            if '07-08' in cmd_string:  # 'D -> E'

                await app.move_D_E()

            if '08-09' in cmd_string:  # 'E -> F'

                await app.move_E_F()

            if '09-10' in cmd_string:  # 'F -> DOWN'

                await app.move_F_DOWN()

            if '10-11' in cmd_string:  # 'DOWN -> UP'

                await app.move_DOWN_UP_RIGHT()

            if '11-12' in cmd_string:  # 'UP -> OUT'

                await app.move_UP_OUT()

            if 'StopAll' in cmd_string:

                await app.stop_all()

        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())
