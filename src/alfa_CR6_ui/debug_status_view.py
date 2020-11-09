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

        self.status_text_browser = QTextBrowser(parent=self.main_frame)
        # ~ self.status_text_browser.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.status_text_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: #FFFFF7;
                    font-size: 18px;
                    font-family: monospace;
                    }
                """)

        self.answer_text_browser = QTextBrowser(parent=self.main_frame)
        # ~ self.answer_text_browser.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.answer_text_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: #FFFFF7;
                    font-size: 16px;
                    font-family: monospace;
                    }
                """)

        self.buttons_frame = QFrame(parent=self.main_frame)
        self.buttons_frame.setStyleSheet("""
                QFrame {
                    background-color: #FFFFF7;
                    font-size: 16px;
                    font-family: monospace;
                    }
                """)
        self.button_group = QButtonGroup(parent=self.buttons_frame)
        for i, n in enumerate([
            ('move_00_01', 'feed to IN'),
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
        ]):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 0, 150, 80)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate([
            ('stop_all', 'stop movement for all heads'),
            ('complete', 'start the complete cycle through the system'),
            ('read BC', 'simulate a bar code read'),
            ('clear jars', 'delete all the jars'),
            ('refresh', 'refresh the view'),
            ('*', '**'),
            ('*', '**'),
            ('*', '**'),
            ('*', '**'),
            ('*', '**'),
            ('*', '**'),
            ('close', 'close this widget'),
        ]):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 90, 150, 80)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        width = 1880
        self.status_text_browser.setGeometry(20, 0, width, 560)
        self.buttons_frame.setGeometry(20, 570, width, 180)
        self.answer_text_browser.setGeometry(20, 760, width, 300)

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

        app = QApplication.instance()
        cmd_txt = btn.text()

        logging.warning(f"cmd_txt:{cmd_txt}")

        if 'refresh' in cmd_txt:
            self.show_status()

        elif 'close' in cmd_txt:
            # ~ app.main_window.main_window_stack.setCurrentIndex(0)
            app.main_window.main_window_stack.setCurrentWidget(app.main_window.project)

        elif 'clear jars' in cmd_txt:

            for k in [_ for _ in app._CR6_application__jar_runners.keys()]:
                t = app._CR6_application__jar_runners[k]['task']
                try:
                    t.cancel()

                    async def _coro(_):
                        await _
                    asyncio.ensure_future(_coro(t))
                except asyncio.CancelledError:
                    logging.info(f"{ t } has been canceled now.")

        elif 'read BC' in cmd_txt:
            t = app._CR6_application__on_barcode_read(0, 23456, skip_checks=True)
            asyncio.ensure_future(t)
            logging.warning(f"t:{t}")

        elif 'complete' in cmd_txt:
            async def coro():
                ret_vals = []
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
                        ret = await t()
                        ret_vals.append(ret)
                        await asyncio.sleep(1)

                return ret_vals

            try:
                t = coro()
                asyncio.ensure_future(t)
            except BaseException:
                logging.error(traceback.format_exc())

        else:
            app.run_a_coroutine_helper(cmd_txt)

    def show_status(self, _=None):

        if not self.main_frame.isVisible():
            return

        app = QApplication.instance()

        named_map = {m.name: m for m in app.machine_head_dict.values()}
        keys_ = named_map.keys()

        html_ = ''

        html_ += '<small>app ver.: {}</small>'.format(app.get_version())
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
        for i, j in enumerate(app._CR6_application__jar_runners.values()):
            html_ += '<br/>{}:"{}"'.format(i, j['jar'])
        html_ += '</td>                                          '

        html_ += '</tr>                                          '
        html_ += '</table>                                       '

        html_ += '<hr></hr>'

        html_ += '<table width="100%" aligbcellpadding="80px" cellspacing="80px">'

        html_ += '<tr bgcolor="#FFFFFF">'
        html_ += '<th align="left">ord.</th>'
        html_ += '<th align="left">name</th>'
        html_ += '<th align="left">addr</th>'
        html_ += '<th align="left">level</th>'
        html_ += '<th align="left">jar_photocells_status</th>'
        html_ += '<th align="left">photocells_status</th>'
        html_ += '<th align="left">last update</th>'
        html_ += '</tr>'

        for k in sorted(keys_):

            m = named_map[k]
            ord = m.index + 1
            photoc_ = m.status.get('photocells_status', -1)
            jar_ph_ = m.status.get('jar_photocells_status', -1)

            html_ += '<tr>'

            html_ += '  <td>head {}</td>'.format(ord)
            html_ += '  <td>{}</td>'.format(m.name)
            html_ += '  <td><a href="http://{0}:8080/admin"> {0} </a></td>'.format(m.ip_add)
            html_ += '  <td>{}</td>'.format(m.status.get('status_level'))
            html_ += '  <td>{0:04b} {1:04b} {2:04b} | 0x{3:04X} {3:5d}</td>'.format(
                0xF & (jar_ph_ >> 8), 0xF & (jar_ph_ >> 4), 0xF & (jar_ph_ >> 0), jar_ph_)
            html_ += '  <td>        {0:04b} {1:04b} | 0x{2:04X} {2:5d}</td>'.format(
                0xF & (photoc_ >> 4), 0xF & (photoc_ >> 0), photoc_)
            html_ += '  <td>{}</td>'.format(m.status.get('last_update'))

            html_ += '</tr>'

        html_ += '</table>'

        self.status_text_browser.setHtml(html_)
