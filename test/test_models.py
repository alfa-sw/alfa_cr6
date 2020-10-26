#!/usr/bin/env python

import sys
import logging

import alfa_CR6.cr6
import alfa_CR6.models 

def test():

    fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=fmt_)

    app = alfa_CR6.cr6.CR6_application(sys.argv)
    logging.warning("version: {} - Ctrl+C to close me.".format(app.get_version()))

    asyncio.get_event_loop().run_forever()

    app.run_forever()


if __name__ == "__main__":
    test()
