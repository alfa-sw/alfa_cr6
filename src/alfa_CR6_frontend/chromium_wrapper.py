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

        if ret is not None:
            return ret.decode()

    def search(self, pid=0):

        # ~ c_ = f'search --pid {pid} --onlyvisible --maxdepth 2'
        c_ = f'search --pid {pid}'
        output_ = self.__xdotool_(c_, True)
        names = []
        wids = []
        toks = []
        if output_:
            toks = output_.split('\n')
            for t in toks:
                c_ = f'getwindowname {t}'
                _name = self.__xdotool_(c_, True)
                names.append(_name)
                wids.append(t)
                # ~ logging.warning(f"  === {name.lower()} {_name.lower()}")
                # ~ if name.lower() in _name.lower():
                    # ~ names.append(_name)
                    # ~ wids.append(t)

        logging.warning(f"output_:{output_}, toks:{toks}, names:{names}, wids:{wids}")

        return wids and wids[-1]

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
            cmd_ = f"killall -w -g {exe_}"
            subprocess.Popen(cmd_.split(" "))

    def open(self, url):

        os.system("{} {}".format(self.chromium_exe, url))

    async def start(self, 
        url, 
        window_name="KCC", 
        opts='', 
        chromium_exe="", 
        path_to_extension_kb="/opt/chromium/extensions/gkiknnlmdgcmhmncldcmmnhhdiakielc/1.2.9.3_0/"):

        os.environ["DISPLAY"] = ":0.0"

        self.chromium_exe = chromium_exe

        if os.path.exists(path_to_extension_kb):
            args_ = "{} --window-size=0,0 --window-position=10,10 --load-extension={} --app={}".format(
                opts, path_to_extension_kb, url).split()
        else:
            args_ = "{} --window-size=0,0 --window-position=10,10 --app={}".format(opts, url).split()

        out_ = open("/dev/null")

        self.kill()
        await asyncio.sleep(1)

        logging.warning(f"self.chromium_exe:{self.chromium_exe}, args_:{ ' '.join(args_) }")

        self.process = await asyncio.create_subprocess_exec(self.chromium_exe, *args_, stdin=None, stdout=out_, stderr=out_, loop=None, limit=1000)
        await asyncio.sleep(2)

        logging.warning(f"self.process:{self.process}")

        self.xdotool = XdoTool()
        logging.warning(f"self.xdotool:{self.xdotool}")
        wid = None

        while not wid:
            await asyncio.sleep(1.)
            wid = self.xdotool.search(pid=self.process.pid)
            logging.warning(f"self.process.pid:{self.process.pid}, window_name:{window_name}, wid:{wid}")

        self.window_id = wid
        logging.warning(f"self.window_id:{self.window_id}")

        self.xdotool.overrideredirect(wid, '1')
        self.xdotool.window_remap(wid, 0)
        self.xdotool.windowsize(wid, '1908', '988')
        self.xdotool.windowmove(wid, '6', '6')

    def window_remap(self, flag):

        if self.xdotool:
            self.xdotool.window_remap(self.window_id, flag)


async def main():

    d = 10.0
    CHROMIUM_EXE = "chromium" 
    PATH_TO_EXTENSION_KB = "/opt/chromium/extensions/virt_kbd/1.2.9.3_0/"
    url_ = "http://kccrefinish.co.kr/"

    if sys.argv[1:]:
        d = float(sys.argv[1])
    if sys.argv[2:]:
        CHROMIUM_EXE = sys.argv[2]
    if sys.argv[3:]:
        PATH_TO_EXTENSION_KB = sys.argv[3]
    if sys.argv[4:]:
        url_ = sys.argv[4]

    logging.basicConfig(
        stream=sys.stdout, level="WARNING",
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    chromium_wrapper = ChromiumWrapper()

    await chromium_wrapper.start(
        window_name="chromium", 
        url=url_, opts='', 
        chromium_exe=CHROMIUM_EXE, 
        path_to_extension_kb=PATH_TO_EXTENSION_KB)

    while True:
        try:
            chromium_wrapper.window_remap(1)
            await asyncio.sleep(d)
            logging.warning(f"chromium_wrapper.process:{chromium_wrapper.process}")

            if chromium_wrapper.process.returncode is not None:

                await chromium_wrapper.start(
                    window_name="chromium", 
                    url=url_, opts='', 
                    chromium_exe=CHROMIUM_EXE, 
                    path_to_extension_kb=PATH_TO_EXTENSION_KB)

            chromium_wrapper.window_remap(0)
            await asyncio.sleep(1.0)
            chromium_wrapper.window_remap(1)
        except (KeyboardInterrupt, EOFError):  # pylint: disable=broad-except
            break
        except Exception:                # pylint: disable=broad-except
            logging.error(traceback.format_exc())


if __name__ == "__main__":

    asyncio.run(main())
