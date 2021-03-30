# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name
# pylint: disable=too-many-lines

from alfa_CR6_frontend.chromium_wrapper import ChromiumWrapper

import sys
import logging
import traceback
import asyncio

async def main():

    d = 10.0
    CHROMIUM_EXE = "chromium" 
    # ~ PATH_TO_EXTENSION_KB = "/opt/chromium/extensions/gkiknnlmdgcmhmncldcmmnhhdiakielc/1.2.9.3_0/"
    PATH_TO_EXTENSION_KB = "/home/giovanni/snap/chromium/common/chromium/Default/Extensions/gkiknnlmdgcmhmncldcmmnhhdiakielc/1.2.9.3_0/"
    if sys.argv[1:]:
        d = float(sys.argv[1])
    if sys.argv[2:]:
        CHROMIUM_EXE = sys.argv[2]
    if sys.argv[3:]:
        PATH_TO_EXTENSION_KB = sys.argv[3]

    logging.basicConfig(
        stream=sys.stdout, level="WARNING",
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    chromium_wrapper = ChromiumWrapper()
    chromium_wrapper.PATH_TO_EXTENSION_KB = PATH_TO_EXTENSION_KB

    await chromium_wrapper.start(
        url="http://kccrefinish.co.kr/", opts='', chromium_exe=CHROMIUM_EXE, path_to_extension_kb=PATH_TO_EXTENSION_KB)

    while True:
        try:
            await asyncio.sleep(d)
            logging.warning(f"chromium_wrapper.process:{chromium_wrapper.process}")

            if chromium_wrapper.process.returncode is not None:

                await chromium_wrapper.start("http://kccrefinish.co.kr/", "")

            chromium_wrapper.window_remap(0)
            await asyncio.sleep(1.0)
            chromium_wrapper.window_remap(1)
        except (KeyboardInterrupt, EOFError):  # pylint: disable=broad-except
            break
        except Exception:                # pylint: disable=broad-except
            logging.error(traceback.format_exc())


if __name__ == "__main__":

    asyncio.run(main())
