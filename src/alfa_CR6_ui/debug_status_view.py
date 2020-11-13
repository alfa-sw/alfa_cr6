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

    def __init__(self, parent):

        app = QApplication.instance()
        
        self.barcode_counter = 0

        self.main_frame = QFrame(parent=parent)
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
            ('KILL', 'KILL_EMULATOR'),
            ('clear answers', 'clear answers'),
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
        parent.main_window_stack.addWidget(self.main_frame)
        parent.main_window_stack.setCurrentWidget(self.main_frame)

        self.status_text_browser.anchorClicked.connect(self.status_text_browser_anchor_clicked)
        self.button_group.buttonClicked.connect(self.on_button_group_clicked)
        app.onHeadMsgReceived.connect(self.on_machine_msg_received)

    def on_machine_msg_received(self, index, msg_dict):       # pylint: disable=no-self-use

        app = QApplication.instance()

        logging.debug(f"msg_dict:{msg_dict}")

        if msg_dict.get('type') == 'device:machine:status':
            status = msg_dict.get('value')
            status = dict(status)
            if status:
                self.show_status()

        elif msg_dict.get('type') == 'answer':
            answer = msg_dict.get('value')
            answer = dict(answer)
            if answer:

                _ = f"name:{ app.machine_head_dict[index].name }, answer:{ answer }"
                # ~ logging.warning(_)
                self.answer_text_browser.append(_)

        elif msg_dict.get('type') == 'time':
            # ~ logging.warning(f"msg_dict:{msg_dict}")
            time_stamp = msg_dict.get('value')
            if time_stamp:
                self.time_stamp = time_stamp

    def status_text_browser_anchor_clicked(self, url):       # pylint: disable=no-self-use

        app = QApplication.instance()
        named_map = {m.name: m for m in app.machine_head_dict.values()}

        logging.warning(f"url:{url.url()}")
        logging.warning(f"url.url().split('@'):{url.url().split('@')}")
        if url.url().split('@')[1:]:
            command, name = url.url().split('@')
            if command == "DIAGNOSTIC":
                m = named_map[name]
                t = m.send_command(cmd_name="ENTER_DIAGNOSTIC", params={}, type_='command', channel='machine')
                asyncio.ensure_future(t)
            elif command == "RESET":
                m = named_map[name]
                t = m.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
                asyncio.ensure_future(t)
        else:
            os.system("chromium-browser {} &".format(url.url()))
            
        # ~ self.show_status()

    def on_button_group_clicked(self, btn):             # pylint: disable=no-self-use

        app = QApplication.instance()
        cmd_txt = btn.text()

        # ~ logging.warning(f"cmd_txt:{cmd_txt}")

        if 'KILL' in cmd_txt:

            m = app.machine_head_dict[0]
            t = m.send_command(cmd_name="KILL_EMULATOR", params={})
            asyncio.ensure_future(t)

        elif 'refresh' in cmd_txt:
            self.show_status()

        elif 'clear answers' in cmd_txt:
            self.answer_text_browser.setText("")
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
            self.barcode_counter += 1
            t = app.on_barcode_read(0, self.barcode_counter, skip_checks=True)
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
        names_ = named_map.keys()

        html_ = ''

        html_ += '<small>app ver.: {}</small>'.format(app.get_version())
        html_ += '<table>'

        html_ += '<tr>                                           '

        html_ += '<td colspan="1">                                           '
        html_ += '<br/># "jar photocells_status" mask bit coding:'
        html_ += '<br/> 0000 0000 0001  | 0x0001 # bit0: JAR_INPUT_ROLLER_PHOTOCELL        '
        html_ += '<br/> 0000 0000 0010  | 0x0002 # bit1: JAR_LOAD_LIFTER_ROLLER_PHOTOCELL  '
        html_ += '<br/> 0000 0000 0100  | 0x0004 # bit2: JAR_OUTPUT_ROLLER_PHOTOCELL       '
        html_ += '<br/> 0000 0000 1000  | 0x0008 # bit3: LOAD_LIFTER_DOWN_PHOTOCELL        '
        html_ += '<br/> 0000 0001 0000  | 0x0010 # bit4: LOAD_LIFTER_UP_PHOTOCELL          '
        html_ += '<br/> 0000 0010 0000  | 0x0020 # bit5: UNLOAD_LIFTER_DOWN_PHOTOCELL      '
        html_ += '<br/> 0000 0100 0000  | 0x0040 # bit6: UNLOAD_LIFTER_UP_PHOTOCELL        '
        html_ += '<br/> 0000 1000 0000  | 0x0080 # bit7: JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL'
        html_ += '<br/> 0001 0000 0000  | 0x0100 # bit8: JAR_DISPENSING_POSITION_PHOTOCELL '
        html_ += '<br/> 0010 0000 0000  | 0x0200 # bit9: JAR_DETECTION_MICROSWITCH_1       '
        html_ += '<br/> 0100 0000 0000  | 0x0400 # bit10:JAR_DETECTION_MICROSWITCH_2       '
        html_ += '</td>                                          '

        html_ += '<td colspan="2">                                          '
        html_ += '<br/># progressing_jars:'
        l_ = [i for i in app._CR6_application__jar_runners.values()]
        l_.reverse()
        for i, j in enumerate(l_):
            html_ += '<br/>{}:{} {}'.format(i, j['jar'], j['jar'].description)
        html_ += '</td>                                          '

        html_ += '</tr>                                          '
        html_ += '</table>                                       '

        html_ += '<hr></hr>'

        html_ += '<table width="100%" aligbcellpadding="80px" cellspacing="80px">'

        html_ += '<tr bgcolor="#FFFFFF">'
        html_ += '<th align="left" width="5%">ord.</th>'
        html_ += '<th align="left" width="7%">name</th>'
        html_ += '<th align="left" width="8%">addr</th>'
        html_ += '<th align="left" width="18%">jar_photocells_status</th>'
        html_ += '<th align="left" width="16%">photocells_status</th>'
        html_ += '<th align="left" width="12%">(cp) level</th>'
        html_ += '<th align="left" width="20%">last update</th>'
        html_ += '<th align="left" width="7%">-</th>'
        html_ += '<th align="left" width="8%">-</th>'
        html_ += '</tr>'

        for n in sorted(names_):

            m = named_map[n]
            ord = m.index + 1
            photoc_ = m.status.get('photocells_status', -1)
            jar_ph_ = m.status.get('jar_photocells_status', -1)

            html_ += '<tr>'

            html_ += '  <td>head {}</td>'.format(ord)
            html_ += '  <td>{}</td>'.format(m.name)
            html_ += '  <td><a href="http://{0}:8080/admin"> {0} </a></td>'.format(m.ip_add)
            html_ += '  <td>{0:04b} {1:04b} {2:04b} | 0x{3:04X} {3:5d}</td>'.format(
                0xF & (jar_ph_ >> 8), 0xF & (jar_ph_ >> 4), 0xF & (jar_ph_ >> 0), jar_ph_)
            html_ += '  <td>        {0:04b} {1:04b} | 0x{2:04X} {2:5d}</td>'.format(
                0xF & (photoc_ >> 4), 0xF & (photoc_ >> 0), photoc_)

            cp = 1 if m.status.get('container_presence') else 0
            html_ += '  <td>({}) {}</td>'.format(cp, m.status.get('status_level'))
            html_ += '  <td>{}</td>'.format(m.status.get('last_update'))

            html_ += f'  <td><a href="RESET@{n}">RESET</a></td>'
            html_ += f'  <td><a href="DIAGNOSTIC@{n}">DIAGNOSTIC</a></td>'

            html_ += '</tr>'

        html_ += '</table>'

        self.status_text_browser.setHtml(html_)

        # ~ logging.warning("")
