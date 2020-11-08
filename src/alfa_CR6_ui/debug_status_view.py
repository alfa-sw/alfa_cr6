# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=bad-continuation
# pylint: disable=protected-access


import os
# ~ import sys
# ~ import time
import logging
import traceback
import asyncio
# ~ import json

from PyQt5.QtWidgets import QApplication, QFrame, QTextBrowser, QButtonGroup, QPushButton   # pylint: disable=no-name-in-module


class DebugStatusView():

    def __init__(self):

        app = QApplication.instance()

        self.main_frame = QFrame(parent=app.main_window.main_window_stack)
        # ~ self.main_frame.setGeometry(0, 0, 1800, 1000)

        self.buttons_frame = QFrame(parent=self.main_frame)
        self.buttons_frame.setStyleSheet("""
                QFrame {
                    background-color: rgb(220, 220, 220);
                    font-size: 16px;
                    font-face: monospace;
                    }
                """)
        self.button_group = QButtonGroup(parent=self.buttons_frame)
        for i, n in enumerate([
            ('move_01_02', 'IN -> A'),
            ('move_02_03', 'A -> B'),
            ('move_03_04', 'B -> C'),
            ('move_04_05', 'C -> UP'),
            ('move_05_06', 'UP -> DOWN'),
            ('move_06_07', 'DOWN -> D'),
            ('move_07_08', 'D -> E'),
            ('move_08_09', 'E -> F'),
            ('move_09_10', 'F -> DOWN'),
            ('move_10_11', 'DOWN -> UP'),
            ('move_11_12', 'UP -> OUT'),
            ('stop_all', ''),
        ]):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 0, 150, 80)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate([
            'feed',
            'deliver',
            'complete',
            'read BC',
            'clear jars',
            'refresh',
            '*',
            '*',
            '*',
            '*',
            '*',
            'close',
        ]):

            b = QPushButton(n, parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 90, 150, 80)
            self.button_group.addButton(b)

        self.status_text_browser = QTextBrowser(parent=self.main_frame)
        self.status_text_browser.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.status_text_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: rgb(230, 230, 230);
                    font-size: 18px;
                    font-face: monospace;
                    }
                """)

        self.answer_text_browser = QTextBrowser(parent=self.main_frame)
        self.answer_text_browser.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.answer_text_browser.setStyleSheet("background-color: rgb(230, 230, 230)")

        self.answer_text_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: rgb(230, 230, 230);
                    font-size: 16px;
                    font-face: monospace;
                    }
                """)

        width = 1880
        self.status_text_browser.setGeometry(10, 0, width, 600)
        self.answer_text_browser.setGeometry(10, 600, width, 300)
        self.buttons_frame.setGeometry(10, 900, width, 180)

        # ~ app.main_window.sinottico.main_view_stack.addWidget(self.main_frame)
        # ~ app.main_window.sinottico.main_view_stack.setCurrentWidget(self.main_frame)
        app.main_window.main_window_stack.addWidget(self.main_frame)
        app.main_window.main_window_stack.setCurrentWidget(self.main_frame)

        self.status_text_browser.anchorClicked.connect(self.on_text_browser_anchor_clicked)
        self.button_group.buttonClicked.connect(self.on_button_group_clicked)
        app.onHeadStatusChanged.connect(self.show_status)

        app.onCmdAnswer.connect(self.on_machine_cmd_answer)

    def on_machine_cmd_answer(self, index, answer):       # pylint: disable=no-self-use

        logging.warning(f"index:{ index }, answer:{ answer }")
        self.answer_text_browser.append(f"index:{ index }, answer:{ answer }")

    def on_text_browser_anchor_clicked(self, url):       # pylint: disable=no-self-use

        logging.warning(f"url:{url.url()}")
        os.system("chromium-browser {} &".format(url.url()))

    def on_button_group_clicked(self, btn):             # pylint: disable=no-self-use
        logging.warning(f"{btn}")

        # ~ if 'reset_tasks' in btn.text():
        # ~ app = QApplication.instance()
        # ~ app.reset_tasks()
        # ~ else:

        app = QApplication.instance()

        if 'refresh' in btn.text():
            self.show_status()

        if 'close' in btn.text():
            # ~ app.main_window.main_window_stack.setCurrentIndex(0)
            app.main_window.main_window_stack.setCurrentWidget(app.main_window.project)

        if 'clear jars' in btn.text():

            for j in app._CR6_application__progressing_jars:
                j.status = 'DONE'

            for k in [_ for _ in app._CR6_application__jar_runners.keys()]:
                t = app._CR6_application__jar_runners[k]
                try:
                    asyncio.ensure_future(t.cancel())
                except asyncio.CancelledError:
                    logging.info(f"{ t } has been canceled now.")

            app._CR6_application__progressing_jars = []
            app._CR6_application__jar_runners = {}

        if 'read BC' in btn.text():
            t = app._CR6_application__on_barcode_read(0, 23456, skip_checks=True)
            asyncio.ensure_future(t)
            logging.warning(f"t:{t}")

        elif 'complete' in btn.text():

            async def coro():

                for i in [
                    'move_01_02',
                    'move_02_03',
                    'move_03_04',
                    'move_04_05',
                    'move_05_06',
                    'move_06_07',
                    'move_07_08',
                    'move_08_09',
                    'move_09_10',
                    'move_10_11',
                    'move_11_12',
                ]:
                    if hasattr(app, i):
                        t = getattr(app, i)
                        await t()
                        await asyncio.sleep(1)

            try:
                t = coro()
                asyncio.ensure_future(t)
            except BaseException:
                logging.error(traceback.format_exc())

        else:
            try:
                if hasattr(app, btn.text()):
                    coro = getattr(app, btn.text())
                    t = coro()
                    asyncio.ensure_future(t)
                    logging.warning(f"t:{t}")
                else:
                    logging.warning(f"action not found! {btn.text()}")

            except BaseException:
                logging.error(traceback.format_exc())

    def show_status(self, _=None):

        if not self.main_frame.isVisible():
            return

        app = QApplication.instance()

        named_map = {m.name: m for m in app.machine_head_dict.values()}
        keys_ = named_map.keys()

        html_ = ''

        html_ += '<table>'

        html_ += '<tr>                                           '

        html_ += '<td colspan="1">                                           '
        html_ += '<br/># "jar photocells_status" mask bit coding:'
        html_ += '<br/># bit0: JAR_INPUT_ROLLER_PHOTOCELL        '
        html_ += '<br/># bit1: JAR_LOAD_LIFTER_ROLLER_PHOTOCELL  '
        html_ += '<br/># bit2: JAR_OUTPUT_ROLLER_PHOTOCELL       '
        html_ += '<br/># bit3: LOAD_LIFTER_DOWN_PHOTOCELL        '
        html_ += '<br/># bit4: LOAD_LIFTER_UP_PHOTOCELL          '
        html_ += '<br/># bit5: UNLOAD_LIFTER_DOWN_PHOTOCELL      '
        html_ += '<br/># bit6: UNLOAD_LIFTER_UP_PHOTOCELL        '
        html_ += '<br/># bit7: JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL'
        html_ += '<br/># bit8: JAR_DISPENSING_POSITION_PHOTOCELL '
        html_ += '<br/># bit9: JAR_DETECTION_MICROSWITCH_1       '
        html_ += '<br/># bit10:JAR_DETECTION_MICROSWITCH_2       '
        html_ += '</td>                                          '

        html_ += '<td colspan="2">                                          '
        html_ += '<br/># progressing_jars:'
        for i, j in enumerate(app._CR6_application__progressing_jars):
            html_ += '<br/>{}:<code>"{}"</code>'.format(i, j)
        html_ += '</td>                                          '

        html_ += '</tr>                                          '
        html_ += '</table>                                       '

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

        html_ += '</table>'

        self.status_text_browser.setHtml(html_)
