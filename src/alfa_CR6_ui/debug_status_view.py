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
# ~ import json

from PyQt5.QtWidgets import (QApplication, QFrame,       # pylint: disable=no-name-in-module
                             # ~ QComboBox,
                             QFileDialog,
                             QTextBrowser, QButtonGroup, QPushButton)

from alfa_CR6_backend.models import Jar, Order
from alfa_CR6_backend.dymo_printer import dymo_print


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
                    font-size: 16px;
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
            ('check\njar', 'check jar from barcode'),
            ('freeze\ncarousel', 'stop the movements of the jars, until unfreeze.'),
            ('unfreeze\ncarousel', 'restar the movements of the jars.'),
            ('stop_all', 'send a stop-movement cmd to all heads'),
            ('alert', 'test alert box'),
            ('', '**'),
            ('LIFTL\nUP', 'send command UP to left lifter without waiting for any condition'),
            ('LIFTL\nDOWN', 'send command DOWN to left lifter without waiting for any condition'),
            ('LIFTR\nUP', 'send command UP to right lifter without waiting for any condition'),
            ('LIFTR\nDOWN', 'send command DOWN to right lifter without waiting for any condition'),
            ('move_12_00', 'deliver jar'),
        ]):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 65, 150, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate([
            ('complete', 'start the complete cycle through the system'),
            ('refresh', 'refresh this view'),
            ('clear\njars', 'delete all the progressing jars'),
            ('clear\nanswers', 'clear answers'),
            ('reset jar\ndb status', 'reset all jar_status to NEW in db sqlite'),
            ('reset all\n heads', 'reset all heads'),
            ('EXIT', 'Beware! terminate the application'),
            ('read\nbarcode', 'simulate a bar code read'),
            ('delete\norders in db', 'delelete all jars and all orders in db sqlite'),
            ('open order\ndialog', '**'),
            ('view\norders', ''),
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

        async def periodic_refresh():
            while 1:
                self.update_status()
                await asyncio.sleep(1)
            return True

        t = periodic_refresh()
        asyncio.ensure_future(t)

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
            # ~ command, barcode = url.url().split('@')
            command, name = url.url().split('@')
            m = named_map[name]
            t = None
            if command == "CANCEL":
                barcode = name
                t = app._CR6_application__jar_runners[barcode]['task']
                try:
                    t.cancel()

                    async def _coro(_):
                        await _
                    asyncio.ensure_future(_coro(t))
                except asyncio.CancelledError:
                    logging.info(f"{ t } has been canceled now.")
            elif command == "DIAGNOSTIC":
                t = m.send_command(cmd_name="ENTER_DIAGNOSTIC", params={}, type_='command', channel='machine')
            elif command == "RESET":
                t = m.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
            elif command == "UPDATE":
                t = m.update_tintometer_data(invalidate_cache=True)
            elif command == "DISP":

                # BEWARE: force size to max
                t = self.dispense_coro(app, m, size=3)

            if t is not None:
                asyncio.ensure_future(t)
        else:
            os.system("chromium-browser {} &".format(url.url()))

        self.update_status()

    async def dispense_coro(self, app, m, size):

        app = QApplication.instance()
        A = app.machine_head_dict[0]
        A.jar_size_detect = size

        self.barcode_counter += 1
        jar, error = await app.get_and_check_jar_from_barcode(self.barcode_counter, skip_checks_for_dummy_read=True)
        logging.warning(f"jar:{jar}, error:{error}")
        r = None
        if jar:
            r = await m.do_dispense(jar)
        return r

    def reset_jar_status_to_new(self):   # pylint: disable=no-self-use

        app = QApplication.instance()
        for j in app.db_session.query(Jar).filter(Jar.status != 'NEW').all():
            logging.warning(f"j:{j}")
            j.status = 'NEW'
            j.position = '_'
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

    def view_jar_deatils(self, jar_id):             # pylint: disable=no-self-use, too-many-branches

        jar = app.db_session.query(Jar).filter(Jar == jar_id).one()

        logging.warning(f"jar:{jar}")
        logging.info(f"jar.json_properties:{jar.json_properties}")

    def delete_orders(self):             # pylint: disable=no-self-use, too-many-branches

        app = QApplication.instance()

        def delete_all_():
            for model in (Jar, Order):
                try:
                    num_rows_deleted = app.db_session.query(model).delete()
                    app.db_session.commit()
                    logging.warning(f"deleted {num_rows_deleted} {model}")
                except Exception as e:
                    logging.error(e)
                    app.db_session.rollback()

        app.show_alert_dialog(f'confirm deleting db data?', callback=delete_all_)

    def view_orders(self):             # pylint: disable=no-self-use, too-many-branches

        app = QApplication.instance()
        html_ = ""
        for j in app.db_session.query(Jar).all()[:100]:
            
            # ~ ingredient_volume_map, total_volume, unavailable_pigment_names = app.check_available_volumes(j)
            # ~ msg_2 = f"{ingredient_volume_map}, {total_volume}, {unavailable_pigment_names}"
            # ~ html_ += f'<p title="{msg_2}">{msg_1}</p>'
            msg_1 = f"j.barcode:{j.barcode} j:{j} "
            html_ += f'<p>{msg_1}</p>'

            logging.warning(msg_1)

        self.answer_text_browser.setHtml(html_)

    def on_button_group_clicked(self, btn):             # pylint: disable=no-self-use, too-many-branches

        app = QApplication.instance()
        cmd_txt = btn.text()

        # ~ logging.warning(f"cmd_txt:{cmd_txt}")

        if 'EXIT' in cmd_txt:
            os.system("kill -9 {}".format(os.getpid()))

        elif 'kill\nemul' in cmd_txt:

            m = app.machine_head_dict[0]
            t = m.send_command(cmd_name="KILL_EMULATOR", params={})
            asyncio.ensure_future(t)

        elif 'reset all\n heads' in cmd_txt:

            for m in app.machine_head_dict.values():
                t = m.send_command(cmd_name="RESET", params={'mode': 0}, type_='command', channel='machine')
                asyncio.ensure_future(t)

        elif 'open order\ndialog' in cmd_txt:

            self.open_order_dialog()

        elif 'delete all\norders from db' in cmd_txt:

            self.delete_orders()

        elif 'view\norders' in cmd_txt:

            self.view_orders()

        elif cmd_txt == 'alert':

            def cb():
                logging.warning(f"callback called!")
                
            r = app.show_alert_dialog("test alert message", callback=cb)
            logging.warning(f"r:{r}")

        elif cmd_txt == 'unfreeze\ncarousel':

            app.freeze_carousel(False)

        elif cmd_txt == 'freeze\ncarousel':

            app.freeze_carousel(True)

        elif 'reset jar\ndb status' in cmd_txt:

            self.reset_jar_status_to_new()

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
            # ~ self.update_status()
            pass

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
            app.run_a_coroutine_helper('on_barcode_read', 0, self.barcode_counter, skip_checks_for_dummy_read=True)

        elif 'check\njar' in cmd_txt:
            self.barcode_counter += 1
            app.run_a_coroutine_helper(
                'get_and_check_jar_from_barcode',
                self.barcode_counter,
                skip_checks_for_dummy_read=True)

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

        self.update_status()

    def update_status(self, _=None):              # pylint: disable=too-many-locals,too-many-statements

        if not self.main_frame.isVisible():
            return

        app = QApplication.instance()

        named_map = {m.name: m for m in app.machine_head_dict.values()}
        names_ = named_map.keys()

        html_ = ''

        s1 = app.machine_head_dict[0].status.get('jar_photocells_status', 0) & 0x200
        s2 = app.machine_head_dict[0].status.get('jar_photocells_status', 0) & 0x400
        jar_size_detect = int(s1 + s2) >> 9

        html_ += '<small>app ver.: {} - jar_size_detect:{}, 0x{:02X} [{}]</small>'.format(
            app.get_version(), app.machine_head_dict[0].jar_size_detect, jar_size_detect, time.asctime())

        html_ += '<p>'
        if app.carousel_frozen:
            html_ += '<b color="#EE0000">carousel_frozen:{}</b>'.format(app.carousel_frozen)
        else:
            html_ += '<b color="#00EE00">carousel_frozen:{}</b>'.format(app.carousel_frozen)
        html_ += ' - mirco: 0x{:02X} 0x{:02X}'.format(s1, s2)
        html_ += '</p>'

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
            html_ += '<p  bgcolor="#F0F0F0">{}:{} {}<a href="CANCEL@{}" title="cancel this jar">CANCEL</a></p>'.format(
                i, j['jar'], j['jar'].description, j['jar'].barcode)

        html_ += '</td>'

        html_ += '</tr>'
        html_ += '</table>'

        html_ += '<hr></hr>'

        html_ += '<table width="100%" aligbcellpadding="80px" cellspacing="80px">'

        html_ += '<tr bgcolor="#FFFFFF">'
        html_ += '<th align="left" width="5%">ord.</th>'
        html_ += '<th align="left" width="9%">name</th>'
        html_ += '<th align="left" width="8%">addr</th>'
        html_ += '<th align="left" width="20%" colspan="4">jar_photocells_status</th>'
        html_ += '<th align="left" width="16%">photocells_status</th>'
        html_ += '<th align="left" width="14%">(cp) level (cs)</th>'
        html_ += '<th align="left" width="8%">last update</th>'
        html_ += '<th align="left" width="16%"  colspan="4">commands</th>'
        html_ += '</tr>'

        for n in sorted(names_):

            m = named_map[n]
            ord_ = m.index + 1
            photoc_ = m.status.get('photocells_status', -1)
            jar_ph_ = m.status.get('jar_photocells_status', -1)

            html_ += '<tr>'

            html_ += '  <td>head {}</td>'.format(ord_)

            if m.low_level_pipes:
                html_ += '  <td bgcolor="#FF9999">{}</td>'.format(m.name)
            else:
                html_ += '  <td>{}</td>'.format(m.name)

            html_ += '  <td><a href="http://{0}:8080/admin"> {0} </a></td>'.format(m.ip_add)

            html_ += '  <td bgcolor="#{}">{:04b}</td>'.format('FFFF00' if 0xF &
                                                              (jar_ph_ >> 8) else 'EEEEEE', 0xF & (jar_ph_ >> 8))
            html_ += '  <td bgcolor="#{}">{:04b}</td>'.format('FFFF00' if 0xF &
                                                              (jar_ph_ >> 4) else 'EEEEEE', 0xF & (jar_ph_ >> 4))
            html_ += '  <td bgcolor="#{}">{:04b}</td>'.format('FFFF00' if 0xF &
                                                              (jar_ph_ >> 0) else 'EEEEEE', 0xF & (jar_ph_ >> 0))
            html_ += '  <td>0x{0:04X}</td>'.format(jar_ph_)

            html_ += '  <td>        {0:04b} {1:04b} | 0x{2:04X} {2:5d}</td>'.format(
                0xF & (photoc_ >> 4), 0xF & (photoc_ >> 0), photoc_)

            cp = 1 if m.status.get('container_presence') else 0
            cs = m.status.get('cycle_step')
            html_ += '  <td>({}) {} ({})</td>'.format(cp, m.status.get('status_level'), cs)

            l_u = m.status.get('last_update', '').split()
            if l_u[1:]:
                l_u = l_u[1]
            html_ += '  <td>{}</td>'.format(l_u)

            html_ += f'  <td bgcolor="#F0F0F0"><a href="RESET@{n}">RESET</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="DIAG@{n}" title="Enter diagnostic status">DIAG</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="UPDATE@{n}" title="Update machine data cache">UPDATE</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="DISP@{n}" title="call do_dispense()">DISP</a></td>'

            html_ += '</tr>'

        html_ += '</table>'

        self.status_text_browser.setHtml(html_)

        # ~ logging.warning("")
    def open_order_dialog(self):

        app = QApplication.instance()
        

        dialog = QFileDialog(self.main_frame)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setDirectory('/opt/alfa_cr6/data/')
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setNameFilter("json order file (*.json)")
        dialog.setViewMode(QFileDialog.Detail)
        dialog.resize(1200, 600)
        fileNames = None
        if dialog.exec_():
            fileNames = dialog.selectedFiles();
        logging.warning(f"fileNames:{fileNames}")
        return
        
        
        fname, filter = QFileDialog.getOpenFileName(self.main_frame, 'Open file', '/opt/alfa_cr6/data/',"json order file (*.json)", options=QFileDialog.DontUseNativeDialog)
        logging.warning(f"fname:{fname}, filter:{filter}")
        if fname:
            order = None
            try:
                order = app.create_order(fname, n_of_jars=3)
                barcodes = [str(j.barcode) for j in order.jars]
                barcodes.sort()
                barcodes_str = '\n'.join([str(j.barcode) for j in order.jars])
                
                def cb():
                    for b in barcodes:
                        def cb_(bc):
                            response = dymo_print(str(bc))
                            logging.warning(f"response:{response}")

                        msg_ = f"confirm printing:{b} ?"
                        app.show_alert_dialog(msg_, callback=cb_, args=[b])

                msg_ = f"creted order with {len(order.jars)} jars. barcodes:\n{barcodes_str} \nclick 'OK' to print barcodes."
                app.show_alert_dialog(msg_, callback=cb)

            except Exception as e:
                logging.error(traceback.format_exc())

        return fname
