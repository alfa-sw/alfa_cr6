# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=multiple-statements
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import logging
import traceback
from functools import partial

from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
    QApplication,
    QPushButton,
    QLabel)


from alfa_CR6_backend.globals import (get_res, tr_)
from alfa_CR6_frontend.pages import BaseStackedPage


class ActionPage(BaseStackedPage):

    ui_file_name = "action_frame.ui"

    @staticmethod
    def __check_conditions(args):

        # ~ Testa 5 vincolare il comando start rulliera dispensazione al fatto che il sollevatore sia in posizione alta ed abbia la fotocellula della rulliera sollevatore libera.
        # ~ Testa 5 vincolare il comando start rulliera sollevatore senso orario al al fatto che il sollevatore sia alto.
        # ~ Testa 5 vincolare il comando start rulliera sollevatore senso anti orario al al fatto che il sollevatore sia basso.

        # ~ Testa 2 vincolare il comando start rulliera dispensazione al fatto che il sollevatore sia in posizione bassa ed abbia la fotocellula della rulliera sollevatore libera.

        # ~ Testa 2 vincolare il comando start rulliera sollevatore senso anti orario al fatto che il sollevatore sia in posizione bassa o alta.
        # ~ Testa 2 vincolare il comando start rulliera sollevatore senso orario al fatto che il sollevatore sia in posizione bassa o alta****************.

        ret = True

        if args in (('single_move', 'C', [0, 1]), ('single_move', 'C', [0, 2])
                    ):  # "Start dispensing roller" "Start dispensing roller to photocell"
            D = QApplication.instance().get_machine_head_by_letter("D")
            C = QApplication.instance().get_machine_head_by_letter("C")
            ret = D.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL')
            ret = ret and not C.jar_photocells_status.get('JAR_LOAD_LIFTER_ROLLER_PHOTOCELL', True)

        elif args == ("single_move", "C", [1, 1]):  # "Start lifter roller CW"
            D = QApplication.instance().get_machine_head_by_letter("D")
            ret = D.jar_photocells_status.get('LOAD_LIFTER_UP_PHOTOCELL')

        elif args == ("single_move", "C", [1, 4]):  # "Start lifter roller CCW"
            D = QApplication.instance().get_machine_head_by_letter("D")
            ret = D.jar_photocells_status.get('LOAD_LIFTER_DOWN_PHOTOCELL')

        # "Start lifter roller CCW", "Start lifter roller CW"
        elif args in (("single_move", "F", [1, 4]), ("single_move", "F", [1, 1])):

            F = QApplication.instance().get_machine_head_by_letter("F")
            ret = F.jar_photocells_status.get('UNLOAD_LIFTER_DOWN_PHOTOCELL')
            ret = ret or F.jar_photocells_status.get('UNLOAD_LIFTER_UP_PHOTOCELL')

        # "Start dispensing roller" "Start dispensing roller to photocell"
        elif args in (('single_move', 'F', [0, 1]), ('single_move', 'F', [0, 2])):
            F = QApplication.instance().get_machine_head_by_letter("F")
            ret = F.jar_photocells_status.get('UNLOAD_LIFTER_DOWN_PHOTOCELL')
            ret = ret and not F.jar_photocells_status.get('JAR_UNLOAD_LIFTER_ROLLER_PHOTOCELL', True)

        logging.info(f"ret:{ret}, args:{args}")

        return ret

    def __do_action(self, condition, args):
        logging.warning(f"condition:{condition}, args:{args}")
        if args[0] == 'open_home_page':
            self.parent().setCurrentWidget(self.main_window.home_page)
        else:
            try:
                if not self.__check_conditions(args):
                    _msg = tr_("action not allowed.") + f"\n\n{args}"
                    self.main_window.open_alert_dialog(_msg, title="ALERT")
                else:
                    QApplication.instance().run_a_coroutine_helper(args[0], *args[1:])
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

    def __do_show_val(self, w, head_letter, bit_name, text):
        logging.debug(f"self:{self}")
        try:
            m = QApplication.instance().get_machine_head_by_letter(head_letter)
            if bit_name.lower() == "container_presence":
                val_ = m.status.get("container_presence")
            else:
                val_ = m.jar_photocells_status.get(bit_name)

            pth_ = (
                get_res("IMAGE", "green.png")
                if val_ else get_res("IMAGE", "gray.png")
            )
            w.setText(
                f'<img widt="50" height="50" src="{pth_}" style="vertical-align:middle;">{tr_(text)}</img>'
            )
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def __init__(self, action_item, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setStyleSheet(
            """
            QFrame { border: 1px solid #999999; border-radius: 4px; background-color: #FEFEFE;}
            QWidget {font-size: 24px;}
            QLabel { border-width: 0px; background-color: #FFFFFF;}
            QPushButton { background-color: #EEEEEE; border: 1px solid #999999; border-radius: 4px;}
            QPushButton:pressed {background-color: #AAAAAA;}
            """
        )

        self.action_title_label.setText(tr_(action_item["title"]))

        for b in action_item["buttons"]:
            i = QPushButton(tr_(b["text"]), self)
            i.setFixedHeight(50)
            if b.get("action_args"):
                args_ = b.get("action_args")
                condition_ = b.get("condition")
                i.clicked.connect(partial(self.__do_action, condition_, args_))
            self.action_buttons_layout.addWidget(i)

        for l in action_item["labels_args"]:
            if l:
                i = QLabel(self)
                i.setTextFormat(Qt.RichText)
                args_ = [i, ] + list(l)
                setattr(i, "show_val", partial(self.__do_show_val, *args_))
                self.action_labels_layout.addWidget(i)

    def show_values_in_labels(self):

        logging.warning("+++++++++++++++++")
        for i in range(self.action_labels_layout.count()):
            lbl = self.action_labels_layout.itemAt(i).widget()
            if hasattr(lbl, "show_val"):
                getattr(lbl, "show_val")()
                logging.warning(f"lbl:{lbl}")

        for w, l in[(self.status_A_label, 'A'),
                    (self.status_B_label, 'B'),
                    (self.status_C_label, 'C'),
                    (self.status_D_label, 'D'),
                    (self.status_E_label, 'E'),
                    (self.status_F_label, 'F')]:

            if w:
                self.__show_head_status(w, l)

    @staticmethod
    def __show_head_status(lbl, head_letter):

        m = QApplication.instance().get_machine_head_by_letter(head_letter)
        if m and m.status.get("status_level") is not None:
            status_level = m.status.get("status_level")
            crx_outputs = m.status.get('crx_outputs_status', -1)
            jar_ph_ = m.status.get("jar_photocells_status", -1)

            txt_ = "{}".format(tr_(f"{status_level}"))
            txt_ += "<br/><small>{:04b} {:04b}</small>\n".format(
                0xF & (crx_outputs >> 4), 0xF & (crx_outputs >> 0))
            txt_ += '<br/><small>{:04b} {:04b} {:04b} </small>'.format(
                0xF & (jar_ph_ >> 8), 0xF & (jar_ph_ >> 4), 0xF & (jar_ph_ >> 0))
            lbl.setText(txt_)
            lbl.show()
        else:
            lbl.hide()
