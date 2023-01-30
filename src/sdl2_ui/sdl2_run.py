# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines
# pylint: disable=logging-fstring-interpolation, consider-using-f-string

import os
import sys
import logging
import traceback
import time
import subprocess
import asyncio
import platform

import sdl2.ext      # pylint: disable=import-error
import websockets      # pylint: disable=import-error


# ~ LOG_LEVEL = 'WARNING'
LOG_LEVEL = 'INFO'
# ~ LOG_LEVEL = 'DEBUG'
if sys.argv[1:]:
    LOG_LEVEL = sys.argv[1]

RES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'alfa_CR6_flask', 'static', 'ui', 'images')
if sys.argv[2:]:
    RES_PATH = sys.argv[2]




class Sdl2LocalUi:

    if platform.processor() == 'x86_64':
        COCKPIT_POSITIONS = [
            (-100, 950),
            (-100 + (1548 + 100) // 2, 950),
            (1548, 950),
        ]
        KBD_POSITION = "0 700"
        KBD_SIZE = "1910 340"
        BROWSER = "chromium"
    else:
        COCKPIT_POSITIONS = [
            (1872, 928),
            (1872 + (3436 - 1872) // 2, 950),
            (3436, 928),
        ]
        KBD_POSITION = "1980 640"
        KBD_SIZE = "1800 340"
        BROWSER = "chromium"

    def __init__(self, res_path):

        logging.warning(f"res_path:{res_path}")

        self.RESOURCES = sdl2.ext.Resources(res_path)

        self._buttons = {}

        sdl2.ext.init()

        logging.debug("")

        win_flags = (
            # ~ sdl2.SDL_WINDOW_FULLSCREEN |
            # ~ sdl2.SDL_WINDOW_RESIZABLE |
            # ~ sdl2.SDL_WINDOW_UTILITY |
            sdl2.SDL_WINDOW_ALWAYS_ON_TOP |
            sdl2.SDL_WINDOW_TOOLTIP |
            # ~ sdl2.SDL_WINDOW_BORDERLESS |
            # ~ sdl2.SDL_WINDOW_OPENGL |
            sdl2.SDL_WINDOW_SHOWN
        )

        logging.debug("")

        self.kbd_visible = False
        self.cockpit_position_index = -1
        pos = self.COCKPIT_POSITIONS[self.cockpit_position_index]
        self.window = sdl2.ext.Window("alfa_cockpit", size=(460, 124), position=pos, flags=win_flags)
        _factory = sdl2.ext.SpriteFactory(sdl2.ext.SOFTWARE)
        self.uifactory = sdl2.ext.UIFactory(_factory)

        self.add_button('arrow_left', "arrow_left.png", (-20, 2), self.on_arrow_left_click)
        self.add_button('keybd', "kbd_up.png", (100, 2), self.on_kbd_click)
        self.add_button('home', "home.png", (240, 2), self.on_home_click)
        self.add_button('arrow_right', "arrow_right.png", (360, 2), self.on_arrow_right_click)

        logging.debug("")
        self.spriterenderer = _factory.create_sprite_render_system(self.window)

        logging.debug("")
        self.spriterenderer.render(list(self._buttons.values()))

    @staticmethod
    def exec_cmds(cmds):

        r = None
        for cmd_ in cmds:
            logging.info(f"cmd_:{cmd_}")
            try:
                r = subprocess.check_output(cmd_, shell=True, stderr=subprocess.STDOUT).decode()
            except Exception as e:  # pylint: disable=broad-except
                logging.error(f"{e}")
                r = traceback.format_exc()

            logging.info(f"r:{r}")

        return r

    def start_browser(self):

        logging.info("")
        os.system(f'{self.BROWSER} 127.0.0.1:8090 &')
        time.sleep(.5)
        os.system('export DISPLAY=:0;xdotool search  --name "Alfa_CRX" windowmove 1966 -76 windowsize 1832 1126 windowfocus windowraise')

    def stop_browser(self):

        logging.info("")
        os.system(f'killall {self.BROWSER}')

    def start_keyboard(self):

        logging.info("")
        os.system('matchbox-keyboard &')
        time.sleep(.5)
        self.exec_cmds([f'export DISPLAY=:0;xdotool search --name  "keyboard" windowsize {self.KBD_SIZE}'])
        self.exec_cmds([f'export DISPLAY=:0;xdotool search --name  "keyboard" windowmove {self.KBD_POSITION}'])
        self.exec_cmds(['export DISPLAY=:0;xdotool search --name  "keyboard" windowmove x 3000'])

    def stop_keyboard(self):

        logging.info("")
        self.exec_cmds(['killall matchbox-keyboard'])

    def add_button(self, name, image_file_name, position, on_click):

        self._buttons[name] = self.uifactory.from_image(sdl2.ext.BUTTON, self.RESOURCES.get_path(image_file_name))
        self._buttons[name].position = position
        self._buttons[name].click += on_click

    def on_arrow_left_click(self, button, event): # pylint: disable=unused-argument
        self.cockpit_position_index = (self.cockpit_position_index - 1) % len(self.COCKPIT_POSITIONS)
        pos = self.COCKPIT_POSITIONS[self.cockpit_position_index]
        logging.info(f"pos:{pos}, self.cockpit_position_index:{self.cockpit_position_index}")
        self.window.position = pos

    def on_arrow_right_click(self, button, event): # pylint: disable=unused-argument

        self.cockpit_position_index = (self.cockpit_position_index + 1) % len(self.COCKPIT_POSITIONS)
        pos = self.COCKPIT_POSITIONS[self.cockpit_position_index]
        logging.info(f"pos:{pos}, self.cockpit_position_index:{self.cockpit_position_index}")
        self.window.position = pos

    def on_home_click(self, button, event): # pylint: disable=unused-argument

        cmds = [
            # ~ "wmctrl -r MainFreame -e '0,-10,800,1920,260' ;",
            # ~ "wmctrl -R MainFrame"
            'export DISPLAY=:0;xdotool search  --name "Alfa_CRX" windowfocus windowraise windowmove 1966 -76 windowsize 1832 1126'
        ]
        self.exec_cmds(cmds)

        return

        try:

            async def _show_home_page():
                ws_url = "ws://127.0.0.1:13000/local_ui_reset_home"
                websocket = await websockets.connect(ws_url, timeout=.1)
                logging.warning(f"websocket:{websocket}")

            t = _show_home_page()
            asyncio.run(t)
            logging.warning(f"t:{t}")

        except Exception:  # pylint: disable=broad-except
            logging.error(traceback.format_exc())

    def on_kbd_click(self, button, event): # pylint: disable=unused-argument

        logging.info(f"button:{button}, event:{event}")
        if self.kbd_visible:
            self.exec_cmds(['export DISPLAY=:0;xdotool search --name  "keyboard" windowmove x 2000'])
            self.kbd_visible = False
        else:
            self.exec_cmds([f'export DISPLAY=:0;xdotool search --name  "keyboard" windowmove {self.KBD_POSITION}'])
            self.exec_cmds(['export DISPLAY=:0;xdotool search --name "keyboard" windowraise'])
            self.kbd_visible = True

    def run(self):

        logging.debug("")

        self.window.show()
        self.start_keyboard()
        self.start_browser()

        running = True
        t0 = 0
        uiprocessor = sdl2.ext.UIProcessor()
        while running:
            try:
                t = time.time()
                events = sdl2.ext.get_events()
                for event in events:
                    if event.type == sdl2.SDL_QUIT:
                        running = False
                        break
                    logging.debug(f"event.type:{event.type}")
                    uiprocessor.dispatch(list(self._buttons.values()), event)
                # ~ if t - t0 > .5:
                if events:
                    t0 = t
                    self.spriterenderer.render(list(self._buttons.values()))

                time.sleep(.01)
            except KeyboardInterrupt:
                break
            except Exception:  # pylint: disable=broad-except
                logging.error(traceback.format_exc())

        logging.debug("")

        sdl2.ext.quit()
        self.stop_keyboard()
        # ~ self.stop_browser()

        logging.debug("")


def main():

    logging.basicConfig(
        stream=sys.stdout, level=LOG_LEVEL,
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    logging.info(f"RES_PATH:{RES_PATH}")

    s = Sdl2LocalUi(RES_PATH)

    s.run()


if __name__ == '__main__':
    main()
