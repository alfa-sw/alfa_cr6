#!/usr/bin/python3

import os
import sys
import logging
import json
import glob

from alfa_CR6_backend.base_application import OrderParser


def main():

    logging.basicConfig(
        stream=sys.stdout, level='WARNING',
        format="[%(asctime)s]%(levelname)s %(funcName)s() %(filename)s:%(lineno)d %(message)s")

    _parser = OrderParser()

    for path_to_file in sys.argv[1:]:

        print(path_to_file)    
        properties = _parser.parse(path_to_file)
        # ~ logging.warning(json.dumps(properties, indent=2))

main()
