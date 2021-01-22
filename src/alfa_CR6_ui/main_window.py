# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=no-name-in-module
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods

import os
import sys
import logging
import traceback

from PyQt5.uic import loadUi
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtWidgets import QApplication, QMainWindow

from alfa_CR6_ui.globals import (
    KEYBOARD_PATH,
    IMAGES_PATH,
    UI_PATH,
    tr_,
    ModalMessageBox,
    EditDialog,
    InputDialog)

from alfa_CR6_ui.pages import (
    OrderPage,
    WebenginePage,
    HomePage,
    HelpPage)

from alfa_CR6_ui.keyboard import Keyboard


class MainWindow(QMainWindow):  # pylint:  disable=too-many-instance-attributes

    def __init__(self, parent=None):

        from alfa_CR6_ui.debug_page import DebugPage  # pylint: disable=import-outside-toplevel

        super().__init__(parent)
        loadUi(os.path.join(UI_PATH, "main_window.ui"), self)

        self.setStyleSheet("""
                QWidget {font-size: 24px; font-family: Times sans-serif;}
                QPushButton {background-color: #F3F3F3F3; border: 1px solid #999999; border-radius: 4px;}
                QPushButton:pressed {background-color: #AAAAAA;}
                QScrollBar:vertical {width: 40px;}
            """)

        self.menu_btn_group.buttonClicked.connect(self.on_menu_btn_group_clicked)

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
        self.webengine_page = WebenginePage(parent=self)
        self.home_page = HomePage(parent=self)

        self.stacked_widget.setCurrentWidget(self.home_page)

        self.__init_dialogs()
        self.__init_icons()

        self.showFullScreen()

        # ~ self.refill_1_lbl.mouseReleaseEvent = lambda event: self.show_reserve(0)
        # ~ self.refill_2_lbl.mouseReleaseEvent = lambda event: self.show_reserve(1)
        # ~ self.refill_3_lbl.mouseReleaseEvent = lambda event: self.show_reserve(2)
        # ~ self.refill_4_lbl.mouseReleaseEvent = lambda event: self.show_reserve(3)
        # ~ self.refill_5_lbl.mouseReleaseEvent = lambda event: self.show_reserve(4)
        # ~ self.refill_6_lbl.mouseReleaseEvent = lambda event: self.show_reserve(5)

    def __init_icons(self):

        self.reserve_movie = QMovie(os.path.join(IMAGES_PATH, "riserva.gif"))

        self.gray_icon = QPixmap(os.path.join(IMAGES_PATH, "gray.png"))
        self.green_icon = QPixmap(os.path.join(IMAGES_PATH, "green.png"))
        self.red_icon = QPixmap(os.path.join(IMAGES_PATH, "red.png"))

        self.jar_icon_map = {
            k: QPixmap(os.path.join(IMAGES_PATH, p))
            for k, p in (
                ("no", ""),
                ("green", "jar-green.png"),
                ("red", "jar-red.png"),
                ("blue", "jat-blue.png"),
            )
        }
        self.tank_icon_map = {
            k: QPixmap(os.path.join(IMAGES_PATH, p))
            for k, p in (
                ("green", "tank_green.png"),
                ("gray", "tank_gray.png"),
            )
        }

    def __init_dialogs(self):

        self.input_dialog = InputDialog(self)
        self.edit_dialog = EditDialog(self)

    def get_stacked_widget(self):
        return self.stacked_widget

    def on_menu_btn_group_clicked(self, btn):

        btn_name = btn.objectName()

        try:

            if "keyboard" in btn_name:
                self.toggle_keyboard()

            elif "home" in btn_name:
                self.toggle_keyboard(on_off=False)
                self.home_page.open_page()

            elif "order" in btn_name:
                self.toggle_keyboard(on_off=False)
                self.order_page.open_page()

            elif "browser" in btn_name:
                self.toggle_keyboard(on_off=True)
                self.webengine_page.open_page()

            elif "global_status" in btn_name:
                self.toggle_keyboard(on_off=False)
                self.stacked_widget.setCurrentWidget(self.debug_page.main_frame)

            elif "help" in btn_name:
                self.toggle_keyboard(on_off=False)
                self.help_page.open_page()

        except Exception as e:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())
            self.open_alert_dialog(
                f"btn_name:{btn_name} exception:{e}",
                title="ERROR",
                callback=None,
                args=None,
            )

    def toggle_keyboard(self, on_off=None):

        if on_off is None:
            on_off = not self.keyboard.isVisible()

        ls = [
            self.webengine_page.webengine_view,
            self.order_page.jar_table_view,
            self.order_page.order_table_view,
            self.order_page.file_table_view, ]

        if on_off and not self.keyboard.isVisible():
            self.keyboard.show()
            for l in ls:
                l.resize(l.width(), l.height() - self.keyboard.height())
        elif not on_off and self.keyboard.isVisible():
            self.keyboard.hide()
            for l in ls:
                l.resize(l.width(), l.height() + self.keyboard.height())

    def update_status_data(self, head_index, _=None):

        try:
            self.debug_page.update_status()

            self.home_page.update_service_btns__presences_and_lifters(head_index)
            self.home_page.update_tank_pixmaps()
            self.home_page.update_jar_pixmaps()
            self.home_page.update_action_pages()

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def show_reserve(self, head_index, flag=None):

        map_ = [
            self.home_page.reserve_1_label,
            self.home_page.reserve_2_label,
            self.home_page.reserve_3_label,
            self.home_page.reserve_4_label,
            self.home_page.reserve_5_label,
            self.home_page.reserve_6_label,
        ]

        if flag is None:
            flag = not map_[head_index].isVisible()

        _label = map_[head_index]
        # ~ logging.warning(f"head_index:{head_index}, flag:{flag}, _label:{_label}.")

        if flag:
            _label.setMovie(self.reserve_movie)
            self.reserve_movie.start()
            _label.show()
        else:
            _label.setText("")
            _label.hide()

    def show_carousel_frozen(self, flag):
        if flag:
            self.home_page.freeze_carousel_btn.setText(tr_("Carousel Frozen"))
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
            self.home_page.update_action_pages()
            self.home_page.update_jar_pixmaps()
            self.home_page.update_tank_pixmaps()
        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def open_edit_dialog(self, order_nr):

        self.edit_dialog.show_dialog(order_nr)
        self.toggle_keyboard(on_off=True)

    def open_input_dialog(self, icon_name=None, message=None, content=None, ok_cb=None, ok_cb_args=None):   # pylint: disable=too-many-arguments

        self.input_dialog.show_dialog(
            icon_name=icon_name,
            message=message,
            content=content,
            ok_cb=ok_cb,
            ok_cb_args=ok_cb_args)

    def open_alert_dialog(self, msg, title="ALERT", callback=None, args=None):

        _msgbox = ModalMessageBox(parent=self, msg=msg, title=title, ok_callback=callback, ok_callback_args=args)

    def open_frozen_dialog(self, msg, title="ALERT"):

        callback = QApplication.instance().freeze_carousel
        args = [False, ]
        logging.info(msg)
        msg_ = tr_("carousel is frozen.")
        msg_ += f'\n------------------------------\n"{msg}"\n------------------------------\n'
        msg_ += tr_("hit 'OK' to unfreeze it")
        self.open_alert_dialog(msg_, title=title, callback=callback, args=args)

    def show_barcode(self, barcode, is_ok=False):

        css = "color: #000000" if is_ok else "color: #990000"
        self.menu_line_edit.setStyleSheet(css)
        self.menu_line_edit.setText(f"{barcode}")


def main():

    fmt_ = (
        "[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s"
    )
    logging.basicConfig(stream=sys.stdout, level="INFO", format=fmt_)

    from alfa_CR6_backend.cr6 import CR6_application  # pylint: disable=import-outside-toplevel

    app = CR6_application(MainWindow, sys.argv)
    app.exec_()


if __name__ == "__main__":
    main()
