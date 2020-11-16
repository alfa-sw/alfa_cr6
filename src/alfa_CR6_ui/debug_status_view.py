# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=bad-continuation
# pylint: disable=protected-access


import os
import time
import logging
import traceback
import asyncio

from PyQt5.QtWidgets import (QApplication, QFrame,       # pylint: disable=no-name-in-module
                             # ~ QComboBox,
                             QTextBrowser, QButtonGroup, QPushButton)

from alfa_CR6_backend.models import Jar


class DebugStatusView():

    def __init__(self, parent):

        # ~ app = QApplication.instance()

        self.barcode_counter = 0

        self.main_frame = QFrame(parent=parent)
        # ~ self.main_frame.setGeometry(0, 0, 1800, 1000)

        self.status_text_browser = QTextBrowser(parent=self.main_frame)
        self.status_text_browser.setOpenLinks(False)
        # ~ self.status_text_browser.setFrameStyle(QFrame.Panel | QFrame.Raised)

        self.status_text_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: #FFFFF7;
                    font-size: 12px;
                    font-family: monospace;
                    }
                """)

        self.answer_text_browser = QTextBrowser(parent=self.main_frame)
        self.answer_text_browser.document().setMaximumBlockCount(500)

        self.answer_text_browser.setStyleSheet("""
                QTextBrowser {
                    background-color: #FFFFF7;
                    font-size: 16px;
                    font-family: monospace;
                    }
                """)

        self.buttons_frame = QFrame(parent=self.main_frame)
        self.buttons_frame.setStyleSheet("""
                QWidget {
                    color: #333366;
                    background-color: #FFFFF7;
                    font-size: 20px;
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
            b.setGeometry(20 + i * 152, 0, 150, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate([
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
            ('', '**'),
        ]):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 65, 150, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate([
            ('stop_all', 'stop movement for all heads'),
            ('complete', 'start the complete cycle through the system'),
            ('read\nbarcode', 'simulate a bar code read'),
            ('clear\njars', 'delete all the jars'),
            ('refresh', 'refresh the view'),
            ('LIFTR\nUP', 'send command UP to right lifter without waiting for any condition'),
            ('LIFTR\nDOWN', 'send command DOWN to right lifter without waiting for any condition'),
            ('LIFTL\nUP', 'send command UP to left lifter without waiting for any condition'),
            ('LIFTL\nDOWN', 'send command DOWN to left lifter without waiting for any condition'),
            # ~ ('kill\nemul', 'kill emulator'),
            # ~ ('run\ntest', '**'),
            ('reset jar\nstatuses', 'reset all jar_status to NEW'),
            ('clear\nanswers', 'clear answers'),
            ('close', 'close this widget'),
        ]):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 130, 150, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        # ~ self.cb = QComboBox(parent=self.buttons_frame)
        # ~ self.cb.setGeometry(20 + 8 * 152, 90, 200, 60)
        # ~ for name in app.MACHINE_HEAD_INDEX_TO_NAME_MAP.values():
            # ~ self.cb.addItem(name)

        width = 1880
        self.status_text_browser.setGeometry(20, 0, width, 600)
        self.buttons_frame.setGeometry(20, 600, width, 200)
        self.answer_text_browser.setGeometry(20, 800, width, 280)

        parent.main_window_stack.addWidget(self.main_frame)
        parent.main_window_stack.setCurrentWidget(self.main_frame)

        self.status_text_browser.anchorClicked.connect(self.status_text_browser_anchor_clicked)
        self.button_group.buttonClicked.connect(self.on_button_group_clicked)

    def add_answer(self, head_index, answer):

        app = QApplication.instance()
        answer = {k: answer[k] for k in ['status_code', 'error', 'command'] if answer.get(k) is not None}
        _ = f"<p>{ app.machine_head_dict[head_index].name }:{time.asctime()}:{ answer }</p>"
        self.answer_text_browser.append(_)

    def status_text_browser_anchor_clicked(self, url):       # pylint: disable=no-self-use

        app = QApplication.instance()
        named_map = {m.name: m for m in app.machine_head_dict.values()}

        logging.warning(f"url:{url.url()}")
        logging.warning(f"url.url().split('@'):{url.url().split('@')}")
        if url.url().split('@')[1:]:
            command, name = url.url().split('@')
            m = named_map[name]
            t = None
            if command == "DIAGNOSTIC":
                t = m.send_command(cmd_name="ENTER_DIAGNOSTIC", params={}, type_='command', channel='machine')
            elif command == "RESET":
                t = m.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
            elif command == "PIPES":
                t = m.update_pipes_and_packages()
            elif command == "DISP":
                t = m.do_dispense()
            if t is not None:
                asyncio.ensure_future(t)
        else:
            os.system("chromium-browser {} &".format(url.url()))

        self.update_status()

    async def reset_jar_status_to_new(self):   # pylint: disable=no-self-use

        app = QApplication.instance()
        for j in app.db_session.query(Jar).filter(Jar.status != 'NEW').all():
            logging.warning(f"j:{j}")
            j.status = 'NEW'
        app.db_session.commit()

    async def run_test(self):                   # pylint: disable=no-self-use

        app = QApplication.instance()

        F = app.get_machine_head_by_letter('F')

        for i in range(100):
            r = await F.wait_for_status_level(['STANDBY'], on=True, timeout=10)
            if r:
                r = await F.can_movement({'Output_Roller': 2})
            else:
                logging.error("timeout !")
            logging.warning(f"i:{i}, r:{r}")

    def on_button_group_clicked(self, btn):             # pylint: disable=no-self-use, too-many-branches

        app = QApplication.instance()
        cmd_txt = btn.text()

        # ~ logging.warning(f"cmd_txt:{cmd_txt}")

        if 'kill\nemul' in cmd_txt:

            m = app.machine_head_dict[0]
            t = m.send_command(cmd_name="KILL_EMULATOR", params={})
            asyncio.ensure_future(t)

        elif 'reset jar\nstatuses' in cmd_txt:

            t = self.reset_jar_status_to_new()
            asyncio.ensure_future(t)

        elif 'run\ntest' in cmd_txt:

            t = self.run_test()
            asyncio.ensure_future(t)

        elif 'LIFTR\nUP' in cmd_txt:

            t = app.single_move('D', {'Lifter': 1})
            asyncio.ensure_future(t)

        elif 'LIFTR\nDOWN' in cmd_txt:

            t = app.single_move('D', {'Lifter': 2})
            asyncio.ensure_future(t)

        elif 'LIFTL\nUP' in cmd_txt:

            t = app.single_move('F', {'Lifter': 1})
            asyncio.ensure_future(t)

        elif 'LIFTL\nDOWN' in cmd_txt:

            t = app.single_move('F', {'Lifter': 2})
            asyncio.ensure_future(t)

        elif 'refresh' in cmd_txt:
            self.update_status()

        elif 'clear\nanswers' in cmd_txt:
            self.answer_text_browser.setText("")
        elif 'close' in cmd_txt:
            # ~ app.main_window.main_window_stack.setCurrentIndex(0)
            app.main_window.main_window_stack.setCurrentWidget(app.main_window.project)

        elif 'clear\njars' in cmd_txt:

            for k in [_ for _ in app._CR6_application__jar_runners.keys()]:
                t = app._CR6_application__jar_runners[k]['task']
                try:
                    t.cancel()

                    async def _coro(_):
                        await _
                    asyncio.ensure_future(_coro(t))
                except asyncio.CancelledError:
                    logging.info(f"{ t } has been canceled now.")

        elif 'read\nbarcode' in cmd_txt:
            self.barcode_counter += 1
            app.run_a_coroutine_helper('on_barcode_read', 0, self.barcode_counter, skip_checks=True)

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

    def update_status(self, _=None):              # pylint: disable=too-many-locals,too-many-statements

        if not self.main_frame.isVisible():
            return

        app = QApplication.instance()

        named_map = {m.name: m for m in app.machine_head_dict.values()}
        names_ = named_map.keys()

        html_ = ''

        jar_size_detect = (
            app.machine_head_dict[0].status['jar_photocells_status'] & 0x200 +
            app.machine_head_dict[0].status['jar_photocells_status'] & 0x400) >> 4

        html_ += '<small>app ver.: {} - jar_size_detect:{}, 0x{:02X}</small>'.format(
            app.get_version(), app.machine_head_dict[0].jar_size_detect, jar_size_detect)
        html_ += '<p>0x{:02X} 0x{:02X}</p>'.format(
            app.machine_head_dict[0].status['jar_photocells_status'] & 0x200,
            app.machine_head_dict[0].status['jar_photocells_status'] & 0x400
        )

        html_ += '<table>'

        html_ += '<tr>                                           '

        html_ += """
        <td colspan="1">
        <br/># "jar photocells_status" mask bit coding:
        <br/> 0000 0000 0001  | 0x0001 # bit0: JAR_INPUT_ROLLER_PHOTOCELL
        <br/> 0000 0000 0010  | 0x0002 # bit1: JAR_LOAD_LIFTER_ROLLER_PHOTOCELL
        <br/> 0000 0000 0100  | 0x0004 # bit2: JAR_OUTPUT_ROLLER_PHOTOCELL
        <br/> 0000 0000 1000  | 0x0008 # bit3: LOAD_LIFTER_DOWN_PHOTOCELL
        <br/> 0000 0001 0000  | 0x0010 # bit4: LOAD_LIFTER_UP_PHOTOCELL
        <br/> 0000 0010 0000  | 0x0020 # bit5: UNLOAD_LIFTER_DOWN_PHOTOCELL
        <br/> 0000 0100 0000  | 0x0040 # bit6: UNLOAD_LIFTER_UP_PHOTOCELL
        <br/> 0000 1000 0000  | 0x0080 # bit7: JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL
        <br/> 0001 0000 0000  | 0x0100 # bit8: JAR_DISPENSING_POSITION_PHOTOCELL
        <br/> 0010 0000 0000  | 0x0200 # bit9: JAR_DETECTION_MICROSWITCH_1
        <br/> 0100 0000 0000  | 0x0400 # bit10:JAR_DETECTION_MICROSWITCH_2
        </td>
        """

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
        html_ += '<th align="left" width="20%" colspan="4">jar_photocells_status</th>'
        html_ += '<th align="left" width="16%">photocells_status</th>'
        html_ += '<th align="left" width="12%">(cp) level</th>'
        html_ += '<th align="left" width="8%">last update</th>'
        html_ += '<th align="left" width="12%"  colspan="4">commands</th>'
        html_ += '</tr>'

        for n in sorted(names_):

            m = named_map[n]
            ord_ = m.index + 1
            photoc_ = m.status.get('photocells_status', -1)
            jar_ph_ = m.status.get('jar_photocells_status', -1)

            html_ += '<tr>'

            html_ += '  <td>head {}</td>'.format(ord_)
            html_ += '  <td>{}</td>'.format(m.name)
            html_ += '  <td><a href="http://{0}:8080/admin"> {0} </a></td>'.format(m.ip_add)

            html_ += '  <td  bgcolor="#{}">{:04b}</td>'.format('FFFF00' if 0xF &
                                                               (jar_ph_ >> 8) else 'EEEEEE', 0xF & (jar_ph_ >> 8))
            html_ += '  <td  bgcolor="#{}">{:04b}</td>'.format('FFFF00' if 0xF &
                                                               (jar_ph_ >> 4) else 'EEEEEE', 0xF & (jar_ph_ >> 4))
            html_ += '  <td  bgcolor="#{}">{:04b}</td>'.format('FFFF00' if 0xF &
                                                               (jar_ph_ >> 0) else 'EEEEEE', 0xF & (jar_ph_ >> 0))
            html_ += '  <td>0x{0:04X}</td>'.format(jar_ph_)

            html_ += '  <td>        {0:04b} {1:04b} | 0x{2:04X} {2:5d}</td>'.format(
                0xF & (photoc_ >> 4), 0xF & (photoc_ >> 0), photoc_)

            cp = 1 if m.status.get('container_presence') else 0
            html_ += '  <td>({}) {}</td>'.format(cp, m.status.get('status_level'))

            l_u = m.status.get('last_update', '').split()
            if l_u[1:]:
                l_u = l_u[1]
            html_ += '  <td>{}</td>'.format(l_u)

            html_ += f'  <td bgcolor="#F0F0F0"><a href="RESET@{n}">RESET</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="DIAG@{n}" title="Enter diagnostic status">DIAG</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="PIPES@{n}" title="Update pipe info">PIPES</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="DISP@{n}" title="Send a dispense cmd">DISP</a></td>'

            html_ += '</tr>'

        html_ += '</table>'

        self.status_text_browser.setHtml(html_)

        # ~ logging.warning("")
