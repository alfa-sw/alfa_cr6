# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=protected-access
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import time
import logging
import traceback
import asyncio

import aiohttp  # pylint: disable=import-error

# ~ import json

from PyQt5.QtWidgets import (     # pylint: disable=no-name-in-module
    QApplication,
    QFrame,
    QFileDialog,
    QTextBrowser,
    QButtonGroup,
    QPushButton)

from alfa_CR6_backend.models import Jar, Order
from alfa_CR6_backend.dymo_printer import dymo_print
from alfa_CR6_backend.globals import tr_, set_language, LANGUAGE_MAP
from alfa_CR6_backend.base_application import download_KCC_specific_gravity_lot

def simulate_read_barcode(allowed_jar_statuses=("NEW", "DONE")):

    app = QApplication.instance()

    # ~ q = app.db_session.query(Jar).filter(Jar.status.in_(("NEW", "DONE")))
    q = app.db_session.query(Jar).filter(Jar.status.in_(allowed_jar_statuses))
    q = q.filter(Jar.position != "DELETED").order_by(Jar.date_created)
    jar = q.first()

    async def set_JAR_INPUT_ROLLER_PHOTOCELL_bit(on_off):
        # set JAR_INPUT_ROLLER_PHOTOCELL bit
        sts_ = app.machine_head_dict[0].status.copy()

        if on_off:
            sts_["jar_photocells_status"] = sts_ .get("jar_photocells_status", 0) | 0x01
        else:
            sts_["jar_photocells_status"] = sts_.get("jar_photocells_status", 0) & ~ 0x01

        await app.machine_head_dict[0].update_status(sts_)
        await app.on_head_msg_received(
            head_index=0, msg_dict={"type": "device:machine:status", "value": sts_})

    if jar:
        async def coro():
            await set_JAR_INPUT_ROLLER_PHOTOCELL_bit(True) # set JAR_INPUT_ROLLER_PHOTOCELL bit
            barcode = await app.on_barcode_read(jar.barcode)
            if barcode is None:
                await set_JAR_INPUT_ROLLER_PHOTOCELL_bit(False) # reset JAR_INPUT_ROLLER_PHOTOCELL bit

        t = coro()
        asyncio.ensure_future(t)
    else:
        app.main_window.open_alert_dialog(f"cant find a valid can in db (not DELETED and with status in {allowed_jar_statuses})")




class DebugPage:

    def __init__(self, parent):

        # ~ app = QApplication.instance()

        self.barcode_counter = 0

        self.main_frame = QFrame(parent=parent)
        self.main_frame.setStyleSheet("""
                QWidget {
                    font-size: 16px;
                    font-family: monospace;
                    }
                """)

        self.status_text_browser = QTextBrowser(parent=self.main_frame)
        self.status_text_browser.setOpenLinks(False)

        self.answer_text_browser = QTextBrowser(parent=self.main_frame)
        self.answer_text_browser.document().setMaximumBlockCount(5000)
        self.status_text_browser.setOpenLinks(False)

        self.buttons_frame = QFrame(parent=self.main_frame)
        self.button_group = QButtonGroup(parent=self.buttons_frame)
        for i, n in enumerate(
            [
                ("move_00_01", "feed to IN"),
                ("move_01_02", "IN -> A"),
                ("move_02_03", "A -> B"),
                ("move_03_04", "B -> C"),
                ("move_04_05", "C -> UP"),
                ("move_05_06", "UP -> DOWN"),
                ("move_06_07", "DOWN -> D"),
                ("move_07_08", "D -> E"),
                ("move_08_09", "E -> F"),
                ("move_09_10", "F -> DOWN"),
                ("move_10_11", "DOWN -> UP"),
                ("move_11_12", "UP -> OUT"),
            ]
        ):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 0, 150, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate(
            [
                # ~ ("check\njar", "check jar from barcode"),
                ("download KCC\nSpecific\nGravity file", "download KCC file with specific gravity lot info"),
                ("freeze\ncarousel", "stop the movements of the jars, until unfreeze."),
                ("unfreeze\ncarousel", "restar the movements of the jars."),
                ("stop_all", "send a stop-movement cmd to all heads"),
                ("alert", "test alert box"),
                ("", "**"),
                # ~ (
                # ~ "LIFTL\nUP",
                # ~ "send command UP to left lifter without waiting for any condition",
                # ~ ),
                # ~ (
                # ~ "LIFTL\nDOWN",
                # ~ "send command DOWN to left lifter without waiting for any condition",
                # ~ ),
                # ~ (
                # ~ "LIFTR\nUP",
                # ~ "send command UP to right lifter without waiting for any condition",
                # ~ ),
                # ~ (
                # ~ "LIFTR\nDOWN",
                # ~ "send command DOWN to right lifter without waiting for any condition",
                # ~ ),
                ("", "**"),
                ("minimize\nmain window", ""),
                ("open URL\nin text bar", "open the URL in text bar at bottom."),
                ("open admin\npage", "."),
                ("move_12_00", "deliver jar"),
            ]
        ):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 65, 150, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        for i, n in enumerate(
            [
                ("run a complete\ncycle", "start the complete cycle through the system"),
                ("refresh", "refresh this view"),
                ("clear\njars", "delete all the progressing jars"),
                ("clear\nanswers", "clear answers"),
                ("reset jar\ndb status", "reset all jar_status to NEW in db sqlite"),
                ("reset all\n heads", "reset all heads"),
                ("EXIT", "Beware! terminate the application"),
                ("ALARM", "simulate ALARM"),
                ("read\nbarcode", "simulate a bar code read"),
                (
                    "delete\norders in db",
                    "delelete all jars and all orders in db sqlite",
                ),
                ("open order\ndialog", "**"),
                ("view\norders", ""),
                ("close", "close this widget"),
            ]
        ):

            b = QPushButton(n[0], parent=self.buttons_frame)
            b.setGeometry(20 + i * 152, 130, 150, 60)
            b.setToolTip(n[1])
            self.button_group.addButton(b)

        width = 1880
        self.status_text_browser.setGeometry(20, 2, width, 592)
        self.buttons_frame.setGeometry(20, 598, width, 200)
        self.answer_text_browser.setGeometry(20, 794, width, 200)

        self.status_text_browser.anchorClicked.connect(
            self.status_text_browser_anchor_clicked
        )
        self.answer_text_browser.anchorClicked.connect(
            self.answer_text_browser_anchor_clicked
        )
        self.button_group.buttonClicked.connect(self.on_button_group_clicked)

        async def periodic_refresh():
            while True:
                self.update_status()
                await asyncio.sleep(1)
            return True

        t = periodic_refresh()
        asyncio.ensure_future(t)

    def add_answer(self, head_index, answer):

        app = QApplication.instance()
        answer = {
            k: answer[k]
            for k in ["status_code", "error", "command"]
            if answer.get(k) is not None
        }
        _ = f"<p>{ app.machine_head_dict[head_index].name }:{time.asctime()}:{ answer }</p>"
        self.answer_text_browser.append(_)

    def answer_text_browser_anchor_clicked(self, url):  # pylint: disable=no-self-use

        # ~ app = QApplication.instance()

        logging.warning(f"url:{url.url()}")
        logging.warning(f"url.url().split('@'):{url.url().split('@')}")

        if url.url().split("@")[1:]:
            command, jar_id = url.url().split("@")
            if command == "SHOW_DETAILS":
                self.view_jar_deatils(jar_id)

    def status_text_browser_anchor_clicked(self, url):  # pylint: disable=no-self-use

        app = QApplication.instance()
        named_map = {m.name: m for m in app.machine_head_dict.values() if m}

        logging.warning(f"url:{url.url()}")
        logging.warning(f"url.url().split('@'):{url.url().split('@')}")

        if url.url().split("@")[1:]:
            # ~ command, barcode = url.url().split('@')
            command, name = url.url().split("@")
            m = named_map.get(name)
            t = None
            if command == "CANCEL":
                barcode = int(name)
                app.delete_jar_runner(barcode)
            elif command == "LOTINFO" and m:

                _ = self._show_KCC_specific_gravity_info(m)
                asyncio.ensure_future(_)

            elif command == "DIAGNOSTIC" and m:
                t = m.send_command(
                    cmd_name="ENTER_DIAGNOSTIC",
                    params={},
                    type_="command",
                    channel="machine",
                )
            elif command == "RESET" and m:
                t = m.send_command(
                    cmd_name="RESET",
                    params={"mode": 0},
                    type_="command",
                    channel="machine",
                )
            elif command == "UPDATE" and m:
                t = m.update_tintometer_data()

            elif command == "LANG":
                def ok_cb_(_lang):
                    logging.warning(f"_lang:{ _lang }")
                    set_language(_lang)
                lang_ = name
                msg_ = tr_("confirm changing language to: {}? \n (WARN: application will be restarted)").format(lang_)
                QApplication.instance().main_window.open_input_dialog(message=msg_, ok_cb=ok_cb_, ok_cb_args=[lang_, ])

            if t is not None:
                asyncio.ensure_future(t)
        else:
            os.system("chromium-browser {} &".format(url.url()))

        self.update_status()

    def reset_jar_status_to_new(self):  # pylint: disable=no-self-use

        app = QApplication.instance()
        for j in app.db_session.query(Jar).filter(Jar.position != "DELETED").all():
            logging.warning(f"j:{j}")
            j.status = "NEW"
            j.position = "_"
            j.json_properties = "{}"
        app.db_session.commit()

    async def run_test(self):  # pylint: disable=no-self-use

        app = QApplication.instance()

        F = app.get_machine_head_by_letter("F")

        for i in range(100):
            r = await F.wait_for_status_level(["STANDBY"], on=True, timeout=10)
            if r:
                r = await F.can_movement({"Output_Roller": 2})
            else:
                logging.error("timeout !")
            logging.warning(f"i:{i}, r:{r}")

    def view_jar_deatils(self, jar_id):  # pylint: disable=no-self-use, too-many-branches

        app = QApplication.instance()

        jar = app.db_session.query(Jar).filter(Jar.id == jar_id).one()
        logging.warning(f"jar:{jar}")
        logging.info(f"jar.json_properties:{jar.json_properties}")

        # ~ msg_ = "<html>"
        # ~ msg_ += f"jar.json_properties:{jar.json_properties}"
        # ~ msg_ += "<br></br>"
        # ~ msg_ += f"jar.order.json_properties:{jar.order.json_properties}"
        # ~ msg_ += "</html>"
        msg_ = ""
        msg_ += f"jar.json_properties:{jar.json_properties}"
        msg_ += "\n"
        msg_ += f"jar.order.json_properties:{jar.order.json_properties}"

        app.main_window.open_input_dialog(message=f"jar:{jar}", content=msg_)

    def delete_orders(self):  # pylint: disable=no-self-use, too-many-branches

        app = QApplication.instance()

        def delete_all_():
            for model in (Jar, Order):
                try:
                    num_rows_deleted = app.db_session.query(model).delete()
                    app.db_session.commit()
                    logging.warning(f"deleted {num_rows_deleted} {model}")
                except Exception as e:  # pylint: disable=broad-except
                    logging.error(e)
                    app.db_session.rollback()

        app.main_window.open_alert_dialog(
            "confirm deleting db data?", callback=delete_all_)

    def view_orders(self):  # pylint: disable=no-self-use, too-many-branches

        app = QApplication.instance()
        html_ = ""
        for j in app.db_session.query(Jar).all()[:100]:

            msg_1 = f"j.barcode:{j.barcode} j:{j} "
            html_ += f'<p><a href="SHOW_DETAILS@{j.id}">{msg_1}</a></p>'

            logging.warning(msg_1)

        self.answer_text_browser.setHtml(html_)

    def on_button_group_clicked(self, btn):  # pylint: disable=no-self-use, too-many-branches, too-many-statements

        app = QApplication.instance()
        cmd_txt = btn.text()

        # ~ logging.warning(f"cmd_txt:{cmd_txt}")

        if "EXIT" in cmd_txt:
            os.system("kill -9 {}".format(os.getpid()))

        elif "kill\nemul" in cmd_txt:

            m = app.machine_head_dict[0]
            t = m.send_command(cmd_name="KILL_EMULATOR", params={})
            asyncio.ensure_future(t)

        elif "ALARM" in cmd_txt:

            m = app.machine_head_dict[0]
            t = m.send_command(cmd_name="SIMULATE_ALARM", params={})
            asyncio.ensure_future(t)

        elif "reset all\n heads" in cmd_txt:

            for m in app.machine_head_dict.values():
                if m:
                    t = m.send_command(
                        cmd_name="RESET",
                        params={"mode": 0},
                        type_="command",
                        channel="machine",
                    )
                    asyncio.ensure_future(t)

        elif "open order\ndialog" in cmd_txt:

            self.open_order_dialog()

        elif "delete\norders in db" in cmd_txt:

            self.delete_orders()

        elif "view\norders" in cmd_txt:

            self.view_orders()

        elif cmd_txt == "alert":

            def cb():
                msg_ = "실차색상 배합입니다. (희석10%, 2회도장) 서페이서 V-1 적용색상입니다. 리피니쉬 벨류쉐이드 가이드 주소안내"
                app.main_window.open_alert_dialog(msg_, callback=None)
                logging.warning(f"msg_:{msg_}")

            msg_ = tr_("test alert message")
            r = app.main_window.open_alert_dialog(msg_, callback=cb)
            logging.warning(f"r:{r}")

        elif cmd_txt == "unfreeze\ncarousel":

            app.freeze_carousel(False)

        elif cmd_txt == "freeze\ncarousel":

            app.freeze_carousel(True)

        elif "reset jar\ndb status" in cmd_txt:

            self.reset_jar_status_to_new()

        elif "run\ntest" in cmd_txt:

            t = self.run_test()
            asyncio.ensure_future(t)

        # ~ elif "LIFTR\nUP" in cmd_txt:

            # ~ t = app.single_move("D", {"Lifter": 1})
            # ~ asyncio.ensure_future(t)

        # ~ elif "LIFTR\nDOWN" in cmd_txt:

            # ~ t = app.single_move("D", {"Lifter": 2})
            # ~ asyncio.ensure_future(t)

        # ~ elif "LIFTL\nUP" in cmd_txt:

            # ~ t = app.single_move("F", {"Lifter": 1})
            # ~ asyncio.ensure_future(t)

        # ~ elif "LIFTL\nDOWN" in cmd_txt:

            # ~ t = app.single_move("F", {"Lifter": 2})
            # ~ asyncio.ensure_future(t)

        elif "refresh" in cmd_txt:
            # ~ self.update_status()
            pass

        elif "clear\nanswers" in cmd_txt:
            self.answer_text_browser.setText("")

        elif "close" in cmd_txt:
            app.main_window.home_page.open_page()

        elif "clear\njars" in cmd_txt:

            for k in list(app.get_jar_runners().keys()):
                app.delete_jar_runner(int(k))

        elif "read\nbarcode" in cmd_txt:

            simulate_read_barcode()

        elif "run a complete\ncycle" in cmd_txt:

            async def coro():
                ret_vals = []
                for i in [
                    "move_01_02",
                    "move_02_03",
                    "move_03_04",
                    "move_04_05",
                    "move_05_06",
                    "move_06_07",
                    "move_07_08",
                    "move_08_09",
                    "move_09_10",
                    "move_10_11",
                    "move_11_12",
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
            except BaseException:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        elif "open admin\npage" in cmd_txt:
            url_ = 'http://127.0.0.1:8090/'
            app.main_window.webengine_page.open_page(url_)

        elif "open URL\nin text bar" in cmd_txt:
            url_ = app.main_window.menu_line_edit.text()
            app.main_window.webengine_page.open_page(url_)

        elif "download KCC\nSpecific\nGravity file" in cmd_txt:
            t = self._download_KCC_lot_info_file()
            asyncio.ensure_future(t)

        elif "minimize\nmain window" in cmd_txt:
            app.main_window.showMinimized()

        else:
            app.run_a_coroutine_helper(cmd_txt)

        self.update_status()

    def update_status(self, _=None):  # pylint: disable=too-many-locals,too-many-statements

        if not self.main_frame.isVisible():
            return

        app = QApplication.instance()

        named_map = {m.name: m for m in app.machine_head_dict.values() if m}
        names_ = named_map.keys()

        html_ = ""

        s1 = app.machine_head_dict[0].status.get("jar_photocells_status", 0) & 0x200
        s2 = app.machine_head_dict[0].status.get("jar_photocells_status", 0) & 0x400
        jar_size_detect = int(s1 + s2) >> 9

        html_ += "<small>app ver.: {} - jar_size_detect:{}, 0x{:02X} ready_to_read_a_barcode:{} [{}]</small>".format(
            app.get_version(),
            app.machine_head_dict[0].jar_size_detect,
            jar_size_detect,
            app.ready_to_read_a_barcode,
            time.asctime(),
        )

        html_ += "<p>"
        if app.carousel_frozen:
            html_ += '<b style="color:#AA0000;">carousel_frozen:{}</b>'.format(app.carousel_frozen)
        else:
            html_ += '<b style="color:#00AA00;">carousel_frozen:{}</b>'.format(app.carousel_frozen)
        html_ += " - mirco: 0x{:02X} 0x{:02X}".format(s1, s2)

        html_ += "</p><p>"

        # ~ html_ += """ <b>Change Language to: </b> """
        # ~ html_ += """ <a href="LANG@en">ENGLISH</a> - """
        # ~ html_ += """ <a href="LANG@it">ITALIAN</a> - """
        # ~ html_ += """ <a href="LANG@kr">KOREAN</a> - """
        # ~ html_ += """ <a href="LANG@de">GERMAN</a> """
        html_ += """ <b>Change Language to: </b> """
        for k, v in LANGUAGE_MAP.items():
            html_ += f""" <a href="LANG@{v}">{k.upper()}</a> - """

        html_ += "</p>"
        html_ += "</p>"

        html_ += "<table>"

        html_ += "<tr>                                           "

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
        html_ += "<br/># progressing_jars:"
        l_ = list(app.get_jar_runners().values())
        l_.reverse()
        for i, j in enumerate(l_):
            html_ += '<p  bgcolor="#F0F0F0">{}:{} {}<a href="CANCEL@{}" title="cancel this jar"> <span style="font-size:20px"><b>CANCEL</b></span> </a></p>'.format(
                i, j.get("jar"), j.get("jar") and j["jar"].description, j.get("jar") and j["jar"].barcode)

        html_ += "</td>"

        html_ += "</tr>"
        html_ += "</table>"

        html_ += "<hr></hr>"

        html_ += '<table width="100%" cellpadding="0" cellspacing="8">'

        html_ += '<tr bgcolor="#FFFFFF">'
        html_ += '<th align="left" width="5%">ord.</th>'
        html_ += '<th align="left" width="9%">name</th>'
        html_ += '<th align="left" width="8%">addr</th>'
        html_ += '<th align="left" width="20%" colspan="4">jar_photocells_status</th>'
        # ~ html_ += '<th align="left" width="16%">photocells_status</th>'
        html_ += '<th align="left" width="16%">crx_outputs</th>'
        html_ += '<th align="left" width="14%">(cp) level (cs)</th>'
        html_ += '<th align="left" width="8%">last update</th>'
        html_ += '<th align="left" width="16%"  colspan="4">commands</th>'
        html_ += "</tr>"

        for n in sorted(names_):

            m = named_map[n]
            ord_ = m.index + 1
            # ~ photoc_ = m.status.get("photocells_status", -1)
            crx_outputs = m.status.get('crx_outputs_status', -1)
            jar_ph_ = m.status.get("jar_photocells_status", -1)

            html_ += "<tr>"

            html_ += "  <td>head {}</td>".format(ord_)

            if m.low_level_pipes:
                html_ += '  <td bgcolor="#FF9999">{}</td>'.format(m.name)
            else:
                html_ += "  <td>{}</td>".format(m.name)

            html_ += '  <td><a href="http://{0}:8080/admin"> {0} </a></td>'.format(
                m.ip_add
            )

            html_ += '  <td bgcolor="#{}">{:04b}</td>'.format(
                "FFFF00" if 0xF & (jar_ph_ >> 8) else "EEEEEE", 0xF & (jar_ph_ >> 8)
            )
            html_ += '  <td bgcolor="#{}">{:04b}</td>'.format(
                "FFFF00" if 0xF & (jar_ph_ >> 4) else "EEEEEE", 0xF & (jar_ph_ >> 4)
            )
            html_ += '  <td bgcolor="#{}">{:04b}</td>'.format(
                "FFFF00" if 0xF & (jar_ph_ >> 0) else "EEEEEE", 0xF & (jar_ph_ >> 0)
            )
            html_ += "  <td>0x{0:04X}</td>".format(jar_ph_)

            # ~ html_ += "  <td>        {0:04b} {1:04b} | 0x{2:04X} {2:5d}</td>".format(
            # ~ 0xF & (photoc_ >> 4), 0xF & (photoc_ >> 0), photoc_
            # ~ )
            html_ += "  <td>        {0:04b} {1:04b} | 0x{2:02X} {2:5d}</td>".format(
                0xF & (crx_outputs >> 4), 0xF & (crx_outputs >> 0), crx_outputs
            )

            cp = 1 if m.status.get("container_presence") else 0
            cs = m.status.get("cycle_step")
            html_ += "  <td>({}) {} ({})</td>".format(
                cp, m.status.get("status_level"), cs
            )

            l_u = m.status.get("last_update", "").split()
            if l_u[1:]:
                l_u = l_u[1]
            html_ += "  <td>{}</td>".format(l_u)

            html_ += f'  <td bgcolor="#F0F0F0"><a href="RESET@{n}">RESET</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="LOTINFO@{n}" title="show KCC specific gravity info">LOTINFO</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="UPDATE@{n}" title="Update machine data cache">UPDATE</a></td>'
            html_ += f'  <td bgcolor="#F0F0F0"><a href="DIAG@{n}" title="Enter diagnostic status">DIAG</a></td>'
            # ~ html_ += f'  <td bgcolor="#F0F0F0"><a href="DISP@{n}" title="call do_dispense()">DISP</a></td>'

            html_ += "</tr>"

        html_ += "</table>"

        self.status_text_browser.setHtml(html_)

    def open_order_dialog(self):

        app = QApplication.instance()

        dialog = QFileDialog(self.main_frame)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setDirectory("/opt/alfa_cr6/data/")
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter("json order file (*.json)")
        dialog.setViewMode(QFileDialog.Detail)
        dialog.resize(1200, 600)
        fileNames = []
        if dialog.exec_():
            fileNames = dialog.selectedFiles()
        logging.warning(f"fileNames:{fileNames}")

        def cb_(bc):
            response = dymo_print(str(bc))
            logging.warning(f"response:{response}")

        def cb(barcodes_):
            for b in barcodes_:
                msg_ = f"confirm printing:{b} ?"
                app.main_window.open_alert_dialog(msg_, callback=cb_, args=[b])

        for fname in fileNames:
            order = None
            try:
                order = app.create_order(fname, n_of_jars=6)
                barcodes = sorted([str(j.barcode) for j in order.jars])
                barcodes_str = "\n".join([str(j.barcode) for j in order.jars])

                msg_ = f"created order with {len(order.jars)} jars. barcodes:\n{barcodes_str} \nclick 'OK' to print barcodes."
                app.main_window.open_alert_dialog(msg_, callback=cb, args=[barcodes])

            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        return fileNames


    async def _download_KCC_lot_info_file(self):  # pylint: disable=no-self-use

        msg_ = tr_("downloading KCC Specific Gravity file.")
        QApplication.instance().main_window.open_alert_dialog(msg_)

        try:
            ret = await download_KCC_specific_gravity_lot(force_download=True, force_file_xfert=True)

            msg_ = tr_("KCC Specific Gravity file downloaded.")
            if not ret:
                msg_ = tr_("KCC Specific Gravity file NOT downloaded.")

            QApplication.instance().main_window.open_alert_dialog(msg_)

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    async def _show_KCC_specific_gravity_info(self, machine_head):  # pylint: disable=no-self-use

        logging.warning(f"machine_head:{machine_head}")

        try:

            async with aiohttp.ClientSession() as aiohttp_session:


                params = {'data_set_name': 'kcc_lot_specific_info'}
                async with aiohttp_session.get(f'http://{machine_head.ip_add}:{machine_head.http_port}/admin/download', params=params) as resp:
                    resp_json = await resp.json()
                    assert resp.ok, f"failure downloading from:{machine_head.ip_add}:{machine_head.http_port}"

                    logging.warning(f"resp_json({type(resp_json)}):{resp_json}"[:500])

                    html_ = "\n<body>"
                    html_ += f'\n<h3>head {machine_head.index + 1}:{machine_head.name}</h3>'
                    html_ += '\n  <table border="0" cellspacing="0" cellpadding="2">'
                    for n, i in enumerate(resp_json):
                        if n == 0:
                            html_ += f'\n    <tr bgcolor="#FFFFAA">'
                            for v in i.values():
                                html_ += f'<th>{v}</th>'
                            html_ += "</tr>"
                        else:
                            bgcol = "#DDDDFF" if n%2 else "#EEEEEE"
                            html_ += f'\n    <tr bgcolor="{bgcol}">'
                            for v in i.values():
                                # ~ if v:
                                    html_ += f'<td>{v}</td>'
                            html_ += "</tr>"
                    html_ += "\n  </table>\n"
                    html_ += "\n</body>\n"

                    # ~ html_ = ""
                    # ~ for n, i in enumerate(resp_json):
                        # ~ if n%2:
                            # ~ html_ += '<p color="#AAAAEE">'
                        # ~ else:
                            # ~ html_ += '<p color="#AAEEAA">'
                        # ~ for v in i.values():
                            # ~ if v:
                                # ~ html_ += f"{v}, "
                        # ~ html_ += "</p>\n"
                    # ~ html_ += ""

                    logging.warning(f"html_:{html_}")

                    self.answer_text_browser.setHtml(html_)

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            # ~ QApplication.instance().main_window.open_alert_dialog(f"{e}")
