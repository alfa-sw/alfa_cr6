# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines


import sys
import os
import logging
import traceback
import asyncio
import subprocess

class XdoTool:

    XDOTOOL = 'xdotool'

    def __xdotool_(self, cmd_, silent=False):

        ret = None
        cmd_ = f'{self.XDOTOOL} {cmd_}'

        try:
            ret = subprocess.check_output(cmd_, shell=True, stderr=subprocess.STDOUT).strip()
        except BaseException:  # pylint: disable=broad-except
            if not silent:
                logging.error(f"cmd_:{cmd_}")
                logging.error(traceback.format_exc())
        logging.warning(f"cmd_:{cmd_}, ret:{ret}")
        return ret

    def search(self, name='', pid=0):

        c_ = f'search --pid {pid}'
        output_ = self.__xdotool_(c_, True)
        names = []
        wids = []
        toks = []
        if output_:
            toks = output_.decode().split('\n')
            for t in toks:
                c_ = f'getwindowname {t}'
                _name = self.__xdotool_(c_, True).decode()
                # ~ logging.warning(f"  === {name.lower()} {_name.lower()}")
                if name.lower() in _name.lower():
                    names.append(_name)
                    wids.append(t)

        logging.warning(f"output_:{output_}, toks:{toks}, names:{names}, wids:{wids}")

        return wids and wids[0]

    def windowsize(self, wid, w, h):
        c_ = f'windowsize {wid} {w} {h}'
        return self.__xdotool_(c_)

    def windowmove(self, wid, x, y):
        c_ = f'windowmove {wid} {x} {y}'
        return self.__xdotool_(c_)

    def overrideredirect(self, wid, flag):
        c_ = f'set_window  --overrideredirect {flag} {wid}'
        return self.__xdotool_(c_)

    def window_remap(self, wid, flag):
        if flag:
            c_ = f'windowmap {wid}'
        else:
            c_ = f'windowunmap {wid}'
        return self.__xdotool_(c_)

    def window_key(self, wid, key):
        c_ = f'key --window {wid} {key}'
        return self.__xdotool_(c_)



class ChromiumWrapper:

    chromium_exe = "chromium"

    process = None
    window_id = None
    xdotool = None

    def kill(self):

        for exe_ in ("chrome", self.chromium_exe):
            cmd_ = f"killall {exe_}"
            subprocess.Popen(cmd_.split(" "))

    def open(self, url):

        os.system("{} {}".format(self.chromium_exe, url))

    async def start(self, 
        url, 
        opts='', 
        chromium_exe="", 
        path_to_extension_kb="/opt/chromium/extensions/gkiknnlmdgcmhmncldcmmnhhdiakielc/1.2.9.3_0/"):

        os.environ["DISPLAY"] = ":0.0"

        self.chromium_exe = chromium_exe

        args_ = "{} --window-size=0,0 --window-position=10,10 --load-extension={} --app={}".format(
            opts, path_to_extension_kb, url).split()

        out_ = open("/dev/null")

        self.kill()
        await asyncio.sleep(.5)

        self.process = await asyncio.create_subprocess_exec(self.chromium_exe, *args_, stdin=None, stdout=out_, stderr=out_, loop=None, limit=1000)
        await asyncio.sleep(.5)

        logging.warning(f"self.process:{self.process}")

        self.xdotool = XdoTool()
        logging.warning(f"self.xdotool:{self.xdotool}")
        wid = None

        while not wid:
            wid = self.xdotool.search(name='KCC', pid=self.process.pid)
            await asyncio.sleep(.5)

        self.window_id = wid
        logging.warning(f"self.window_id:{self.window_id}")

        self.xdotool.overrideredirect(wid, '1')
        self.xdotool.window_remap(wid, 0)
        self.xdotool.windowsize(wid, '1908', '988')
        self.xdotool.windowmove(wid, '6', '6')
        self.xdotool.window_remap(wid, 1)

    def window_remap(self, flag):

        self.xdotool.window_remap(self.window_id, flag)


