# coding: utf-8

# pylint: disable=missing-docstring
# pylint: disable=logging-format-interpolation
# pylint: disable=line-too-long
# pylint: disable=invalid-name


import os
import sys
import time
import logging
import traceback
import json
import asyncio

import aiohttp


from alfa_CR6_backend.base_application import download_KCC_specific_gravity_lot




fmt_ = '[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s'
logging.basicConfig(stream=sys.stdout, level='WARNING', format=fmt_)


asyncio.run(download_KCC_specific_gravity_lot())
