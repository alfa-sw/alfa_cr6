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
            'StopAll',
        ]):

            b = QPushButton(n, parent=self.buttons_frame)
            b.setGeometry(20 + i * 144, 0, 140, 60)
            self.button_group.addButton(b)

        for i, n in enumerate([
            'reset_tasks',
            '*',
            '*',
            '*',
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
        # ~ logging.warning(f"{btn}")
        
        # ~ if 'reset_tasks' in btn.text():
            # ~ app = QApplication.instance()
            # ~ app.reset_tasks()
        # ~ else:
            try:
                t = self.move_task(btn.text())
                # ~ logging.warning(f"{t}")
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

        try:

            # ~ app = self
            app = QApplication.instance()

            A = app.get_machine_head_by_letter('A')
            B = app.get_machine_head_by_letter('B')
            C = app.get_machine_head_by_letter('C')
            D = app.get_machine_head_by_letter('D')
            E = app.get_machine_head_by_letter('E')
            F = app.get_machine_head_by_letter('F')

            logging.warning(f"cmd_string:{cmd_string}")
            if '01-02' in cmd_string:  # ->A

                # ~ await app.wait_for_condition(A.input_roller_busy)
                # ~ await app.wait_for_condition(A.dispense_position_available)
                await A.can_movement({'Input_Roller': 1, 'Dispensing_Roller': 2})
                await app.wait_for_condition(A.dispense_position_busy)

            if '02-03' in cmd_string:  # A->B

                await app.wait_for_condition(B.dispense_position_available)
                await A.can_movement({'Dispensing_Roller': 1, 'Input_Roller': 1})
                await B.can_movement({'Dispensing_Roller': 2})
                await app.wait_for_condition(B.dispense_position_busy)
                await A.can_movement()

            if '03-04' in cmd_string:  # B->C

                await app.wait_for_condition(C.dispense_position_available)
                await B.can_movement({'Dispensing_Roller': 1})
                await C.can_movement({'Dispensing_Roller': 2})
                await app.wait_for_condition(C.dispense_position_busy)
                await B.can_movement()

            if '04-05' in cmd_string:  # C -> load_lifter

                await app.wait_for_condition(D.load_lifter_available)
                C.can_movement({'Dispensing_Roller': 1})
                D.can_movement({'Lifter_Roller': 2})
                await app.wait_for_condition(D.load_lifter_busy)
                C.can_movement()

            if '04-05' in cmd_string:  # lifter up -> lifter down

                await app.wait_for_condition(D.load_lifter_available)
                await app.wait_for_condition(D.load_lifter_up)
                C.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 2})
                await app.wait_for_condition(D.load_lifter_busy)
                C.can_movement()

            if '05-06' in cmd_string:  # lifter down -> D

                D.can_movement({'Lifter': 2})
                await app.wait_for_condition(D.load_lifter_down)

            if '06-07' in cmd_string:  # D -> E

                await app.wait_for_condition(D.dispense_position_available)
                C.can_movement({'Lifter_Roller': 3})
                D.can_movement({'Dispensing_Roller': 2})
                await app.wait_for_condition(D.dispense_position_busy)
                C.can_movement()
                D.can_movement({'Lifter': 1})
                await app.wait_for_condition(D.load_lifter_up)

            if '07-08' in cmd_string:  # E -> E

                await app.wait_for_condition(E.dispense_position_available)
                D.can_movement({'Dispensing_Roller': 1})
                E.can_movement({'Dispensing_Roller': 2})
                await app.wait_for_condition(E.dispense_position_busy)
                D.can_movement()

            if '08-09' in cmd_string:

                await app.wait_for_condition(F.dispense_position_available)
                E.can_movement({'Dispensing_Roller': 1})
                F.can_movement({'Dispensing_Roller': 2})
                await app.wait_for_condition(F.dispense_position_busy)
                E.can_movement()

            if '09-10' in cmd_string:
                # ~ """
                # ~ Da STEP_9 a STEP_10
                # ~ ATTESA ASSENZA Barattolo sulla Rulliera del Sollevatore di Uscita 'jar_photocells_status' – bit7 (JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL)
                # ~ ATTESA PRESENZA del Sollevatore di Uscita sul Tutto Basso 'jar_photocells_status' – bit5 (UNLOAD_LIFTER_DOWN_PHOTOCELL)
                # ~ Invio comando alla TESTA2 di spostamento Barattolo sulla Rulliera del Sollevatore di Uscita:
                    # ~ “CAN_MOVEMENT”: 'Dispensing_Roller' = 1, 'Lifter_Roller' = 5 (Start Movement CCW till Photocell
                    # ~ transition LIGHT - DARK), 'Input_Roller' = 0, 'Lifter' = 0, ‘Output_Roller’ = 0
                    # ~ Il FW quando rileva la PRESENZA del Barattolo sulla Rulliera del Sollevatore di Uscita arresta il
                    # ~ movimento della Rulliera di Dispensazione e di quella del Sollevatore di Uscita.
                # ~ """
                await app.wait_for_condition(F.unload_lifter_available)
                await app.wait_for_condition(F.unload_lifter_down)
                F.can_movement({'Dispensing_Roller': 1, 'Lifter_Roller': 5})

            if '10-11' in cmd_string:

                # ~ """
                    # ~ Il FW gestisce automaticamente lo spostamento del Sollevatore di Uscita sul Tutto Alto: il movimento
                    # ~ si arresta automaticamente quando risulta
                # ~ """
                pass

            if '11-12' in cmd_string:

                # ~ """
                # ~ Da STEP_11 a STEP_12
                # ~ Se sulla Rulliera di Uscita NON è presente un Barattolo, il FW attiva la Rulliera del Sollevatore di Uscita
                # ~ e la Rulliera di Uscita fino a copertura della Fotocellula sulla Rulliera di Uscita. A questo punto Il FW
                # ~ arresta il movimento della Rulliera del Sollevatore di Uscita e della Rulliera di Uscita. Il FW gestisce
                # ~ automaticamente lo spostamento del Sollevatore di Uscita sul Tutto Basso: il movimento si arresta
                # ~ automaticamente quando risulta oscurato il sensore di Tutto Basso 'jar_photocells_status' – bit5
                # ~ (UNLOAD_LIFTER_DOWN_PHOTOCELL).

                # ~ Se invece sulla Rulliera di Uscita è presente un Barattolo il processo termina. In quest’ultimo caso:

                # ~ ▪ Interrogazione Stato TESTA2: verifica ATTESA ASSENZA Barattolo sulla Rulliera di Uscita
                # ~ 'jar_photocells_status' – bit2 (JAR_OUTPUT_ROLLER_PHOTOCELL) e che 'status_level' !=
                # ~ 'JAR_POSITIONING'
                # ~ ▪ Invio comando alla TESTA2 di spostamento Barattolo dalla Rulliera del Sollevatore di Uscita e di
                # ~ spostamento Rulliera di Uscita fino a oscuramento della Fotocellula:
                # ~ “CAN_MOVEMENT”: 'Dispensing_Roller' = 0, 'Lifter_Roller' = 3 (Start Movement CCW),
                # ~ 'Input_Roller' = 0, 'Lifter' = 0, ‘Output_Roller’ = 1 (Start Movement CCW till Photocell transition
                # ~ LIGHT – DARK)
                # ~ ▪ Interrogazione Stato TESTA2: verifica ATTESA PRESENZA Barattolo sulla rulliera di Uscita
                # ~ 'jar_photocells_status' – bit2 (JAR_OUTPUT_ROLLER_PHOTOCELL):
                # ~ Il FW arresta il movimento della Rulliera del Sollevatore di Uscita e della Rulliera di Uscita.
                # ~ Il FW gestisce automaticamente lo spostamento del Sollevatore di Scarico sul Tutto Basso: il
                # ~ movimento si arresta automaticamente quando risulta oscurato il sensore di Tutto Basso
                # ~ 'jar_photocells_status' – bit5 (UNLOAD_LIFTER_DOWN_PHOTOCELL)

                # ~ """

                await app.wait_for_condition(F.output_roller_available)
                F.can_movement({'Lifter_Roller': 3, 'Output_Roller': 1})

            if 'StopAll' in cmd_string:
                await A.can_movement()
                await B.can_movement()
                await C.can_movement()
                await D.can_movement()
                await E.can_movement()
                await F.can_movement()

        except Exception:                           # pylint: disable=broad-except
            logging.error(traceback.format_exc())
